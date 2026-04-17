from __future__ import annotations

from typing import Any

import torch
import torch.nn.functional as F


def build_person_input(Ip: torch.Tensor, M: torch.Tensor | None, mask_free: bool) -> torch.Tensor:
    """Build Ii from target person image and optional cloth-agnostic mask."""
    if mask_free:
        return Ip
    if M is None:
        raise ValueError("M is required for mask-based mode.")
    return Ip * M


def concat_width(left: torch.Tensor, right: torch.Tensor) -> torch.Tensor:
    """Concatenate two tensors along width dimension."""
    if left.shape != right.shape:
        raise ValueError(f"concat_width shape mismatch: {tuple(left.shape)} vs {tuple(right.shape)}")
    return torch.cat([left, right], dim=-1)


def split_width(value: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    """Split tensor into two halves along width dimension."""
    width = value.shape[-1]
    if width % 2 != 0:
        raise ValueError(f"Cannot split odd width tensor: W={width}")
    return torch.chunk(value, 2, dim=-1)


def _vae_scaling_factor(vae: Any) -> float:
    config = getattr(vae, "config", None)
    if config is not None and hasattr(config, "scaling_factor"):
        return float(config.scaling_factor)
    if hasattr(vae, "scaling_factor"):
        return float(vae.scaling_factor)
    return 1.0


def _extract_sample(output: Any) -> torch.Tensor:
    if torch.is_tensor(output):
        return output
    if hasattr(output, "sample") and torch.is_tensor(output.sample):
        return output.sample
    if isinstance(output, (tuple, list)) and output and torch.is_tensor(output[0]):
        return output[0]
    raise TypeError("Unexpected VAE output type; cannot extract tensor sample.")


def encode_to_latent(vae: Any, pixel_values: torch.Tensor) -> torch.Tensor:
    """Encode image tensor to latent space with scaling factor."""
    encoded = vae.encode(pixel_values)
    if hasattr(encoded, "latent_dist"):
        latent = encoded.latent_dist.sample()
    else:
        latent = _extract_sample(encoded)
    return latent * _vae_scaling_factor(vae)


def decode_from_latent(vae: Any, latent: torch.Tensor) -> torch.Tensor:
    """Decode latent tensor to image space with inverse scaling."""
    decoded = vae.decode(latent / _vae_scaling_factor(vae))
    return _extract_sample(decoded)


def build_mask_condition(mask: torch.Tensor, latent_hw: tuple[int, int]) -> torch.Tensor:
    """Build Mi for mask-based branch and resize to latent H/W."""
    mask_cat = torch.cat([mask, torch.zeros_like(mask)], dim=-1)
    return F.interpolate(mask_cat, size=latent_hw, mode="nearest")
