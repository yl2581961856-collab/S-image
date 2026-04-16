from __future__ import annotations

from typing import Any

import torch
import torch.nn.functional as F


@torch.inference_mode()
def catvton_forward(
    Ip: torch.Tensor,
    Ig: torch.Tensor,
    vae: Any,
    unet: Any,
    scheduler: Any,
    M: torch.Tensor | None = None,
    mask_free: bool = True,
) -> torch.Tensor:
    """Run one CATVTON denoising pass.

    Args:
        Ip: Target person image tensor, shape [B, 3, H, W].
        Ig: Garment image tensor, shape [B, 3, H, W].
        vae: VAE module with encode/decode and scaling_factor.
        unet: Denoiser module.
        scheduler: Diffusion scheduler with timesteps and step().
        M: Optional binary mask tensor [B, 1, H, W].
        mask_free: If True, do not use mask branch.

    Returns:
        Output image tensor, shape [B, 3, H, W].

    Notes:
        - This follows the paper's high-level formulation.
        - Concrete UNet/Scheduler call signatures can differ by implementation.
    """
    if Ip.ndim != 4 or Ig.ndim != 4:
        raise ValueError("Ip and Ig must be 4D tensors [B, C, H, W].")
    if Ip.shape != Ig.shape:
        raise ValueError(f"Ip/Ig shape mismatch: {Ip.shape} vs {Ig.shape}")
    if not mask_free:
        if M is None:
            raise ValueError("M is required when mask_free=False")
        if M.ndim != 4 or M.shape[0] != Ip.shape[0] or M.shape[-2:] != Ip.shape[-2:]:
            raise ValueError("M must be [B, 1, H, W] with same B/H/W as Ip")

    # (1) build person input Ii
    Ii = Ip if mask_free else Ip * M

    # (2) concat along spatial width and encode to latent
    # x_in: [B, 3, H, 2W]
    x_in = torch.cat([Ii, Ig], dim=-1)
    Xi = vae.encode(x_in).latent_dist.sample() * vae.config.scaling_factor

    # (3) optional mask latent condition
    Mi = None
    if not mask_free:
        # M_cat: [B, 1, H, 2W]
        M_cat = torch.cat([M, torch.zeros_like(M)], dim=-1)
        Mi = F.interpolate(M_cat, size=Xi.shape[-2:], mode="nearest")

    # initial noise z_T
    z = torch.randn_like(Xi)

    # (4) denoising loop
    for t in scheduler.timesteps:
        if mask_free:
            cond = torch.cat([z, Xi], dim=1)
        else:
            cond = torch.cat([z, Mi, Xi], dim=1)

        # Some UNet impls use named args, adjust here if needed.
        eps = unet(cond, t).sample
        z = scheduler.step(eps, t, z).prev_sample

    # (5) split back along width, decode person branch
    z_person, _ = torch.chunk(z, 2, dim=-1)
    out = vae.decode(z_person / vae.config.scaling_factor).sample
    return out
