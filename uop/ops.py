from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, IntEnum, auto
from functools import reduce
from typing import Any, Callable, Iterable, Mapping, Union

ShapeDim = Union[int, str]
Shape = tuple[ShapeDim, ...]


class FastEnum(IntEnum):
    def __str__(self) -> str:
        return Enum.__str__(self)

    def __repr__(self) -> str:
        return str(self)

    @staticmethod
    def _generate_next_value_(
        name: str,
        start: int,
        count: int,
        last_values: list[int],
    ) -> int:
        return 1 + max([0, *last_values, *[max(c) for c in FastEnum.__subclasses__()]])


class Ops(FastEnum):
    # graph roots / program structure
    NOOP = auto()
    CONST = auto()
    PARAM = auto()
    BUFFER = auto()
    VIEW = auto()
    CUSTOM = auto()
    KERNEL = auto()

    # memory / layout
    LOAD = auto()
    STORE = auto()
    COPY = auto()
    CONTIGUOUS = auto()
    TO_LAYOUT = auto()

    # shape movement
    RESHAPE = auto()
    PERMUTE = auto()
    EXPAND = auto()
    PAD = auto()
    SLICE = auto()
    CAT = auto()
    SPLIT = auto()
    PATCHIFY = auto()
    UNPATCHIFY = auto()

    # unary elementwise
    CAST = auto()
    BITCAST = auto()
    NEG = auto()
    EXP = auto()
    LOG = auto()
    SQRT = auto()
    RSQRT = auto()
    RECIP = auto()
    SIN = auto()
    COS = auto()
    TANH = auto()
    SIGMOID = auto()
    RELU = auto()
    SILU = auto()
    GELU = auto()

    # binary elementwise
    ADD = auto()
    SUB = auto()
    MUL = auto()
    DIV = auto()
    POW = auto()
    MAX = auto()
    MIN = auto()
    CMPLT = auto()
    CMPLE = auto()
    CMPGT = auto()
    CMPGE = auto()
    CMPEQ = auto()
    CMPNE = auto()

    # ternary elementwise
    WHERE = auto()
    CLAMP = auto()
    MULACC = auto()

    # reductions
    SUM = auto()
    MEAN = auto()
    VAR = auto()
    REDUCE_MAX = auto()
    SOFTMAX = auto()

    # tensor / neural ops
    MATMUL = auto()
    LINEAR = auto()
    CONV2D = auto()
    LAYERNORM = auto()
    RMSNORM = auto()

    # Flux/DiT focused composite ops
    ROPE = auto()
    ATTENTION = auto()
    FLASH_ATTENTION = auto()
    MODULATE = auto()
    ADA_LN = auto()

    # backend-specific leaves. These should be late lowering targets, not model code.
    TRITON_KERNEL = auto()
    TILELANG_KERNEL = auto()


class GroupOp:
    Unary = {
        Ops.NEG,
        Ops.EXP,
        Ops.LOG,
        Ops.SQRT,
        Ops.RSQRT,
        Ops.RECIP,
        Ops.SIN,
        Ops.COS,
        Ops.TANH,
        Ops.SIGMOID,
        Ops.RELU,
        Ops.SILU,
        Ops.GELU,
    }
    Binary = {
        Ops.ADD,
        Ops.SUB,
        Ops.MUL,
        Ops.DIV,
        Ops.POW,
        Ops.MAX,
        Ops.MIN,
        Ops.CMPLT,
        Ops.CMPLE,
        Ops.CMPGT,
        Ops.CMPGE,
        Ops.CMPEQ,
        Ops.CMPNE,
    }
    Ternary = {Ops.WHERE, Ops.CLAMP, Ops.MULACC}
    Compare = {Ops.CMPLT, Ops.CMPLE, Ops.CMPGT, Ops.CMPGE, Ops.CMPEQ, Ops.CMPNE}
    Elementwise = Unary | Binary | Ternary | {Ops.CAST, Ops.BITCAST}
    Movement = {
        Ops.RESHAPE,
        Ops.PERMUTE,
        Ops.EXPAND,
        Ops.PAD,
        Ops.SLICE,
        Ops.CAT,
        Ops.SPLIT,
        Ops.PATCHIFY,
        Ops.UNPATCHIFY,
        Ops.CONTIGUOUS,
        Ops.TO_LAYOUT,
    }
    Reduce = {Ops.SUM, Ops.MEAN, Ops.VAR, Ops.REDUCE_MAX, Ops.SOFTMAX}
    Tensor = {Ops.MATMUL, Ops.LINEAR, Ops.CONV2D, Ops.LAYERNORM, Ops.RMSNORM}
    Flux = {Ops.ROPE, Ops.ATTENTION, Ops.FLASH_ATTENTION, Ops.MODULATE, Ops.ADA_LN}
    Backend = {Ops.KERNEL, Ops.TRITON_KERNEL, Ops.TILELANG_KERNEL}
    Commutative = {Ops.ADD, Ops.MUL, Ops.MAX, Ops.MIN, Ops.CMPEQ, Ops.CMPNE}
    All = set(Ops)


