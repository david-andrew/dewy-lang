# Linear Algebra

Dewy does not have a separate vector or matrix type. An array is the container; vector, matrix, and tensor are shapes of that array.

```dewy
v = [1 2 3]
A = [
    1 2
    3 4
]
B = [0 1 ; 1 0]
```

Whitespace separates elements. A semicolon or a newline starts a new dimension.

## Multiplication and Broadcasting

Writing arrays next to each other, or using `*`, multiplies them by the usual linear-algebra rules when the shapes allow it.

```dewy
C = A * B
scaled = 2A
```

Elementwise work uses `.`:

```dewy
A .+ B
A .* B
20 .% primes
```

A leading `.` on almost any infix operator broadcasts it. Both operands must have broadcastable shapes.

Broadcasting lets you combine arrays of different dimensions by broadcasting singleton dimensions in one over corresponding dimensions in the other

```dewy

A = [
    1 2 3
    4 5 6
]

# scalar addition
A .+ 10
# result = [
#    11 12 13
#    14 15 16
# ]


# broadcast
A .+ [10 100 1000]
# result = [
#     11 102 1003
#     14 105 1006
# ]

# broadcast along the other dimension requires an extra dimension
A .+ [[10 20]]   # or A .+ [10 20][... new]
# result = [
#     11 12 13
#     24 25 26
# ]
```

(TODO: describe broadcasting rules better (basically numpy))

## Indexing and Slices

Ranges index any dimension. `end` is the last index of that axis.

```dewy
A[0 1]                 # row 0, column 1
A[1..5]                # rows 1-5
A[2 [0..4) ... end-3]  # row 2, cols 0-3, all inner dims, 3rd from last of last dim
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
