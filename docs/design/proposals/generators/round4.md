# Generators and multi-values, round 4

This delta replaces the affected rules in rounds 2–3. Recommend **one owned value per advance**, a borrowed loop for a single pull, and `generator<T failure=E>` for a cursor. Remove the generator's flat `.next` and public `length=`. D44 determines what a *consuming loop* does with cancellation. An adapter that promises to forward a stream must preserve the upstream terminal outcome all the way to that consumer. [Round 3](round3.md) · [Soundness review](review-soundness-r3.md)

## 1. Cancellation at a source loop

```dewy
map = (source f) => lazy loop x in source or_throw { f(x) }

save = (source journal) => {
    let n:int = 0
    loop token in map(source @id) or_throw {
        journal.write(token) or_throw
        n += 1
    } else {
        return journal.commit_empty() or_throw
    }
    return journal.commit(n) or_throw
}
```

On cancel before the first token, both source suffixes forward the task's actual failure. Neither commit runs. After two tokens, the two writes have happened and neither commit runs. At genuine EOF, exactly one commit runs. `child...` in a streaming body forwards in the same way. If a child fails, the parent unwinds before reaching a following child or success tail. Scope exits can add cleanup failures.

| What the source delivers | Plain consuming loop in an ordinary function | With `or_throw` after the source |
|---|---|---|
| An item, including a legal `none` or exception payload | Enter the body | Enter the body |
| Clean end | End the loop. Enter `else` if the body never ran | Same |
| This task's pure `Canceled` | End quietly in the same canceled task. The usual zero-turn fallback and subsequent code can run | Skip fallback and following code. Forward the actual cancellation to the enclosing function or active lazy advance |
| Ordinary terminal failure or cancellation combined with an ordinary failure | A generator source with this possibility requires a forwarding suffix | Forward the **whole** failure after cleanup |

The quiet stop follows D44, including the consequence for an *unguarded* consumer like the review's `save`. A library cannot stop arbitrary code after a deliberately quiet loop from committing. Put the suffix on a consumer whose success action requires clean traversal. For a partial-progress consumer, code after an unmarked loop can still observe cancellation and use the prefix. Here the counter update is local and there is no side effect in a zero-turn fallback.

```dewy
show_progress = (counts:Channel<int> ui) => {
    let total:int = 0
    loop n in counts { total += n }
    let status = check_cancel()
    if status is? Canceled { ui.show_partial(total) return status }
    ui.show_total(total)
}
```

The checkpoint asks whether the current request is canceled **now**. It can also see a cancellation that arrived after EOF. For the outcome of the pull itself, use the forwarding loop. A later traversal of a cursor whose failure was already handled sees end. A consumer that also needs to detect a *previously* canceled task can check its request before publication. Neither check makes publication atomic with a later cancellation. This rule adds no poll to a pure yield, no remembered failure in a finished cursor and no transferable cancellation value. The advancing task lends its own context to a wait. D44 still controls which call sites can cancel, who can hold the value, and how a group consumes its own cancellation. [D44 Q1–Q2](../../../../docs/design/open_decisions.md:62) · [D44 Q5 and its publishing example](../../../../docs/design/proposals/cancellation/round6.md:88) · [D41 checkpoint](../../../../docs/design/open_decisions.md:230)

**Version 1 check for producer code.** Inside a `lazy` body, require `or_throw` on a source clause whose advance can report cancellation or ordinary terminal failure. Check the body against the contexts where it may run, including an unknown generic upstream. Diagnose the review's unmarked generic `map` at `in source`; the fix is the first line above. A proven pure range or array still admits `lazy loop x in xs x`. An ordinary helper deliberately consuming a partial result retains D44's quiet form and may return that application result to its caller. The checker does not promise that arbitrary callbacks are transparent adapters. This restriction is a proposed generator rule, not a change to D44's behavior for accepted plain loops. It avoids inferring whether a user method called `commit` publishes something.

Finish releasing tentative items and loop-owned sources on an exit before entering a fallback or continuing the caller. Keep the actual stop reason until that cleanup finishes. Even on a quiet stop, if disposing a different header owner fails, report cancellation combined with the cleanup failure through its checked receiver. Only a pure cancellation can be consumed quietly. A borrowed source remains owned by its caller.

