from __future__ import annotations

from pathlib import Path
from statistics import mean
from typing import Iterable, Sequence


def _resolve_device(requested: str, torch_module) -> str:
    if requested.startswith("cuda") and not torch_module.cuda.is_available():
        return "cpu"
    return requested


def _load_image_tensor(path: Path, image_size: int | None, torch_module):
    from PIL import Image
    import numpy as np

    image = Image.open(path).convert("RGB")
    if image_size is not None:
        resampling = getattr(Image, "Resampling", Image)
        image = image.resize((image_size, image_size), resampling.BICUBIC)

    arr = np.asarray(image, dtype=np.float32) / 255.0
    tensor = torch_module.from_numpy(arr).permute(2, 0, 1).contiguous()  # [3,H,W]
    return tensor


def _iter_batches(paths: Sequence, batch_size: int) -> Iterable[Sequence]:
    for idx in range(0, len(paths), batch_size):
        yield paths[idx : idx + batch_size]


def _gaussian_window(channels: int, window_size: int, sigma: float, torch_module, device, dtype):
    coords = torch_module.arange(window_size, device=device, dtype=dtype) - window_size // 2
    gauss = torch_module.exp(-(coords**2) / (2.0 * sigma**2))
    gauss = gauss / gauss.sum()
    kernel_2d = gauss[:, None] * gauss[None, :]
    window = kernel_2d.expand(channels, 1, window_size, window_size).contiguous()
    return window


