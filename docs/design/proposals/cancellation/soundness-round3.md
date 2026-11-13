Verdict: revise before implementation; confinement is viable, but the stated rules do not establish it.
Must-fix count: 4 — fresh-request ingress, structural residual safety, canceled block bindings, and cancellation flag/stack semantics.
R1: resolved at the contextual-typing level; R2: partly resolved, still blocked by M2 and M4; R3: the original shielding defect is resolved.
Decidability: a conservative, demand-driven check is feasible on finite demanded instances, but needs domain-transfer and escape summaries beyond the listed write summaries.
Batch 10: a flag can represent a typed cancellation facet; silently deduplicating cancellation occurrences and changing stack observations cannot be justified as representation alone.

This is a design review, not a compiler test. I read the binding brief, the earlier soundness review, round 3 and all twenty programs, decisions batches 3–10, D40–D42, the requested LANGUAGE sections, the signals summary, and relevant concurrency and combined-failure contracts. The specimens below are self-contained programs under the proposed surface. Timing examples describe a possible execution in which the long wait starts before its deadline; they do not assume a scheduler guarantee. No programs or benchmarks were run. Only this review file was written. References to sections and lines without a filename mean `round3.md`.

## Disposition of the earlier must-fixes

| Earlier finding | Round-3 disposition | Strongest remaining test |
|---|---|---|
| R1: contextual cleanup results invalidate one-body typing | Resolved in principle. Complete contextual typing is now required; sharing depends on equivalent lowering. Removing cleanup's `Timeout` is not what proves this. | N1 exercises cleanup, aggregate returns, stored handles and generic inspection together. It now has a coherent answer. S2 identifies the separate, unfinished publication-view contract. |
| R2: cancellation and repeated cleanup failures need more than a top-level singleton alternative | Partly resolved. An internal cancellation component beside an ordinary failure payload is viable. The stated projections do not prove a residual is structurally safe (M2), and flag merging changes the value algebra (M4). | M2's plain-record facet puts cancellation in a failure that clearing its outer flag cannot sanitize. M4 and S3 exercise repeated failures and stacks. |
| R3: the universal join rule defeats protection | The original defect is resolved: parent closure starts the grace timer without closing the protected request. | N2 replays the stopped-parent/save case successfully. M1 is a new ingress defect involving protection; S1 is a separate contradiction in cleanup's claimed equivalence. |

There is no surviving direct R1 or R3 counterexample once their new rules are followed. Those findings should not be kept open merely because other parts of round 3 need repair.

## M1 — A shorter-lived fresh work can read another request's cancellation

**Severity: must-fix.** Location: §2.2 lines 110–140, especially the unconditional permission to read enclosing locals at line 137; §2.3 lines 179–182; protected/cleanup entry in §2.1.

```dewy
job = () => {
    let stopped = sleep(1s)
    if stopped is? Canceled {
        let inspect = () => {
            let own = check_cancel()
            printl(own is? Canceled)
            printl(stopped is? Canceled)
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

Take an execution where the deadline closes `job`'s request during its sleep and `inspect` finishes well before its one-second grace expires. The first print is false; the second is true. The captured value belongs to the closed outer request, while `inspect` runs under a fresh, open request. This directly falsifies both “always the current work's own” and “a work whose request didn't close can't hold `Canceled`.”

There is no write to an outer variable, mutex, channel or global, and no constructor. The ordinary value capture is made locally. Protection is synchronous and joined, so its environment need not outlive `job`. A check for writes through captured places finds nothing. The same problem survives an extra helper, a generic identity call, or a record containing the closure.

If “no publication outside the work” is intended to prohibit this transfer already, it must override the unconditional read/capture permissions. The explicit lifetime/write rules and listed summaries do not implement that interpretation. A shorter lifetime is not the same request domain.

Automatic cleanup has the same issue through its receiver:

```dewy
Logged:type = <T>[
    value:T
    $__drop__ = () => { printl(value) }
]

job = () => {
    let r = sleep(1s)
    let owner = Logged(r)
    printl(owner.value)
}