In an `and` header, each source clause has its own suffix. `loop i in [0..n) and x in upstream or_throw { x }` checks the left budget first on each turn and forwards right-side terminal failure. If both can cancel, write `a in left or_throw and b in right or_throw`. The suffix is allowed on a source proved infallible. Evaluating a fallible factory before iteration still needs its own ordinary handling. A zero budget makes no right **pull**, even though source operands are evaluated once at entry. Finishing a limit before an unrequested upstream failure is successful completion of the prefix operation. It claims nothing about upstream EOF.

## 2. One protocol for generator iteration

Dispatch by the checked source kind. A built-in generator supplies an **internal** three-way result to the loop or delegating parent. Only the item arm binds the body pattern. The end arm runs the normal end path. The failure arm applies the source policy in §1. The discriminant belongs to the handoff, so an element of type `Bad` and a terminal failure of that very same type remain distinguishable. A clean end is never represented to Dewy code as a successful `none` item. Reading a finished cursor through a borrow gives end.

A generator exposes **no** `next` member and does not satisfy the legacy structural iterator protocol. A plain generator loop moves its owner, and `@g` borrows it. A conventional copyable iterator with `next` still follows the guide's copy/step-until-`none` rule. The source kind and transfer convention survive record fields, imports and generic lowering. An erased source can use a checked iteration entry carrying these semantics. If the callee knows only the legacy `next` interface, passing a generator fails at the boundary. For a union without a common checked iteration contract, narrow first. No fallback from an unknown generator to calling a method named `next`. [Legacy iterator contract](../../../../docs/LANGUAGE.md:5014) · [Prior generator ownership rule](round2.md:63)

For one demand use `loop t in @g or_throw { … return … }` inside a helper, or leave its body with `break` and resume later. The helper can translate the clean end into the caller's domain. In the parser it returns a grammar end position or a token; an ordinary failure exits the helper. In monitor replay, a delivered `none` still clears the measurement. A search for `g.next` on a generator should offer the borrowed-loop form. This replaces round 3's disjointness test for **all** element types. [Parser](programs-r1/05-port-rules-r4.dewy:37) · [Monitor replay](programs-r1/10-monitor-replay-r3.dewy:20)

## 3. What a cursor type can promise

**Arity.** Remove written `length=N` and all exported length or ordered-prefix proofs. A parameter, field, factory result or merged control-flow path carries no proof of remaining positions. A direct generator spread into a positional call has one small v1 case: a fresh `lazy` with a statically fixed, straight-line list of visible contributions, written directly at the spread or introduced by a same-block local whose sole use is that spread. Flatten nested grouping under A and check every position against the selected signature. Use existing fixed-width, ordered result types at eager entries. Reject control-dependent widths, loops, delegation, unbounded expressions without a proven finite traversal, and sources with possible terminal failure or cancellation at this drain. No evaluation to discover arity. A permitted spread must also meet the ordinary rules for effects and abandoning any initialized arguments. The call still waits for successful terminal cleanup. Otherwise collect the finite input with `[loop x in g or_throw x]`, establish the materialized array's shape under existing rules, then call. Collecting runtime-sized input can allocate.

Thus `let g = lazy (20 22)` followed only by `add(g...)` works. A one-turn borrow followed by `add(g...)` fails the sole-use test. Moving that suffix to `pair(g:generator<int64>)` does not restore the proof. A two-element materialized tuple can cross the call boundary with its shape intact. This deliberately gives up some provable factory spreads to eliminate a cross-module position analysis. [Earlier positional drain and evaluation order](round2.md:53)

**Failure.** Check both sides of every cursor annotation, conversion and exported result: T admits every item, and E covers every *ordinary terminal outcome*, including completion and abandonment cleanup and their possible combinations. In a written `generator<T>`, E is empty. A factory returning that type whose lazy body says `read_int() or_throw` fails typechecking if the read can give `ReadFailed`. If the factory itself opens a resource *before* `lazy`, the open failure instead belongs to the factory call. A possible cancellation is inferred at an applicable call site. Its ordinary cleanup facets are still owed even when the written E excludes cancellation. Forward the combined value intact. D42's ability to select a facet does not by itself discharge another facet at a result conversion. [Earlier failure bound](round2.md:81) · [D42 conversion rule](../../../../docs/design/open_decisions.md:290)

