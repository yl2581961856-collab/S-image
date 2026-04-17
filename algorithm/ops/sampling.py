from __future__ import annotations

from typing import Any

import torch


def init_noise_like(reference: torch.Tensor) -> torch.Tensor:
    """Initialize diffusion noise z_T with the same shape as reference latent."""
    return torch.randn_like(reference)


def _extract_unet_sample(output: Any) -> torch.Tensor:
    if torch.is_tensor(output):
        return output
    if hasattr(output, "sample") and torch.is_tensor(output.sample):
        return output.sample
    if isinstance(output, (tuple, list)) and output and torch.is_tensor(output[0]):
        return output[0]
    raise TypeError("Unexpected UNet output type; cannot extract predicted noise tensor.")


def _call_unet(unet: Any, cond: torch.Tensor, t: Any) -> torch.Tensor:
    try:
        result = unet(cond, t)
    except TypeError:
        try:
            result = unet(sample=cond, timestep=t)
        except TypeError:
            result = unet(cond, timestep=t)
    return _extract_unet_sample(result)


def _scheduler_prev_sample(scheduler: Any, eps: torch.Tensor, t: Any, z: torch.Tensor) -> torch.Tensor:
    result = scheduler.step(eps, t, z)
    if torch.is_tensor(result):
        return result
    if hasattr(result, "prev_sample") and torch.is_tensor(result.prev_sample):
        return result.prev_sample
    if isinstance(result, dict) and "prev_sample" in result and torch.is_tensor(result["prev_sample"]):
        return result["prev_sample"]
    raise TypeError("Unexpected scheduler.step output type; cannot extract prev_sample.")


def _timestep_to_int(value: Any) -> int:
    if hasattr(value, "item"):
        return int(value.item())
    return int(value)


def denoise(
    unet: Any,
    scheduler: Any,
    z_init: torch.Tensor,
    Xi: torch.Tensor,
    Mi: torch.Tensor | None = None,
    trace: dict[str, Any] | None = None,
) -> torch.Tensor:
    """Run denoising loop using UNet and scheduler."""
    timesteps = getattr(scheduler, "timesteps", None)
    if timesteps is None:
        raise ValueError("scheduler.timesteps is required before denoise().")

    z = z_init
    total = len(timesteps)
    key_steps = {0, max(total // 2, 0), max(total - 1, 0)}

    if trace is not None:
        trace["num_steps"] = total
        trace["step_snapshots"] = []

    for idx, t in enumerate(timesteps):
        if Mi is None:
            cond = torch.cat([z, Xi], dim=1)
        else:
            cond = torch.cat([z, Mi, Xi], dim=1)

        eps = _call_unet(unet, cond, t)
        z = _scheduler_prev_sample(scheduler, eps, t, z)

        if trace is not None and idx in key_steps:
            trace["step_snapshots"].append(
                {
                    "step_index": idx,
                    "timestep": _timestep_to_int(t),
                    "latent_shape": list(z.shape),
                }
            )

    return z
