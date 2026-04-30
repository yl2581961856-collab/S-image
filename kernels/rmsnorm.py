from __future__ import annotations

import torch
import triton
import triton.language as tl


@triton.jit
def _rmsnorm_fwd_kernel(
    X,
    W,
    Y,
    stride_x: tl.constexpr,
    stride_y: tl.constexpr,
    N: tl.constexpr,
    eps: tl.constexpr,
    BLOCK_SIZE: tl.constexpr,
) -> None:
    row = tl.program_id(0)
    cols = tl.arange(0, BLOCK_SIZE)
    mask = cols < N

    x = tl.load(X + row * stride_x + cols, mask=mask, other=0.0).to(tl.float32)
    w = tl.load(W + cols, mask=mask, other=0.0).to(tl.float32)

    sum_sq = tl.sum(x * x, axis=0)
    inv_std = tl.rsqrt(sum_sq / N + eps)
    y = x * inv_std * w

    tl.store(Y + row * stride_y + cols, y, mask=mask)


def rmsnorm_torch(x: torch.Tensor, weight: torch.Tensor, eps: float = 1e-6) -> torch.Tensor:
    x_f32 = x.to(torch.float32)
    weight_f32 = weight.to(torch.float32)
    inv_std = torch.rsqrt(x_f32.pow(2).mean(dim=-1, keepdim=True) + eps)
    return (x_f32 * inv_std * weight_f32).to(x.dtype)


def rmsnorm_triton(
    x: torch.Tensor,
    weight: torch.Tensor,
    eps: float = 1e-6,
    out: torch.Tensor | None = None,
    inplace: bool = False,
) -> torch.Tensor:
    if x.ndim < 1:
        raise ValueError("rmsnorm expects at least one dimension")
    if weight.ndim != 1:
        raise ValueError("rmsnorm weight must be rank-1")

    hidden = x.shape[-1]
    if weight.numel() != hidden:
        raise ValueError(f"weight size={weight.numel()} must match hidden={hidden}")

    if x.stride(-1) != 1:
        if inplace:
            raise ValueError("in-place rmsnorm requires contiguous last dimension")
        x = x.contiguous()

    if inplace:
        y = x
    elif out is not None:
        if out.shape != x.shape:
            raise ValueError(f"out shape={out.shape} must match x shape={x.shape}")
        if out.stride(-1) != 1:
            raise ValueError("out must have contiguous last dimension")
        y = out
    else:
        y = torch.empty_like(x)

    if not x.is_cuda:
        ref = rmsnorm_torch(x, weight, eps=eps)
        y.copy_(ref)
        return y

    rows = x.numel() // hidden
    x_2d = x.reshape(rows, hidden)
    y_2d = y.reshape(rows, hidden)

    block_size = triton.next_power_of_2(hidden)
    if block_size > 65536:
        raise ValueError(f"hidden={hidden} is too large for one-block RMSNorm")
    num_warps = 8 if block_size >= 2048 else 4 if block_size >= 1024 else 1

    _rmsnorm_fwd_kernel[(rows,)](
        x_2d,
        weight,
        y_2d,
        x_2d.stride(0),
        y_2d.stride(0),
        hidden,
        eps,
        BLOCK_SIZE=block_size,
        num_warps=num_warps,
    )
    return y


class RMSNorm(torch.nn.Module):
    def __init__(self, hidden_size: int, eps: float = 1e-6, dtype: torch.dtype | None = None) -> None:
        super().__init__()
        self.weight = torch.nn.Parameter(torch.ones(hidden_size, dtype=dtype))
        self.eps = eps

    def forward(self, hidden_states: torch.Tensor) -> torch.Tensor:
        return rmsnorm_triton(hidden_states, self.weight, eps=self.eps)


__all__ = ["RMSNorm", "rmsnorm_torch", "rmsnorm_triton"]


## variance = mean(x^2)
inv_std = rsqrt(variance + eps)
y = x * inv_std * weight   ————> RMSNorm

## mean = mean(x)
var = mean((x - mean)^2)
x_hat = (x - mean) * rstd
y = x_hat * w + b     ——————> LayerNorm