def _ssim_batch(
    x,
    y,
    torch_module,
    window_size: int = 11,
    sigma: float = 1.5,
    data_range: float = 1.0,
):
    import torch.nn.functional as F

    channels = x.shape[1]
    window = _gaussian_window(channels, window_size, sigma, torch_module, x.device, x.dtype)

    mu_x = F.conv2d(x, window, padding=window_size // 2, groups=channels)
    mu_y = F.conv2d(y, window, padding=window_size // 2, groups=channels)

    mu_x_sq = mu_x * mu_x
    mu_y_sq = mu_y * mu_y
    mu_xy = mu_x * mu_y

    sigma_x_sq = F.conv2d(x * x, window, padding=window_size // 2, groups=channels) - mu_x_sq
    sigma_y_sq = F.conv2d(y * y, window, padding=window_size // 2, groups=channels) - mu_y_sq
    sigma_xy = F.conv2d(x * y, window, padding=window_size // 2, groups=channels) - mu_xy

    c1 = (0.01 * data_range) ** 2
    c2 = (0.03 * data_range) ** 2

    numerator = (2.0 * mu_xy + c1) * (2.0 * sigma_xy + c2)
    denominator = (mu_x_sq + mu_y_sq + c1) * (sigma_x_sq + sigma_y_sq + c2)
    ssim_map = numerator / (denominator + 1e-12)
    return ssim_map.mean(dim=(1, 2, 3))


def _normalize_for_inception(x, torch_module):
    import torch.nn.functional as F

    x = F.interpolate(x, size=(299, 299), mode="bilinear", align_corners=False)
    mean = torch_module.tensor([0.485, 0.456, 0.406], device=x.device, dtype=x.dtype).view(1, 3, 1, 1)
    std = torch_module.tensor([0.229, 0.224, 0.225], device=x.device, dtype=x.dtype).view(1, 3, 1, 1)
    return (x - mean) / std


def _build_inception(torch_module, device: str):
    import torch.nn as nn
    from torchvision.models import Inception_V3_Weights, inception_v3

    model = inception_v3(weights=Inception_V3_Weights.IMAGENET1K_V1, aux_logits=False)
    model.fc = nn.Identity()
    model.eval()
    model.to(device)
    return model


def _extract_inception_features(paths: Sequence[Path], image_size: int | None, batch_size: int, device: str, torch_module):
    model = _build_inception(torch_module, device)

    feats = []
    with torch_module.inference_mode():
        for batch_paths in _iter_batches(paths, batch_size):
            batch = torch_module.stack([_load_image_tensor(p, image_size, torch_module) for p in batch_paths]).to(device)
            batch = _normalize_for_inception(batch, torch_module)
            out = model(batch)
            if out.ndim == 1:
                out = out.unsqueeze(0)
            feats.append(out.detach().float().cpu())

    if not feats:
        raise ValueError("No features extracted.")

    return torch_module.cat(feats, dim=0)


def _covariance(features, torch_module):
    if features.shape[0] < 2:
        raise ValueError("At least two samples are required to compute covariance.")
    centered = features - features.mean(dim=0, keepdim=True)
    return centered.t().mm(centered) / (features.shape[0] - 1)


def _matrix_sqrt_psd(mat, torch_module, eps: float = 1e-12):
    eigvals, eigvecs = torch_module.linalg.eigh(mat)
    eigvals = torch_module.clamp(eigvals, min=0.0)
    sqrt_diag = torch_module.diag(torch_module.sqrt(eigvals + eps))
    return eigvecs @ sqrt_diag @ eigvecs.t()


def _polynomial_mmd_unbiased(x, y, torch_module):
    # Kernel: k(a,b) = (a·b / d + 1)^3
    d = x.shape[1]
    k_xx = ((x @ x.t()) / d + 1.0) ** 3
    k_yy = ((y @ y.t()) / d + 1.0) ** 3
    k_xy = ((x @ y.t()) / d + 1.0) ** 3

    m = x.shape[0]
    n = y.shape[0]
    if m < 2 or n < 2:
        raise ValueError("KID subset size must be >= 2.")

    sum_xx = (k_xx.sum() - k_xx.diagonal().sum()) / (m * (m - 1))
    sum_yy = (k_yy.sum() - k_yy.diagonal().sum()) / (n * (n - 1))
    sum_xy = k_xy.mean()

    return sum_xx + sum_yy - 2.0 * sum_xy


def _build_alexnet_feature_slices(torch_module, device: str):
    from torchvision.models import AlexNet_Weights, alexnet

    model = alexnet(weights=AlexNet_Weights.IMAGENET1K_V1).features.eval().to(device)
    # ReLU outputs after conv blocks in alexnet.features
    capture_indices = {1, 4, 7, 9, 11}
    return model, capture_indices


def _extract_alex_features(x, model, capture_indices):
    feats = []
    h = x
    for idx, layer in enumerate(model):
        h = layer(h)
        if idx in capture_indices:
            feats.append(h)
    return feats


def _normalize_feature_map(feat, torch_module):
    denom = torch_module.sqrt((feat * feat).sum(dim=1, keepdim=True) + 1e-10)
    return feat / denom


def compute_ssim(
    pairs: Sequence[tuple[Path, Path]],
    image_size: int | None,
    batch_size: int,
    device: str,
) -> float:
    """Compute mean SSIM over paired images (higher is better), pure PyTorch implementation."""
    if not pairs:
        raise ValueError("No image pairs provided for SSIM.")

    try:
        import torch
    except ImportError as exc:
        raise ImportError("SSIM requires PyTorch. Install with: pip install torch") from exc

    run_device = _resolve_device(device, torch)
    scores: list[float] = []

    with torch.inference_mode():
        for batch in _iter_batches(list(pairs), batch_size):
            ref_batch = torch.stack([_load_image_tensor(ref_path, image_size, torch) for ref_path, _ in batch]).to(run_device)
            gen_batch = torch.stack([_load_image_tensor(gen_path, image_size, torch) for _, gen_path in batch]).to(run_device)
            ssim_vals = _ssim_batch(ref_batch, gen_batch, torch_module=torch)
            scores.extend([float(v.item()) for v in ssim_vals])

    return float(mean(scores))


def compute_lpips(
    pairs: Sequence[tuple[Path, Path]],
    image_size: int | None,
    batch_size: int,
    device: str,
) -> float:
    """Compute LPIPS-like score with pure PyTorch + torchvision (lower is better).

    Note:
    - This is a lightweight LPIPS-like implementation using AlexNet feature distances.
    - It avoids external `lpips` package but keeps similar perceptual behavior.
    """
    if not pairs:
        raise ValueError("No image pairs provided for LPIPS.")

    try:
        import torch
    except ImportError as exc:
        raise ImportError("LPIPS requires PyTorch. Install with: pip install torch") from exc

    try:
        import torchvision  # noqa: F401
    except ImportError as exc:
        raise ImportError("LPIPS-like metric requires torchvision. Install with: pip install torchvision") from exc

    run_device = _resolve_device(device, torch)
    model, capture_indices = _build_alexnet_feature_slices(torch, run_device)

    all_scores: list[float] = []
    with torch.inference_mode():
        for batch in _iter_batches(list(pairs), batch_size):
            ref_batch = torch.stack([_load_image_tensor(ref_path, image_size, torch) for ref_path, _ in batch]).to(run_device)
            gen_batch = torch.stack([_load_image_tensor(gen_path, image_size, torch) for _, gen_path in batch]).to(run_device)

            # expected range [-1, 1]
            ref_batch = ref_batch * 2.0 - 1.0
            gen_batch = gen_batch * 2.0 - 1.0

            f_ref = _extract_alex_features(ref_batch, model, capture_indices)
            f_gen = _extract_alex_features(gen_batch, model, capture_indices)

            score = 0.0
            for fr, fg in zip(f_ref, f_gen):
                fr_n = _normalize_feature_map(fr, torch)
                fg_n = _normalize_feature_map(fg, torch)
                layer_dist = ((fr_n - fg_n) ** 2).mean(dim=(1, 2, 3))
                score = score + layer_dist

            score = score / len(f_ref)
            all_scores.extend([float(v.item()) for v in score])

    return float(mean(all_scores))


def compute_fid(
    reference_paths: Sequence[Path],
    generated_paths: Sequence[Path],
    image_size: int | None,
    batch_size: int,
    device: str,
) -> float:
    """Compute FID between two image sets (lower is better), pure PyTorch implementation."""
    if not reference_paths or not generated_paths:
        raise ValueError("FID requires non-empty reference and generated sets.")

    try:
        import torch
    except ImportError as exc:
        raise ImportError("FID requires PyTorch. Install with: pip install torch") from exc

    try:
        import torchvision  # noqa: F401
    except ImportError as exc:
        raise ImportError("FID requires torchvision. Install with: pip install torchvision") from exc

    run_device = _resolve_device(device, torch)

    real_feats = _extract_inception_features(reference_paths, image_size, batch_size, run_device, torch)
    fake_feats = _extract_inception_features(generated_paths, image_size, batch_size, run_device, torch)

    real_feats = real_feats.float()
    fake_feats = fake_feats.float()

    mu_r = real_feats.mean(dim=0)
    mu_f = fake_feats.mean(dim=0)
    sigma_r = _covariance(real_feats, torch)
    sigma_f = _covariance(fake_feats, torch)

    # symmetric PSD route for sqrtm
    eps = 1e-6
    eye = torch.eye(sigma_r.shape[0], dtype=sigma_r.dtype)
    sigma_r = sigma_r + eye * eps
    sigma_f = sigma_f + eye * eps

    sigma_r_sqrt = _matrix_sqrt_psd(sigma_r, torch)
    cov_prod = sigma_r_sqrt @ sigma_f @ sigma_r_sqrt
    covmean = _matrix_sqrt_psd(cov_prod, torch)

    diff = mu_r - mu_f
    fid = diff.dot(diff) + torch.trace(sigma_r + sigma_f - 2.0 * covmean)
    fid = torch.clamp(fid, min=0.0)
    return float(fid.item())


def compute_kid(
    reference_paths: Sequence[Path],
    generated_paths: Sequence[Path],
    image_size: int | None,
    batch_size: int,
    device: str,
) -> float:
    """Compute KID mean between two image sets (lower is better), pure PyTorch implementation."""
    if not reference_paths or not generated_paths:
        raise ValueError("KID requires non-empty reference and generated sets.")

    try:
        import torch
    except ImportError as exc:
        raise ImportError("KID requires PyTorch. Install with: pip install torch") from exc

    try:
        import torchvision  # noqa: F401
    except ImportError as exc:
        raise ImportError("KID requires torchvision. Install with: pip install torchvision") from exc

    run_device = _resolve_device(device, torch)

    real_feats = _extract_inception_features(reference_paths, image_size, batch_size, run_device, torch).float()
    fake_feats = _extract_inception_features(generated_paths, image_size, batch_size, run_device, torch).float()

    n_real = real_feats.shape[0]
    n_fake = fake_feats.shape[0]
    subset_size = min(1000, n_real, n_fake)
    if subset_size < 2:
        raise ValueError("KID requires at least 2 samples in each set.")

    # More subsets for larger datasets; capped to avoid heavy runtime.
    num_subsets = max(10, min(50, (min(n_real, n_fake) // subset_size) * 10 or 10))

    mmd_vals = []
    for _ in range(num_subsets):
        idx_r = torch.randperm(n_real)[:subset_size]
        idx_f = torch.randperm(n_fake)[:subset_size]

        x = real_feats[idx_r]
        y = fake_feats[idx_f]
        mmd2 = _polynomial_mmd_unbiased(x, y, torch)
        mmd_vals.append(float(mmd2.item()))

    return float(mean(mmd_vals))
