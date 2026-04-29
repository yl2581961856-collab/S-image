# Model Contract (Flux UOp <-> Infra)

- Version: v2
- Status: Draft (Flux rewrite)
- Last Updated: 2026-04-29

## Scope

Flux/DiT inference integration contract for gateway/worker deployment.

## Current Status

1. `uop.ops` provides the tinygrad-style UOp IR scaffold.
2. `uop.algo.flux_forward_graph` builds a backend-neutral Flux graph skeleton.
3. Runtime worker is not wired to lower/execute the Flux UOp graph yet.
4. Current evaluation caller is `scripts/evaluate.py` -> `uop.metrics.*`.

## Call Map

Current:

```text
scripts/evaluate.py
  -> uop.metrics.compute_ssim/lpips/fid/kid

uop/algo.py
  -> uop/ops.py
```

Target:

```text
Frontend -> FastAPI Gateway -> Redis -> GPU Worker
  -> uop.algo.flux_forward_graph
  -> lowering planner
  -> Triton/Tile-Lang kernels
  -> result callback/polling
```

## Input Contract (Worker -> Flux Graph)

1. `latent`: `[B,C,H,W]`, default `C=16`, dtype `bf16/f16/f32`.
2. `text_tokens`: `[B,T_txt,HIDDEN]`, default `HIDDEN=3072`.
3. `conditioning`: `[B,HIDDEN]`, timestep/guidance/pooled text conditioning.
4. `rope_freqs`: `[B,T_total,HEAD_DIM]`, default `HEAD_DIM=128`.
5. `FluxConfig` controls patch size, heads, depth, dtype, and backend hints.

## Output Contract (Flux Graph -> Worker)

1. Success: UOp root named `flux_latent_out`, shape `[B,C,H,W]`.
2. Lowering: backend-neutral nodes should lower to Python/Torch/Triton/Tile-Lang execution plans.
3. Failure: raise explicit exception, worker maps to stable error code.

Recommended error code mapping:

- `E_INPUT_SHAPE`
- `E_GRAPH_CONTRACT`
- `E_LOWERING_UNSUPPORTED`
- `E_KERNEL_COMPILE`
- `E_RUNTIME_OOM`
- `E_RUNTIME_INTERNAL`

## Handoff Checklist (UOp -> Infra)

1. `ModelManifest` (weights, hash, deps, min VRAM).
2. This contract file.
3. Golden UOp graph snapshot.
4. Golden output set + threshold.
5. Triton/Tile-Lang kernel registry.
6. Perf baseline report (4090/L20).
7. Rollback plan.

## Progress Snapshot

1. UOp IR scaffold: 30%
2. Flux graph skeleton: 20%
3. Kernel/lowering backend: 5%
4. Infra wiring: 20%
5. End-to-end runnable loop: 20%