main = () => {
    let answer = within(1ms @job)
    printl(answer)
}
```

`Logged` is an ordinary local record, not an error. When `r` holds cancellation, its drop hook reads that value under the cleanup's fresh request. The receiver is an implicit argument; a check only at explicit captures misses it. Rejecting every such hook is a possible conservative implementation restriction, but it contradicts the unqualified claim that ordinary local storage/logging needs no additional restriction.

**Fix.** Check ingress as well as egress at every request-changing edge: arguments, captured values and places, receiver fields, callbacks and implicit cleanup calls. Associate a cancellation-bearing value with its producing work in the static analysis. Same-request helpers preserve that association; entering protection, a task body or cleanup does not automatically rebind it. Without runtime value provenance, conservatively reject a foreign-domain value entering a fresh work, and diagnose the actual transfer. Allow ordinary read-only captures proven free of cancellation.

For the first program, inspect/log `stopped` before protection, and capture only the ordinary save inputs into protected work. Merely starting the protected request closed would defeat protection and is not a repair. Cleanup that must inspect old cancellation data needs an explicit design choice: inspect/project before switching requests, restrict such receivers, or support provenance-bearing data with corresponding normalization rules. A bare flag cannot distinguish old and new cancellation if both are admitted and combined.

## M2 — Removing a top-level facet does not sanitize nested data

**Severity: must-fix.** Location: §2.2 lines 127 and 138–147, particularly “Neither may hold `Canceled`, so the residual can be stored anywhere”; D42 Q4 and combined-failure round 4 C1.

```dewy
publish = (out:Mutex<[cause:exception]>) => {
    let r = sleep(1s)
    if r is? Canceled {
        let box = [cause=r]
        let residual = box as ~Canceled
        @(out.lock) = residual
    }
}

main = () => {
    let seed:[cause:exception] = [cause=none]
    let out = mutex(seed)
    within(1ms @publish(out)) ?? void
    printl((@(out.lock)).cause is? Canceled)
}
```

D42 projection selects facets. The plain record `box` is not a `Canceled` facet. Consequently `box as ~Canceled` keeps that record unchanged, including its `cause`. A fresh runtime representation does not change this semantic fact.

The proposal gives conflicting instructions here. Its structural no-publication rule must reject the mutex assignment; its unconditional residual rule declares the projected value cancellation-free and storable anywhere. Following the latter lets an actual cancellation reach `main`. This is not an assertion that an implementation following the structural rule must accept the program: it is a counterexample to the claimed projection guarantee.

There is a related failure-publication hole under the literal “an error's own fields” restriction:

```dewy
Failed:type = type of error

job = () => {
    let r = sleep(1s)
    if r is? Canceled return Failed and [cause=r]
    Failed
}

main = () => {
    let answer = within(1ms @job)
    printl(answer)
}
```

`Failed` has no fields. The allowed local record holds cancellation in its own plain-record facet, and `and` constructs a combined failure with that facet. It is not `Failed[cause=r]`. Clearing an outer cancellation flag leaves `cause` untouched; the deadline must not publish `Timeout` combined with that unsanitized failure. If rule 3 is intended to cover all fields of the entire combined failure, this program should be explicitly rejected at `and`, not treated as the recommended way to combine a cancellation-bearing record with an error.

The check must also cover non-error minted facets with fields, captured environments attached to retained values, mutations after construction, family widening and generic construction. Checking only a named error constructor is insufficient.

Finally, `as error` and `as ~Canceled` are not generally synonyms. A user-defined non-error exception facet survives the latter and not the former:

```dewy
OtherStop:type = type of exception

job = () => {
    let r = sleep(1s)
    if r is? Canceled {
        let both = r and OtherStop
        let rest = both as ~Canceled
        printl(rest is? OtherStop)
        both;
        return rest
    }
}

