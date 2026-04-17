from __future__ import annotations

from typing import Tuple

import torch


def _ensure_4d_image(name: str, value: torch.Tensor) -> None:
    if value.ndim != 4:
        raise ValueError(f"{name} must be 4D [B, C, H, W], got shape={tuple(value.shape)}")
    if value.shape[1] != 3:
        raise ValueError(f"{name} channel must be 3 (RGB), got C={value.shape[1]}")


def _ensure_float(value: torch.Tensor) -> torch.Tensor:
    if torch.is_floating_point(value):
        return value
    return value.float()


def _normalize_mask(mask: torch.Tensor, reference: torch.Tensor) -> torch.Tensor:
    if mask.ndim == 3:
        mask = mask.unsqueeze(1)
    if mask.ndim != 4:
        raise ValueError(f"M must be 4D [B, 1, H, W], got shape={tuple(mask.shape)}")

    batch, _, height, width = reference.shape
    if mask.shape[0] != batch or mask.shape[-2:] != (height, width):
        raise ValueError(
            "M batch/spatial mismatch with Ip: "
            f"M={tuple(mask.shape)}, Ip={tuple(reference.shape)}"
        )
    if mask.shape[1] != 1:
        raise ValueError(f"M channel must be 1, got C={mask.shape[1]}")

    mask = mask.to(device=reference.device, dtype=reference.dtype)
    return mask.clamp(0.0, 1.0)


def prepare_inputs(
    Ip: torch.Tensor,
    Ig: torch.Tensor,
    M: torch.Tensor | None,
    mask_free: bool,
) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor | None]:
    """Validate and align input tensors for the forward pipeline."""
    _ensure_4d_image("Ip", Ip)
    _ensure_4d_image("Ig", Ig)

    Ip = _ensure_float(Ip)
    Ig = _ensure_float(Ig).to(device=Ip.device, dtype=Ip.dtype)

    if Ip.shape != Ig.shape:
        raise ValueError(f"Ip/Ig shape mismatch: {tuple(Ip.shape)} vs {tuple(Ig.shape)}")

    mask = None
    if not mask_free:
        if M is None:
            raise ValueError("M is required when mask_free=False")
        mask = _normalize_mask(M, Ip)

    return Ip, Ig, mask
