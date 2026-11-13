# Cleanup round 7: one parse, ordered failures, bounded guard rules

## Three recommendations, before the details

**1. Keep observable cleanup at the end of the owning block, but teach short scopes as part of the rule.** The added large-buffer case makes block-end lose the severity tally: last-use/mixed/block-end now score **15/15/17**, with raw counts **6/7/7**. Recommend block-end for stable, explicit boundaries, not because the counted examples favor it. Plain hook-free storage can still be reclaimed early when unobservable.

Before: a Batch's hook needs its large buffer, so the buffer survives unrelated tail work.

```dewy
summarize = (path:Path) => {
    let batch = Batch[path.read_bytes or_throw]
    let summary = decode(@batch.bytes) or_throw
    long_tail(summary) or_throw
    return summary
}
```

After: end that owner's scope before the tail; the summary owns no buffer alias.

```dewy
summarize = (path:Path) => {
    let summary = {
        let batch = Batch[path.read_bytes or_throw]
        decode(@batch.bytes) or_throw
    }
    long_tail(summary) or_throw
    return summary
}
```

Batch's infallible hook observes its bytes before they are freed. If its hook could fail, the inner block would need `or_throw`. Program 25 supplies the type, contract, and hook-free control.

**2. Keep one `or_throw` operator, with ordinary syntactic attachment and ordered value-then-cleanup behavior.** A postfix suffix belongs to its complete operand expression. It acknowledges only a scope owned by that operand itself: a plain scoped block or scoped `parallel`. Group a loop body or conditional/match arm explicitly to make its scoped block the operand. Missing coverage is a conservative compile error. Reject inline lending guards whose kept cleanup may fail; name the place in a marked block instead.

Before: round 6 left whether this suffix belongs to the loop or its body unresolved.

```dewy
write_all = (paths:array<Path>) => {
    loop path in paths {
        let out = files.open(path 'w') or_throw
        out.write_text("row\n") or_throw;
        if path =? p"last.txt" break
    } or_throw
    printl("completed")
}
```

After: grouping says exactly which block acknowledges completion on fallthrough or a jump.

```dewy
write_all = (paths:array<Path>) => {
    loop path in paths ({
        let out = files.open(path 'w') or_throw
        out.write_text("row\n") or_throw;
        if path =? p"last.txt" break
    } or_throw)
    printl("completed")
}
```

The before-version is now rejected for an uncovered body, not silently reparsed when a File appears. A selected body failure is pending **before** cleanup: `ParseError` followed by failed close `F` returns `errors.join(ParseError F)`. A close failure with no pending failure returns `F` itself. The joined result is not tested a second time against the original selector.

**3. Recommend dropping `defer` from the cleanup design: the concrete owner is as good for the foreign toggle, and no remaining capability case is established by this program set.** Depth parameters and result capture replace the two functional examples. Small owners cover the global toggle and shared-channel completion; a checked local callback owner covers the non-owning borrowed bool in program 27. The latter must retain borrow provenance through its record and reject escape before an implementation removes defer. More local ceremony is a real cost, not a missing unwind capability.

Before:

```dewy
render_quiet = (gate:Mutex<int> scene:Scene) => {
    let held = @(gate.lock)
    let prior = $unsafe legacy.get_diagnostics
    $unsafe legacy.set_diagnostics(false)
    defer $unsafe legacy.set_diagnostics(prior)
    return $unsafe legacy.render(scene) or_throw
}
```

After, with one internal module-level type:

```dewy
SavedDiagnostics:type = type of [prior:bool
    $__drop__ = ():>void => { $unsafe legacy.set_diagnostics(prior) }
]
render_quiet = (gate:Mutex<int> scene:Scene) => {
    let held = @(gate.lock)
    let saved = SavedDiagnostics[$unsafe legacy.get_diagnostics]
    $unsafe legacy.set_diagnostics(false)
    return $unsafe legacy.render(scene) or_throw
}
```

The owner is constructed before changing the flag, after the lock guard; reverse cleanup restores then unlocks. Its first use costs two more nonblank lines including the three-line definition; each reuse saves a call-site statement. Those are the actual convenience costs. Program 27 closes the copying objection with an **explicitly shared callback** held only in a local owner: it restores the caller's bool, while returning that owner is rejected. That scoped borrow proof is an implementation gate, not permission to hide a pointer or relax existing escape rules. With these replacements, there is no remaining affirmative case for keeping defer in the tested scenarios; recommend drop rather than continue calling the foreign example indispensable.