## 4. Captures, relocation and re-entry

**Construction owns the snapshot.** At creation, copy each free local if copying is allowed, otherwise move it at its legal last use. Effects of source expressions in the body occur when control reaches them. Thus the capture in `lazy loop row in sock.rows() or_throw row` transfers the socket at `lazy`, and the first demand calls `rows()` on that captured socket. A later `let other = sock` is a move error. Capturing a scalar n = 1 and assigning n = 2 outside still yields 1. A fresh cursor's disposal releases its captures, including a socket it never read. A body-local `connect()` instead waits until demand. A failed construction disposes each initialized capture once. The review's alternative reading of lookup is refuted by the explicit snapshot rule. [Round 2, body evaluation](round2.md:28) · [Round 2, capture and partial construction](round2.md:69)

**No surviving loan into a movable generator frame in v1.** Reject a suspended child, callback, pending item, iterator or cleanup object that stores an address into that frame or into storage whose stability depends on that frame's current placement. Containment proves lifetime alone. External loans still need a separately proved stable base, lifetime and exclusive access throughout. A child may own an integer index and a value snapshot or stable owning handle to its tree. Compiler-managed references to a generator's own locals, including a registered defer reading a counter, are slot numbers resolved against the *current* frame when code runs. They cannot be exposed as stored addresses. Lower a suspended built-in array traversal with owner and index, or reject a representation whose stability cannot be proved. An optimizer that boxes or fuses a particular case must preserve v1 source legality. The asset-tree rewrite passes a child ID by value. [Existing stability obligation](round2.md:73) · [Asset tree](programs-r1/04-asset-tree-r4.dewy:14)

The review's literal first pull yields `node.value` before the child exists, and its `walk` declares a value parameter for a call spelled with `@`. The real regression test uses a place-taking child, advances into that child, then attempts the parent move. Reject the surviving loan at suspension even if no move happens in that particular caller. [Streaming order](round2.md:30) · [Place parameters and calls](../../../../docs/LANGUAGE.md:579)

**Re-entry is a compile error.** The current owner is exclusively borrowed during resume and disposal, including callbacks and cleanup. An iteration loan of `@g` also excludes another step before that loop exits. Moving g into `box.g` consumes g. In the repaired review example, where both calls instead use the box, reject a callback path that could reach the active field. A callback whose access to the same shared owner cannot be excluded is insufficient proof. A callback passed another independently owned cursor is fine. There is no run-time busy result, transition to finished or cleanup from a rejected program. [Exclusive-place rule](round2.md:65)

## 5. Cleanup when control leaves

| Review witness | Which action runs and when |
|---|---|
| Unlabeled producer `break` followed by `complete = true` | It exits the inner loop; the assignment runs. This is the specified control flow. For a producer limit that means partial, prefix the `lazy` with `$done` and use `break $done` to skip the assignment. If abandonment occurs while suspended, the assignment is never reached. [Round 2, control](round2.md:45) |
| `loop token in @stream` breaks, then `finish_preview()` | Breaking releases the loan and leaves a resumable owner. A later operation requiring prior publication must **own** the traversal or obtain the result of a function that owns and disposes it before returning. A borrower has no such ordering guarantee. The timing example in round 3 already used the owning form. [Round 3, transfers and stops](round3.md:39) |
| Zero budget versus empty upstream | A body-local `defer` is registered on execution. Fresh drop releases captured owners only. When *each successfully reserved request* owes a journal entry, reserve in the ordinary factory, wrap the reservation immediately in a ticket with an infallible hook, and move it into the frame at construction. At first demand move it into a writable local. A fresh drop records (0, partial); a genuine upstream EOF records (0, complete). A zero budget never opens the session. A failed reservation creates no ticket. [Round 2, fresh disposal and registration](round2.md:91) · [Revised reply](programs-r1/01-reply-r4.dewy:16) |
| Left row acquired, right ends, fails, quietly cancels or its guard rejects | Left has advanced. Release each tentative item once, in reverse acquisition order; no body owns it. In v1 reject a combined header if an item in a tentative prefix could require **fallible** disposal before a later clause accepts it. Give the diagnostic at the earlier binding. An ordinary fixed scalar qualifies. For a resource row, bind it in a written outer scope and use a nested one-turn borrowed loop for the partner. Let a D40 checked receiver own the row, e.g. transfer it to a function that owns it and returns before the outer loop continues. The source suffix cannot assume responsibility for an unmatched item's close. A fully matched body still has its ordinary ownership duties. [Earlier zip rule](round2.md:59) · [D40 locally continuing exits](../../../../docs/design/open_decisions.md:519) |