main = () => {
    let answer = within(1ms @job)
    printl(answer)
}
```

`as error` is not a replacement for `rest`: no error facet is present. A projection with no valid retained value also needs the ordinary projection validity rule; it cannot silently claim an `error` value exists.

**Fix.** Preserve D42's shallow facet projection semantics. Recompute or retain the structural may-hold summary for the projected value. A projection can remove the direct cancellation facet while still containing cancellation in fields or captures. Permit publication only with a proof that the entire retained value is cancellation-free.

Define a normalizable failure invariant over the *complete retained failure*, including additional facets and stack storage: any cancellation it contains must be in the designated cancellation component, with every other retained component structurally free of it. Enforce the invariant whenever failure values are built, combined or mutated, including generics and family-typed fields. Alternatively specify a recursive transformation and its resulting types, but that is more machinery than clearing one flag. Preserve non-error exception residuals as well as `error` facets.

## M3 — Discarding every canceled success leaves ordinary block bindings without values

**Severity: must-fix.** Location: §2.2 lines 138–140 versus §2.4's `parallel` parent-cancellation cells, lines 203–205; batch 3 C3 and the binding straight-line-control requirement.

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

Let the outer deadline expire while the item waits. `job`'s request and its child's request close. `wait_value` returns cancellation to the item, and the written `??` handles it. The item's complete result for `n` is the successful integer 42. Its type is `int`, with no cancellation alternative.

The new blanket rule forbids publishing that success. But this item contains no exit from `job`, and the table allows execution after the join with bindings that “keep” cancellation. It gives no value for `n`:

- Publishing 42 violates the blanket success-discard rule, although it is safe for confinement.
- Publishing `Canceled` violates `n:int` and makes `n + 1` ill-typed at runtime.
- Omitting the binding violates definite assignment.
- Silently leaving `job` at the join adds a cancellation exit where the programmer wrote none, contrary to the binding brief. `wait_value`'s `or_throw` returned from that helper and was handled by `??`.

The outer `within` eventually discarding `job`'s result does not make `printl(n + 1)` unreachable. Cancellation is cooperative, and code following a wait continues unless the specified source control flow leaves it. This is a new contradiction introduced by discarding canceled successes, not the original non-cancellable-after-block narrowing hole.

**Fix.** Give every boundary a complete value/publication and continuation rule. The minimal repair for this program is to preserve successful results proven structurally free of cancellation, including 42. Confinement does not require discarding them. Keep the explicit discard policy of result-selecting boundaries separately.

For an exported block binding whose success may contain cancellation, either require a proof that it is free of cancellation before export, or define an explicit whole-block cancellation result and a control-flow/narrowing rule that prevents using unpublished bindings without handling that result. Do not insert cancellation into a narrower field or binding. Translating a child's top-level cancellation into a parent's cancellation must also be an explicit boundary operation requiring that the parent's request is closed; it is not permission to retain arbitrary child aggregates unchanged.

This does not require restoring the blanket ban on local records or collectors. The problem is the export of their results on a path that continues.

## M4 — A flag is a viable encoding, but idempotence is a change to the error algebra

**Severity: must-fix.** Location: §2.2 lines 142–147; decisions batch 10 lines 719–734; combined-failure round 4 C1 and C4.

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

Both values come from the same closed request, with no construction or domain transfer. Batch 10 makes the *value expression* `first and second` a compile error because the operand types overlap. Round 3 expressly makes it one `Canceled`. This is an observable change in which programs type-check. Sharing a request does not establish that two failed wait operations are the same failure occurrence, and it does not override David's explicit duplicate-type rule.

Distinguish type and value algebra: canonicalizing the *type expression* `Canceled & Canceled` to `Canceled` is compatible with a set of types. It does not authorize merging two values of that type. The same distinction already applies to `E & E` versus `e1 and e2` for ordinary errors.

A flag is entirely consistent with an unordered set of typed parts if it is the physical representation of the logical singleton facet. For `c and CloseFailed[7]`, the logical parts remain `Canceled` and `CloseFailed`; projection, matching, generic type inspection and demanded metadata must behave accordingly. There is no need to allocate a separate object for the unit facet. The statement “not an element” must not make that logical part disappear from the public combination model.

Stacks need a precise contract too. Consider this local design probe:

```dewy
job = () => {
    let r = sleep(1s)
    if r is? Canceled {
        let failures = ErrorStack[r r]
        printl(failures.length)
        printl(failures.first is? Canceled)
        failures;
        return r
    }
}

