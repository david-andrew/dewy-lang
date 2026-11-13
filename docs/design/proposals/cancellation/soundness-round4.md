Verdict: revise before implementation; confinement is viable, but whole-failure retention lacks a legal result for repeated non-error exceptions.
Must-fix count: 1 — retained failures outside the error-only stack constraint.
Round-3 disposition: M1, M2 and M4 are resolved; M3 is sound under its specific closed-parent transfer rule, whose precedence needs clarification.
Decidability: conservative, demand-driven checking is feasible over finite demanded instances, with cancellation ancestry and stable refinement proofs.
Within: keeping a fully completed cancellation-free success is sound; protection wording and cancellation metadata still need clarification.

This is a design review, not an implementation test. I read the binding brief, the previous soundness review, round 4 and all 23 programs in the required order; then the inherited round-3 rules, relevant round-2 rules, decisions batches 3–10, D40–D42, the requested language sections, the signals summary, and relevant concurrency and combined-failure contracts. No programs or benchmarks were run. Only this report was written; nothing was committed. The verdict was saved provisionally before the detailed review and updated as the findings settled.

Locations below refer to `round4.md` unless another file is named. Programs are self-contained design specimens, using the proposed language. Deadline examples describe an execution in which the long wait starts before cancellation; they make no scheduler guarantee. Acceptance means either the stated result or the stated compile-time rejection, not a claim that the current implementation supports these proposals.

## Disposition of the four round-3 must-fixes

| Previous finding | Disposition | Strongest remaining probe |
|---|---|---|
| M1: fresh-request ingress | Resolved for confinement. Protection, cleanup receivers, deferred captures and outside-group tasks are now checked. The descendant exception is safe only for cancellation-propagating ancestry, not mere lexical nesting. | N1 must be rejected. S3 covers the remaining distinction between cancellation authority and diagnostic origin. |
| M2: structurally unsafe residuals | Resolved. The whole-failure invariant covers additional record facets and stack elements; shallow projection no longer claims to sanitize a record. | N2 must be rejected at combination, and its plain-record variant at egress. |
| M3: missing continuing block bindings | Resolved for the integer counterexample and, under the specific table row, for aggregate bindings. The general publication prohibition conflicts with that row and should be qualified. | N3 publishes 42; S1 publishes an intact aggregate only into the already-closed parent. |
| M4: user-value idempotence and stack observations | Resolved for cancellation. Duplicate user combinations are rejected, and cancellation is outside the ordinary cleanup stack. | N4 must be rejected. M1 below is a different, newly exposed result-aggregation problem involving non-cancellation exceptions. |

There is no surviving direct confinement counterexample to the repaired M1 or M2, or a surviving user-`and` counterexample to M4. It would be misleading to keep those findings open merely because a different failure case remains.

## M1 — Retaining whole sibling failures can require a stack that the design forbids

**Severity: must-fix.** Locations: §2.2 lines 103–108, §2.3 line 128, and the whole-failure change in Q8. Related contract: `docs/design/proposals/errors/combined/round3.md`, M3 and M6, inherited by that proposal's round 4.

```dewy
Stopped:type = type of exception & [id:int]

finish_after_stop = (ready:Channel<int> id:int) => {
    ready.send(id) or_throw
    sleep(1s) ?? void
    Stopped[id]
}

main = () => {
    let ready = channel<int>(2)
    parallel {
        finish_after_stop(ready 1)
        finish_after_stop(ready 2)
        {
            ready.receive or_throw;
            ready.receive or_throw;
            return
        }
    }
}
```

Consider an execution in which both sends succeed and the third item returns before either one-second sleep completes. Both siblings are canceled. Each handles its `Canceled` and returns a distinct `Stopped` value, carrying 1 or 2. `Stopped` is a non-error exception, not a success and not a cancellation facet.

Round 4 now requires **both whole failures** to survive beside the exit, replacing its successful `void`. Neither contains `Canceled`, so all four confinement rules permit them. However:

- A single `Stopped` loses the other occurrence and its `id`.
- An intersection cannot contain two distinguishable facets of the same minted type. Its canonical type is still `Stopped`; user `and` rejects the overlap.
- `ErrorStack<Stopped>` violates the explicit error-only element constraint.
- A plain array holds the values, but is not the specified failure result and changes failure matching, forwarding and exit handling.

Automatic cleanup is allowed to choose a stack without being user-written `and`; that does not remove the stack's element constraint or supply a different aggregate for these values. “The runtime records cancellation once” is irrelevant: these are two ordinary, distinct non-cancellation failures.

This is not a claim that the program leaks cancellation. It is a missing legal result for a program the new retention rule admits. It becomes material precisely because round 4 retains siblings' complete failures, rather than only their cleanup errors. The same question applies wherever a group promises to retain multiple such failures.

**Fix.** Define one total aggregation operation for all retained failures, including repeated non-error exceptions and mixtures with errors. A small option is to allow cancellation-free exception elements in the existing stack, retaining the rule that no element may structurally contain `Canceled`. That changes the stated element constraint and must be acknowledged, including how the resulting stack matches `error` and `exception`. Alternatively specify a distinct existing aggregate mechanism with complete typing and forwarding rules, or explicitly reject these group result types at compile time and document the restriction. Do not silently drop or deduplicate the occurrences.

**Acceptance:** the program either returns a documented failure holding both numbered occurrences, or gets a deliberate diagnostic explaining the unsupported aggregation and an actionable rewrite. It must not fail during shutdown, silently choose one, or pretend `Stopped and Stopped` is a valid two-value intersection.

## S1 — Closed-parent transport needs an explicit exception to the publication prohibition

**Severity: should-fix.** Locations: §2.3 lines 118–120 versus lines 128–130; §2.1 rule 2.

```dewy
job = () => {
    parallel (
        let box = [result=sleep(1s)]
    )
    printl(box.result is? Canceled)
    7
}

main = () => {
    let answer = within(1ms @job)
    printl(answer)
}
```

When the outer deadline closes the requests during the sleep, the item's successful record contains `Canceled` in its field. The general rule says that this success is **never published**, because its type can hold cancellation. The continuing-`parallel` row says that `box` is available with its unchanged type and holds the parent's cancellation.

The specific row has a sound interpretation: the child is joined, the receiving parent is already closed, and the complete aggregate is transferred into that parent's cancellation domain. No field changes type; the program prints true and reaches 7. Nothing holding cancellation reaches `main`; `job`'s final successful integer can be published by `within`.

I therefore do not count this as a remaining type-soundness defect in M3. It is an explicit contradiction in the general wording, and an important exception to identify before implementation. Treating the general prohibition as authoritative would revive the old missing-binding problem; replacing the record with a top-level `Canceled` would be ill-typed.

**Fix.** Distinguish two operations:

- Export into a request that can still be open: require the success to be structurally cancellation-free, or apply that boundary's specified discard/rejection policy.
- Privileged joined transfer into an already-closed parent: preserve the complete value and its type, and associate its cancellation-bearing contents with the parent's domain for subsequent confinement checks.

Name the continuing block row as the latter operation and explicitly exempt it from ordinary egress. This is not permission for arbitrary writes to an outer place, a mutex or a background task. Preserve captured environments and generic specializations. State the diagnostic-origin policy separately (S3); do not imply an unaccounted deep rewriting pass over every field and capture.

**Acceptance:** this program is well-typed and prints true in the described execution; N3 still prints 43. The same value remains forbidden as an input to a fresh protected request or as shared data.

## S2 — Protection has two different answers after its body handles cancellation

**Severity: should-fix.** Locations: §2.3 line 126 (“as `within`'s own column”), §2.7 line 171 (“Protection's expiry gives `Timeout`”), and inherited round-3 §2.1.5.

```dewy
finish = () => {
    sleep(1s) ?? void
    7
}

job = () => {
    sleep(1s) ?? void
    protect_from_cancel(1ms @finish)
}

main = () => {
    let answer = within(1ms @job)
    printl(answer)
}
```