class DType(str, Enum):
    BOOL = "bool"
    I32 = "i32"
    I64 = "i64"
    F16 = "f16"
    BF16 = "bf16"
    F32 = "f32"
    F64 = "f64"

    @property
    def is_float(self) -> bool:
        return self in {DType.F16, DType.BF16, DType.F32, DType.F64}

    @property
    def is_int(self) -> bool:
        return self in {DType.I32, DType.I64}


class KernelBackend(str, Enum):
    AUTO = "auto"
    PYTHON = "python"
    TORCH = "torch"
    TRITON = "triton"
    TILELANG = "tilelang"
    CANN = "cann"


@dataclass(frozen=True)
class LayoutSpec:
    order: tuple[int, ...] | None = None
    tile: tuple[int, ...] | None = None
    contiguous: bool = True
    name: str | None = None


@dataclass(frozen=True)
class TensorSpec:
    shape: Shape = ()
    dtype: DType = DType.F32
    layout: LayoutSpec = field(default_factory=LayoutSpec)

    def replace(
        self,
        *,
        shape: Shape | None = None,
        dtype: DType | None = None,
        layout: LayoutSpec | None = None,
    ) -> TensorSpec:
        return TensorSpec(
            shape=self.shape if shape is None else tuple(shape),
            dtype=self.dtype if dtype is None else dtype,
            layout=self.layout if layout is None else layout,
        )


@dataclass(frozen=True)
class KernelHint:
    backend: KernelBackend
    name: str | None = None
    block: tuple[int, ...] | None = None
    num_warps: int | None = None
    num_stages: int | None = None
    shared_bytes: int | None = None
    meta: Mapping[str, Any] = field(default_factory=dict)


