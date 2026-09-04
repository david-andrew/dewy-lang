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

- ~~advancement and short-circuit behavior when iterator clauses mix with ordinary Boolean predicates~~ (settled, see below);
- stored generators and some dynamic iterator sources; and
- result types, normalization, empty-span behavior, and representation for arbitrary runtime range arithmetic.

See [Design Maturity and Open Questions](design-status.md).

## Iterators with Boolean Predicates

A loop condition may join iterator clauses and ordinary Boolean predicates with `and`. The iterators advance first, then the predicates are tested with the targets bound; the loop ends at the first false predicate, and inside the body the predicates are known to hold — so `i <? src.length` proves the index in `src[i]`:

<!-- dewy-example: compiler -->
```dewy
const whitespace = set[' ' '\t' '\n' '\r']
leading = (src:string):>int64 => {
    let n:int64 = 0
    loop i in 0.. and i <? src.length and src[i] in? whitespace { n += 1 }
    return n
}
```

`loop x in xs and x <? 4 { … }` visits the prefix of `xs` below 4 (it stops at the first element that fails, it does not filter — put an `if` in the body to filter). Predicates may sit anywhere in the chain; only word-`and` joins them to the iterators, and `or`/`xor` chains stay multiiterator formulas.

## Runtime Range Ends

A loop range's end may be a runtime value: `loop i in [0..argv.length)` visits each index, and the bare `loop i in 0..n` includes `n` (ranges are inclusive unless the bracket says otherwise). The end becomes a per-iteration guard on an open counter, so it composes with the mixed conditions above and bounds the counter the same way. A runtime *start* still needs the general runtime range representation.

In a dictionary loop the value target may unpack an object element by field name: `loop [prefix [digits case_insensitive extra]] in BASE_SPECS` declares each name as a copy of the field of that name (any subset, in any order).