Take an execution where the outer deadline cancels `job` at its first sleep. Protection then starts with its one-millisecond grace already running. Its body handles the cancellation of its own sleep and returns 7, with no cleanup failures.

The new boundary table says protection follows `within`: it keeps 7. The explicit adapter description and inherited rule say expiry gives `Timeout`. Both policies can preserve confinement, but they give different observable results and inferred result types. The amendment should not leave the implementation to choose between them.

**Fix.** Prefer the new table's uniform policy: protection maps a **returned cancellation facet** to `Timeout`; a fully completed, cancellation-free successful value survives. Update §2.7 and round-3 replacement wording accordingly. If protection must report expiry even after handling, explicitly make it differ from `within` and include `Timeout` in its result. Either choice must also cover a body that handles cancellation by returning a different failure without a cancellation facet.

This is a policy ambiguity, not a demonstration that keeping 7 is unsafe. The deadline remains cooperative under either policy.

## S3 — Descendant transport and cleanup-only cancellation need a diagnostic-origin rule

**Severity: should-fix.** Locations: §2.1 rule 4, §2.2 lines 105–112, and the closed-parent translation in §2.3.

```dewy
job = () => {
    let prior = sleep(1s)
    if prior is? Canceled {
        parallel {
            {
                printl(prior.$origin)
                let current = check_cancel()
                if current is? Canceled printl(current.$origin)
            }
        }
        return prior
    }
}

main = () => {
    let answer = within(1ms @job)
    printl(answer)
}
```

The descendant capture is explicitly allowed. The child's request must start closed before its first instruction. The captured `prior` already has the parent's sleep as its origin, while the child's first cancellation point is `check_cancel()`. Before that call, the child can already inspect the captured cancellation.

The confinement proof needs only that both requests are closed. It does not imply that the two values have the same diagnostic origin. Calling all cancellation “the current work's own” and saying its origin is the first cancellation point in that work must be reconciled with retaining captured values unchanged. A similar question arises for S1's aggregate transfer back into the parent.

There is also a path with no ordinary cancellation point in the owning work:

```dewy
SlowClose:type = [
    $__drop__ = () => { sleep(1s) or_throw }
]

value = () => {
    let owner = SlowClose[]
    7
}

main = () => {
    let answer = within(1ms @value)
    printl(answer)
}
```

If the deadline expires during cleanup and cleanup's grace subsequently expires, the owning work returns its recorded cancellation through the cleanup adapter. Its body never received cancellation at a wait. The hook's wait occurred under a different request. The promised origin must still have a defined value.

**Fix.** Separate cancellation authority, which may be safely associated with a closed descendant or parent for normalization, from diagnostic provenance. Preserve the origin on an already-existing value; define an origin for an adapter-created cancellation, such as the explicit/implicit boundary that reports it. State when the per-work first-observation record is initialized, including cleanup-only cancellation, and what translation preserves. This can be demand-driven metadata; no runtime request identity on every value is required merely to prove confinement.

## N1 — The former fresh-request ingress counterexample is now rejected

**Severity: note.** Location: §2.1 rule 4. Disposition: previous M1 resolved.

```dewy
job = () => {
    let stopped = sleep(1s)
    if stopped is? Canceled {
        let inspect = () => {
            printl(check_cancel() is? Canceled)
            stopped
        }
        protect_from_cancel(1s @inspect);
        return stopped
    }
}

main = () => {
    let answer = within(1ms @job)
    printl(answer)
}
```

**Required result:** compile-time rejection at the protected call, because its callback captures `stopped`. Capturing `stopped is? Canceled` as a bool before entering protection is the valid rewrite. The same analysis must inspect an implicit drop-hook receiver and a deferred capture; the revised rule explicitly requires both.

There is no remaining open-request counterexample here. Descendant entry is different: it is safe only if the destination inherits cancellation before executing. A descendant reached through a shield is not a cancellation-propagating descendant of the outside work. A group passed to a helper needs its actual cancellation-domain relation, not just the lexical location of that helper's call.

**Fix:** retain this rule and these entry checks; no additional surface restriction is needed for this specimen.

## N2 — The former residual counterexample fails at construction or egress

