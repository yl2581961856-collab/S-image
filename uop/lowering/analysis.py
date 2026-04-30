from __future__ import annotations

from collections import defaultdict

from uop.ops import DType, Ops, UOp


INPLACE_ELIGIBLE_OPS = {
    Ops.RMSNORM,
    Ops.LAYERNORM,
    Ops.GELU,
    Ops.SILU,
    Ops.RELU,
    Ops.TANH,
    Ops.SIGMOID,
    Ops.NEG,
    Ops.MODULATE,
    Ops.ADA_LN,
}

F32_ACCUM_OPS = {
    Ops.MATMUL,
    Ops.LINEAR,
    Ops.CONV2D,
    Ops.LAYERNORM,
    Ops.RMSNORM,
    Ops.ADA_LN,
    Ops.VAR,
    Ops.SOFTMAX,
    Ops.ATTENTION,
    Ops.FLASH_ATTENTION,
}


def consumer_map(root: UOp) -> dict[UOp, tuple[UOp, ...]]:
    consumers: dict[UOp, list[UOp]] = defaultdict(list)
    for node in root.toposort():
        for child in node.src:
            consumers[child].append(node)
    return {node: tuple(users) for node, users in consumers.items()}


def consumer_count(root: UOp) -> dict[UOp, int]:
    return {node: len(users) for node, users in consumer_map(root).items()}


def can_inplace(node: UOp, consumers: dict[UOp, int]) -> bool:
    if node.op not in INPLACE_ELIGIBLE_OPS or not node.src:
        return False
    src = node.src[0]
    return (
        consumers.get(src, 0) == 1
        and node.spec.shape == src.spec.shape
        and node.spec.dtype == src.spec.dtype
    )


def compute_dtype_for(node: UOp) -> DType | None:
    if node.op in F32_ACCUM_OPS and node.spec.dtype in {DType.F16, DType.BF16, DType.F32}:
        return DType.F32
    return node.spec.dtype if node.op in {Ops.CAST, Ops.BITCAST} else None
