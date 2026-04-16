from __future__ import annotations

from pathlib import Path
from statistics import mean
from typing import Iterable, Sequence


def _resolve_device(requested: str, torch_module) -> str:
    if requested.startswith("cuda") and not torch_module.cuda.is_available():
        return "cpu"
    return requested


def _load_image_np(path: Path, image_size: int | None):
    from PIL import Image
    import numpy as np

    image = Image.open(path).convert("RGB")
    if image_size is not None:
        resampling = getattr(Image, "Resampling", Image)
        image = image.resize((image_size, image_size), resampling.BICUBIC)
    arr = np.asarray(image, dtype=np.float32) / 255.0
    return arr


def _load_image_tensor(path: Path, image_size: int | None, torch_module):
    import numpy as np

    arr = _load_image_np(path=path, image_size=image_size)
    tensor = torch_module.from_numpy(np.transpose(arr, (2, 0, 1)))  # [3,H,W]
    return tensor


def _iter_batches(paths: Sequence[Path], batch_size: int) -> Iterable[Sequence[Path]]:
    for idx in range(0, len(paths), batch_size):
        yield paths[idx : idx + batch_size]


def compute_ssim(
    pairs: Sequence[tuple[Path, Path]],
    image_size: int | None,
    batch_size: int,
    device: str,
) -> float:
    """Compute mean SSIM over paired images (higher is better)."""
    del batch_size, device
    if not pairs:
        raise ValueError("No image pairs provided for SSIM.")

    try:
        from skimage.metrics import structural_similarity
    except ImportError as exc:
        raise ImportError(
            "SSIM requires scikit-image. Install with: pip install scikit-image"
        ) from exc

    scores: list[float] = []
    for ref_path, gen_path in pairs:
        ref = _load_image_np(ref_path, image_size)
        gen = _load_image_np(gen_path, image_size)
        score = structural_similarity(ref, gen, channel_axis=2, data_range=1.0)
        scores.append(float(score))

    return float(mean(scores))


def compute_lpips(
    pairs: Sequence[tuple[Path, Path]],
    image_size: int | None,
    batch_size: int,
    device: str,
) -> float:
    """Compute mean LPIPS over paired images (lower is better)."""
    if not pairs:
        raise ValueError("No image pairs provided for LPIPS.")

    try:
        import lpips
    except ImportError as exc:
        raise ImportError("LPIPS requires package 'lpips'. Install with: pip install lpips") from exc

    try:
        import torch
    except ImportError as exc:
        raise ImportError("LPIPS requires PyTorch. Install with: pip install torch") from exc

    run_device = _resolve_device(device, torch)
    model = lpips.LPIPS(net="alex")
    model = model.to(run_device)
    model.eval()

    all_scores: list[float] = []
    with torch.inference_mode():
        for batch in _iter_batches([p for p in pairs], batch_size):
            ref_batch = torch.stack([
                _load_image_tensor(ref_path, image_size, torch) for ref_path, _ in batch
            ])
            gen_batch = torch.stack([
                _load_image_tensor(gen_path, image_size, torch) for _, gen_path in batch
            ])

            # LPIPS expects [-1, 1]
            ref_batch = (ref_batch * 2.0 - 1.0).to(run_device)
            gen_batch = (gen_batch * 2.0 - 1.0).to(run_device)

            scores = model(gen_batch, ref_batch).view(-1)
            all_scores.extend([float(x.item()) for x in scores])

    return float(mean(all_scores))


def compute_fid(
    reference_paths: Sequence[Path],
    generated_paths: Sequence[Path],
    image_size: int | None,
    batch_size: int,
    device: str,
) -> float:
    """Compute FID between two image sets (lower is better)."""
    if not reference_paths or not generated_paths:
        raise ValueError("FID requires non-empty reference and generated sets.")

    try:
        import torch
    except ImportError as exc:
        raise ImportError("FID requires PyTorch. Install with: pip install torch") from exc

    try:
        from torchmetrics.image.fid import FrechetInceptionDistance
    except ImportError as exc:
        raise ImportError(
            "FID requires torchmetrics + torch-fidelity. Install with: "
            "pip install torchmetrics torch-fidelity"
        ) from exc

    run_device = _resolve_device(device, torch)
    metric = FrechetInceptionDistance(feature=2048, normalize=True).to(run_device)

    with torch.inference_mode():
        for batch_paths in _iter_batches(reference_paths, batch_size):
            real = torch.stack([_load_image_tensor(p, image_size, torch) for p in batch_paths]).to(run_device)
            metric.update(real, real=True)

        for batch_paths in _iter_batches(generated_paths, batch_size):
            fake = torch.stack([_load_image_tensor(p, image_size, torch) for p in batch_paths]).to(run_device)
            metric.update(fake, real=False)

        value = metric.compute()

    return float(value.item())


def compute_kid(
    reference_paths: Sequence[Path],
    generated_paths: Sequence[Path],
    image_size: int | None,
    batch_size: int,
    device: str,
) -> float:
    """Compute KID mean between two image sets (lower is better)."""
    if not reference_paths or not generated_paths:
        raise ValueError("KID requires non-empty reference and generated sets.")

    try:
        import torch
    except ImportError as exc:
        raise ImportError("KID requires PyTorch. Install with: pip install torch") from exc

    try:
        from torchmetrics.image.kid import KernelInceptionDistance
    except ImportError as exc:
        raise ImportError(
            "KID requires torchmetrics + torch-fidelity. Install with: "
            "pip install torchmetrics torch-fidelity"
        ) from exc

    run_device = _resolve_device(device, torch)
    subset_size = min(1000, len(reference_paths), len(generated_paths))
    if subset_size < 2:
        raise ValueError("KID requires at least 2 samples in each set.")

    metric = KernelInceptionDistance(subset_size=subset_size, normalize=True).to(run_device)

    with torch.inference_mode():
        for batch_paths in _iter_batches(reference_paths, batch_size):
            real = torch.stack([_load_image_tensor(p, image_size, torch) for p in batch_paths]).to(run_device)
            metric.update(real, real=True)

        for batch_paths in _iter_batches(generated_paths, batch_size):
            fake = torch.stack([_load_image_tensor(p, image_size, torch) for p in batch_paths]).to(run_device)
            metric.update(fake, real=False)

        kid_mean, _kid_std = metric.compute()

    return float(kid_mean.item())