main = () => {
    let answer = within(1ms @job)
    printl(answer)
}
```

This is intentionally an acceptance probe, not an assumption that the existing stack element constraint admits `Canceled`. If the error-only element constraint is retained, reject the constructor and say so. If round 3 intends its local-stack permission to admit these elements, two ordered entries cannot become a flag with no entries while retaining ordinary `.length`, indexing, iteration and nonemptiness semantics. Repeated waits can also have distinct demanded origins. The flag-only wording does not define those observations.

Automatic cleanup has a clean alternative: represent its result logically as `Canceled & ErrorStack<CloseFailed>`, with a cancellation facet outside a stack of ordinary failures. Each ordinary failure occurrence remains in the stack. An internal flag may implement that outer facet. A boundary then removes that facet without rewriting the stack's element type or deleting its ordinary entries.

**Fix.** Prefer keeping the batch-10 value-level overlap check, including for `Canceled`. Keep the error-only stack constraint if that is the chosen stack design, and explicitly specify the ordinary stack plus cancellation-facet form for automatic cleanup. Define how the runtime coalesces its own pending request state without pretending this is user-written `and` of duplicate failure values. Specify the logical type, projections, stack observations and optional metadata independently of the physical flag.

If cancellation-value deduplication or cancellation-bearing stack elements are desired instead, present the changed value/stack semantics as an explicit decision, with these observable consequences. Neither confinement nor an unordered type set makes that exception necessary. The current “batch 10 ... doesn't apply” sentence cannot substitute for that decision.

## S1 — Cleanup is not protection “word for word”

**Severity: should-fix.** Location: §2.1.5–6 lines 87–95; §2.6 line 224; Q8.

```dewy
SlowClose:type = [
    $__drop__ = () => { sleep(1s) or_throw }
]

finish_owner = () => {
    let owner = SlowClose[]
    7
}

slow = () => { sleep(1s) or_throw; 7 }

job = () => {
    let stopped = sleep(1s)
    if stopped is? Canceled {
        let protected = protect_from_cancel(100ms @slow)
        let cleaned = finish_owner
        printl(protected)
        printl(cleaned)
        return stopped
    }
}

main = () => {
    let answer = within(1ms @job)
    printl(answer)
}
```

After `job` is stopped, both operations get a 100 ms grace. Explicit protection reports `Timeout`. The cleanup contract makes `finish_owner` report the owning work's `Canceled`. Both outcomes can be coherent; they are not the same result contract. Moreover, cleanup's return is a privileged translation from a fresh cleanup request into the already-closed owning request. It must not be mistaken for permission to copy arbitrary old cancellation into fresh work as in M1.

**Fix.** Say cleanup shares protection's shielding and deadline machinery, with a different boundary adapter: normalize the cleanup request's cancellation, preserve its ordinary failures, then emit the owning work's cancellation only when that owning request is closed. Remove “word for word.” Keep nested deadlines cooperative and continue joining all cleanup; expiry is a stop request, not forced termination. The contextual typing repair already handles either explicitly chosen result policy.

## S2 — A narrowed publication view must preserve generic and captured behavior

**Severity: should-fix.** Location: §2.4 comprehension cell, line 205; §2.10's “no other conversion” estimate; programs 14 and 18.

```dewy
Box:type = <T>[
    value:T
    alternatives = () => {
        let n = 0
        loop t in members(T | string) n += 1
        n
    }
]

box = <T>(value:T) => Box<T>[value]

