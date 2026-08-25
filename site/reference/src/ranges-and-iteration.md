# Ranges and Iteration

## Range Forms

A range contains `..`. Endpoints immediately juxtaposed with `..` supply its anchors:

```dewy
first..last
first..
..last
..
```

Square and round boundaries independently include or exclude an endpoint:

```dewy
[first..last]
[first..last)
(first..last]
(first..last)
```

An unbracketed `first..last` includes both endpoints.

A first pair determines a step:

```dewy
1,3..9       # 1 3 5 7 9
5,4..0       # 5 4 3 2 1 0
```

The step is `second - first` and cannot be zero. A descending range requires a negative step; `5..0` is empty rather than implicitly descending.

## Iterability

A range with a first element may be consumed from that element onward. A left-unbounded range is a valid range value but cannot be iterated because it has no starting value.

Right-unbounded iteration continues until surrounding control flow or a finite companion iterator stops it.

## Membership

`value in? range` tests whether the value belongs to the range, respecting open bounds and step alignment. Each runtime operand is evaluated once.

## Sequence Slices

A range used as an index selects a slice. `end` refers to the last valid index of the selected axis:

```dewy
text[3..12)
values[..end-1]
matrix[row][1..end]
```

## Iterator Conditions

In a loop condition, `name in iterable` requests the next value, binds it to `name`, and reports whether a value was produced:

```dewy
loop item in items
    process(item)
```

Iterator clauses may be combined with Boolean operators. Leaves advance from left to right once per condition evaluation:

```dewy
loop index in 0.. and item in items
    printl"{index}: {item}"
```

For `and`, iteration ends when a required leaf is exhausted. Operators such as `or` may allow one leaf to continue after another is exhausted; an exhausted leaf's bound value is then optional.

The exact truth and exhaustion formulas for `and`, `or`, `xor`, `nand`, `nor`, and `xnor` follow their Boolean meanings applied to the per-leaf step results.

## Provisional Boundaries

The following remain under design:

- advancement and short-circuit behavior when iterator clauses mix with ordinary Boolean predicates;
- stored generators and some dynamic iterator sources; and
- result types, normalization, empty-span behavior, and representation for arbitrary runtime range arithmetic.

See [Design Maturity and Open Questions](design-status.md).
