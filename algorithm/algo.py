from __future__ import annotations

from typing import Any

import torch

from .ops import (
    build_mask_condition,
    build_person_input,
    concat_width,
    decode_from_latent,
    denoise,
    encode_to_latent,
    init_noise_like,
    prepare_inputs,
    split_width,
)


@torch.inference_mode()
def catvton_forward(
    Ip: torch.Tensor,
    Ig: torch.Tensor,
    vae: Any,
    unet: Any,
    scheduler: Any,
    M: torch.Tensor | None = None,
    mask_free: bool = True,
    return_trace: bool = False,
) -> torch.Tensor | tuple[torch.Tensor, dict[str, Any]]:
    """Run one CATVTON denoising pass.

    Args:
        Ip: Target person image tensor, shape [B, 3, H, W].
        Ig: Garment image tensor, shape [B, 3, H, W].
        vae: VAE module with encode/decode and scaling_factor.
        unet: Denoiser module.
        scheduler: Diffusion scheduler with timesteps and step().
        M: Optional binary mask tensor [B, 1, H, W].
        mask_free: If True, do not use mask branch.
        return_trace: If True, return key intermediate metadata for debugging.

    Returns:
        Output image tensor [B, 3, H, W], or (output, trace) when return_trace=True.

    Notes:
        - This follows the paper's high-level formulation.
        - Concrete UNet/Scheduler call signatures can differ by implementation.
    """
    Ip, Ig, M = prepare_inputs(Ip=Ip, Ig=Ig, M=M, mask_free=mask_free)
    trace: dict[str, Any] | None = None
    if return_trace:
        trace = {
            "mask_free": mask_free,
            "input_shape": list(Ip.shape),
            "mask_shape": list(M.shape) if M is not None else None,
        }

    # (1) build person input Ii
    Ii = build_person_input(Ip=Ip, M=M, mask_free=mask_free)
    # (2) concat along width and encode latent Xi
    x_in = concat_width(Ii, Ig)
    Xi = encode_to_latent(vae, x_in)
    # (3) optional mask condition Mi
    Mi = build_mask_condition(M, Xi.shape[-2:]) if not mask_free else None
    # initial noise z_T
    z_init = init_noise_like(Xi)

    if trace is not None:
        trace["concat_input_shape"] = list(x_in.shape)
        trace["latent_condition_shape"] = list(Xi.shape)
        trace["latent_mask_shape"] = list(Mi.shape) if Mi is not None else None

    # (4) denoise loop
    z = denoise(unet=unet, scheduler=scheduler, z_init=z_init, Xi=Xi, Mi=Mi, trace=trace)
    # (5) split width and decode person branch
    z_person, _ = split_width(z)
    out = decode_from_latent(vae, z_person)

    if trace is not None:
        trace["output_shape"] = list(out.shape)
        return out, trace

    return out
