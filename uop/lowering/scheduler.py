from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Mapping, MutableMapping

from uop.ops import KernelBackend, LayoutSpec, Ops, UOp

from .planner import LoweringPlan, LoweringStatus, TargetSpec, plan_lowering

KernelCallable = Callable[..., Any]


@dataclass(frozen=True)
class ScheduleKey:
    graph: str
    device: str
    backend: str
    arch: str | None = None

    def short(self) -> str:
        arch = "" if self.arch is None else f":{self.arch}"
        return f"{self.graph[:12]}@{self.device}/{self.backend}{arch}"


@dataclass(frozen=True)
class KernelRun:
    index: int
    op: Ops
    backend: KernelBackend
    name: str
    input_keys: tuple[str, ...]
    output_key: str
    executed: bool

    def render(self) -> str:
        status = "call" if self.executed else "replay"
        inputs = ", ".join(self.input_keys)
        return f"{self.index:04d} {status:<6} {self.backend.value:<8} {self.name}({inputs}) -> {self.output_key}"


@dataclass(frozen=True)
class ExecutableKernel:
    index: int
    op: Ops
    backend: KernelBackend
    name: str
    input_keys: tuple[str, ...]
    output_key: str
    args: Mapping[str, Any] = field(default_factory=dict)
    kernel_fn: KernelCallable | None = None

    def render(self) -> str:
        inputs = ", ".join(self.input_keys)
        return f"{self.index:04d} capture {self.backend.value:<8} {self.name}({inputs}) -> {self.output_key}"

    def run(self, buffers: MutableMapping[str, Any] | None = None) -> KernelRun:
        buffers = {} if buffers is None else buffers
        if self.kernel_fn is not None:
            missing = tuple(key for key in self.input_keys if key not in buffers)
            if missing:
                raise KeyError(f"missing input buffers for {self.name}: {missing}")
            inputs = tuple(buffers[key] for key in self.input_keys)
            outputs = (buffers[self.output_key],) if self.output_key in buffers else ()
            self.kernel_fn(*inputs, *outputs, **dict(self.args))
        return KernelRun(
            index=self.index,
            op=self.op,
            backend=self.backend,
            name=self.name,
            input_keys=self.input_keys,
            output_key=self.output_key,
            executed=self.kernel_fn is not None,
        )


@dataclass(frozen=True)
class CapturedProgram:
    key: ScheduleKey
    plan: LoweringPlan
    kernels: tuple[ExecutableKernel, ...]

    def pretty(self) -> str:
        header = f"CapturedProgram(key={self.key.short()}, kernels={len(self.kernels)})"
        return "\n".join([header, *(kernel.render() for kernel in self.kernels)])


@dataclass(frozen=True)
class ExecutionTrace:
    key: ScheduleKey
    cache_hit: bool
    kernels_run: int
    events: tuple[KernelRun, ...]

    def pretty(self) -> str:
        cache = "hit" if self.cache_hit else "miss"
        header = f"ExecutionTrace(cache={cache}, key={self.key.short()}, kernels={self.kernels_run})"
        return "\n".join([header, *(event.render() for event in self.events)])