## Scope and authority

This follows review-round6.md's M1/M2 and S1–S4. The original round, its 19 programs, and both grades/review are preserved. This is a new paper specification with 27 revised/extended programs and fresh grades, not compiler implementation. No new language names or public library members are proposed by the example helper types.

Error semantics are taken from [errors round 2](../errors/round2.md) **as amended by [round 3](../errors/round3.md)**: `errors.join`, `errors.split`, inherited context, ownership-preserving partition, ErrorGroup/ExceptionGroup and cancellation-carrying behavior. Those files are the user's supplied design, not a claim of accepted implementation. No new pair type appears here. A lone cleanup failure remains itself, optionally decorated with context. Group construction under explicit allocation exhaustion remains the errors design's K3 implementation gate.

Binding cleanup decisions remain: failure is the enclosing function's result; cleanup never publishes a transaction; assigned hooks; `{}` scoped, `()` unscoped; returned owners move only after successful handoff; no invented cross-task jump permissions. Functions and expressions may still deliver ordinary error values as data until an existing propagation/collector rule or an explicit return makes them a function failure.

## M1. One attachment rule

### Parsing is determined before ownership or types

**Parse ordinary expressions and their complete delimited compound forms first; then attach the postfix operator to that expression at its existing precedence.** For a delimited `if`, `loop`, or `match`, a suffix after the completed construct applies to the whole construct, including any attached `else` chain. A suffix inside a parenthesized body/arm expression applies inside that grouping. An unbraced loop body keeps its existing rest-of-line expression rule; this proposal does not change it.

Single-expression grouping parentheses are transparent to identifying the operand expression; they do not create a scope. An unscoped sequence with several expressions or declarations is not an owning block. This is syntax, not a test of how many values an expression eventually emits. Adding a hook, changing an instance, or narrowing a union never changes the parse.

For cleanup acknowledgement, inspect **only the operand's own evaluation scope**, not descendant scopes:

| Source form | Operand of suffix | Cleanup scope it acknowledges |
|---|---|---|
| `{ B } or_throw` | Scoped block | That block |
| `({ B } or_throw)` | Scoped block, inside grouping | That block |
| `({ B }) or_throw` | The same grouped scoped block | That block |
| `loop x in xs { B } or_throw` | Whole loop | None of its body scopes |
| `loop x in xs ({ B } or_throw)` | Block used as the body expression | That iteration's block |
| `if p { A } else { B } or_throw` | Whole if/else | Neither arm's scope |
| `if p ({ A } or_throw) else ({ B } or_throw)` | Each arm's block separately | Each chosen block |
| `loop x in xs ({ A } or_throw) else ({ B } or_throw)` | Body/fallback blocks separately | Executed iteration or fallback block |
| `match x { … } or_throw` | Whole match | No arm's local scope; arm-list braces are structural |
| Arm `pattern => ({ A } or_throw)` | That arm's block | That chosen arm's block |
| `parallel { B } or_throw` | Scoped parallel expression | Its own shared owning scope, after items join |
| `parallel ( B ) or_throw` | Unscoped parallel expression | None; lifted owners belong outside it |
| `f(x) or_throw` | Call | No caller-owned descendant/argument duty; callee cleanup is already in its result |

The table contains syntax forms, not freestanding program examples. Full functions instantiate every difficult form in programs 19–24 and below.

`parallel { … }` is an expression that introduces its own scope for its top-level item bindings. Its delimiter is not a separate sequential block expression that a suffix must somehow reach through. By contrast, a loop/if owns a **body/arm expression**, and a match's braces enumerate arms. This distinction is fixed in the grammar/AST, before lifecycle analysis. It preserves parallel items instead of rewriting a parallel block into one sequential item merely to obtain a marker.

Owned iteration/pattern bindings transferred into a **braced body/arm** join that body's owning scope; borrowed bindings create no new cleanup duty. If a fallible implicit pattern/iterator/temporary duty cannot be assigned to a written owning scope in the supported form, reject it with a named binding/braced-body fix. Do not introduce a new unmarked implicit scope boundary to accept it. This is deliberately bounded support, not a complete promise that every expression form can own fallible cleanup. In particular, an owned fallible iterator temporary can be named outside the loop and borrowed by it, rather than secretly completed at an unmarked header boundary.

