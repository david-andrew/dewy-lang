# Arrays, objects, and strings

Assignment, passing, and return copy arrays and objects. `@x` is the place `x` lives. A function writes the caller's value only when both the parameter and the argument are places.

```dewy
let a = [1 2 3]
let b = a
b[0] = 9                    # a is still [1 2 3]

update = (@xs:array<int64>) => { xs[0] = 9 }
update(@a)                  # a is now [9 2 3]
update(a)                   # error: expected a place
```

`@?` is true when two names are the same place, not when two copies still share storage. Function handles use the same `@`; see [Functions and calls](functions-and-calls.md).

## Arrays

Implemented arrays are homogeneous. Exact-length arrays carry a length refinement, expose `.length`, and support constant or flow-proven indexing. Some non-escaping local literals and module constants lower directly to raw storage. General dynamic-length and escaping arrays remain incomplete.

## Objects

Object literals contain named fields in source order and have structural types. Fields can be read and mutated when the originating binding permits it. Function fields can read sibling fields, and zero-argument function fields are called by ordinary member access.

## Strings

Strings are immutable sequences of Unicode extended grapheme clusters. Length, indexing, slicing, iteration, exact equality, grapheme ranges, UTF-8 byte views, Unicode scalar views, and grapheme-array conversion are implemented. Equality currently preserves exact scalar spelling rather than normalizing text. Slice endpoints may be computed at runtime when flow-sensitive bounds analysis proves their effective open or closed boundaries stay within the string.