**One cleanup authority.** Natural end, terminal failure and destruction enter finalization under the exclusive owner. A successful item handoff suspends the frame with its live duties intact. Mark a duty discharged *before* calling its hook. Transfer clears the old slot's ownership bit; matched items transferred to the consumer cease to be prefix temporaries. Unwind the active child first and then the parent's outstanding duties in the existing lexical order. Attempt all remaining duties after a failure, combining failures by D42. Mark each cursor **finished before delivering its terminal outcome to its caller**. Any later disposal of that finished cursor releases inert frame storage only. Thus a child read plus failed close is reported once on that advance; the parent's unwind cannot re-run the child's close. A moved-from shell has no cleanup authority either. The existing D40 return boundary receives a failed drop of a suspended owning parameter. The same terminal boundary handles a tail loop whose owner scope exits directly from the lazy body. A possible fallible drop at a *locally continuing* exit still needs checked consumption or D40's marked scope; otherwise reject the path. [Round 2, discharge and unwind](round2.md:87) · [Round 3 socket return boundary](round3.md:64) · [D40 accepted function-result rule](../../../../docs/design/open_decisions.md:492)

A defer inside a lazy body remains provisional under D40 Q5. It reads live frame state, cannot suspend, fail or perform a nonlocal transfer, and has no effect before registration. A resource obligation already incurred when constructing the frame belongs to a captured owner. For the socket helper that owns its cursor, successful UI completion remains after successful disposal; read, display and close errors combine on the path where each occurs. [D40 one-off restoration](../../../../docs/design/open_decisions.md:540) · [Socket workload](programs-r1/11-inventory-socket-r3.dewy:13)

## 6. Which counterexamples actually follow from the old rules

The following distinctions matter for regression tests.

- **Review §2 — the illustrative loop.** The dispatch collision was real, but the written program could not produce its claimed trace under round 2. The semicolon discards the 1, and a generator with possible ordinary terminal `Bad` requires a source suffix. Use `lazy { 1 Bad[0] or_throw }` and `loop x in g or_throw { printl(x) }` as the positive regression: print 1 once, then leave the consuming function with Bad. Also test `lazy { Bad[0] Bad[0] or_throw }`: the body receives the first Bad, and the second exits through the terminal edge. [Semicolon rule](../../../../docs/LANGUAGE.md:1549) · [Round 2, handling a fallible source](round2.md:77)
- **Review §6 — the parser.** Bare ordinary `or_throw` can forward `none`; the risk in the flat API was real. The round 3 separator used **typed** `or_throw<BadPortSyntax>` at both sites, as did the required-number read. A final valid interval did commit. Removing the flat API removes the need to choose a selector for a generator end. Ordinary postfix handling of an application's own value keeps its existing meaning. [Required number](programs-r1/05-port-rules-r3.dewy:35) · [First separator](programs-r1/05-port-rules-r3.dewy:47) · [Second separator](programs-r1/05-port-rules-r3.dewy:52)
- **Review §6 — the eager print.** The reported trace is correct and intentional. An ordinary helper that returns a fixed pack finishes its print and computes both results on the first demand. After transfer of the first field, the frame owns the second. An early drop releases it and cannot undo the print. Write the group directly in the streaming body or delegate to a lazy helper when the print must wait for the second pull. This is a boundary between evaluation and handoff under both A and B. [Round 2, side-by-side demand traces](round2.md:32)

## 7. Contracts across a module boundary