**Severity: note.** Location: §2.1 rule 3 and shallow projections. Disposition: previous M2 resolved.

```dewy
Failed:type = type of error

job = () => {
    let stopped = sleep(1s)
    if stopped is? Canceled return Failed and [cause=stopped]
    Failed
}

main = () => {
    let answer = within(1ms @job)
    printl(answer)
}
```

**Required result:** compile-time rejection at `and`. The extra plain-record facet is part of the complete failure, so it cannot hide cancellation.

For the complementary projection probe, replace the rejected return inside the same branch with a local `let residual = [cause=stopped] as ~Canceled`. That expression is legal local storage, but `residual` still structurally contains cancellation. Publishing it through a shared place must be rejected; returning it as the successful result of `within` must be rejected at that boundary's nested-cancellation check. Shallow projection does not remove `cause`. Round 4 no longer asserts that it does. A failure's residual, unlike this record's projection, is structurally safe by the strengthened construction-and-mutation invariant.

**Fix:** retain the whole-value check through generic constructors, broad-family fields, captures and mutations. The invariant should cover reachable stored data, not merely fields named directly on the error declaration. This is already the stated structural-summary intent.

## N3 — The formerly missing integer binding now has a value

**Severity: note.** Location: §2.3 line 130. Disposition: previous M3 resolved subject to S1's clarification.

```dewy
wait_value = () => {
    sleep(1s) or_throw
    7
}

job = () => {
    parallel (
        let n = wait_value ?? 42
    )
    printl(n + 1)
    n
}

main = () => {
    let answer = within(1ms @job)
    printl(answer)
}
```

After cancellation at the item wait, the explicitly written default produces 42. The binding has type `int`, is published, and the subsequent line prints 43. `job` returns 42; with its own deadline as the cause, `within` now keeps that handled success too. No implicit function exit or dynamically ill-typed binding is required.

**Fix:** preserve this behavior. For the strongest remaining aggregate variant, use S1: it needs the special closed-parent transfer rule, not the ordinary cancellation-free export rule.

## N4 — User cancellation combinations obey the accepted overlap rule

**Severity: note.** Location: §2.2. Disposition: previous M4 resolved.

```dewy
job = () => {
    let first = sleep(1s)
    if first is? Canceled {
        let second = check_cancel()
        if second is? Canceled return first and second
    }
}

main = () => {
    let answer = within(1ms @job)
    printl(answer)
}
```

**Required result:** compile-time overlap error at `and`. Replacing that expression with `ErrorStack[first second]` is also rejected under the stated element constraint. Neither operation silently deduplicates values or changes stack length.

`Canceled & ErrorStack<CloseFailed>` for automatic cleanup has a coherent logical representation: one cancellation facet outside an ordered collection of ordinary failures. Clearing that facet leaves the stack and its occurrences intact. A flag can encode the unit facet without changing its public type or projection behavior.

**Fix:** keep these rules. M1's non-error-exception aggregation must be repaired independently; it is not a reason to restore cancellation idempotence for user values.

## N5 — The four rules can support a decidable confinement check

**Severity: note.** Locations: §2.1 checker summaries, §2.3 boundary operations and §2.4 refinements.

```dewy
identity = <T>(x:T):>T => x

relay = (n:int) => {
    if n >? 0 return relay(n - 1)
    identity(sleep(1s))
}

main = () => {
    let answer = within(1ms @relay(2))
    printl(answer)
}
```

This is legal same-request transport through a generic and recursion. The responsible deadline maps the returned cancellation to `Timeout`. It requires neither exact dynamic call-tree enumeration nor runtime origin tags on the value.

The safety argument, with S1's explicit transfer interpretation, is:

1. Runtime construction introduces cancellation only into a closed request.
2. Same-work helpers preserve that property. Descendant input preserves it only along cancellation-propagating edges, including closed-at-entry late spawns. Protection, cleanup and unrelated task entry reject such inputs.
3. Ordinary egress cannot export cancellation-bearing data to another work or longer-lived/shared place.
4. Failure normalization removes all cancellation because every other retained component is structurally free of it.
5. Ordinary successful export is either proved cancellation-free, discarded or rejected. A continuing block may instead transfer the intact value to a joined, already-closed parent. Subsequent stores and fresh-request entries still obey the rules.
6. A value from a work that was never canceled contains no cancellation. Its publication refinement is justified by that fact, provided the refinement remains stable under later mutation and calls.

The result is the useful confinement theorem: no value holding cancellation becomes accessible in an open-request work, including the entry work. The stronger wording “always produced by the current work” is unnecessary and is not literally true of allowed descendant captures. Diagnostic provenance is separate (S3).

A conservative decidable implementation is feasible, with these qualifications:

- Demand function/context/type instances only from reachable roots and relevant obligations. Assume the language's ordinary specialization-termination rule; unrestricted generation of ever-new generic instances is not made decidable by this analysis.
- Memoize structural may-hold summaries, including recursive types, environment storage and broad families. A function handle that can produce fresh cancellation when called is not automatically a stored cancellation value.
- Use finite symbolic domain relations for parameters, results, captures, receivers and group handles. The four labels listed in §2.1 need an accompanying proof of cancellation ancestry: “other work” alone cannot distinguish an allowed descendant from an unrelated task. Unknown relations can be conservatively rejected.
- Model request-changing edges and privileged boundary transfers explicitly. Do not equate lexical nesting with inheritance through shields. Check receivers and implicit cleanup entry as well as explicit calls.
- Use ordinary place/alias analysis to preserve refinements. A narrowed readable field cannot remain trusted after a call or write that may widen it. Keep the original generic specialization and captured behavior as §2.4 now requires; a narrow view is not permission to pretend a different generic object was constructed.
- Solve recursive summaries monotonically over finite domains, with conservative widening for unbounded shapes and checked summaries for indirect calls.

**Fix:** make those representation/transfer details part of the implementation contract. The cost statement is now appropriately qualified: control-flow work times lattice height, plus normalization and demanded instances. Only context reachability is simply linear in graph size. No performance conclusion follows from this paper review; the stated flagship measurement remains required.

## N6 — Keeping a handled value at `within` is safe, with a precise completion point

**Severity: note.** Locations: §2.3, program 23, Q8; inherited round-3 §2.1.7's definition of a complete result.

```dewy
best = () => {
    sleep(1s) ?? void
    42
}

main = () => {
    let answer = within(1ms @best)
    printl(answer + 1)
}
```

On the deadline path, `best` handles cancellation and produces an `int`; after all cleanup completes successfully, keeping it is safe. The child's closed request does not somehow taint 42. No runtime tag test or recursive sanitation is necessary for a structurally cancellation-free type.

Conversely, changing `best`'s result to `[value=sleep(1s)]` must trigger the declared nested-cancellation result diagnostic at `within`, even on runs where the actual wait finishes normally. That conservative restriction is explicit. A canceled result-selecting loser can still be discarded by `race` or `first_ok`: their selection policy overrides mere eligibility to publish.

The completion point matters. With `SlowClose` from S3 acquired inside `best`, a grace-expired cleanup can replace the candidate 42 with cancellation, and an ordinary close failure can replace it with a failure. The result must be classified **after** the child's cleanup and joins. The current inherited definition supplies that ordering; keep it when implementing the new success rule. If the parent request closes, the table's parent-cancellation result takes precedence over the child's handled value; no arbitrary CPU-time preemption is added.

**Fix:** express the rule as “a complete successful result whose retained data is proved free of `Canceled` is eligible for publication,” then apply the boundary's selection/translation policy. Program 23's `Move` result is sound only with that full inferred result, including any cleanup failures; handling `search` alone cannot erase them.

## Required resolution

Resolve M1 before implementation: the new promise to retain whole sibling failures needs a legal representation for every admitted failure type. Clarify S1–S3 without reopening the repaired direct confinement cases. In particular, preserve the handled integer and anytime-result behaviors, the strict fresh-request ingress checks, the whole-failure structural invariant, and the rejection of duplicate user cancellation combinations.
