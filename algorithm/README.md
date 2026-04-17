# Algorithm Module

This folder contains two parts:

1. `algo.py`
- CATVTON forward-pass orchestrator (`catvton_forward`).
- Core flow only: validate -> build condition -> denoise -> decode.

2. `ops/`
- Minimal operator library used by `algo.py`.
- `ops/io.py`: input validation/alignment.
- `ops/latent.py`: width concat/split, VAE encode/decode, mask condition.
- `ops/sampling.py`: noise init + denoising loop.

3. `metrics.py`
- Metric helpers used by `scripts/evaluate.py`.
- Implemented metric entrypoints:
  - `compute_ssim` (pairwise, higher is better)
  - `compute_lpips` (pairwise, lower is better; LPIPS-like via AlexNet features)
  - `compute_fid` (dataset-level, lower is better)
  - `compute_kid` (dataset-level, lower is better)

## Dependency strategy

To stay close to a tinygrad-like engineering style:
- `algo.py` is orchestration-only.
- operator details are split into small pure-PyTorch files under `ops/`.
- metrics are implemented in native PyTorch math without metric packages like
  `scikit-image`, `lpips`, or `torchmetrics`.

Required:

```bash
pip install torch torchvision pillow numpy
```

## Evaluate script example

```bash
python scripts/evaluate.py \
  --reference-dir ./data/ref \
  --generated-dir ./data/gen \
  --metrics ssim lpips fid kid \
  --output ./reports/eval.json
```
