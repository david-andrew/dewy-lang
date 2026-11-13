Verdict: revise before implementation; the restrictions close the original direct leaks, but the stated implementation is not soundly specified.
Must-fix count: 3 — contextual cleanup types, cancellation inside automatic failure stacks, and the protection/join contradiction.
Round-1 status: M1 and M3 remain open through a new counterexample; M2 is conditionally resolved; M4's original counterexamples are resolved.
Decidability and cost: conservative checks are decidable on demanded finite instances; only context reachability has the stated linear bound.
Minimal sound restriction: confine ambient cancellation to its producing request domain, normalize it at boundaries, and retain contextual typing; banning all local data uses and type inspection is unnecessary.

This review covers `brief.md`, `soundness-round1.md`, all of `round2.md`, all thirteen `programs-r2/` files, the requested LANGUAGE sections and decisions batches 3, 9 and 10. Relevant D40–D42, error-combination/storage contracts, task protection contracts and foreign-call rules were also checked. The owner's conversational decisions take precedence. Programs below are self-contained design specimens using the proposed rules, not claims that the current compiler implements them. No programs were executed, no performance measurements were made, and no repository files were changed. References to numbered lines are to `round2.md` unless another source is named.

## R1 — Cleanup changes ordinary types after every `Canceled` has been translated

**Severity: must-fix.** Rules: §2.3 lines 154–175, §2.5 lines 208–210, §2.10 lines 268–285; round-1 M1 and M3.

The original `pack = () => [outcome=sleep(1s)]`, captured-wait-result, and `count_alternatives(wait_value)` specimens are rejected in their cancellable instances. That closes those particular programs. It does not establish that ordinary types are context invariant.

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
    loop t in members(T | string) { n += 1 }
    n
}

probe = () => count_alternatives(value)

main = () => {
    let callbacks = [@pack]
    let a = callbacks[0]()
    printl(a)
    printl(probe)
    parallel {
        let b = callbacks[0]()
        printl(b)
        printl(probe)
    }
}
```

The drop is a fallible cleanup hook under the proposal: its own wait can return cancellation, which the cleanup boundary translates to `Timeout`. Section 2.5 explicitly says a cancellable task's cleanup adds `Timeout`, whereas cleanup in `main` gains nothing. Therefore:

| Expression | N instance | C instance |
|---|---|---|
| `value` | `int` | `int | Timeout` |
| `pack` | `[outcome:int]` | `[outcome:int | Timeout]` |
| `probe`'s generic argument | `int` | `int | Timeout` |
| `probe`'s answer | 2 | 3 |

No actual timeout is needed to observe the last difference. Every parallel item is checked as C even when nothing in this particular block can cancel it. The difference is in the inferred type, just as in round-1 M3. The generic argument contains no `Canceled`; neither record contains it; nothing forbidden by §2.2 is passed, captured, constructed, or inspected. A closure capturing `value`'s result would similarly capture ordinary `int | Timeout`, which is permitted.

This also defeats the claim that an effect bit plus an unchanged result describes every stored handle. `pack` has a context-dependent field without a top-level cancellation to forward. Returning a record containing `Timeout` is a successful result, so its layout cannot be repaired by adding a top-level cancellation tag.

Including `Timeout` conservatively in the N result would be sound, but would reverse §2.5's explicit precision promise. Inferring that a particular hook is too fast to time out is not a sound general solution, nor is it consistent with the syntactic all-items-C policy. The same issue occurs in real cleanup that waits on flushing or closing.

**Suggested fix.** Keep complete contextual result descriptions and typed IR, including cleanup's ordinary failures, for demanded N/C instances. Share machine code only when its behavior and representations agree. A single function containing explicit context dispatch is also possible, but that is additional machinery, not the context-independent body justified in §2.10. The owner already authorized compilation per context; this requires no new surface decision.

Withdraw both “one body, with no exceptions” and the converse “allowing storage requires two bodies.” A common representation plus context dispatch can sometimes share a body even with storage; conversely, forbidding storage of cancellation does not guarantee sharing. The “one move per call, no copy” ABI cost also needs a representation proof and measurement, especially for aggregates and combined failures.

## R2 — Allowed combinations and automatic cleanup contradict “top-level alternative only”

**Severity: must-fix.** Rules: §2.2 lines 113–133, §2.3 line 172, §2.4 lines 183–195, Q2; `docs/design/proposals/errors/combined/round4.md` contracts C3–C5.

Even before considering collections, the permitted result is not always `R | Canceled`:

```dewy
Detail:type = type of error & [number:int]

