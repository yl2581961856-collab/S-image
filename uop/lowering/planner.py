from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .analysis import can_inplace, compute_dtype_for, consumer_count
from uop.ops import DType, GroupOp, KernelBackend, Ops, Shape, UOp


class DeviceTarget(str, Enum):
    CPU = "cpu"
    NVIDIA = "nvidia"
    AMD = "amd"
    ASCEND = "ascend"


class LoweringStatus(str, Enum):
    INPUT = "input"
    VIEW = "view"
    GENERIC = "generic"
    KERNEL = "kernel"
    COMPOSITE = "composite"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True)
class TargetSpec:
    device: DeviceTarget = DeviceTarget.CPU
    backend: KernelBackend = KernelBackend.AUTO
    arch: str | None = None
    name: str | None = None


@dataclass(frozen=True)
class LoweringStep:
    index: int
    op: Ops
    status: LoweringStatus
    backend: KernelBackend | None
    shape: Shape
    dtype: DType
    compute_dtype: DType | None = None
    can_inplace: bool = False
    name: str | None = None
    hint_name: str | None = None

    def render(self) -> str:
        backend = "-" if self.backend is None else self.backend.value
        label = f" {self.name}" if self.name else ""
        hint = f" hint={self.hint_name}" if self.hint_name else ""
        compute = f" compute={self.compute_dtype.value}" if self.compute_dtype else ""
        inplace = " inplace" if self.can_inplace else ""
        return (
            f"{self.index:04d} {self.status.value:<11} {backend:<8} "
            f"{self.op.name:<18} shape={self.shape} dtype={self.dtype.value}{compute}{inplace}{label}{hint}"
        )


@dataclass(frozen=True)
class LoweringPlan:
    target: TargetSpec
    steps: tuple[LoweringStep, ...]

    @property
    def unsupported(self) -> tuple[LoweringStep, ...]:
        return tuple(step for step in self.steps if step.status is LoweringStatus.UNSUPPORTED)

    def pretty(self) -> str:
        header = (
            f"LoweringPlan(device={self.target.device.value}, "
            f"backend={self.target.backend.value}, steps={len(self.steps)}, "
            f"unsupported={len(self.unsupported)})"
        )
        return "\n".join([header, *(step.render() for step in self.steps)])


def plan_lowering(root: UOp, target: TargetSpec | None = None) -> LoweringPlan:
    target = target or TargetSpec()
    consumers = consumer_count(root)
    steps = []
    for index, node in enumerate(root.toposort()):
        status = classify_op(node.op)
        backend = None if status in {LoweringStatus.INPUT, LoweringStatus.VIEW} else choose_backend(node, target)
        steps.append(
            LoweringStep(
                index=index,
                op=node.op,
                status=status,
                backend=backend,
                shape=node.spec.shape,
                dtype=node.spec.dtype,
                compute_dtype=compute_dtype_for(node),
                can_inplace=can_inplace(node, consumers),
                name=node.name,
                hint_name=node.hint.name if node.hint else None,
            )
        )
    return LoweringPlan(target=target, steps=tuple(steps))


def choose_backend(node: UOp, target: TargetSpec) -> KernelBackend:
    if target.backend is not KernelBackend.AUTO:
        return target.backend
    if (
        node.hint is not None
        and node.hint.backend is not KernelBackend.AUTO
        and backend_compatible(node.hint.backend, target.device)
    ):
        return node.hint.backend
    if target.device is DeviceTarget.ASCEND:
        return KernelBackend.CANN
    if target.device in {DeviceTarget.NVIDIA, DeviceTarget.AMD}:
        return KernelBackend.TRITON
    return KernelBackend.TORCH


def backend_compatible(backend: KernelBackend, device: DeviceTarget) -> bool:
    if backend in {KernelBackend.PYTHON, KernelBackend.TORCH}:
        return True
    if backend is KernelBackend.TRITON:
        return device in {DeviceTarget.NVIDIA, DeviceTarget.AMD}
    if backend is KernelBackend.TILELANG:
        return device in {DeviceTarget.NVIDIA, DeviceTarget.AMD}
    if backend is KernelBackend.CANN:
        return device is DeviceTarget.ASCEND
    return backend is KernelBackend.AUTO


def classify_op(op: Ops) -> LoweringStatus:
    if op in {Ops.PARAM, Ops.CONST, Ops.BUFFER}:
        return LoweringStatus.INPUT
    if op in GroupOp.Movement or op in {Ops.VIEW, Ops.COPY}:
        return LoweringStatus.VIEW
    if op in GroupOp.Elementwise or op in GroupOp.Reduce:
        return LoweringStatus.GENERIC
    if op in GroupOp.Tensor or op in GroupOp.Backend:
        return LoweringStatus.KERNEL
    if op in GroupOp.Flux:
        return LoweringStatus.COMPOSITE
    return LoweringStatus.UNSUPPORTED
