# Algorithm Module

This folder contains two parts:

1. `algo.py`
- CATVTON forward-pass scaffold (`catvton_forward`).
- Shape checks and mask-free/mask-based condition flow are included.

2. `metrics.py`
- Metric helpers used by `scripts/evaluate.py`.
- Implemented metric entrypoints:
  - `compute_ssim` (pairwise, higher is better)
  - `compute_lpips` (pairwise, lower is better)
  - `compute_fid` (dataset-level, lower is better)
  - `compute_kid` (dataset-level, lower is better)

## Optional dependencies

Install only what you need:

```bash
pip install pillow numpy
pip install scikit-image           # SSIM
pip install torch lpips            # LPIPS
pip install torchmetrics torch-fidelity  # FID/KID
```

## Evaluate script example

```bash
python scripts/evaluate.py \
  --reference-dir ./data/ref \
  --generated-dir ./data/gen \
  --metrics ssim lpips fid kid \
  --output ./reports/eval.json
```