annotated_wait = () => {
    let r = sleep(1s)
    if r is? Canceled return r and Detail[7]
}

main = () => {
    let answer = within(1ms @annotated_wait)
    printl(answer)
}
```

Its cancellable result can contain `Canceled & Detail`, with an ordinary payload. Replacing that with a bare cancellation tag loses `Detail[7]`. The deadline result must preserve the ordinary facet while translating cancellation. “Canceled occurs only as a top-level result alternative” must at least mean a cancellation component of a result, with a specified accompanying ordinary failure representation. It cannot literally mean adding the singleton alternative `| Canceled`.

The stronger problem uses automatic storage, with no user-written forbidden store:

```dewy
CloseFailed:type = type of error & [id:int]
Owner:type = [
    id:int
    $__drop__ = () => CloseFailed[id]
]

nested = (depth:int) => {
    let owner = Owner[depth]
    if depth >? 0 return nested(depth - 1)
    sleep(1s) or_throw
}

main = () => {
    let answer = within(1ms @nested(2))
    printl(answer)
}
```

Choose an execution where the deadline interrupts the deepest sleep. Unwinding adds three distinct occurrences of `CloseFailed` to the pending cancellation. Repeated failure types require the error stack, not an intersection that silently merges them. C4 explicitly stores pending results in reference-counted storage surviving their frames and links cleanup slots to them. Thus the existing automatic mechanism can carry cancellation inside a stored failure representation even though this source never collects or captures it.

Round 2 must resolve the following fork:

* If its no-storage rule also rejects this automatic operation, an ordinary canceled call with multiple failing owners becomes illegal. That contradicts the promised lossless cleanup and recursive failure storage.
* If the operation is exempt, an ordinary-looking `ErrorStack` cannot conceal cancellation from the no-storage/no-passing checks. Nor can a boundary implement containment by deleting only a direct `Canceled` alternative. It must preserve every `CloseFailed` and translate/remove the embedded cancellation.

The boundary's knowledge that it closed the request establishes ownership of any cancellation component; it does not establish that a returned error contains such a component. A canceled child may handle cancellation and return an ordinary error or success (§2.1.5). Therefore “never needs to inspect the value” (line 133) is too strong: no per-value request identity is needed under confinement, but the boundary still needs a cancellation-presence discriminator and the complete residual result.

**Suggested fix.** Specify one of these representations and its typing, rather than relying on the spelling of the outer type:

1. Keep ambient cancellation in a distinguished internal result component, separate from an ordinary failure/stack payload. Automatic cleanup appends only ordinary failures; public combined-result operations preserve the component until the boundary normalizes it.
2. Permit a compiler-controlled, request-confined failure graph, with a recursive summary that it may contain ambient cancellation and a defined lossless boundary transformation.

In either case, user storage, matching, projections, stack operations and generic instantiation must preserve that fact. A user-created `ErrorStack[c]` remains forbidden under round 2 as written; automatic unwinding requires its own explicit contract. An internal envelope does not require a new public error name or a dynamic origin identity per value.

For parent cancellation, write the complete boundary transformations too: `within`, `parallel` and `task.tasks` preserve retained ordinary cleanup failures beside the parent's cancellation; a later owner consumes/translates only the cancellation component. The table's parent column must not be read as replacing an entire combined result with bare `Canceled`. Q6's whole-result discard is limited to results actually discarded by a result-selecting group.

## R3 — The universal join rule cancels the work that protection promises to shield

**Severity: must-fix.** Rules: §2.1.3 lines 91–96, §2.1.4 line 104, §2.4 line 190, §2.5 lines 208–211; program 12; D41 Q2 and proposal-v5's protection contract.

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

main = () => within(1ms @job);
```

