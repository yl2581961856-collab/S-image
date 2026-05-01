#!/usr/bin/env python3
"""Static MNIST-shaped graph smoke test for the S-image scheduler.

This is not a training script. It keeps the graph static so the scheduler can
capture once and replay the same instruction stream on later iterations.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from uop import DType, DeviceTarget, SImageScheduler, TargetSpec, TensorSpec, UOp, Ops, param, placeholder


def build_mnist_graph(batch_size: int = 32, channels: int = 8, hidden: int = 128) -> UOp:
    image = placeholder("image", (batch_size, 1, 28, 28), DType.F32)
    conv_weight = param("conv.weight", (channels, 1, 3, 3), DType.F32)
    conv = UOp(
        Ops.CONV2D,
        TensorSpec(shape=(batch_size, channels, 26, 26), dtype=DType.F32),
        src=(image, conv_weight),
        arg={"stride": (1, 1), "padding": (0, 0), "dilation": (1, 1)},
        name="conv2d_3x3",
    )
    act = conv.gelu()
    flat = act.reshape(batch_size, channels * 26 * 26)

    fc1_weight = param("fc1.weight", (hidden, channels * 26 * 26), DType.F32)
    hidden_state = flat.linear(fc1_weight).gelu()

    head_weight = param("head.weight", (10, hidden), DType.F32)
    return hidden_state.linear(head_weight).with_name("logits")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MNIST-shaped static scheduler smoke test.")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--channels", type=int, default=8)
    parser.add_argument("--hidden", type=int, default=128)
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--device", choices=[target.value for target in DeviceTarget], default=DeviceTarget.CPU.value)
    parser.add_argument("--show-plan", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.repeat < 1:
        raise ValueError("--repeat must be >= 1")

    target = TargetSpec(device=DeviceTarget(args.device))
    graph = build_mnist_graph(batch_size=args.batch_size, channels=args.channels, hidden=args.hidden)
    scheduler = SImageScheduler(target=target)

    if args.show_plan:
        print(scheduler.create_schedule(graph).pretty())

    traces = [scheduler.run_graph(graph, inputs={"image": object()}) for _ in range(args.repeat)]
    for step, trace in enumerate(traces):
        print(f"\niteration={step}")
        print(trace.pretty())

    expected_hits = args.repeat - 1
    if scheduler.cache_misses != 1 or scheduler.cache_hits != expected_hits:
        raise RuntimeError(
            f"unexpected cache stats: misses={scheduler.cache_misses}, "
            f"hits={scheduler.cache_hits}, expected hits={expected_hits}"
        )

    print(f"\ncache ok: misses={scheduler.cache_misses}, hits={scheduler.cache_hits}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
