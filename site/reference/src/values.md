# Values, Copies, and Places

## Value Semantics

Assignment, argument passing, and return supply an independent value. Mutating the destination cannot change the source merely because an implementation reused backing storage.

```dewy
let original = [1 2 3]
let copy = original
copy[0] = 9                  # original remains [1 2 3]
```

The compiler may realize that semantic copy through physical copying, a move, ownership transfer, borrowed reading, shared immutable storage, or another representation whose differences are unobservable.

Scalar, array, object, string, and container values all follow this rule. A field whose own type has explicit handle semantics retains those semantics when its containing value is copied.

## Places

`@` explicitly selects the place occupied by a mutable value. A parameter that accepts a place also carries `@`, making caller-visible mutation explicit at both boundaries:

<!-- dewy-example: compiler -->
```dewy
let update = (@xs:array<int64 length=3>):>void => {
    xs[0] = 9
}

let values = [1 2 3]
update(@values)
```

Passing `values` without `@` supplies an ordinary value. Passing `@values` to a non-place parameter is likewise a type error.

## Projected Routes

A leading `@` selects the place at the end of the complete field-and-index route:

```dewy
set(@pair.left)
set(@values[i])
set(@box.rows[row][column])
```

The parser groups `@pair.left` as `(@pair).left`, but the language does not expose `@pair` as a separate reference value before applying `.left`. The whole expression refers to the place occupied by `left`. `@(pair.left)` selects the same place, and there is no `pair.@left` form. A computed index in a place route evaluates once before the call.

## Type and Aliasing Rules

A mutable place is invariant in its value type: a callee must not reinterpret the caller's storage through a broader or narrower place contract.

Two mutable place arguments in one call must be proven disjoint. Sibling object fields and distinct constant indices are disjoint. Prefix-related routes overlap. Dynamic indices are potentially overlapping unless analysis proves otherwise.

A `const` binding does not provide a mutable place.

## Escaping Places and Identity

Nonescaping place calls have settled semantics. Storing or returning a place, sharing it across concurrent work, and defining lifetime-bearing place types require the provisional ownership and escape design.

The intended `@?` operation asks whether two place expressions designate the same semantic place. It does not expose unobservable storage sharing used to optimize independent values.

Function handles build on the same root-and-route interpretation of `@`; see [Functions and Calls](functions-and-calls.md#function-handles).