Consider the execution where the outer deadline cancels `job` during its first sleep. The protected call starts with parent cancellation already pending. The protection contract runs `save` on its fresh request despite that cancellation; the 10 ms sleep can complete and print `saved`. It leaves the parent's request pending for the caller's next checkpoint. No cancellation is captured or passed to `save`; forwarding the local `stopped` afterward is explicitly permitted.

But §2.1.3 expressly includes `protect_from_cancel` among joins that close children's requests immediately when the joiner's request is closed. The §2.4 row groups protection with `within` and gives parent cancellation precedence. Following those rules prevents the save and defeats program 12's claim to finish the current job. If the same rule is used to implement cleanup's advertised equivalence to protection, it also defeats the cleanup shield.

**Suggested fix.** Separate protection from `within` in the transfer and boundary tables. Parent cancellation must not close the protected child's request; the protection's own effective deadline may. The caller still joins the protected child, restores its previous request, and receives the child's normalized result. Do not fabricate a post-call cancellation return that discards that result. Define how an enclosing protection deadline bounds nested protection, and how cleanup grace begins when the owning task becomes canceled. These are explicit exceptions to the universal downward-close rule, not exceptions to structured joining.

## S1 — Define the restriction structurally, including selectors, family types and hidden calls

**Severity: should-fix.** Rules: §2.2 lines 111–124, §2.3 lines 165–175, §3's D42 rewrite.

```dewy
identity = <T>(x:T):>T => x

probe = () => {
    match sleep(1s) {
        c:Canceled => {
            let wide:exception = c
            let copy = identity(wide)
            return copy
        }
        _ => {}
    }
}

main = () => within(1ms @probe);
```

Under the intended rule this must be rejected at `identity(wide)`, despite the argument being written as `exception`, not as a union spelling out `Canceled`. Parent-typed storage preserves a descendant's identity (LANGUAGE, Errors as values). An alias, `any`, a broad exception family, an erased interface, or R2's stack representation must not wash the restriction away. A generic type argument can also be a broad family that admits cancellation without explicitly naming it, so line 175's syntactic argument is insufficient.

Conversely, `error` is not the same as `exception`: the documented `Canceled` is an `exception` but not an `error`. The D42 rewrite's `result as error` can exclude cancellation and store the ordinary failure facets. Do not reject that rewrite merely because it processes a combined failure. Programs 09 and 10's `problem:error` arms do not automatically bind bare cancellation either.

A `match` binder holds the whole matched value, including other facets. For `Canceled & Detail`, `c:Canceled => ...` does not reduce the value to bare `Canceled`; it owes the other part under D42. It may forward the whole value or project and handle each part. The no-passing check must inspect the preserved whole type, including hidden receiver arguments, interpolation and operator overloads. Compiler-owned combination/forwarding operations need an explicit exception if their lowering normally calls a function.

There is also a literal wording conflict: §2.2 forbids writing `Canceled` in *any type*, then recommends `c:Canceled`, and permits `as Canceled` and selectors such as `??<~Canceled>`. These all contain type syntax. State the intended prohibited positions: data annotations and explicit stored/parameter types, rather than pattern/selector/projection positions. Otherwise the advertised repair is itself forbidden.

**Suggested fix.** Define a conservative, structural “may contain ambient cancellation” summary over canonical types and value origins, surviving family widening and inferred instantiation. Reject forbidden operations on that summary; allow a projection only when it proves that the retained facets cannot contain it. For broad unknown families, either retain the restriction or require a proven safe subset. Reuse existing narrowing and combination obligations rather than a textual search for `Canceled`.