Check a producer once against a compact interface. The written item and failure types come first. The compiled interface preserves the source kind and move convention, a verified sendability bit, and separate upper bounds for constructing, advancing and disposing (ordinary failure, potential cancellation point and existing effect/cost restrictions). Construction facts belong to the factory signature; cursor facts travel with the cursor. Derive sendability over *every possible suspended state*, including a child, pending field, deferred duty and captured callback. A callback's ordinary place-access contract must prove exclusivity at an indirect call; unknown access to a reachable active owner is grounds to reject. Erasure may forget precision, never an obligation. For example, an imported cursor whose interface establishes no sendability may iterate locally, but cannot enter another task. A plain written E with no phase refinement is possible both on advance and on disposal.

Use the existing D42 type checker on whole known outcomes. For opaque or large compositions keep a conservative upper bound on ordinary facet families, possible co-occurrence and repeated failures (including the D42 stack form). Check an exact small outcome when available; otherwise accept a broad bound only if **all** outcomes it summarizes can travel intact under that type. Reject an unproved narrow annotation. Never silently project `ReadFailed & CloseFailed` to a lone read error. Preserve the actual combined value at runtime. Keep work-local cancellation outside an ordinary error stack and apply D44's group rules. With flat stepping removed there is no item/failure disjointness analysis and no reason to enumerate a powerset of cleanup failures. [D42 family coverage](../../../../docs/design/proposals/errors/combined/round8.md:223) · [D44, stacks and cleanup](../../../../docs/design/proposals/cancellation/round6.md:153)

Opaque call sites consume interfaces, never reopen an adapter chain. Compose from direct callees' summaries, and widen unknown or recursive facts before accepting restrictive annotations. The local control construction still visits each demanded body node, CFG edge and explicit fixed-pack slot once, apart from existing type, borrow and effect checks. Limit positional analysis to §3's syntactic case; export no position facts. A shared erased resume/dispose entry per necessary item ABI and ordinary Dewy instance suffices. Fuse a small known nonescaping producer into its consumer when proven equivalent. Cap fusion work per consuming site; crossing an opaque boundary uses the shared entry. Neither proof nor code-generation keys may grow into a distinct adapter type for every upstream chain. [Round 2, lowering and compile-speed budget](round2.md:127)

**Alternative B takes the same fixes.** Its entry grouping, fixed-width alternatives, callback rules, eager evaluation and forwarding of whole rows are as in round 3 Q1. Replace its manual step rule with the same borrowed loop: the binder receives one complete contribution, including a mixed-width step-local view when necessary. Distinguish a two-field row from a singleton whose value is a tuple by that existing step shape. Apply §3's fresh spread proof to the *concatenated positions* of the visible fixed rows. B has no public count and no flat step for any width. Its tentative prefix owns every field of the complete left step and is subject to §5's fallible-drop check. [Full entry and row rules](round3.md:125)

## Workloads and remaining gates

| Revised program | Behavior exercised |
|---|---|
| [01 Reply journal](programs-r1/01-reply-r4.dewy) | The factory reserves before returning. A zero limit still publishes a partial record before the preview finishes. At the exact limit the program cannot certify upstream EOF without another pull; it records partial. |
| [02 Access log](programs-r1/02-access-log-r4.dewy) | The generic path source forwards its terminal outcome before an empty-state UI can run. The independent line-reader API still distinguishes its own EOF from read failure. |
| [04 Asset tree](programs-r1/04-asset-tree-r4.dewy) | A parent retains its index across suspension and passes the child ID by value. Relocation requires no repair to an element loan. |
| [05 Port parser](programs-r1/05-port-rules-r4.dewy) | One borrowed turn returns a token. At clean end a local grammar value carries the missing token's byte offset. Valid EOF commits; missing number, reversed range or lexer failure leaves the old configuration installed. |
| [06 Retry preview](programs-r1/06-retry-preview-r4.dewy) | Generic take forwards a failing or canceled right pull. The concrete retry source is pure. Once the left budget ends there is no extra right pull. |
| [07 Meter pipeline](programs-r1/07-meter-pipeline-r4.dewy) | Both generic adapters forward. Chart completion is behind the consumer's checked loop. |
| [08 Ledger zip](programs-r1/08-ledger-zip-r4.dewy) | Both source clauses forward. An unmatched signed amount has infallible disposal. The preflight compares snapshot array lengths rather than cursor positions. |
| [13 Recorder flags](programs-r1/13-recorder-flags-r4.dewy) | Forward failure of the frame source. The eager decoder still computes a pair before the first flag can stop the search. |

