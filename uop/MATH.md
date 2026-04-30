# Math Notes for UOp Operators

This note records the math contracts for the operators used by the Flux-oriented UOp graph.

The goal is to keep each operator's semantics clear before lowering it to Python, Torch, Triton, or Tile-Lang.

## Hot Operator References

These papers are useful anchors for the high-value operators in this project.

| Area | Operators | Paper |
| --- | --- | --- |
| Transformer attention | `ATTENTION`, `SOFTMAX`, `LINEAR` | Attention Is All You Need: https://arxiv.org/pdf/1706.03762 |
| IO-aware attention kernel | `FLASH_ATTENTION` | FlashAttention: https://arxiv.org/pdf/2205.14135 |
| Faster attention partitioning | `FLASH_ATTENTION` | FlashAttention-2: https://arxiv.org/pdf/2307.08691 |
| Rotary positional embedding | `ROPE` | RoFormer: https://arxiv.org/pdf/2104.09864 |
| Layer normalization | `LAYERNORM` | Layer Normalization: https://arxiv.org/pdf/1607.06450 |
| Root mean square normalization | `RMSNORM` | Root Mean Square Layer Normalization: https://arxiv.org/pdf/1910.07467 |
| GELU activation | `GELU` | Gaussian Error Linear Units: https://arxiv.org/pdf/1606.08415 |
| Convolution shape arithmetic | `CONV2D` | A guide to convolution arithmetic for deep learning: https://arxiv.org/pdf/1603.07285 |
| Diffusion transformer blocks | `PATCHIFY`, `ADA_LN`, `ATTENTION`, `LINEAR` | Scalable Diffusion Models with Transformers: https://arxiv.org/pdf/2212.09748 |

## Notation

- `X`, `Y`, `A`, `B`, `W`: tensors.
- `B`: batch size when used as a shape dimension.
- `T`: token count.
- `H`: hidden size, or image height when context is NCHW.
- `W_img`: image width.
- `C`: channel count.
- `eps`: small numerical stabilizer.
- `axis=-1`: usually the hidden/channel dimension.
- Broadcasting follows NumPy/PyTorch-style shape broadcasting.

## Elementwise Ops

For tensors with broadcast-compatible shapes:

```text
ADD:  Y = A + B
SUB:  Y = A - B
MUL:  Y = A * B
DIV:  Y = A / B
POW:  Y = A ** B
MAX:  Y = max(A, B)
MIN:  Y = min(A, B)
```

Unary ops:

```text
NEG:      Y = -X
EXP:      Y = exp(X)
LOG:      Y = log(X)
SQRT:     Y = sqrt(X)
RSQRT:    Y = 1 / sqrt(X)
RECIP:    Y = 1 / X
TANH:     Y = tanh(X)
SIGMOID:  Y = 1 / (1 + exp(-X))
RELU:     Y = max(X, 0)
SILU:     Y = X * sigmoid(X)
```

Approximate GELU, commonly used by transformer MLPs:

```text
GELU(x) = 0.5 * x * (1 + tanh(sqrt(2/pi) * (x + 0.044715 * x^3)))
```

## Reductions

For reducing tensor `X` along axis set `R`:

```text
SUM:        Y = sum(X, axis=R)
MEAN:       Y = mean(X, axis=R)
REDUCE_MAX: Y = max(X, axis=R)
VAR:        Y = mean((X - mean(X, axis=R))^2, axis=R)
```

Softmax over an axis, usually the attention key axis:

```text
softmax(X)_i = exp(X_i - max(X)) / sum_j exp(X_j - max(X))
```

The `max(X)` subtraction is part of the numerical stability contract.

## MATMUL

For rank-2 tensors:

```text
C = A @ B
C[i, j] = sum_k A[i, k] * B[k, j]
```

For batched tensors:

```text
A: [..., M, K]
B: [..., K, N]
C: [..., M, N]

C[..., i, j] = sum_k A[..., i, k] * B[..., k, j]
```

The leading batch dimensions may broadcast.

## LINEAR

Linear is matrix multiplication with an optional bias.

Common model weight layout:

```text
X: [B, T, in_features]
W: [out_features, in_features]
b: [out_features]
Y: [B, T, out_features]
```

Math:

```text
Y[b, t, o] = sum_i X[b, t, i] * W[o, i] + b[o]
```

Without bias:

```text
Y[b, t, o] = sum_i X[b, t, i] * W[o, i]
```

Equivalent compact form:

```text
Y = X @ W^T + b
```

## CONV2D

The default contract is NCHW input and OIHW kernel.