Closure capture is checked transitively through its environment and nested records, not just the immediate variable's printed type. Under the strict round-2 rule, capturing `wide` in the example is rejected even if the closure will never be called. Invoking a handle that captures no cancellation remains context-sensitive at the invocation site, as intended.

## S2 — Marked signal waits cannot simultaneously drain normally and prioritize cancellation

**Severity: should-fix.** Rules: §2.1.2 line 86, §2.7 lines 228–241, Q3; batch 9's pending-notification and continuation contract.

```dewy
import p"@lib/std/signals.dewy" as signals

main = () => parallel {
    sleep(1ms) or_throw
    $until_others_finish {
        loop _ in signals.sigterm { printl"notification" }
        if sleep(0ns) is? Canceled printl"tail is canceled"
    }
}
```

Once the ordinary item finishes, this marked signal listener satisfies both categories of the trigger. Section 2.7 closes the signal view and the item's request. Section 2.1 gives its cancellation request priority. Consequently the next wait sees cancellation, not normal `Closed<E>`; an already pending notification need not be delivered, and the tail's next wait is canceled. That is coherent cancellation behavior for a marked item, but is not the claimed unchanged batch-9 drain-and-normal-continuation behavior for that same item.

Unmarked listeners can also drain a pending event and resume ordinary work after the cutoff. Canceling all marked items at the cutoff is irreversible. Therefore “essential work is done” means a particular frontier condition occurred, not that no essential code will ever run again. Batch 9 already allows continuations; the new marker must document this interaction. A marked producer may be needed by such a continuation. Banning exported names and locks across waits does not exclude dependencies through a channel, an atomic, or a shared service.

**Suggested fix.** Keep the implementation's existing cancellation priority and explicitly scope the pending-drain guarantee to listeners whose requests were not canceled. State that marking a listener opts it into cancellation, including possible loss of its pending notification. Define closure as a latched transition: publish ready dependents before testing, close views once, request stops once, and never reopen. Alternatively, wait for unmarked signal continuations to finish before canceling marked work, but that is a different policy and needs a new frontier definition. Do not claim both behaviors simultaneously.

This does not reopen the original M4 type hole: affected marked items cannot export bindings, and unmarked listeners still receive ordinary `Closed<E>`. It does invalidate the absolute “batch 9 unchanged” wording for marked listeners and the asserted proof that a marked item cannot wedge essential work.

## S3 — Q6 is a policy change, with winner and strict-mode obligations; Q7 needs complete outcomes

**Severity: should-fix.** Rules: §2.4, §3 lines 300–302, Q6 lines 398–414, Q7 lines 416–428; programs 03 and 11.

```dewy
CloseFailed:type = type of error
Owner:type = [ $__drop__ = () => CloseFailed ]

candidate = () => {
    let owner = Owner[]
    7
}

good = () => { sleep(1ms) or_throw; 9 }

main = () => {
    $explicit_cancellation
    first_ok(@candidate @good) or_throw;
}
```

`candidate`'s complete result is `CloseFailed`, not the body value 7. `first_ok` must decide success after the candidate's cleanup has completed; it must wait for `good` rather than elect 7 and classify the winner's failed cleanup as a discardable loser result. If every candidate fails, the selected first failure also includes that candidate's cleanup. An ordinary failure can precede any cancellation, so `$explicit_cancellation` cannot rely solely on the caller being C when checking this discard policy.

The unqualified Q6 says the strict tag makes the call an error when its work can lose a cleanup failure. Section 3 introduces that check with “in cancellable code,” which would exempt the root call above. Make the check depend on what the invoked group can discard, even in N. Also specify whether it applies to cleanup failures already handled within the work and to summaries of indirect callees; otherwise “handle it inside the work” has no stable acceptance rule.

Discarding losers' complete results is type-safe once explicitly specified, but is not logically entailed by `Canceled` being confined. It is a policy choice about losing ordinary failures. A group can discard a non-canceled loser, and `first_ok` can discard earlier failures after finding a success. D42's current syntactic part-discharge rule must explicitly recognize that boundary contract; saying the operation “names” every possible part is a proposed extension, not a proof from the existing selector rule. Debug logging adds formatting and output costs and cannot substitute for the strict check.