The catalog's `page.next` is a pagination field. Game input polls a nonblocking input queue; channel export iterates a concrete array. Monitor replay already uses the borrowed terminal-aware loop, and inventory already disposes its owned socket cursor on function return. Their existing sources exercise the revised rules without a rewrite.

**Changed grades only** (paper assessment). The rest keep the most recent grade on each axis.

| Workload | Axis | Previous → round 4 | Why |
|---|---|---|---|
| 01 Reply | Concise | 5 → 4 | Covering a request that never starts requires an eager ticket with its own cleanup. A reusable journal library owning that ticket could regain the point. The earlier 5 covered only started requests. |
| 05 Port parser | Concise | 5 → 4 | Mapping a borrowed loop's end to a reusable parser result costs a short reader and a grammar-end type. A shared token-reader abstraction would repay this if multiple grammars use it. |

The parser's discoverability stays at 4 pending a cold reader finding the one-turn loop. The socket still costs its owning helper. No new perfect score follows from removing an unsound operation. The cold-name result covers **lazy**, **generator** and the **failure** parameter as used here; **length** was tested but the feature is cut. `RuleEnd`, `ReplyTicket`, parser functions and example method names are application vocabulary. There is no new language name for end, step, copying, polling or closing.

**Checked this round.** Independent control-flow models compared 9,331 token sequences of length zero through five, checking consumed input, staged intervals, reported offsets and commit decisions. A second model checked 320 combinations of forwarding map/take, zero through three available items, five budgets, both consumer policies, and EOF, cancellation, read failure or cancellation plus close failure. These are paper-design witnesses with executable models; they exercise neither generated code nor a real scheduler.

**Still required before implementation is accepted.**

1. Compile positive and negative probes through direct, generic, imported and erased sources. Include `Bad` as both data and terminal failure, a delivered `none`, a copied legacy iterator, partial moves and a partially drained field used as fixed arguments. Verify a failing tail never enters the callee.
2. Inject cancellation before item 1 and after k, at either zip partner, and while cleaning up. Check callback count, zero-turn fallback, group confinement, observed post-loop cancellation, whole failures and no commit on the forwarding path. Include a deliberate quiet partial consumer and a pure loop with no inserted polls.
3. Move suspended parents repeatedly, attempt to capture element places, and exercise re-entry through shared callback state and imports. Prove frame-relative cleanup and transfer of initialized slots; test fresh, partially constructed, suspended and finished drops and each joint read/display/close failure. Validate the rejected unmatched fallible row and its checked nested alternative.
4. Compare instruction counts on the flagship compile panel, emitted code size and number of adapter instances as distinct chains increase. Compare fused and erased behavior against an explicit loop, including unmatched pulls, pending fields, cleanup order and allocation under strict policy. No runtime speed or compile-budget claim rests on the models.
5. Validate D40 Q5/Q6 in the actual checker, then cold-test reading a paused cursor, a forwarding generic adapter and the parser's EOF path. Keep the existing dogfood deductions until the workloads meet the bar. No repository decision is implied by this delta.

## Open questions for the designer

### Q1 (a). What does one turn give the loop?

```dewy
let g = lazy (1 (2 3) 4)
loop x in g { printl([x]) }
```

Should this print four singletons, or three arrays with `[2 3]` in the middle?

**Recommendation.** Four singletons (A). An ordinary unary map or filter can process every turn. B lets a fixed two-field row pass straight through positional callbacks; A writes `[a b]` at the producer and `row...` at the call. The paired workloads favored A three times and B twice, with eight ties. B won the meter and ledger pipelines, which forward fixed rows. The choice fixes callback arity and the point at which a consumer can stop. **Reversible before release.** [Paired programs and callback test](round2.md:103)

### Q2 (c). What should programmers write?

```dewy
ids = (n:int64):>generator<int64> => lazy loop i in [0..n) i
# This reader has infallible disposal.
numbers = (file):>generator<int64 failure=ReadFailed> => lazy { file.read_int() or_throw }
```