@dataclass(eq=False, frozen=True)
class UOp:
    op: Ops
    spec: TensorSpec = field(default_factory=TensorSpec)
    src: tuple[UOp, ...] = ()
    arg: Any = None
    name: str | None = None
    hint: KernelHint | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "src", tuple(self.src))

    def __repr__(self) -> str:
        name = f", name={self.name!r}" if self.name else ""
        arg = f", arg={self.arg!r}" if self.arg is not None else ""
        hint = f", hint={self.hint.backend.value}" if self.hint else ""
        return f"UOp({self.op.name}, shape={self.spec.shape}, dtype={self.spec.dtype.value}{name}{arg}{hint})"

    def argstr(self) -> str:
        return f", arg={self.arg!r}" if self.arg is not None else ""

    def tagstr(self) -> str:
        tags: list[str] = []
        if self.name is not None:
            tags.append(f"name={self.name!r}")
        if self.hint is not None:
            hint_name = f":{self.hint.name}" if self.hint.name else ""
            tags.append(f"hint={self.hint.backend.value}{hint_name}")
        return f", {', '.join(tags)}" if tags else ""

    def pretty(self) -> str:
        return pretty_print(self)

    def replace(self, **kwargs: Any) -> UOp:
        values = {
            "op": self.op,
            "spec": self.spec,
            "src": self.src,
            "arg": self.arg,
            "name": self.name,
            "hint": self.hint,
        }
        values.update(kwargs)
        return UOp(**values)

    def with_name(self, name: str) -> UOp:
        return self.replace(name=name)

    def with_hint(self, hint: KernelHint | None = None, **kwargs: Any) -> UOp:
        if hint is None:
            backend = kwargs.pop("backend", KernelBackend.TRITON)
            hint = KernelHint(backend=backend, **kwargs)
        return self.replace(hint=hint)

    def toposort(self) -> list[UOp]:
        seen: set[UOp] = set()
        ordered: list[UOp] = []

        def visit(node: UOp) -> None:
            if node in seen:
                return
            seen.add(node)
            for child in node.src:
                visit(child)
            ordered.append(node)

        visit(self)
        return ordered

    def walk(self) -> Iterable[UOp]:
        return iter(self.toposort())

    def f(
        self,
        op: Ops,
        *src: UOp,
        spec: TensorSpec | None = None,
        arg: Any = None,
        name: str | None = None,
        hint: KernelHint | None = None,
    ) -> UOp:
        return UOp(
            op=op,
            spec=self.spec if spec is None else spec,
            src=(self, *src),
            arg=arg,
            name=name,
            hint=hint,
        )

    def cast(self, dtype: DType) -> UOp:
        return self.f(Ops.CAST, spec=self.spec.replace(dtype=dtype), arg=dtype.value)

    def reshape(self, *shape: ShapeDim) -> UOp:
        return self.f(Ops.RESHAPE, spec=self.spec.replace(shape=tuple(shape)), arg=tuple(shape))

    def permute(self, *order: int) -> UOp:
        shape = tuple(self.spec.shape[i] for i in order) if self.spec.shape else ()
        return self.f(Ops.PERMUTE, spec=self.spec.replace(shape=shape), arg=tuple(order))

    def expand(self, *shape: ShapeDim) -> UOp:
        return self.f(Ops.EXPAND, spec=self.spec.replace(shape=tuple(shape)), arg=tuple(shape))

    def contiguous(self) -> UOp:
        return self.f(Ops.CONTIGUOUS, spec=self.spec.replace(layout=LayoutSpec()))

    def to_layout(self, layout: LayoutSpec) -> UOp:
        return self.f(Ops.TO_LAYOUT, spec=self.spec.replace(layout=layout), arg=layout)

    def patchify(self, patch_size: int) -> UOp:
        if len(self.spec.shape) != 4:
            raise ValueError(f"patchify expects NCHW rank-4 input, got {self.spec.shape}")
        batch, channels, height, width = self.spec.shape
        tokens_h = height // patch_size if isinstance(height, int) else f"{height}//{patch_size}"
        tokens_w = width // patch_size if isinstance(width, int) else f"{width}//{patch_size}"
        tokens = tokens_h * tokens_w if isinstance(tokens_h, int) and isinstance(tokens_w, int) else f"({tokens_h})*({tokens_w})"
        patch_dim = channels * patch_size * patch_size if isinstance(channels, int) else f"{channels}*{patch_size}*{patch_size}"
        return self.f(
            Ops.PATCHIFY,
            spec=self.spec.replace(shape=(batch, tokens, patch_dim)),
            arg={"patch_size": patch_size},
        )

    def unpatchify(self, *, channels: ShapeDim, height: ShapeDim, width: ShapeDim, patch_size: int) -> UOp:
        batch = self.spec.shape[0] if self.spec.shape else "B"
        return self.f(
            Ops.UNPATCHIFY,
            spec=self.spec.replace(shape=(batch, channels, height, width)),
            arg={"channels": channels, "height": height, "width": width, "patch_size": patch_size},
        )

    def slice(self, slices: tuple[slice | int, ...]) -> UOp:
        return self.f(Ops.SLICE, arg=slices)

    def unary(self, op: Ops, *, arg: Any = None) -> UOp:
        if op not in GroupOp.Unary:
            raise ValueError(f"{op} is not a unary op")
        return self.f(op, arg=arg)

    def binary(self, op: Ops, other: UOp | int | float | bool) -> UOp:
        if op not in GroupOp.Binary:
            raise ValueError(f"{op} is not a binary op")
        rhs = ensure_uop(other, dtype=self.spec.dtype)
        dtype = DType.BOOL if op in GroupOp.Compare else promote_dtype(self.spec.dtype, rhs.spec.dtype)
        shape = broadcast_shape(self.spec.shape, rhs.spec.shape)
        return UOp(op=op, spec=TensorSpec(shape=shape, dtype=dtype), src=(self, rhs))

    def reduce(self, op: Ops, axis: int | tuple[int, ...], keepdim: bool = False) -> UOp:
        if op not in GroupOp.Reduce:
            raise ValueError(f"{op} is not a reduce op")
        axes = (axis,) if isinstance(axis, int) else tuple(axis)
        shape = reduce_shape(self.spec.shape, axes, keepdim)
        return self.f(op, spec=self.spec.replace(shape=shape), arg={"axis": axes, "keepdim": keepdim})

    def sum(self, axis: int | tuple[int, ...], keepdim: bool = False) -> UOp:
        return self.reduce(Ops.SUM, axis, keepdim)

    def mean(self, axis: int | tuple[int, ...], keepdim: bool = False) -> UOp:
        return self.reduce(Ops.MEAN, axis, keepdim)

    def max(self, axis: int | tuple[int, ...], keepdim: bool = False) -> UOp:
        return self.reduce(Ops.REDUCE_MAX, axis, keepdim)

    def softmax(self, axis: int = -1) -> UOp:
        return self.f(Ops.SOFTMAX, arg={"axis": axis})

    def matmul(self, rhs: UOp, *, out_dtype: DType | None = None, hint: KernelHint | None = None) -> UOp:
        shape = matmul_shape(self.spec.shape, rhs.spec.shape)
        dtype = out_dtype or promote_dtype(self.spec.dtype, rhs.spec.dtype)
        return UOp(Ops.MATMUL, TensorSpec(shape=shape, dtype=dtype), (self, rhs), hint=hint)

    def linear(self, weight: UOp, bias: UOp | None = None, *, hint: KernelHint | None = None) -> UOp:
        src = (self, weight) if bias is None else (self, weight, bias)
        out_features = weight.spec.shape[0] if len(weight.spec.shape) >= 2 else "out"
        shape = (*self.spec.shape[:-1], out_features)
        dtype = promote_dtype(self.spec.dtype, weight.spec.dtype)
        return UOp(Ops.LINEAR, TensorSpec(shape=shape, dtype=dtype), src, hint=hint)

    def layernorm(self, weight: UOp | None = None, bias: UOp | None = None, eps: float = 1e-6) -> UOp:
        src = tuple(x for x in (self, weight, bias) if x is not None)
        return UOp(Ops.LAYERNORM, self.spec, src, arg={"eps": eps})

    def rmsnorm(self, weight: UOp | None = None, eps: float = 1e-6) -> UOp:
        src = (self,) if weight is None else (self, weight)
        return UOp(Ops.RMSNORM, self.spec, src, arg={"eps": eps})

    def gelu(self, approximate: str = "tanh") -> UOp:
        return self.f(Ops.GELU, arg={"approximate": approximate})

    def silu(self) -> UOp:
        return self.f(Ops.SILU)

    def modulate(self, shift: UOp, scale: UOp) -> UOp:
        return UOp(Ops.MODULATE, self.spec, (self, shift, scale))

    def ada_ln(self, shift: UOp, scale: UOp, gate: UOp | None = None, eps: float = 1e-6) -> UOp:
        src = (self, shift, scale) if gate is None else (self, shift, scale, gate)
        return UOp(Ops.ADA_LN, self.spec, src, arg={"eps": eps})

    def rope(self, freqs: UOp, *, rotary_dim: int | None = None) -> UOp:
        return UOp(Ops.ROPE, self.spec, (self, freqs), arg={"rotary_dim": rotary_dim})

    def attention(
        self,
        key: UOp,
        value: UOp,
        mask: UOp | None = None,
        *,
        causal: bool = False,
        scale: float | None = None,
        hint: KernelHint | None = None,
    ) -> UOp:
        src = (self, key, value) if mask is None else (self, key, value, mask)
        op = Ops.FLASH_ATTENTION if hint and hint.backend in {KernelBackend.TRITON, KernelBackend.TILELANG} else Ops.ATTENTION
        shape = (*self.spec.shape[:-1], value.spec.shape[-1]) if self.spec.shape and value.spec.shape else self.spec.shape
        return UOp(op, self.spec.replace(shape=shape), src, arg={"causal": causal, "scale": scale}, hint=hint)

    def __neg__(self) -> UOp:
        return self.unary(Ops.NEG)

    def __add__(self, other: UOp | int | float | bool) -> UOp:
        return self.binary(Ops.ADD, other)

    def __radd__(self, other: UOp | int | float | bool) -> UOp:
        return ensure_uop(other, dtype=self.spec.dtype).binary(Ops.ADD, self)

    def __sub__(self, other: UOp | int | float | bool) -> UOp:
        return self.binary(Ops.SUB, other)

    def __rsub__(self, other: UOp | int | float | bool) -> UOp:
        return ensure_uop(other, dtype=self.spec.dtype).binary(Ops.SUB, self)

    def __mul__(self, other: UOp | int | float | bool) -> UOp:
        return self.binary(Ops.MUL, other)

    def __rmul__(self, other: UOp | int | float | bool) -> UOp:
        return ensure_uop(other, dtype=self.spec.dtype).binary(Ops.MUL, self)

    def __truediv__(self, other: UOp | int | float | bool) -> UOp:
        return self.binary(Ops.DIV, other)

    def __rtruediv__(self, other: UOp | int | float | bool) -> UOp:
        return ensure_uop(other, dtype=self.spec.dtype).binary(Ops.DIV, self)