Q7's changes are likewise separable choices:

* Removing cancellation from non-waiting `try_*` operations is coherent. Code relying on them as its only checkpoint must add `check_cancel()`; they no longer promise cancellation responsiveness.
* Discarding a canceled send's moved payload is not required to identify its request. It is an ownership/API choice. State when its drop completes even when the caller handles cancellation and keeps running; whole-value operations should finish their owned cleanup before returning. Preserve any drop failure beside cancellation under R2. `reserve` needs a cancellation-safe permit/commit lifetime, not just a source rewrite.
* Consuming a stopped child's cancellation in `Task.wait()` is sound with confinement, but does not consume cancellation of the waiter. Apply this to every authorized wait of a stopped task, including a wait with no immediately preceding `stop()`; clarify wait-handle transfer rules if ownership restricts such calls.
* Reading `.running` before `stop()` (line 203 and program 13) observes one instant. The child may finish between the read and the stop; it does not distinguish natural completion from a successful stop atomically. Narrow the claim rather than adding an API solely for this example.
* The marked-item `or_throw` exemption must preserve and forward an accompanying ordinary failure after its cancellation component is consumed. A `Canceled & CloseFailed` is not an ignorable bare stop.
* Removing the three-press exit does not affect type soundness. It changes shutdown policy and cannot establish that cooperative cleanup terminates.

**Suggested fix.** Separate these policies from the soundness argument, define winner selection at complete-result publication, make the strict discard check context-independent, and state combined results and resource ownership for every changed operation. No additional unapproved surface is necessary for these clarifications.

## S4 — Foreign callback ABIs are not effect-permitting Dewy function slots

**Severity: should-fix.** Rules: §2.3 lines 156–168, §2.10's result convention; LANGUAGE, Foreign functions, especially `$export` callbacks.

```dewy
$extern
qsort = (base:ptr<int32> count:uint64 size:uint64
         compare:((a:ptr<int32> b:ptr<int32>):>int32)):>void

$export
compare = (a:ptr<int32> b:ptr<int32>):>int32 => $unsafe {
    sleep(1ms) or_throw
    if a[0] <? b[0] -1 else if a[0] >? b[0] 1 else 0
}

sort = () => $unsafe {
    let xs:array<int32> = [2 1]
    qsort(xs.ptr 2 size_of<int32> @compare)
}

main = () => within(1ms @sort);
```

The written callback type contains no `Canceled`, and passing a handle is explicitly allowed. Nevertheless a synchronous callback executing in the sorting task can reach a cancellation point and try to forward its cancellation through an `int32` C return slot. C's `qsort` knows nothing about an added result tag. A foreign callback invoked later or on another thread also needs an entry-context contract; reachability through ordinary Dewy calls alone will not discover it.

This is not evidence of a hole in safe code: the boundary is explicitly unsafe and existing FFI checks may reject the callback. It is a missing compatibility rule in the proposal's universal function-slot and one-body claims. A known ABI mismatch must not be silently manufactured by adding an inferred effect to a fixed C signature.

**Suggested fix.** Fixed foreign ABIs cannot propagate the implicit cancellation result. Reject such exported callbacks, or require a checked adapter that consumes/translates cancellation to the actual foreign protocol. Register foreign entry roots and trusted context-transfer contracts explicitly. Ordinary C return codes cannot manufacture `Canceled`; only a trusted runtime operation may interpret them as the current request's cancellation. Arbitrary unsafe fabrication remains outside the safe-language theorem. No generic foreign-call analysis can prove arbitrary external code's behavior.

## N1 — Round-1 M2: the direct foreign-request leak is resolved, conditionally

**Severity: note.** Rules: §2.1 lines 75–77, §2.4, §2.6 lines 217–221.