```text
X: [N, C_in, H, W_img]
K: [C_out, C_in, R, S]
Y: [N, C_out, H_out, W_out]
```

Math:

```text
Y[n, co, h, w] =
  sum_ci sum_r sum_s
    X[n, ci, h * stride_h + r * dilation_h - pad_h,
             w * stride_w + s * dilation_w - pad_w]
    * K[co, ci, r, s]
```

With bias:

```text
Y[n, co, h, w] = Y[n, co, h, w] + bias[co]
```

Output size:

```text
H_out = floor((H + 2 * pad_h - dilation_h * (R - 1) - 1) / stride_h) + 1
W_out = floor((W_img + 2 * pad_w - dilation_w * (S - 1) - 1) / stride_w) + 1
```

## LAYERNORM

For hidden-dimension layer norm:

```text
X: [B, T, H]
gamma: [H]
beta: [H]
```

Mean:

```text
mu[b, t] = (1 / H) * sum_i X[b, t, i]
```

Variance:

```text
var[b, t] = (1 / H) * sum_i (X[b, t, i] - mu[b, t])^2
```

Normalize:

```text
X_hat[b, t, i] = (X[b, t, i] - mu[b, t]) / sqrt(var[b, t] + eps)
```

Affine:

```text
Y[b, t, i] = X_hat[b, t, i] * gamma[i] + beta[i]
```

## RMSNORM

RMSNorm does not subtract the mean. It normalizes by root mean square.

```text
X: [B, T, H]
gamma: [H]
```

RMS:

```text
rms[b, t] = sqrt((1 / H) * sum_i X[b, t, i]^2 + eps)
```

Normalize:

```text
X_hat[b, t, i] = X[b, t, i] / rms[b, t]
```

Affine:

```text
Y[b, t, i] = X_hat[b, t, i] * gamma[i]
```

Compact form:

```text
Y = X * rsqrt(mean(X^2, axis=-1, keepdim=True) + eps) * gamma
```

## PATCHIFY

For image latents in NCHW format:

```text
X: [B, C, H, W_img]
patch_size: P
```

Patch count:

```text
T_img = (H / P) * (W_img / P)
patch_dim = C * P * P
```

Output:

```text
Y: [B, T_img, patch_dim]
```

Each token is a flattened `C x P x P` patch.

## UNPATCHIFY

Inverse of patchify:

```text
X: [B, T_img, C * P * P]
Y: [B, C, H, W_img]
```

`T_img` must match:

```text
T_img = (H / P) * (W_img / P)
```

## ROPE

Rotary positional embedding rotates pairs of hidden dimensions.

For each 2D pair:

```text
x_even = x[2i]
x_odd  = x[2i + 1]
theta  = position_angle[i]
```

Rotation:

```text
y_even = x_even * cos(theta) - x_odd * sin(theta)
y_odd  = x_even * sin(theta) + x_odd * cos(theta)
```

In attention, RoPE is usually applied to `q` and `k`, not `v`.

## ATTENTION

Scaled dot-product attention:

```text
Q: [B, heads, T_q, D]
K: [B, heads, T_k, D]
V: [B, heads, T_k, D_v]
```

Scores:

```text
S[b, h, i, j] = sum_d Q[b, h, i, d] * K[b, h, j, d] * scale
```

Default scale:

```text
scale = 1 / sqrt(D)
```

Masking, if present:

```text
S = S + mask
```

Weights:

```text
P = softmax(S, axis=-1)
```

Output:

```text
O[b, h, i, d] = sum_j P[b, h, i, j] * V[b, h, j, d]
```

Shape:

```text
O: [B, heads, T_q, D_v]
```

`FLASH_ATTENTION` should preserve this same math contract while changing the execution strategy.

## MODULATE

Common transformer conditioning modulation:

```text
Y = X * (1 + scale) + shift
```

Typical shapes:

```text
X:     [B, T, H]
shift: [B, H] or [B, 1, H]
scale: [B, H] or [B, 1, H]
```

Broadcasting applies along token dimension.

## ADA_LN

Adaptive layer norm combines normalization and conditioning modulation.

One useful contract:

```text
N = layernorm(X, eps)
Y = N * (1 + scale) + shift
```

With gate:

```text
Y_gated = Y * gate
```

Typical Flux/DiT residual usage:

```text
hidden = hidden + block(ada_ln(hidden, shift, scale)) * gate
```

The exact placement of `gate` can vary by model variant; the UOp node should keep `gate` explicit so lowering can preserve the chosen contract.
