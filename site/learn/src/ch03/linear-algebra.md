# Arrays and Linear Algebra

> **Unpublished design draft:** This page is retained as source material for a future linear-algebra guide. The general shape annotation, multidimensional literal, axis-selection, broadcasting, and matrix-overload rules are being designed together, so its examples illustrate direction rather than settled syntax.

Dewy uses arrays as the foundation for vectors, matrices, and tensors rather than requiring unrelated container classes for each rank.

<!-- dewy-example: design-only -->
```dewy
let vector = [1 2 3]
let matrix = [
    1 2
    3 4
]
```

## Shape Is Type Information

A matrix is an array whose type carries a two-dimensional shape. Shape facts support bounds checking, operator selection, specialization, and contiguous storage without making those representation choices visible in ordinary code.

Nested arrays remain meaningful values in their own right. A nested `array<array<T>>` must not prevent a separate contiguous representation for an array with multidimensional shape.

## Multiplication and Elementwise Operations

`*` selects the conventional linear-algebra operation when array shapes make that contract applicable. A leading `.` requests elementwise application:

<!-- dewy-example: design-only -->
```dewy
let product = left * right
let pairwise = left .* right
let shifted = matrix .+ 10
```

Broadcasting aligns compatible dimensions while preserving explicit shape rules. A scalar can broadcast across every element; singleton dimensions can expand along a corresponding dimension.

<!-- dewy-example: design-only -->
```dewy
let values = [
    1 2 3
    4 5 6
]

values .+ [10 100 1000]
```

## Indexing and Slicing

Indexes and ranges select positions or spans along axes. `end` refers to the final index of the selected axis.

<!-- dewy-example: design-only -->
```dewy
matrix[0 1]
matrix[1..end]
```

## Constructing Results

Loops naturally express array elements and nested dimensions:

<!-- dewy-example: design-only -->
```dewy
let multiplication_table = [
    loop row in 1..3
        [loop column in 1..3
            row * column]
]
```

For ordinary one-dimensional behavior, see [Containers](container-types.md). Physical dimensions such as meters and seconds are independent of array dimensions; see [Physical Quantities and Units](units.md).