### The operator's two jobs, in a fixed order

A suffix always performs ordinary **value selection**. Additionally, if its operand itself owns a scope, it authorizes that scope's implicit cleanup failures on locally continuing exits. This is an all-exit property of the scoped operand, not a later statement that `continue` skips. The two parts are emitted from one parsed suffix node; a full-expression temporary elsewhere is not covered by proximity.

The ordered rules are:

1. Evaluate body expressions in their ordinary order. At an ordinary result contribution, test that **outer value** against the written selector (`exception` for bare `or_throw`), with the existing descendant-aware exception for `or_throw<Canceled>` from the errors design. Do not inspect fields, arrays, or group children for ordinary selectors.
2. If selected, establish that exact value as the pending function failure **at that point**, stop the body and take its function-unwind path. Later statements and later values in that body do not run. This works identically with no owners and with a File. An explicit `return`/inner `or_throw` already establishes its pending return/failure and keeps its ordinary target; the enclosing suffix cannot catch or change that target.
3. An unselected ordinary exception stays **data**, just as under ordinary selected `or_throw`. It is not a pending failure merely because its type derives from exception. Normal collector cancellation rules still apply at a collector boundary; `$explicit_cancellation` still rejects an unacknowledged carrying contribution there. Ordinary records containing errors remain ordinary records.
4. On any exit from the scoped operand, finish initialized live duties in the established order. For `break`/`continue`, the pending action is a jump, not a failure. For a pending ordinary success, finish/retain its owner until handoff succeeds as the existing ownership rules require.
5. A first cleanup failure `F` replaces a pending success/local jump with a function failure `F`. If failure `E` was already pending, retain `errors.join(E F)`. More cleanup failures fold in execution order: `errors.join(errors.join(E F1) F2)`. Add the errors design's owner/exit context to each cleanup child, not a new typed role or pair record. A pending `none` being returned/propagated is a real exception child, not an empty accumulator.
6. Once propagation is pending, do **not** re-test its changed group kind against the original selector. This is ordinary unwind behavior: a selected ParseError does not become locally recoverable because a later close added an ErrorGroup. Remaining cleanup still runs exactly once. Dispose a withheld success owner when handoff fails, and append any resulting cleanup failures, without duplicating owning error payloads. Disposing unselected owning data can itself fail: append that new cleanup failure, but do not retroactively turn the original data value into a pending cause.
7. With no failure, take the original continuation/jump or publish the scalar success. With a failure, leave the enclosing function; never resume after a failed brace or take the pending jump. A cleanup error is never emitted as a normal generator/collector element.

A streaming collector can already have consumed earlier successful or deliberately unselected contributions. There is no automatic rollback and **no new per-iteration buffering**. Round 6 program 19's universal "successful cleanup publishes this iteration's pending length" wording was too broad and is withdrawn. Scalar pending return/assignment results follow their ordinary completion/handoff sequencing; a stream of values is not silently converted into one buffered scalar result. If constructing an array fails, the incomplete array is not returned, but external effects or an already-observed streaming prefix cannot be retracted.

### Selective suffixes must cover cleanup conservatively

For a scope whose local-continuation cleanup can fail, a selective suffix is a valid marker only if it provably covers **every possible direct cleanup failure** for that scope. An individual hook can itself return a group; its possible outer groups/cancellation flags therefore enter that coverage check. A group synthesized *after* propagation is pending does not need a second selector match. Bare `or_throw` is the easy generic spelling.

`or_throw<ParseError>` cannot cover a File whose close can give FileError. `or_throw<ParseError | FileError>` can cover a modeled scope whose only direct cleanup alternative is FileError, even though a coincident body/close failure returns ErrorGroup. `or_throw<FileError>` may leave an ordinary ParseError as data while covering the close: if close then fails with F, F is the lone pending failure. The unselected ParseError was not marked as failed control flow and is not harvested from discarded output. That cost of intentional selection is explicit; use bare `or_throw` if both should count as failures.

If an actual File can also return other completion alternatives, the marker needs those too; the modeled File in program 20 has exactly `void | FileError`. For an owning scoped operand, the ordinary selector-possibility check includes its direct cleanup alternatives as well as its ordinary value alternatives: FileError is therefore a possible selection in the close-only example even though the body itself only contributes ParseError. Generated unwind groups appear in the function's escape/result summary; they do not get a second selection opportunity. No inference that a flag is false or an exception impossible is permitted without a proof. Errors round 3's impossible-selector/cancellation-carry rules remain in force; a broad `error` does not select a cancellation-carrying ExceptionGroup.