@dataclass(frozen=True)
class UPat:
    op: Ops | set[Ops] | None = None
    name: str | None = None
    src: tuple[UPat, ...] | None = None
    predicate: Callable[[UOp], bool] | None = None

    def match(self, node: UOp, captures: dict[str, UOp] | None = None) -> dict[str, UOp] | None:
        captures = {} if captures is None else dict(captures)
        if self.op is not None:
            allowed = self.op if isinstance(self.op, set) else {self.op}
            if node.op not in allowed:
                return None
        if self.predicate is not None and not self.predicate(node):
            return None
        if self.name is not None:
            existing = captures.get(self.name)
            if existing is not None and existing is not node:
                return None
            captures[self.name] = node
        if self.src is not None:
            if len(self.src) != len(node.src):
                return None
            for pat, child in zip(self.src, node.src):
                captures = pat.match(child, captures)
                if captures is None:
                    return None
        return captures


@dataclass(frozen=True)
class RewriteRule:
    pattern: UPat
    rewrite: Callable[..., UOp | None]
    name: str | None = None

    def apply(self, node: UOp) -> UOp | None:
        captures = self.pattern.match(node)
        if captures is None:
            return None
        return self.rewrite(**captures)


class GraphRewriter:
    def __init__(self, rules: Iterable[RewriteRule] = ()) -> None:
        self.rules = tuple(rules)

    def rewrite(self, root: UOp) -> UOp:
        cache: dict[UOp, UOp] = {}

        def visit(node: UOp) -> UOp:
            if node in cache:
                return cache[node]
            new_src = tuple(visit(child) for child in node.src)
            current = node.replace(src=new_src) if new_src != node.src else node
            for rule in self.rules:
                rewritten = rule.apply(current)
                if rewritten is not None and rewritten is not current:
                    current = visit(rewritten)
                    break
            cache[node] = current
            return current

        return visit(root)