Keep `lazy`, `generator` and `failure`, and keep the word `loop` in a streaming loop?

**Recommendation.** Yes. Three fresh readers understood the proposed names cold. The second signature makes the caller account for an ordinary read failure. The type also has to cover a possible failed close when the cursor owns that duty. **Reversible before release.**

### Q3 (b). Does an early stop pause or release the cursor?

```dewy
suffix = () => {
    let g = lazy (10 20)
    loop x in @g { break }
    return [g...]
}
preview = (g:generator<int64>) => { loop x in g { break } }
```

Should `suffix` return `[20]`, while the owning loop in `preview` releases its source at the break?

**Recommendation.** Yes, for a source whose disposal can safely finish there. Use `@` to keep the cursor. Show the owner at the exit and diagnose a later use after transfer. If a child needs a parent's element after suspension, pass a value or a stable owner and index. This keeps a movable cursor from carrying a dangling address. **Reversible before release.**

### Q4 (b). How does a parser read one token?

```dewy
required_number = (@tokens end_offset) => {
    loop t in @tokens or_throw {
        if t is? PortNumber { return t }
        return BadPortSyntax[t.offset]
    }
    return BadPortSyntax[end_offset]
}
```

Use the borrowed loop for one pull, including when the source can deliver `none` or an error as data?

**Recommendation.** Yes. The body handles one actual token, the last line handles clean end, and a failed pull leaves the function immediately. Keep legacy iterators' `next` method on those iterators. This eliminates the generator-specific choice of EOF selector. **Reversible.** A separately designed convenience operation could be added later.

### Q5 (a). When should an abandoned request write its record?

```dewy
started = (source metrics) => lazy {
    let seen:int64 = 0
    defer metrics.record(seen)
    loop x in source or_throw { seen += 1 x }
}
```

For a bounded source and an infallible recorder, should a started request record the current count when its consumer stops? What if every created request owes a record?

**Recommendation.** Keep D40's checked one-off `defer` provisionally for the first case. For the second, acquire a ticket with a drop hook in the factory and move it into the cursor. It can record zero even if the body never starts. **Reversible before release.** D40 Q5 governs whether the shorter form survives.

### Q6 (a). Who reports a failed close?

```dewy
show_first = (rows ui) => {
    loop row in @rows or_throw { ui.show(row) or_throw return true }
    return false
}
preview = (rows ui) => {
    let found = show_first(rows ui) or_throw
    ui.finish(found)
}
```

Should the function that owns the rows finish closing them before `preview` can call `ui.finish`, including when display and close both fail?

**Recommendation.** Yes. Apply D40's function-return rule and preserve both failures under D42. For a local exit with more work afterward, require checked consumption or a scope marked under D40 Q6. Reject a zip that would silently discard an unmatched row with a fallible close. **Reversible before release** for the local spelling. The caller's right to receive a close failure is already decided.

### Q7 (a). When can a canceled source look empty?

```dewy
mapped = (source f) => lazy loop x in source or_throw { f(x) }
publish = (source sink) => {
    loop x in mapped(source @id) or_throw { sink.stage(x) or_throw }
    return sink.commit() or_throw
}
```

Require the source suffix in a lazy producer when its input may cancel? Should an ordinary consumer still choose whether to forward cancellation or keep a partial result?

**Recommendation.** Yes to both. Here a canceled read leaves `publish` before its commit. An ordinary progress display can use a quiet loop and then `check_cancel()` to report its partial count. Pure arrays still work in a plain `lazy loop`. This gives generic adapters one rule without polling every item. **Reversible before release.** Accepting more explicitly handled producer cases later is additive.

### Q8 (b). Which cursors may fill a fixed call?

```dewy
let fresh = lazy (20 22)
add(fresh...)

pair = (g:generator<int64>) => add(g...)
```

Allow the first spread and reject the one in `pair`, where the caller might already have consumed 20?

**Recommendation.** Yes. Check the visible fresh sequence and its sole use. Omit `length=` from the cursor type. Pass a fixed tuple when two remaining arguments must be guaranteed across a function boundary. **Reversible.** A future remaining-length proof could admit additional calls without changing existing ones.