```dewy
import p"@lib/std/tasks.dewy" as task

Envelope:type = [request:task.CancelRequest]
publish = (out:Channel<Envelope>) => {
    out.send(Envelope[task.cancel_request]) or_throw
    sleep(1s) or_throw
}

main = (app:BackgroundTasks) => {
    let out = channel<Envelope>(1)
    let child = app.spawn(@publish(out))
    let message = out.receive or_throw
    child.stop()
    child.wait() or_throw
    let waits = [@message.request.receive]
    let answer = waits[0]()
    printl(answer)
}
```

After the stop/join, the final receive in N gives `Closed<task.CancelRequest>`, not `Canceled`. Passing the handle through a record and closure does not change that. Racing this receive, using it in `first_ok`, or putting it under `within` can return the ordinary `Closed` outcome; no type is incorrectly narrowed. Reference-counted request storage addresses the old lifetime problem.

No alternative safe counterexample based solely on foreign requests survives these rules. The proof requires that every runtime producer emits cancellation only for its executing request, every closure/data path obeys confinement, and every fresh-request boundary normalizes before publication. R2 specifies the missing automatic-storage case; R3 specifies protection's missing transfer rule. With those repairs, boundary-owned request state plus a cancellation discriminator is sufficient; a request identity on every failure value is not necessary. The runtime still needs request identities to route closes and distinguish parent/deadline state—“no origin tracking” does not mean no request state exists.

**Suggested disposition.** Mark old M2's explicit manufacture and foreign-request cases resolved, subject to those implementation invariants; do not claim the entire containment theorem already follows from a syntactic ban on user stores.

## N2 — Round-1 M4: the original narrowing and pre-winner holes are resolved

**Severity: note.** Rules: §2.4 lines 197–204, §2.7 lines 228–241.

```dewy
import p"@lib/std/signals.dewy" as signals

listen = () => signals.sigterm.next
main = () => {
    parallel (
        let event = listen
        sleep(0ns) or_throw
    )
    printl(event)
}
```

Normal signal-only closure gives `Signal | Closed<Signal>` here. It does not close the essential listener's request. If another item instead exits the enclosing function, this continuation is skipped. A marked version exporting `event` is rejected. Thus the original M4 counterexample does not survive, assuming item-escape checks also cover dependencies and indirect publication of a possibly canceled value.

```dewy
import p"@lib/std/signals.dewy" as signals

main = () => {
    let answer = race(@signals.sigterm.next @signals.sighup.next)
    printl(answer)
}
```

Outside an owning parallel block, root signal subscriptions do not auto-close. This race waits for a signal, not a fabricated cancellation winner. Inside an owning block that reaches signal-only quiescence, the children may return ordinary `Closed` outcomes, which are valid results of the race. `first_ok` can report an ordinary first failure if all close. A timeout-bearing wait remains ordinary frontier activity; a nested explicit owner must close its own views.

**Suggested disposition.** Mark the two original M4 defects resolved by the signal/owner rules and static marked-item escape restriction, not by “control, not data” alone. Keep S2's overlapping marked-signal case explicit. Retain §2.1.5: request closure neither forces a cancellation result nor proves termination.

## N3 — `task.tasks` is consistent if it normalizes before publishing the body result

**Severity: note.** Rules: §2.1.4 line 102, §2.3 lines 147 and 163, §2.4 line 194.

```dewy
import p"@lib/std/tasks.dewy" as task

Broken:type = type of error
slow = () => { sleep(1s) or_throw }
fail = () => Broken

main = () => {
    let answer = task.tasks((group:Tasks) => {
        group.spawn(@slow)
        group.spawn(@fail)
        sleep(1s) or_throw
        42
    })
    printl(answer)
}
```

The body and both spawned tasks execute in C. A child failure cancels the body and siblings, drains them, and returns `Broken` with any retained cleanup failures. The body's resulting ambient cancellation is not a generic `R` value published to `main`. If the body instead returns 42 successfully, that normal return joins remaining children. A spawn racing with shutdown must inherit the already closed group request or be rejected by the group's admission protocol; it must not create uncanceled orphan work.