main = () => {
    let xs = [parallel i in [0..1) box(sleep(0ns))]
    printl(xs[0].alternatives)
}
```

The child constructs a `Box<void | Canceled>`, and its method is specialized with that `T`. Nothing cancels this comprehension, so the stored value is `void`. This proves a runtime value fact; it does not turn all behavior of the produced object into that of `Box<void>`. Blindly substituting `void` for the type argument after the join changes `alternatives` from 3 to 2. Reinstantiating closures from narrowed captures has the same problem.

A field-refined view retaining the original generic specialization can be sound, and the prose may intend it. It needs definition. Its cancellation-free proof must survive later generic calls and widening without falsely claiming a new generic object was constructed. Mutable methods and aliasing also need the existing place/variance checks.

**Fix.** Specify publication as a proven refinement of the existing value, preserving captured environments, generic method specializations and runtime representation. Do not reinstantiate an object merely because an impossible cancellation alternative is hidden from its readable field type. If an API requires a different concrete type, use a checked conversion/adapter or reject it. Apply `lower alike` transitively through called specializations; a wrapper's own scalar layout alone does not prove its calls are interchangeable. Treat the zero-conversion claim as conditional on an actual layout/view proof.

## S3 — The task-group and comprehension table still abbreviates away retained failures

**Severity: should-fix.** Location: §2.4 lines 205–206; §2.1.7 and §5's claimed N3 resolution.

```dewy
import p"@lib/std/tasks.dewy" as task

CloseFailed:type = type of error & [id:int]
Owner:type = [
    id:int
    $__drop__ = () => CloseFailed[id]
]

child = () => {
    let owner = Owner[2]
    sleep(1s) or_throw
}

grouped = () => task.tasks((group:Tasks) => {
    let owner = Owner[1]
    group.spawn(@child);
    sleep(1s) or_throw
    42
})

main = () => {
    let answer = within(1ms @grouped)
    printl(answer)
}
```

Assume both owners are acquired before the deadline. Parent cancellation stops the body and child, and both cleanup hooks fail. The `task.tasks` parent column says only “drains, then `Canceled`”; the outer `within` must receive both `CloseFailed` occurrences as well. Reading the table literally loses them. The general failure-preservation rule suggests the intended interpretation is correct, so this is a specification repair rather than a separate demonstrated type hole.

The body is result-polymorphic. A normal body return is saved until all children and body cleanup are complete; a child failure replaces the saved success and is combined with every retained cleanup failure. The callback and spawned children each need their own domain-entry checks from M1. The body's return is privileged boundary transport, not an ordinary publication that bypasses normalization. A child returning only its expected stop must not be confused with an ordinary failure that newly fails the group.

**Fix.** Write the full parent-cancellation transformation for `task.tasks`, comprehensions and parallel loops: enclosing-work cancellation plus all failures that their discard policy retains, with repeated ordinary types in the stack. Normalize body and child results before exposing `.wait()`, `.error` or the group result. Define the successful body-return case and expected-child-stop case explicitly, and retain the rule that a late admitted spawn starts closed during shutdown. The specimen's final deadline result must preserve both numbered close failures beside `Timeout`.

## N1 — R1's strongest old counterexample now has a coherent contextual answer

**Severity: note.** Location: §2.1.6, §2.3 and §2.10; earlier R1.

```dewy
SlowClose:type = [
    $__drop__ = () => { sleep(1ms) or_throw }
]

value = () => {
    let owner = SlowClose[]
    7
}

pack = () => [outcome=value]

count_alternatives = <T>(x:T) => {
    let n = 0
    loop t in members(T | string) n += 1
    n
}

main = () => {
    let callbacks = [@pack]
    printl(callbacks[0]())
    printl(count_alternatives(value))
    parallel {
        printl(callbacks[0]())
        printl(count_alternatives(value))
    }
}
```

Under the round-3 cleanup policy, the non-cancellable `value` result is `int`; the cancellable one may include `Canceled`. `pack` therefore has different contextual field types. The generic inspection gives 2 and 3 respectively. This needs no actual cancellation, because every item is checked in C. Unlike round 2, the design now permits the local aggregate and requires the full contextual typing that explains these differences. A handle descriptor can select the appropriate entry; sharing remains an optimization.

**Disposition/fix.** Mark original R1 resolved at the semantic-design level. Keep separate typed instances and contextual call results even when the eventual machine code is identical. Do not use a top-level effect bit as the complete description of an inferred aggregate-returning handle. A written callback result allowing only a fixed aggregate plus top-level cancellation must reject an implementation whose cancellation can occur inside that aggregate, unless a richer checked contract describes it.

## N2 — R3's original protected-save counterexample is repaired

**Severity: note.** Location: §2.1.3 and §2.1.5; earlier R3.

```dewy
save = () => {
    sleep(10ms) or_throw
    printl"saved"
}