### The requested seven traces

**(a) No owner; bare ParseError.**

```dewy
without_owner = () => {
    return [loop text in ["12" "bad"] ({ parse(text) } or_throw)]
}
```

With program 19's `parse`, 12 is contributed, then ParseError is selected; the function returns that occurrence, and no completed array is handed out. No cleanup exists. The review's ungrouped `loop … { parse(text) } or_throw` also forwards its ordinary loop values, but its suffix owns no body scope.

**(b) Same body with a File.**

```dewy
with_owner = (paths:array<Path>) => {
    return [loop path in paths ({
        let input = files.open(path 'r') or_throw
        parse(input.read_text or_throw)
    } or_throw)]
}
```

ParseError is selected at the same stage as (a). Successful close preserves the identical ParseError occurrence/metadata. The ungrouped review form with a File is a compile error for an uncovered body, not an alternate parse or silent permission from the outer loop suffix.

**(c) ParseError plus failed close.** Use (b) with body P and close F: select P → complete input → observe F → return `errors.join(P F)` as ErrorGroup. With successful body 12 and failed close F, return F itself. With `Canceled` selected instead of P, the result is `errors.join(Canceled F)`, an ExceptionGroup carrying cancellation; defaulting cannot turn it into success. Ordinary body error stays first. Program 20 makes the direct close failure deterministic as a model, not an OS fault-injection claim.

**(d) Selective suffix.**

```dewy
selected = (fail:bool) => {
    return [loop _ in [0..1) ({
        let input = File[fail]
        ParseError
    } or_throw<ParseError | FileError>)]
}
```

Program 20 supplies File's assigned hook. `fail=false`: return ParseError. `fail=true`: return `errors.join(ParseError FileError)`, without re-testing ErrorGroup. Changing the selector to ParseError alone is rejected for missing close coverage; changing it to FileError alone gives `[ParseError]` when close succeeds and lone FileError when close fails. Those are intentional ordered semantics, not an accidental body-type-dependent result. A returned record containing ParseError is data in every variant.

**(e) If/else and loop/else.**

```dewy
choose = (flag:bool) => {
    let n = if flag ({
        let out = files.open(p"yes.txt" 'w') or_throw
        1
    } or_throw) else ({
        let out = files.open(p"no.txt" 'w') or_throw
        2
    } or_throw)
    return n
}
first_or_default = (paths:array<Path>) => {
    return [loop path in paths ({
        let input = files.open(path 'r') or_throw
        if path =? p"stop.txt" break
        input.read_text or_throw
    } or_throw) else ({
        let input = files.open(p"default.txt" 'r') or_throw
        input.read_text or_throw
    } or_throw)]
}
```

Only the selected if arm acquires/cleans its owner. A loop's fallback runs only when its body never enters, including **not** after a break from an entered body. Each executed block applies its own marker. An ungrouped suffix after a complete `if … else …` or `loop … else …` propagates that complete construct's values but covers neither nested owning block. Program 21 includes the rejected outer-only case.

**(f) Braced match arms.**

```dewy
read_choice = (choice:bool) => {
    let text = match choice {
        <true> => ({
            let input = files.open(p"left.txt" 'r') or_throw
            input.read_text or_throw
        } or_throw)
        <false> => "empty"
    }
    return text
}
```

The true arm's block owns input; failed read E then failed close F returns `errors.join(E F)`. False constructs no input and returns ordinary data. A suffix after the whole match does not mark the true arm. Program 22 demonstrates both marked arms and the rejected whole-match replacement. Fallible transferred pattern owners require a braced owning arm, as stated in the scope rule; this does not turn a borrowed match binding into an owner.

**(g) Scoped versus unscoped parallel.**

```dewy
scoped = (text:string) => {
    let n = parallel {
        let out = files.open(p"scoped.txt" 'w') or_throw
        out.write_text("row") or_throw;
        parse(text)
    } or_throw
    printl("completed")
    return n
}
unscoped = (text:string) => {
    let n = parallel (
        let out = files.open(p"unscoped.txt" 'w') or_throw
        out.write_text("row") or_throw;
        parse(text)
    ) or_throw
    printl("accepted; still owned here")
    return n
}
```