def pretty_print(x: UOp, cache: dict[UOp, list[Any]] | None = None, d: int = 0) -> str:
    def dfs(node: UOp, seen: dict[UOp, list[Any]]) -> None:
        for child in node.src:
            seen.setdefault(child, [len(seen), 0, False])[1] += 1
            if seen[child][1] == 1:
                dfs(child, seen)

    if cache is None:
        cache = {}
        dfs(x, cache)

    cx = cache.setdefault(x, [len(cache), 0, False])
    if cx[2]:
        return f"{' ' * d}x{cx[0]}"

    cx[2] = True
    srcs = "".join(f"\n{pretty_print(child, cache, d + 2)}," for child in x.src)
    label = f"x{cx[0]}:=" if cx[1] > 1 else ""
    return (
        f"{' ' * d}{label}UOp({x.op.name}, shape={x.spec.shape}, "
        f"dtype={x.spec.dtype.value}{x.argstr()}{x.tagstr()}, src=({srcs}))"
    )


def placeholder(name: str, shape: Shape, dtype: DType = DType.F32, layout: LayoutSpec | None = None) -> UOp:
    return UOp(
        Ops.PARAM,
        TensorSpec(shape=tuple(shape), dtype=dtype, layout=layout or LayoutSpec()),
        name=name,
    )


def param(name: str, shape: Shape, dtype: DType = DType.F32) -> UOp:
    return placeholder(name=name, shape=shape, dtype=dtype)


def buffer(name: str, shape: Shape, dtype: DType = DType.F32, layout: LayoutSpec | None = None) -> UOp:
    return UOp(
        Ops.BUFFER,
        TensorSpec(shape=tuple(shape), dtype=dtype, layout=layout or LayoutSpec()),
        name=name,
    )


def const(value: int | float | bool, dtype: DType | None = None) -> UOp:
    if dtype is None:
        if isinstance(value, bool):
            dtype = DType.BOOL
        elif isinstance(value, int):
            dtype = DType.I64
        else:
            dtype = DType.F32
    return UOp(Ops.CONST, TensorSpec(dtype=dtype), arg=value)


def ensure_uop(value: UOp | int | float | bool, dtype: DType | None = None) -> UOp:
    return value if isinstance(value, UOp) else const(value, dtype=dtype)