job = () => {
    let stopped = sleep(1s)
    if stopped is? Canceled {
        protect_from_cancel(1s @save) or_throw
        return stopped
    }
}

main = () => {
    let answer = within(1ms @job)
    printl(answer)
}
```

The parent's already-closed request starts the one-second grace but does not close `save`'s fresh request. In an execution where the 10 ms sleep completes within that grace, `saved` prints. Protection returns its own result, and the explicitly written `return stopped` forwards the outer cancellation afterward. The protected callback captures no cancellation-bearing input, so M1 does not apply. The deadline owner subsequently produces `Timeout`.

**Disposition/fix.** Mark original R3 resolved. Preserve this behavior when implementing M1's transfer check and S1's cleanup adapter; neither repair should reinstate downward cancellation through a shield or fabricate a post-protection cancellation return.

## N3 — Decidable checking is feasible, but lifetime and write bits are insufficient

**Severity: note.** Location: §2.2 structural summary and §2.3 fixed point; earlier N4–N5.

```dewy
forward = <T>(x:T):>T => x

relay = (n:int) => {
    if n >? 0 return relay(n - 1)
    let r = sleep(1s)
    forward(r)
}

main = () => {
    let answer = within(1ms @relay(2))
    printl(answer)
}
```

This is safe same-request transport: recursion and the generic helper keep the producing domain, and the responsible deadline boundary normalizes the result. No blanket prohibition on locals, arguments, collections or type inspection is necessary. A by-place helper writing to a proven same-work local can likewise be allowed. A `$capture @` place must be checked by its actual domain and escape behavior, not confused with a by-value closure environment or automatically treated as globally shared.

A conservative implementation can be demand-driven and decidable as follows:

1. Demand concrete function/type instances from entry and runtime roots, with the existing termination rule for specialization. N/C reachability on the resolved finite graph retains its O(|B| + |E|) bound.
2. Memoize structural cancellation summaries across unions, facets, arrays, recursive records, broad families and closure environments. Distinguish an object's stored data from a method that may produce new cancellation when called later. A plain `@sleep` handle carries no old cancellation merely because its C entry can produce one.
3. Add finite domain-relative parameter, result, capture and receiver summaries: same current work, a caller-owned place, foreign/escaping work, or unknown. Track read/transport and retained-capture paths as well as writes. Apply these summaries at every fresh-request entry and every publication boundary. Use conservative rejection for unknown transfers; do not enumerate arbitrary runtime request identities.
4. Check the normalizable-failure invariant from M2 at failure construction, combination, mutation and automatic cleanup. Projection preserves structural information unless it actually removes the containing data.
5. Check definite assignment and cancellation-refined publication separately, including the continuation paths in M3. Preserve generic specializations and capture types as in S2.
6. Solve recursive summaries monotonically over a bounded abstract domain; use indexed places and finite conservative widening for unbounded shapes. Unknown higher-order calls must use checked summaries or be rejected for the affected transfer, not assumed nonretaining. Seal runtime-only cancellation construction against aliases, descendant construction and generic/reflection constructors too.

These are static origin/domain facts, not runtime origin tags on every value. They are more than the draft's structural type bit plus “writes cancellation” bit. The phrase “no origin tracking” should be qualified accordingly.

**Disposition/fix.** Keep confinement as the design direction, with explicit domain-transfer contracts. State the complexity as CFG transfer work times finite lattice height, plus type normalization, indirect-target analysis and demanded specializations; only context reachability has the simple linear bound. Exact semantic “will this value outlive its work?” inference for arbitrary programs is unnecessary and should not be promised. Conservative region/escape checks are enough. Measure those checks, adapters and emitted bodies on the flagship panel before accepting the runtime/code-size estimates.

## Required resolution

The four must-fixes are independent: M1 prevents foreign-domain input, M2 makes residual publication structurally safe, M3 defines valid continuing block results, and M4 reconciles the flag with the accepted public value algebra. Fixing only the flag does not prove confinement; fixing only lifetime escapes does not cover fresh nested requests. R1 and the original R3 should remain closed while these repairs are made.