In scoped, the suffix's operand owns the scope. Value selection establishing P invokes the existing fail-fast/join path. Join started items before completing out, which may still be borrowed by those items. If out initialized and close fails, retain P then F; if it never initialized, no out cleanup is invented. On success, scalar n is published after scope completion; the print means completion succeeded.

In unscoped, the suffix performs ordinary value propagation only. On success out remains owned in the enclosing function through the print and finishes at return. On P, the written suffix already leaves that function, whose cleanup can join F. **Parentheses did not acquire a cleanup boundary.** Bindings themselves contribute no values; `let parsed = parse(text)` would retain an ordinary error value instead of propagating it through this suffix.

Concurrent failure ordering uses the supplied errors design: trigger first; additional observed item failures in source-index order; each child's cleanup retained in its execution order; then the containing scope's own cleanup. The winner may depend on scheduling. No failure is fabricated for unstarted work, no owner is destroyed while a joined item can still use it, and no marker grants cross-task `break` or `continue`.

### Is one suffix clean enough?

It is coherent with this syntax and order, and removes the review's type-dependent attachment ambiguity. It is **not** free: loop/arm grouping adds punctuation, a suffix still annotates exits that bypass normal evaluation, and selective data versus pending failures requires explanation. O/D grades remain 3 on those cases. The smallest syntax-preserving fallback is to keep `or_throw` value-only and require explicit consuming close/helper results on local exits; that loses the automatic local-exit convenience. If David requires a marker on each jump line, explicit marked jumps remain a separate alternative, not a property this design claims. No new keyword is requested here.

## M2. Fallible inline kept guards: reject, then name

```dewy
rejected = (host:Host) => {
    inspect(@(host.view))
    printl("continued")
}
accepted = (host:Host) => {
    {
        let value = @(host.view)
        inspect(@value)
    } or_throw
    printl("continued")
}
```

Program 24 supplies the review's Host/Kept counterexample in assigned-hook form. Its acquisition succeeds, inspection returns void, and its kept guard returns FinishError. **Reject the inline form if any kept cleanup can fail or its summary is unknown.** Neither `inspect(…) or_throw` nor an outer marker authorizes that hidden statement-end failure. The bounded restriction applies even in an explicit return expression; supporting that special case later would need its own complete operand/temporary ordering rule, so it is not silently accepted now.

Named places transfer their kept cleanup duty to the explicit owning block. FinishError at its acknowledged exit leaves accepted before the print. A pending inspection error E would become `errors.join(E FinishError)`. Infallible `inspect(@(m.lock))` remains legal and unlocks at the end of its statement; naming its place keeps its guard through the owning block. Lending methods themselves transfer kept locals with the returned place; they do not destroy those locals while publishing the loan.

This closes M2's hidden failure edge without extending full-expression propagation. Other unsupported short-lived fallible temporary duties likewise require a named binding/scope or rejection, never an inferred invisible exit. Destructive replacement of a preexisting owner is a different operation, not solved by a scope suffix; this packet does not approve unmarked fallible replacement or claim to specify its replacement API.

## S1. Large owned-buffer retention changes the evidence

The original 14 adversarial cases and their weights remain unchanged, mapped to programs 01–10 and 18. Add this independent case, not another timer or EOF variant:

| Added case | Weight | Last-use | Mixed | Block-end |
|---|---:|---:|---:|---:|
| T15 Batch hook reads a large owned buffer after decode; unrelated long tail retains it, program 25:4–15 | 3 | 0 | 0 | 1 |
| Control: hook-free buffer, program 25:28–37 | — | 0 | 0 | 0 |
| Updated raw total | | **6** | **7** | **7** |
| Updated severity total | | **15** | **15** | **17** |

Weight 3 reflects a possible memory-cap/allocation failure, not an assertion that every retained byte causes one. Under a stated N-active-calls/B-byte-buffers scenario, up to N×B bytes can remain tied to these owner duties during the tail instead of just their small summaries; allocator overhead and unrelated live data are extra. This is a bound from the example's ownership, not a measured workload distribution. Last-use wins this case because this Batch has an infallible hook and no further real use.

The hook deliberately observes the contents of bytes. It cannot run early or free those fields early without changing observable timing or destroying required data. For a different hook with a proved disjoint footprint, field storage might be reclaimed earlier if all effects remain unchanged, but such an optimization is neither promised by this example nor a basis for claiming universal small retention. The hook-free control only permits unobservable early reclamation; it does not establish a peak-memory guarantee.

