# Model Contract (Algorithm <-> Infra)

- Version: v1
- Status: Active (MVP)
- Last Updated: 2026-04-17

## Scope

CATVTON inference integration contract for gateway/worker deployment.

## Current Status

1. `algorithm.catvton_forward` is implemented.
2. Runtime worker is not wired to call `catvton_forward` yet.
3. Current live caller is `scripts/evaluate.py` -> `algorithm.metrics.*`.

## Call Map

Current:

```text
scripts/evaluate.py
  -> algorithm.metrics.compute_ssim/lpips/fid/kid

algorithm/algo.py
  -> algorithm/ops/io.py
  -> algorithm/ops/latent.py
  -> algorithm/ops/sampling.py
```

Target:

```text
Frontend -> FastAPI Gateway -> Redis -> GPU Worker -> algorithm.catvton_forward -> result callback/polling
```

## Input Contract (Worker -> Algorithm)

1. `Ip`: `[B,3,H,W]`, float, range `[0,1]`
2. `Ig`: `[B,3,H,W]`, float, range `[0,1]`
3. `mask_free=False` requires `M`: `[B,1,H,W]`, range `[0,1]`
4. `vae/unet/scheduler` must be initialized before call
5. `scheduler.timesteps` must be set before denoising

## Output Contract (Algorithm -> Worker)

1. Success: `out` tensor `[B,3,H,W]`
2. Optional debug: `(out, trace)` when `return_trace=True`
3. Failure: raise explicit exception, worker maps to stable error code

Recommended error code mapping:

- `E_INPUT_SHAPE`
- `E_MODEL_SIGNATURE`
- `E_RUNTIME_OOM`
- `E_RUNTIME_INTERNAL`

## Handoff Checklist (Algorithm -> Infra)

1. `ModelManifest` (weights, hash, deps, min VRAM)
2. This contract file
3. Golden set + threshold
4. Perf baseline report (4090/L20)
5. Rollback plan

## Progress Snapshot

1. Algorithm module engineering: 70%
2. Infra wiring: 20%
3. End-to-end runnable loop: 30%
