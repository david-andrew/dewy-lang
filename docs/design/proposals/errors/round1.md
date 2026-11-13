# Combining failures, round 1

```dewy
import p"@lib/std/errors.dewy" as errors
WriteFailed:type = type of error
CloseFailed:type = type of error
save_failure = () => {
    return errors.join(WriteFailed CloseFailed)
}
show_failure = () => {
    let failure = save_failure
    loop part in errors.leaves(failure) {
        errors.report(part)
    }
}
```

```dewy
import p"@lib/std/errors.dewy" as errors
FieldError:type = type of error & [field:string message:string]
validate = (name:string age:int) => {
    let failed:array<error> = []
    if name.length =? 0 failed.push(FieldError["name" "required"])
    if age <? 18 failed.push(FieldError["age" "must be at least 18"])
    errors.join(failed...)
}
```

These are paper programs, not implemented syntax. **Round 2 supersedes this candidate.** This file preserves the first design and the counterexamples that changed it; it is not a second recommendation.

## Scope and acceptance

Owned: this directory only. Read-only: the entire Dewy checkout. Budget: about three hours. No compiler implementation, cleanup-timing redesign, commits, or edits to the decision ledger. Acceptance: specify composition, its type and every named handler; retain order and duplicates; preserve cancellation; exercise at least ten realistic programs; give line-cited comparative grades and a usage-only name list. New names remain provisional until independent cold reads. As the assigned sub-agent I do not launch more agents.

## Starting choice

Use a standard-library factory `errors.join(first second ...)`, one `ErrorGroup` holding ordered children, and an ordinary array plus `push` for an accumulator. Zero arguments give `void`; one returns the original exception; two or more produce a group. Nested groups remain nested. Direct parts are `.errors`; `errors.leaves` traverses left to right. This makes splitting a pair exact, rather than reconstructing two intersected payloads.

Do not overload `&` for accumulation. The existing type operation means one value satisfies both constraints. `A & A` cannot represent two occurrences of A with different payloads. `A & B` merges shared fields, whereas two errors may both have a different `message`. Type intersection also cannot encode insertion order. At value level Dewy already uses `&` for integer masks, set intersection and function intersections/overload families. One could add an overload returning a distinct group, but its type would **not** be `A & B`. That shortcut would add a second meaning exactly where David asks how to split the result. The explicit call is the recommendation, not a claim that operator overloading is impossible.

Handlers should select the outer value. `FileError` does not mean “contains a FileError,” for either `match` or `is?`. A selected `??` must never erase unrelated failures. A separate `errors.split<E>` partitions leaves and retains unmatched failures for forwarding. Reuse `partition_failures` for arrays of successful and failed outcomes; it is already accepted.

Initially, I considered making every group an `error`, adding a cancellation bit so `??` and `or_throw<Canceled>` still forward cancellation. Context would attach a message to the existing exception rather than replacing its kind. Origins would be optional metadata.

## Counterexamples from the first paper pass

1. **The single error family is unsafe.** `errors.join(Canceled CloseFailed)` would be an `error`. `if result is? error return fallback` would swallow cancellation even if `??` had a special guard. Making `is? error` data-dependent would break ordinary nominal narrowing. Round 2 instead uses two ordinary, disjoint nominal group types: all-error groups and groups with non-error exceptions.
2. **Array literals are not an inert way to package cancellation.** `errors.join([Canceled CloseFailed]...)` invokes a collector before joining: D4 Q1 makes it leave the function with Canceled. The variadic call above and explicit `push` avoid that. Round 2 explicitly tests this distinction. No new “capture cancellation” array syntax.
3. **Repeated concatenation is a poor accumulator.** `failed = [failed... next]` copies a growing prefix unless an optimization rescues it. Keep `array<exception>` with amortized `push`; join once. Recursive joins remain useful for preserving boundaries, but not the idiom for a flat batch.
4. **Flattening loses meaningful boundaries.** Flattening a contextualized group moves “loading config” onto unrelated cleanup errors or discards it. Keep group nesting; flatten only in a requested traversal. A split must preserve context on the reconstructed subtrees.
5. **“Optional origin” does not settle recording.** Asking for a location after unwinding cannot recover a site or trace that was never recorded. Round 2 records a small origin token at construction and makes stack capture an explicit setting, with honest unknown/disabled results.
6. **An empty group is not a failure.** A successful validation must return `void`, not an `ErrorGroup([])` that `or_throw` treats as failure. Splitting uses arrays to represent an empty side, rather than confusing it with the real exception `none`.

## First-pass grades, before revision

These are defects in the candidate, not claims about an implemented compiler. Each deficient grade cites the exact counterexample above by numbered item; final grades use program line numbers in dogfood.md.

| Slice | O/D/C/S/K | Reason for each deduction |
|---|---|---|
| Cancellation and ordinary error handlers | 4/3/5/2/3 | O/D: item 1 gives incompatible meanings of error; S/K: broad handlers consume Canceled. |
| Form/batch accumulation | 5/4/3/4/4 | D: item 6's empty behavior was unspecified; C/S/K: items 2–3 need a better construction path. |
| Nested context and selective recovery | 4/3/4/3/3 | O/D/C: item 4 needs a separate tree walk; S/K: flattened context cannot be reconstructed. |
| Origin after forwarding | 4/3/5/4/2 | O/D: item 5 conflates requesting and recording; S: misleading attribution; K: no recording contract. |

Round 2 fixes these design defects. Remaining costs must stay visible in the grades; adding words to a specification is not evidence that a compiler or readers can do it.
