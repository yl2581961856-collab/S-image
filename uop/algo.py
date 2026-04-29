from __future__ import annotations

from dataclasses import dataclass

from .ops import DType, KernelHint, Ops, UOp, cat, param, placeholder, triton_hint


@dataclass(frozen=True)
class FluxConfig:
    batch: int | str = "B"
    latent_channels: int = 16
    height: int | str = "H"
    width: int | str = "W"
    patch_size: int = 2
    hidden_size: int = 3072
    txt_tokens: int | str = "T_txt"
    heads: int = 24
    head_dim: int = 128
    depth: int = 1
    mlp_ratio: int = 4
    dtype: DType = DType.BF16
    attention_hint: KernelHint | None = None

    @property
    def patch_dim(self) -> int:
        return self.latent_channels * self.patch_size * self.patch_size

    @property
    def image_tokens(self) -> int | str:
        tokens_h = self.height // self.patch_size if isinstance(self.height, int) else f"{self.height}//{self.patch_size}"
        tokens_w = self.width // self.patch_size if isinstance(self.width, int) else f"{self.width}//{self.patch_size}"
        return tokens_h * tokens_w if isinstance(tokens_h, int) and isinstance(tokens_w, int) else f"({tokens_h})*({tokens_w})"


@dataclass(frozen=True)
class FluxInputs:
    latent: UOp
    text: UOp
    conditioning: UOp
    rope_freqs: UOp


def flux_inputs(config: FluxConfig) -> FluxInputs:
    return FluxInputs(
        latent=placeholder(
            "latent",
            (config.batch, config.latent_channels, config.height, config.width),
            config.dtype,
        ),
        text=placeholder(
            "text_tokens",
            (config.batch, config.txt_tokens, config.hidden_size),
            config.dtype,
        ),
        conditioning=placeholder(
            "conditioning",
            (config.batch, config.hidden_size),
            config.dtype,
        ),
        rope_freqs=placeholder(
            "rope_freqs",
            (config.batch, "T_total", config.head_dim),
            DType.F32,
        ),
    )


def flux_forward_graph(config: FluxConfig | None = None) -> UOp:
    config = config or FluxConfig()
    inputs = flux_inputs(config)

    image_tokens = inputs.latent.patchify(config.patch_size)
    image_tokens = image_tokens.linear(
        param("x_embedder.weight", (config.hidden_size, config.patch_dim), config.dtype),
        hint=triton_hint("flux_x_embedder"),
    )

    hidden = cat((inputs.text, image_tokens), axis=1)
    for block_idx in range(config.depth):
        hidden = flux_block(
            hidden=hidden,
            conditioning=inputs.conditioning,
            rope_freqs=inputs.rope_freqs,
            config=config,
            prefix=f"blocks.{block_idx}",
        )

    image_hidden = UOp(
        Ops.SLICE,
        hidden.spec.replace(shape=(config.batch, config.image_tokens, config.hidden_size)),
        (hidden,),
        arg={"axis": 1, "start": config.txt_tokens, "end": None, "label": "image_tokens"},
    )

    image_hidden = image_hidden.ada_ln(
        param("final_layer.shift", (config.hidden_size,), config.dtype),
        param("final_layer.scale", (config.hidden_size,), config.dtype),
    )
    patches = image_hidden.linear(
        param("final_layer.proj.weight", (config.patch_dim, config.hidden_size), config.dtype),
        hint=triton_hint("flux_final_proj"),
    )
    return patches.unpatchify(
        channels=config.latent_channels,
        height=config.height,
        width=config.width,
        patch_size=config.patch_size,
    ).with_name("flux_latent_out")


def flux_block(
    *,
    hidden: UOp,
    conditioning: UOp,
    rope_freqs: UOp,
    config: FluxConfig,
    prefix: str,
) -> UOp:
    shift = conditioning.linear(param(f"{prefix}.ada.shift.weight", (config.hidden_size, config.hidden_size), config.dtype))
    scale = conditioning.linear(param(f"{prefix}.ada.scale.weight", (config.hidden_size, config.hidden_size), config.dtype))
    gate = conditioning.linear(param(f"{prefix}.ada.gate.weight", (config.hidden_size, config.hidden_size), config.dtype))

    normed = hidden.ada_ln(shift, scale, gate=gate)
    attn = flux_attention(normed, rope_freqs=rope_freqs, config=config, prefix=f"{prefix}.attn")
    hidden = hidden + (attn * gate.reshape(config.batch, 1, config.hidden_size))

    mlp_shift = conditioning.linear(param(f"{prefix}.mlp_ada.shift.weight", (config.hidden_size, config.hidden_size), config.dtype))
    mlp_scale = conditioning.linear(param(f"{prefix}.mlp_ada.scale.weight", (config.hidden_size, config.hidden_size), config.dtype))
    mlp_gate = conditioning.linear(param(f"{prefix}.mlp_ada.gate.weight", (config.hidden_size, config.hidden_size), config.dtype))
    mlp_in = hidden.ada_ln(mlp_shift, mlp_scale, gate=mlp_gate)
    mlp = flux_mlp(mlp_in, config=config, prefix=f"{prefix}.mlp")
    return hidden + (mlp * mlp_gate.reshape(config.batch, 1, config.hidden_size))


def flux_attention(hidden: UOp, *, rope_freqs: UOp, config: FluxConfig, prefix: str) -> UOp:
    q = hidden.linear(param(f"{prefix}.to_q.weight", (config.hidden_size, config.hidden_size), config.dtype))
    k = hidden.linear(param(f"{prefix}.to_k.weight", (config.hidden_size, config.hidden_size), config.dtype))
    v = hidden.linear(param(f"{prefix}.to_v.weight", (config.hidden_size, config.hidden_size), config.dtype))

    q = q.reshape(config.batch, "T_total", config.heads, config.head_dim).permute(0, 2, 1, 3).rope(rope_freqs)
    k = k.reshape(config.batch, "T_total", config.heads, config.head_dim).permute(0, 2, 1, 3).rope(rope_freqs)
    v = v.reshape(config.batch, "T_total", config.heads, config.head_dim).permute(0, 2, 1, 3)

    attn = q.attention(
        k,
        v,
        scale=config.head_dim**-0.5,
        hint=config.attention_hint or triton_hint("flux_flash_attention"),
    )
    attn = attn.permute(0, 2, 1, 3).reshape(config.batch, "T_total", config.hidden_size)
    return attn.linear(
        param(f"{prefix}.to_out.weight", (config.hidden_size, config.hidden_size), config.dtype),
        hint=triton_hint("flux_attn_out"),
    )


def flux_mlp(hidden: UOp, *, config: FluxConfig, prefix: str) -> UOp:
    inner = config.hidden_size * config.mlp_ratio
    up = hidden.linear(
        param(f"{prefix}.up.weight", (inner, config.hidden_size), config.dtype),
        hint=triton_hint("flux_mlp_up"),
    ).gelu()
    return up.linear(
        param(f"{prefix}.down.weight", (config.hidden_size, inner), config.dtype),
        hint=triton_hint("flux_mlp_down"),
    )


__all__ = [
    "FluxConfig",
    "FluxInputs",
    "flux_attention",
    "flux_block",
    "flux_forward_graph",
    "flux_inputs",
    "flux_mlp",
]
