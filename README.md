# S-image

Working on a computation-graph style image generation engine.

This repository is currently moving away from a conventional app-first image workflow and toward a small UOp/IR layer for experimenting with Flux-style model execution, graph rewrites, and backend lowering.

## Current Focus

- Build a tinygrad-inspired UOp graph representation.
- Describe Flux/DiT blocks as backend-neutral graph nodes.
- Keep Triton and Tile-Lang as possible lowering targets for core kernels.
- Grow the engine from a small, inspectable operator set instead of hiding everything behind framework calls.

## Active Area

- `uop/ops.py`: core UOp, operator groups, tensor specs, rewrite patterns, and backend hints.
- `uop/algo.py`: Flux graph skeleton built from UOps.
- `kernels/`: experimental backend kernels.

This is work in progress. The goal is not just to run an image model, but to understand and control the graph that runs it.