`task.tasks` and other runtime boundaries are privileged result consumers. A literal application of “no passing cancellation” to their internal result transport would make them unimplementable, just as in R2. The compiler/runtime contract must distinguish normalization transport from ordinary user arguments.

**Suggested disposition.** No additional source-level counterexample is needed here. Specify this normalization, late-spawn behavior and full ordinary-failure preservation; test with R2's nested failing owners as children and body cleanup. Do not add a third ambient context just for task groups.

## N4 — A smaller sound restriction exists

**Severity: note.** Rules: Q2's necessity claim, §2.2, §2.10; the binding preference for ordinary error values and exceptions that earn their keep.

For ambient-only cancellation without per-value runtime origin tracking, the needed invariant is **request-domain confinement**, not “never data”: only the active request can produce ambient cancellation; a value containing it cannot move into another request domain or outlive normalization by its responsible boundary. A task can enter a new request domain during protection or cleanup, so “same task” alone is insufficient.

For example, this is forbidden by round 2, but a checked same-request helper can safely support it:

```dewy
forward = <T>(x:T):>T => x
wait_and_forward = () => {
    let r = sleep(1s)
    forward(r)
}
main = () => within(1ms @wait_and_forward);
```

`forward` does not retain the argument, capture it into escaping code, send it, or enter a new request domain. Its returned value has the original domain and type. The boundary translates it just as it would translate a direct `return r`. A conservative parameter/result summary establishes this without dynamic request identities per value.

| Restriction | What it buys | Smallest useful relaxation |
|---|---|---|
| No construction | Prevents a cancellation with no closed producing request under the ambient-only contract. | Keep it for ambient cancellation. Ordinary synthetic cancellation would need distinct intrinsic/data provenance and cannot be erased as an owner stop. |
| No outer storage or sending | Prevents publication beyond the request boundary and into other tasks. | Keep the confinement requirement. Permit only proven storage within the same request lifetime; otherwise retain data provenance and conservative types. |
| No fields, elements or sequential collections | Avoids deeply context-dependent types and escape checking. | Permit request-confined aggregates whose types preserve cancellation and which cannot escape. This needs contextual typing, already required by R1. |
| No capture | Prevents a closure from transporting an old cancellation into a new execution context. | Permit proven nonescaping, same-request captures. Do not retype captures at the later call site. |
| No arguments | Avoids parameter escape/effect summaries. | Permit checked same-request, nonretaining calls such as `forward`; reject unknown summaries conservatively. |
| No written types | Prevents annotations from pretending a context-dependent alternative is unconditional, and simplifies the chosen effect surface. | The blanket ban is unnecessary for safety. Types/selectors do not manufacture values. Validate contextual contracts and preserve containment independently. The annotation policy remains a surface choice. |
| No type inspection | Removes some reasons N/C bodies differ. | Permit it on contextual typed instances. Inspection does not transport cancellation. Specialize or dispatch correctly; sharing is an optimization. |
| Foreign requests return `Closed` | Gives a storable, nonambient notification without cancellation provenance. | Keep this inexpensive distinction; no special storage ban is needed for `Closed`. |

If ordinary persistent `Canceled` values are desired, a second sound design allows them, keeps their types everywhere, and never erases them merely because a group has stopped. It needs a distinction between ambient propagation and independent data, using provenance or conservative summaries. It does **not** require a new public spelling. Whether that machinery is worth it is a design choice; the blanket restriction is not the only sound option.

**Suggested disposition.** Adopt the confinement invariant and contextual typing as the semantic contract. A first implementation may conservatively reject more escaping cases, but label those as implementation limits, not logically unavoidable restrictions. There is no uniquely smallest syntactic ban independent of the representation and analysis chosen.

## N5 — Decidable, demand-driven checking is feasible; the linear claim has a narrow scope

