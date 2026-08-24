# Values, places, and containers

## Value semantics

Assignment, argument passing, and return give the destination an independent value. The compiler may avoid a physical copy when that cannot be observed, but ordinary source code does not create aliases accidentally.

```dewy
let a = [1 2 3]
let b = a
b[0] = 9                    # a is still [1 2 3]
```

## Places and projected routes

`@` explicitly selects storage rather than copying its value. For ordinary data, both the parameter and the call argument use `@`, making mutation visible on both sides of the call:

```dewy
update = (@xs:array<int64 length=3>) => { xs[0] = 9 }

update(@a)                  # a is now [9 2 3]
update(a)                   # error: expected a place
```

Selectors project a place along a route. Prefix precedence means `@pair.left` is `(@pair).left`: start at the place occupied by `pair`, then select the place occupied by `left`. Indexing follows the same rule, and routes can mix selectors:

```dewy
set(@pair.left)
set(@values[i])
set(@box.rows[row][column])

set(@(pair.left))           # equivalent, with explicit grouping
```

The place is the location at the end of the route, not just its first binding. There is no separate `pair.@left` form. Each computed index is evaluated once before the call.

The current compiler requires an explicitly typed place parameter and an exact type match. The root must be mutable, places cannot yet be stored or returned, and potentially overlapping mutable routes cannot be passed in one call. Sibling fields and distinct constant indices are known to be disjoint; dynamic indices are conservatively treated as possibly overlapping.

The planned `@?` operator asks whether two expressions identify the same place, not whether two independent values happen to share optimized backing storage. Function handles use the same root-and-route interpretation of `@`; see [Functions and calls](functions-and-calls.md).

## Arrays

Implemented arrays are homogeneous. Exact-length arrays carry a length refinement, expose `.length`, and support constant or flow-proven indexing. Some non-escaping local literals and module constants lower directly to raw storage. General dynamic-length and escaping arrays remain incomplete.

## Objects

Object literals contain named fields in source order and have structural types. Fields can be read and mutated when the originating binding permits it. Function fields can read sibling fields, and zero-argument function fields are called by ordinary member access.

## Strings

Strings are immutable sequences of Unicode extended grapheme clusters. Length, indexing, slicing, iteration, exact equality, grapheme ranges, UTF-8 byte views, Unicode scalar views, and grapheme-array conversion are implemented. Equality currently preserves exact scalar spelling rather than normalizing text. Slice endpoints may be computed at runtime when flow-sensitive bounds analysis proves their effective open or closed boundaries stay within the string.