class SImageScheduler:
    def __init__(self, target: TargetSpec | None = None) -> None:
        self.target = target or TargetSpec()
        self.jit_cache: dict[ScheduleKey, CapturedProgram] = {}
        self.cache_hits = 0
        self.cache_misses = 0

    def run_graph(
        self,
        root: UOp,
        inputs: MutableMapping[str, Any] | None = None,
        *,
        target: TargetSpec | None = None,
    ) -> ExecutionTrace:
        target = target or self.target
        key = make_schedule_key(root, target)
        program = self.jit_cache.get(key)
        cache_hit = program is not None
        if program is None:
            self.cache_misses += 1
            program = self.capture(root, target)
            self.jit_cache[key] = program
        else:
            self.cache_hits += 1

        events = tuple(kernel.run(inputs) for kernel in program.kernels)
        return ExecutionTrace(key=key, cache_hit=cache_hit, kernels_run=len(events), events=events)

    def capture(self, root: UOp, target: TargetSpec | None = None) -> CapturedProgram:
        target = target or self.target
        plan = self.create_schedule(root, target)
        if plan.unsupported:
            unsupported = ", ".join(step.op.name for step in plan.unsupported)
            raise ValueError(f"cannot capture graph with unsupported ops: {unsupported}")
        key = make_schedule_key(root, target)
        return CapturedProgram(key=key, plan=plan, kernels=self.compile_to_kernels(root, plan))

    def create_schedule(self, root: UOp, target: TargetSpec | None = None) -> LoweringPlan:
        return plan_lowering(root, target or self.target)

    def compile_to_kernels(self, root: UOp, plan: LoweringPlan) -> tuple[ExecutableKernel, ...]:
        nodes = root.toposort()
        node_keys = {node: _node_key(index, node) for index, node in enumerate(nodes)}
        kernels: list[ExecutableKernel] = []
        for step, node in zip(plan.steps, nodes):
            if step.status in {LoweringStatus.INPUT, LoweringStatus.VIEW}:
                continue
            if step.backend is None:
                continue
            kernels.append(
                ExecutableKernel(
                    index=step.index,
                    op=step.op,
                    backend=step.backend,
                    name=step.name or step.hint_name or step.op.name.lower(),
                    input_keys=tuple(node_keys[src] for src in node.src),
                    output_key=node_keys[node],
                    args={
                        "arg": stable_value(node.arg),
                        "shape": tuple(str(dim) for dim in step.shape),
                        "dtype": step.dtype.value,
                        "compute_dtype": None if step.compute_dtype is None else step.compute_dtype.value,
                        "can_inplace": step.can_inplace,
                    },
                )
            )
        return tuple(kernels)


def make_schedule_key(root: UOp, target: TargetSpec) -> ScheduleKey:
    return ScheduleKey(
        graph=graph_fingerprint(root),
        device=target.device.value,
        backend=target.backend.value,
        arch=target.arch,
    )


def graph_fingerprint(root: UOp) -> str:
    nodes = root.toposort()
    node_ids = {node: index for index, node in enumerate(nodes)}
    payload = []
    for index, node in enumerate(nodes):
        payload.append(
            {
                "index": index,
                "op": node.op.name,
                "shape": tuple(str(dim) for dim in node.spec.shape),
                "dtype": node.spec.dtype.value,
                "layout": layout_payload(node.spec.layout),
                "src": tuple(node_ids[src] for src in node.src),
                "arg": stable_value(node.arg),
                "name": node.name,
                "hint": None
                if node.hint is None
                else {
                    "backend": node.hint.backend.value,
                    "name": node.hint.name,
                    "block": node.hint.block,
                    "num_warps": node.hint.num_warps,
                    "num_stages": node.hint.num_stages,
                    "shared_bytes": node.hint.shared_bytes,
                    "meta": stable_value(node.hint.meta),
                },
            }
        )
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def layout_payload(layout: LayoutSpec) -> dict[str, Any]:
    return {
        "order": layout.order,
        "tile": layout.tile,
        "contiguous": layout.contiguous,
        "name": layout.name,
    }


def stable_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, slice):
        return {"slice": (stable_value(value.start), stable_value(value.stop), stable_value(value.step))}
    if isinstance(value, tuple):
        return tuple(stable_value(item) for item in value)
    if isinstance(value, list):
        return [stable_value(item) for item in value]
    if isinstance(value, Mapping):
        return {str(key): stable_value(value[key]) for key in sorted(value, key=str)}
    return repr(value)


def _node_key(index: int, node: UOp) -> str:
    if node.name is not None:
        return node.name
    return f"%{index}:{node.op.name.lower()}"


__all__ = [
    "CapturedProgram",
    "ExecutableKernel",
    "ExecutionTrace",
    "KernelRun",
    "SImageScheduler",
    "ScheduleKey",
    "graph_fingerprint",
    "make_schedule_key",
]