Block-end still wins stable regions and eliminates mixed timing by fallibility/composition. It **does not win this panel's count or weighted total anymore**. I recommend its movable source boundary for the language's default, accepting that an author must sometimes shorten the scope or consume/move the owner. A representative workload study could change that preference; this packet contains none. Never use the old one-point lead in the decision summary.

## S2. Concrete owners defeat the defer examples

Program 16 supplies the exact internal owner the reviewer requested. Both variants use the same trusted foreign contract and the same serialization assumption, so neither gets a safety advantage from better assumptions. Both restore during supported unwind before unlocking. The module-level definition avoids the earlier local-nominal packaging problem. The owner has one fewer call-site statement and a three-line definition; once reused it centralizes the invariant. **For the foreign-toggle case, the owner is as good, and defer has no remaining case.** Program 17 reaches the same conclusion for shared-channel close coordination.

Programs 13 and 14 remain the simpler functional rewrites: depth parameter; capture result, record, forward. Program 12 now recovers compound file errors with `errors.split<FileError>` and explicitly forwards `errors.join(parts.rest...)`; cancellation is preserved.

The final check was arbitrary caller-owned state. Merely putting a bool into a nominal owner does not restore the caller's bool; program 27 retains that wrong-copy counterexample. Its actual replacement uses an explicit shared capture of a **non-owning bool place**, a non-failing callable type, and a local owner:

```dewy
RestoreAction:type = type of [action:(():>void & no panics & no allocates & no blocks)
    $__drop__ = ():>void => action()
]
refresh = (@busy:bool) => {
    let prior = busy
    let restore = ($capture @busy):>void => { busy = prior }
    let saved = RestoreAction[@restore]
    busy = true
    ui.paint() or_throw
}
```

The callback explicitly shares busy and snapshots prior. Capture/owner construction happens before mutation. The owner cannot outlive this function; the caller's lent place therefore remains alive when the hook restores it. Its action only assigns bool, so the written no-panic/no-allocation/no-block contract is checkable rather than a trusted foreign promise. It captures neither an owning editor nor a method's implicit member environment. Program 15 uses the same pattern on a named bool-field place and requires that paint leave no conflicting loan live after its call; its deferred setter is invoked only at exit.

A callback type annotation or enclosing record cannot erase that borrow. Program 27's function returning RestoreAction is rejected. Storing the callback in a local aggregate is not itself an escape **from the function**; storing/returning it where the caller-place loan could expire is. This follows the nonescape requirement for mutable parameter captures (LANGUAGE.md:609–613), not a relaxation of it. The stricter rules for method-member captures (616–620) and borrowed **owner** closures (2196–2199) are not waived. General borrowed owner captures, escaping restorers and reference fields remain outside this example.

A compiler must preserve place provenance and the callable's checked effects through the record field and its cleanup call. If it currently rejects all aggregate storage conservatively, implement/prove this bounded local case **before deleting defer**; the packet does not claim a successful compiler run or demand acceptance on an unknown callback summary. Adding an unsafe raw pointer or treating a copied closure as shared would not satisfy the gate. A rejected escape remains rejected even if the callable/owner is otherwise copyable.

Count the cost honestly: callback owner definition is three nonblank lines; its call site is five body statements versus four for the bool defer. Thus the first one-off case costs four extra lines including definition, and reuse still costs one extra call-site statement unless a library helper pairs construction and activation. Unlike the foreign owner, it is not syntactically shorter. It nevertheless supplies the same supported unwind action without a language defer construct. Captures may incur storage costs at construction under the normal allocation policy; no zero-allocation lowering or perfect inference of a missing registration is claimed.

**Verdict: drop defer from the proposed design.** No remaining capability case is established by this set, and the extra local ceremony does not justify keeping the construct for these examples. This supersedes the provisional keep recommendation; David must approve it. It is not a theorem that no future use could ever favor defer. Implementation removal is gated on the concrete local callback-owner proof, not on an unexamined assertion that "everything can be an owner." The foreign/native-contract and callback-lifetime gates remain honestly below 5 where appropriate.

## S3. Marker checking is conservative

Use the existing indexed owner/place/initialization identities and lifecycle summaries. At each locally continuing exit, compute a conservative set of duties that **may** remain live. A duty can be removed only by a proved consume, move, noninitialization, or infallible completion; a path can be ignored only when established as a function exit or unreachable by the existing sound facts. Conditional branches merge states conservatively. No exact path-feasibility solver is promised.

