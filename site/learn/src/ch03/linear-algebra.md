# Linear Algebra

Dewy does not have a separate vector or matrix type. An array is the
container; vector, matrix, and tensor are shapes of that array.

```dewy
v = [1 2 3]
A = [
    1 2
    3 4
]
B = [0 1 ; 1 0]
```

Whitespace separates elements. A semicolon starts a new dimension.

## Multiplication and Broadcasting

Writing arrays next to each other, or using `*`, multiplies them by the
usual linear-algebra rules when the shapes allow it.

```dewy
C = A * B
scaled = 2 A
```

Elementwise work uses `.`:

```dewy
A .+ B
A .* B
20 .% primes
```

A leading `.` on almost any infix operator broadcasts it. Both operands
may be arrays of the same shape, or one may be a scalar.

## Indexing and Slices

Ranges index any dimension. `end` is the last index of that axis.

```dewy
A[0 1]          # row 0, column 1
A[0..]          # remaining rows
row = A[1]
```

See [Ranges](range-types.md) and [Container Types](container-types.md).

## Building Arrays

Loops fill higher dimensions without a special list-building syntax.

```dewy
outer_product = [
    loop i in [1..3]
    [loop j in [1..3] i * j]
]
```
