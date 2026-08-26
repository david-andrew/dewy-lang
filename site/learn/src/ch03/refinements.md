# Refinements and Proven Facts

A refinement is a type together with facts its values must satisfy. Length is a familiar example:

```dewy
let triple:array<int64 length=3> = [10 20 30]
```

The type says more than “array of integers”; it also says that the valid shape has exactly three elements.

## Why Refinements Matter

Useful facts let Dewy reject invalid programs and remove unnecessary runtime work:

```dewy
let first = triple[0]
```

The index needs no dynamic bounds check because the type already proves it valid.

The same idea can describe nonempty containers, positive values, relationships between parameters and results, and state changes such as an operation reducing a collection's length by one.

## Writing Refinements

A parameterize block after a type may hold conditions. A one-argument lambda states a condition on the value itself; a `?`-comparison on `length` states one on a container:

<!-- dewy-example: compiler -->

```dewy
Positive = int< i=>i>?0 >
NonEmptyArray = array< length>?0 >

score:Positive = 42
values:NonEmptyArray<int> = [3 5 8]

first = values[0]
```

Conditions and parameters are told apart by their shape: a lambda, a `?`-comparison, or a `length=N` assignment is a condition; anything else is a parameter. `NonEmptyArray` leaves the element type open, so `NonEmptyArray<int>` supplies it later.

Checking a value against a refined type has three outcomes: **proven** (a literal or known fact establishes the condition, with no runtime cost), **refuted** (`score:Positive = -3` is an error), and **unknown**, which is reported as unproven rather than false. The binding then carries the base type plus the proven facts, so `values[0]` needs no runtime check.

## Facts from Ordinary Control Flow

Dewy should infer common refinements from the code programmers already write:

```dewy
if index >=? 0 and index <? values.length
    use(values[index])
```

Inside the body, the condition establishes the indexing precondition. Assignment or a call that may mutate a relevant value invalidates facts that are no longer guaranteed.

## Explicit Boundaries

The intended model distinguishes several outcomes:

- a fact the compiler proves automatically has no runtime cost;
- an explicit runtime check refines the value after it succeeds;
- a checked proof can discharge an obligation outside automatic inference;
- `unsafe` can assert an unproved obligation while making that trust boundary visible for review.

> **Provisional design:** Refined annotations on bindings, integer-literal comparisons, length facts, and interval reasoning are settled. Refined parameters and results, proofs of annotations from control flow, richer propositions, checked proof values, and the `unsafe` syntax are not fully specified. Unsupported general Dewy expressions must not silently become refinement claims.

The design goal is inference-first: ordinary code should expose enough facts for routine safety without requiring programmers to write proofs throughout application code.
