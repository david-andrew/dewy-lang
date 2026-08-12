Optimizations and semantic contracts in Dewy.
> In no specified order

## inferred integer width
unless a width is specified, all integers behave as if they have arbitrary precision
e.g.
```
x:int = 20     # x:bigint = 20
y = 10         # y:bigint = 10
Z:uint32 = 30  # z:uint32 = 30
```

There shall be an optimization pass that analyzes the possible range any given variable could take on, and when that range fits within a fixed width size, the compiler will make use of that fixed-width int instead of the more general bigint.

> note that explicitly annotated int widths will rollover and behave as that width. the semantic contract is anything else not explicitly specified will behave as if it was infinite precision, even if that precision was not needed under the hood
> For udewy, use of `int` is unidiomatic and will produce not-well-formed code (since all udewy ints are 64-bits wide). Idiomatic udewy will explicitly annotate the width for integer types

## Multiiterator fusion and scalar replacement

Semantic contract: every iterator leaf advances eagerly, left-to-right, exactly
once per condition evaluation. Exhausted leaves assign `undefined`, contribute
`false`, and the complete logical formula retains its literal truth table after
all leaves are exhausted.

Correct baseline: lower each leaf to its own offset, active flag, and target
storage, then evaluate the source formula from all active flags.

Deferred lowering: fuse static range compositions into directly mutated
counters and a simplified exit condition. Constant trip counts can eliminate
unnecessary active flags, `undefined` writes and tags, and dead iterator
targets.

Proof required: the replacement must preserve source-order effects, one advance
per leaf per evaluation, target values observed by the body, `continue`
behavior, and all-exhausted truth-table behavior.

## Optional layout niches

Semantic contract: `T | undefined` preserves every value of `T`, has a distinct
`undefined` state, and uses value semantics for assignment and parameter
binding.

Correct baseline: represent an optional as a defined tag plus one aligned
payload slot.

Deferred lowering: use a spare representation as the undefined niche. Possible
cases include packing a narrow integer and tag into one 64-bit value, using a
third Boolean state, or using a proven-invalid pointer representation.

Proof required: the selected niche cannot be any value permitted by the payload
type, including after rollover, transmutation, or future representation
changes.

## Optional ABI specialization

Semantic contract: optional arguments are copied into callee-local storage and
optional results have caller-owned lifetime. Calls do not expose mutable
optional-cell aliasing or return pointers to expired stack cells.

Correct baseline: pass optional cells by pointer, copy their tag and payload at
parameter binding, and return optionals through a hidden caller-owned result
cell.

Deferred lowering: specialize direct calls, scalar-replace non-escaping cells,
pass tag and payload in ordinary parameters or result registers, and elide
copies when non-aliasing value semantics are proven.

Proof required: whole-call provenance and escape analysis must show that each
removed allocation or copy is unobservable and that result storage outlives
every use.