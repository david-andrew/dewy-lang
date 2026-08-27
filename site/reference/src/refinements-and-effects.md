# Refinements, Effects, and Safety

This area has a settled semantic direction and a provisional general syntax. The rules below constrain the eventual design; they do not authorize arbitrary expressions as refinements or effects.

## Refinements

A refinement combines a base type with facts every value of that type satisfies. Exact array length is a concrete instance:

```dewy
array<int64 length=3>
```

A parameterize block may attach conditions to any type. An entry is a condition when it is a one-argument lambda about the value (`int< i => i >? 0 >`), a `?`-comparison on `length` (`array< length >? 0 >`), or a `length=N` assignment; every other entry is a type parameter. A refined array type may leave its element open and receive it on application (`NonEmptyArray<int>`). Conditions currently compare against integer literals.

Checking a value against a refined type yields one of three outcomes: proven, refuted (a compile error), or unknown (reported as unproven, never as false). A binding declared with a refined type carries the base type together with the proven facts: integer bounds feed range analysis and minimum lengths feed bounds proofs. Refinements currently apply to bindings; refined parameters and results are provisional.

Refinement facts may arise from annotations, literals, ordinary control-flow conditions, successful explicit checks, and trusted interfaces. The facts the compiler tracks today include exact and minimum array lengths, `i <? xs.length` index guards, integer intervals, narrowed union members, and proven dictionary and set keys.

```dewy
if index >=? 0 and index <? values.length
    use(values[index])
```

Inside the body, the index relationship is available to prove the access valid. Mutation and calls invalidate any fact they may falsify.

The general proposition language must be a deliberately bounded, decidable fragment. Unsupported Dewy expressions produce an unknown proof result or a diagnostic; they do not silently enter refinement checking as trusted predicates.

## Operation Preconditions

An ordinary partial operation is valid when its precondition is proven. Examples include indexing within bounds, dividing by a nonzero value, narrowing a number into a smaller representation, and satisfying a function's refined input contract.

When a fact cannot be proven statically, the program chooses an explicit checked operation, establishes the fact with control flow, supplies a checked proof, or crosses an explicit `unsafe` boundary. The compiler must not insert a hidden semantic fallback that changes the operation's type.

## Assertions

`$assert condition` states a fact the compiler must prove; `$assert condition, message` adds a string literal to the diagnostic. It has the three refinement outcomes: proven (nothing is emitted), refuted (`assertion refuted`), or unknown (`cannot prove assertion` — the fact is neither proven nor refuted). Facts come from the checker's folding and from the bounds analysis: constants, exact and minimum lengths, integer intervals, and index facts from guards.

A refuted or unproven `$assert` underlines the condition, uses the message as the pointer text, and explains in `note:` lines what the analysis knows about each operand and what that decides for each comparison (`` `i` is 3 ``, `` `xs.length` is 3 (the array has exactly 3 elements) ``, ``so `i <? xs.length` is false``).

`$runtime_assert condition` and `$runtime_assert condition, message` evaluate the condition at runtime. When it fails, the program writes the same report shape to stderr through `library/reporting.dewy` — the excerpt with the condition underlined, the message (which may interpolate values) as the pointer text, and `note:` lines with the value of each non-literal comparison operand (re-evaluated on the failure path) — and exits with status 101. The failure path diverges, so the code after the assertion holds the condition's facts exactly as code after an early-return guard does. A runtime assertion whose condition the analyses refute is still a compile-time error.

<!-- dewy-example: compiler -->

```dewy
let xs:array<int64> = [1 2 3]
$assert xs.length =? 3, "three elements"

let get = (ys:array<int64> i:int64):>int64 => {
    $runtime_assert i >=? 0 and i <? ys.length, "index {i} out of range"
    return ys[i]                      # proven by the assertion
}

let main = ():>int64 => {
    loop i in 0..2 { $assert i <? 3 }
    return get(xs 1)                  # 2
}
```

The comma binds tighter than comparisons, so `x <? 3, "message"` is read as the condition `x <? 3` with the message split off the end of the expression. A compile-time message must be a string literal.

## Effects

An effect describes observable behavior relevant beyond a function's return value. The intended effect model covers at least mutation, allocation, blocking, I/O or host capability access, failure, nonreturning control flow, and escape of storage or handles.

Effects propagate through calls. A caller may preserve a refinement or borrow storage only when the callee's effects prove that behavior safe. Unresolved indirect calls require a conservative effect contract.

`noreturn` is a settled effect used by a function that cannot return to its caller. It is distinct from the `never` result type.

Expected failures remain [error alternatives in the return type](errors-and-forwarding.md), not members of the effect set. A contract may contain both a returned error union and effects, but `|` combines the returned alternatives while the effect syntax describes evaluation behavior separately.

## `unsafe`

`unsafe` identifies a proof or memory-safety obligation the compiler has not established. It is an auditable trust boundary, not a request to turn off unrelated checking.

## Provisional Boundary

The complete proposition grammar, qualifier inference, proof-value form, effect vocabulary, effect polymorphism, and surface syntax for `unsafe` remain provisional. Error-value propagation has its own settled core and provisional surface details; see [Errors and Forwarding](errors-and-forwarding.md) and [Design Maturity](design-status.md).