def cat(values: Iterable[UOp], axis: int = -1) -> UOp:
    nodes = tuple(values)
    if not nodes:
        raise ValueError("cat requires at least one input")
    shape = list(nodes[0].spec.shape)
    axis = normalize_axis(axis, len(shape))
    if all(isinstance(x.spec.shape[axis], int) for x in nodes):
        shape[axis] = sum(int(x.spec.shape[axis]) for x in nodes)
    else:
        shape[axis] = "+".join(str(x.spec.shape[axis]) for x in nodes)
    return UOp(Ops.CAT, nodes[0].spec.replace(shape=tuple(shape)), nodes, arg={"axis": axis})


def where(cond: UOp, true_value: UOp | int | float | bool, false_value: UOp | int | float | bool) -> UOp:
    tv = ensure_uop(true_value)
    fv = ensure_uop(false_value, dtype=tv.spec.dtype)
    shape = broadcast_shape(cond.spec.shape, tv.spec.shape, fv.spec.shape)
    dtype = promote_dtype(tv.spec.dtype, fv.spec.dtype)
    return UOp(Ops.WHERE, TensorSpec(shape=shape, dtype=dtype), (cond, tv, fv))


def triton_hint(name: str | None = None, **meta: Any) -> KernelHint:
    return KernelHint(backend=KernelBackend.TRITON, name=name, meta=meta)


def tilelang_hint(name: str | None = None, **meta: Any) -> KernelHint:
    return KernelHint(backend=KernelBackend.TILELANG, name=name, meta=meta)


def custom_kernel(
    name: str,
    src: Iterable[UOp],
    spec: TensorSpec,
    *,
    backend: KernelBackend,
    meta: Mapping[str, Any] | None = None,
) -> UOp:
    if backend is KernelBackend.TRITON:
        op = Ops.TRITON_KERNEL
    elif backend is KernelBackend.TILELANG:
        op = Ops.TILELANG_KERNEL
    else:
        op = Ops.KERNEL
    return UOp(op, spec, tuple(src), name=name, hint=KernelHint(backend=backend, name=name, meta=meta or {}))


def promote_dtype(lhs: DType, rhs: DType) -> DType:
    order = [DType.BOOL, DType.I32, DType.I64, DType.F16, DType.BF16, DType.F32, DType.F64]
    return order[max(order.index(lhs), order.index(rhs))]


def normalize_axis(axis: int, rank: int) -> int:
    axis = axis + rank if axis < 0 else axis
    if axis < 0 or axis >= rank:
        raise ValueError(f"axis={axis} out of range for rank={rank}")
    return axis


def broadcast_shape(*shapes: Shape) -> Shape:
    shapes = tuple(tuple(s) for s in shapes if s != ())
    if not shapes:
        return ()
    rank = max(len(s) for s in shapes)
    padded = [((1,) * (rank - len(s)) + s) for s in shapes]
    return tuple(reduce(broadcast_dim, dims) for dims in zip(*padded))


def broadcast_dim(lhs: ShapeDim, rhs: ShapeDim) -> ShapeDim:
    if lhs == 1:
        return rhs
    if rhs == 1:
        return lhs
    if lhs == rhs:
        return lhs
    if isinstance(lhs, int) and isinstance(rhs, int):
        raise ValueError(f"cannot broadcast dimensions {lhs} and {rhs}")
    return f"max({lhs},{rhs})"


def reduce_shape(shape: Shape, axes: tuple[int, ...], keepdim: bool) -> Shape:
    rank = len(shape)
    norm_axes = {normalize_axis(axis, rank) for axis in axes}
    if keepdim:
        return tuple(1 if i in norm_axes else dim for i, dim in enumerate(shape))
    return tuple(dim for i, dim in enumerate(shape) if i not in norm_axes)


def matmul_shape(lhs: Shape, rhs: Shape) -> Shape:
    if len(lhs) < 2 or len(rhs) < 2:
        raise ValueError(f"matmul requires rank >= 2, got {lhs} and {rhs}")
    batch = broadcast_shape(lhs[:-2], rhs[:-2])
    return (*batch, lhs[-2], rhs[-1])


__all__ = [
    "DType",
    "FastEnum",
    "GraphRewriter",
    "GroupOp",
    "KernelBackend",
    "KernelHint",
    "LayoutSpec",
    "Ops",
    "RewriteRule",
    "Shape",
    "ShapeDim",
    "TensorSpec",
    "UOp",
    "UPat",
    "buffer",
    "cat",
    "const",
    "custom_kernel",
    "ensure_uop",
    "param",
    "placeholder",
    "pretty_print",
    "tilelang_hint",
    "triton_hint",
    "where",
]