**Severity: note.** Rules: §2.3 lines 158–168 and §2.10's cost paragraph; round-1 S1.

```dewy
even = (n:int) => {
    if n <=? 0 return 0
    sleep(0ns) or_throw
    odd(n - 1)
}
odd = (n:int) => {
    if n <=? 0 return 0
    even(n - 1)
}
main = () => {
    printl(even(4))
    printl(within(1s @odd(4)))
}
```

This demands at most N and C nodes for each of the two concrete functions. No third context or dynamic request enumeration is needed. The finite graph reachability claim is correct, provided generic specializations and indirect-target summaries are already finite. R1 demonstrates why that reachability bit is not the entire type analysis.

A conservative implementation can work as follows:

1. Demand bodies from actual roots, including runtime cleanup and foreign callback entries. Resolve ordinary type/effect instances using the existing specialization termination rules.
2. Propagate N/C reachability over the resolved graph. This part costs O(|B| + |E|), up to the constant two-context expansion.
3. Compute structural may-contain-cancellation summaries, including combinations, stacks and broad family values. Solve recursive summary SCCs monotonically over a bounded abstract domain. Use conservative rejection when a summary is unknown; do not try to prove arbitrary runtime reachability.
4. At affected operations, apply existing narrowing plus the restricted-use checks. For the smaller restriction in N4, add bounded region/escape summaries for parameters, captures and returns; these are extra work, not free consequences of an effect bit.
5. Type-check demanded contextual instances, including cleanup-derived ordinary failures and type-directed generic operations. Share emitted bodies only after equivalence of the required behavior and representation is established.

For a fixed finite type graph, a recursive containment summary can be memoized per type/instance and solved by a finite worklist. Flow-sensitive checking costs its CFG transfer work times the abstract lattice height; failure-part obligations already have their own occurrence/bitset costs. Existing subtype, intersection and complement normalization costs remain separate. Do not promise O(|B| + |E|) for all of this, nor that allowing local aggregates makes checking undecidable.

Signal quiescence is runtime bookkeeping, not a static proof that code eventually stops. Its ownership tree needs indexed frontier counts and updates on task creation, parking, wakeup and publication; account for the cost of updates through nested owners. None of the cancellation rules proves that a CPU loop or a blocking foreign call terminates.

Incremental edits need invalidation in both directions: new context demands flow to callees, but changed result/effect summaries must reach callers; deleted edges can retract reachability and require SCC recomputation. Lazy hover predecessor links are appropriate. The flagship panel must measure contextual checking, cleanup/type summaries, emitted size, adapters and quiescence bookkeeping before any cost promise is accepted.

**Suggested disposition.** Retain the finite two-context reachability design. Correct the scope of the cost claim, repair incremental invalidation, and use conservative finite summaries. No new proof of general-purpose program termination is necessary.

## Round-1 disposition

| Original must-fix | Strongest round-2 result | Disposition |
|---|---|---|
| M1: a bit cannot describe aggregates/callables | Direct cancellation aggregates are rejected, but R1 stores ordinary cleanup `Timeout` in a context-dependent field. R2 also requires a richer combined-result representation. | Not resolved. |
| M2: ambient versus foreign/data origins | N1's foreign request yields ordinary `Closed`; explicit manufacture and escaping captures are rejected. Automatic cleanup still needs R2's representation invariant. | Direct cases resolved; containment conditional. |
| M3: one body changes generic semantics | The old direct-cancellation generic argument is rejected. R1's argument contains only `int | Timeout` and still changes `members` results. | Not resolved. |
| M4: incidental shutdown breaks narrowing/winners | N2's unmarked signal result keeps `Closed`; root winner groups are transparent; marked items cannot export bindings. S2 concerns the new overlap policy, not the old missing-winner proof. | Original cases resolved. |

The three required repairs are R1–R3. The smaller sound rule is request-domain confinement plus complete contextual result typing and boundary normalization; all the additional bans in Q2 need a cost or implementation justification of their own.