Program 26's `consume_every_path` consumes on one branch and moves into a real finishing helper on the other. Both locally continuing paths have no duty: no marker. `maybe_live` retains on one branch: reject without a marker whenever T may have fallible cleanup. An unknown indirect helper's summary is not evidence that it consumed the owner or cannot fail. Passing an owner by a checked consuming signature establishes the transfer; an unavailable signature cannot be guessed.

Generic templates retain symbolic/conditional obligations and are checked where already provable. At instantiation, concrete summaries discharge them or report the missing marker at its template span with an instantiation note naming T and its cleanup alternatives. An exported generic may instead carry checked constraints sufficient to establish its contract. A bare marker is allowed for infallible instances, so portable generic text need not fork by fallibility. Type/callable erasure must preserve ownership and completion effects; failure-set narrowing that erases a reachable cleanup failure is an error.

At the existing analysis budget limit or a recursive fixed point whose precise facts are unavailable, widen to may-live/may-fail and require the marker or a checked helper/signature. Do not accept based on timeout, an assumed branch correlation or a fabricated runtime check. If a sound effect/result summary itself cannot be established, reject that boundary with the ordinary "not proven" diagnostic. Requiring a marker is sufficient only when a conservative callable/result contract remains available. This policy can produce conservative diagnostics; it is deliberately not a false-positive-free oracle.

Work is demand-driven on scopes/types with cleanup obligations; store summaries by indexed identities, reuse them across exit edges, and bound the existing analysis. This paper gives no compile-speed measurement or new budget setting.

## S4. Integer obligations

Program 01 now uses exact `int` for balance, amount and entries. Its additions no longer depend on an unstated int64 range proof or runtime-check opt-in. This does not assert arbitrary-precision addition is allocation-free. Existing allocation policy applies; cleanup semantics do not get a free arithmetic exemption. The shared-channel arithmetic example uses exact int too. The renderer retains its already-stated finite-depth assumption; no general recursion-bound claim is added.

## Acceptance matrix and readiness

In addition to the seven traces, validate: marked fallthrough; break/continue/labels through multiple owning scopes; return-only exemption; successfully consumed/moved duties; failed return handoff; conditional initialization; selective coverage with unknown hook summaries; infallible inline kept guards; rejected fallible/unknown inline guards; whole-match/outer-loop suffix rejection; scoped parallel join-before-own-cleanup; ordinary records/arrays containing error data; implicit versus explicit cancellation acknowledgement; and cleanup grouping without copying an owning payload.

The programs and grades are paper artifacts. No parser, compiler, library, task scheduler or native adapter was executed. The required grammar/lowering changes are specified, not claimed shipped. Grouping under allocation exhaustion remains limited by the supplied errors design, and the callback owner's lifetime/effect preservation must still be demonstrated by the compiler. Both gates remain visible in grades rather than become 5s by assertion.

### Semantic approvals for David

1. **Timing:** observable hooks/kept named guards live to the owning scoped boundary, independent of fallibility; accept larger-buffer retention and short-scope repairs. Plain storage reclamation remains conditional on unobservability.
2. **Attachment and all-exit behavior:** postfix applies to the complete syntactic operand; group individual bodies/arms to mark them. Only that operand's own scope is acknowledged; scoped parallel owns a scope, unscoped parallel does not. Missing coverage is an error.
3. **Ordered propagation:** select ordinary values before cleanup; preserve already-pending failures with the supplied `errors.join`; no selector re-test after joining; unselected exceptions remain data; selective markers must conservatively cover direct cleanup failures. No automatic stream buffering or error-data scanning.
4. **Bounded support:** reject fallible/unknown inline kept guards, including return expressions, and unsupported implicit fallible temporary scopes; fix with a named owner/place in a marked scope. Conservative generic/budget diagnostics preserve safety rather than infer missing facts.
5. **Defer removal:** replace the provisional keep decision with drop, using the functional/owner rewrites. Before removing implementation support, prove the local shared-callback owner preserves borrow provenance/effects and rejects escape; no new permission to escape borrowed places, store borrowed-owner closures, or use unsafe pointers is implied.

The errors design's names, groups, metadata, allocation policy and cancellation behavior have their own approval boundary; using that supplied design here does not independently approve it. No new error representation, keyword, marker name or public resource type is submitted by this round.
