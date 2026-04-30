# UOp Module

This package is the Flux-oriented operator playground.

1. `ops.py`
- Tinygrad-style UOp IR scaffold.
- Defines `Ops`, `UOp`, `TensorSpec`, rewrite patterns, and backend hints for Triton/Tile-Lang lowering.
- This is the intended place to grow core operator definitions.

2. `algo.py`
- Flux/DiT graph skeleton built from UOps.
- Keeps model structure backend-neutral while allowing selected ops to carry Triton/Tile-Lang hints.

## Minimal UOp example

```python
from uop.ops import DType, placeholder, param, triton_hint

x = placeholder("hidden", ("B", "T", 3072), DType.BF16)
w = param("to_q.weight", (3072, 3072), DType.BF16)
q = x.linear(w, hint=triton_hint("linear_bf16"))
q = q.rmsnorm(eps=1e-6)
```

## Flux graph example

```python
from uop import DeviceTarget, FluxConfig, TargetSpec, flux_forward_graph, plan_lowering

graph = flux_forward_graph(FluxConfig(depth=2))
print(graph.pretty())

plan = plan_lowering(graph, TargetSpec(device=DeviceTarget.NVIDIA))
print(plan.pretty())
```

## Intended direction

- Keep model code backend-neutral by composing `UOp` nodes.
- Use `KernelHint` only at lowering boundaries, such as fused attention, RMSNorm, or tiled matmul.
- Keep scheduler decisions in `uop/lowering`: backend choice, compute dtype, and safe in-place candidates.
- Add rewrite rules with `UPat` + `RewriteRule` before writing backend-specific kernels.

## Notes

- `MATH.md`: math contracts for core UOp operators.
