# Independent review: combining failures, rounds 1–2

Verdict: keep David's typed, unordered combination and explicit projection direction, but do not present these rounds as settled or uniformly safe. Six contracts need correction. The largest problems are the two meanings assigned to a record type intersection, an incomplete dropped-part check, and changing the duplicate-error rule by introducing a generic helper. The all-parts fallback itself is a useful safety rule.

Scope: the brief, rounds 1–2, summary, fourteen amended paper programs, and the binding decisions in batches 4, 9 and 10, with batch 5's accepted explicit-cancellation check. I also checked the language's intersection, matching, precedence, refinement and value-semantics contracts, the original cancellation examples, and the previous ErrorGroup round/review. Owned files: this review and `regrade-round2.md` only. Non-goals: implementation, naming decisions, concurrency/cleanup timing redesign, checkout edits, commits, or further agents. Budget: about 90 minutes. No compiler tests or machine benchmarks were run; none could establish the proposed semantics before implementation. Independent grades were written before opening the author's dogfood.

## Must-fix

### M1 — Give `A & B` one type meaning across annotations and aliases

**Location:** round1:410–415; program 11:3,6,9,13–15; LANGUAGE:4220–4225.

The program constructs `User[7 "ana"] & Settings[31 'dark' 14]` and passes it to `profile:User & Settings`. It requires two `id` values. The existing `Name:type = User & Settings` contract instead defines one record with one intersected `id`. The round says the declaration keeps that old meaning, while the parameter annotation in program 11 needs the new meaning. A type alias cannot change the value set of the expression it aliases:

```dewy
Both:type = User & Settings
direct = (x:User & Settings) => (x as User).id
aliased = (x:Both) => (x as User).id
```

Either these accept the same arguments or the design has introduced context-sensitive type syntax. With conflicting field types, rather than merely different integer values, the difference becomes inhabitable two-part storage versus an invalid merged-record intersection. This is not resolved by keeping both original values internally.

**Fix:** specify a canonical type representation and alias/substitution laws for a faceted combination, including how the existing merged-record intersection relates to it. If both representations inhabit the same type, specify how `x.id`, `as`, parameter conversion and writes work uniformly for all inhabitants; a bare `User & Settings` annotation cannot promise one field view only in some contexts. If the types differ, do not silently use the same type expression for both. The record compatibility decision must be explicit before program 11 is graded complete. The direction to use projection for conflicting combined fields is binding; the unresolved part is its integration with the old type contract, not permission to discard it.

Related type hole: round1:463–465 gives `$parts` type `array<exception>` and then offers it for combined records/functions. A User or a callable is not an exception. Give that view a sound result type for each domain; do not route ordinary records through `array<exception>`.

### M2 — The proposed dropped-part check misses implicit projections and rejects its own observer example

**Location:** round1:26–29,172–190,407–409; summary point 1; author's claim that no program can lose a part without a compile error.

The check explicitly runs when a **variable's type** contains a combination. Implicit parameter projection can lose a part without any such variable in the receiving code:

```dewy
A:type = type of error
B:type = type of error
pair = ():>A & B => A & B
take_a = (a:A):>A => a
lose_b = ():>A => take_a(pair)
```

By the proposed parameter rule, `take_a` gets A. `lose_b` has no combination-typed local, `take_a` has only an A parameter, and neither explicitly drops B. Yet the caller receives only A. Adding a temporary must not be what turns this loss into an error. Equivalent holes arise through reassignment of a combination binding, an expression used only for a field, and projection into a callback/record field unless those consumption boundaries are covered too.

There is also a false-positive problem. The minimal `host_of(failure:QuotaExceeded & Offline)` example returns only `offline.host`; it never names QuotaExceeded. The stated check rejects it even though the design explicitly permits observing one part while the caller retains the original. Ordinary combined records would suffer similarly: calculating `profile.theme` should not force a function to mention an unrelated User part. Value copies, observing callees and the one original handling obligation need different treatment.

**Fix:** define what value owns an outstanding failure obligation, how copies/projections and observers preserve it, and which actions discharge it. Cover temporaries, returns, last uses, reassignment, aggregate/erased storage, closure capture and call boundaries; do not use syntactic mention of a local as the contract. Track failures rather than imposing must-use-every-field rules on arbitrary records. Include the above negative case and the minimal `host_of` positive case. If inspection-only functions are exempt, give that exemption a checked contract rather than inferring intention from a function's name.

Merely testing every part is explicitly accepted by the current rule. That can prove acknowledgment, not successful recovery. Do not advertise a stronger guarantee. A deliberately broad `??<error>` or explicit `;` may of course discard a whole ordinary failure; those are acknowledged consuming actions, not counterexamples.

The analysis also needs the project's normal demand, indexing and cost contract. A reasonable starting obligation representation is one indexed component set per relevant failure value, with joins and checked call summaries, activated only for compound failures. Arbitrarily many unions/paths must not force enumeration of every subset; state the cap/conservative diagnostic and measure its flagship cost before landing. This is a specification requirement, not a request to build the analysis during this review.

### M3 — Generic abstraction must not evade the binding duplicate prohibition

**Location:** round1:388–395; program 13:2–7,17–19; decisions:722–724.

David's direction says two failures of the same type combined with `&` are a compile error pointing to the error stack. Round 1 instead makes that expression legal when written through a type parameter or union, producing `ErrorStack<T>`. Program 13's two DiskLow calls are exactly that case after instantiation. Moving `a & b` into a generic helper should not turn a rejected operation into a different operation unless David approves that semantic change. This is not just an internal representation choice.

The helper is also unconstrained. `T=void` makes a successful first call satisfy `a is? T`; `T=Canceled` permits a forbidden cancellation stack at `T=U`. Error-family types with overlapping descendants raise the same static-versus-runtime identity question. Returning a stack of errors cannot be justified for all values admitted by the shown signature.

**Fix:** enforce the duplicate/disjointness obligation at generic instantiation under the current binding rule, with the same diagnostic as concrete code. Constrain the helper's admitted failures and success/cancellation alternatives. For repeated errors use a separate helper that explicitly constructs `ErrorStack[a b]`. Alternatively present generic automatic stack lifting as a requested change to the duplicate rule, including union/erased-family cases, allocation and cancellation; do not call it settled behavior.

### M4 — A one-shot helper can own a fallible resource; its failures need a representation

**Location:** round1:361–365; program 04:3–7,12; program 07:4,8,12,18–23. Related omission: program 14:12–15.

“One-shot path methods … own no handle after they return, so they never produce a combination” does not follow. A helper that opens, reads and closes owns a handle **during** its call. Its read can fail and its close can then fail. A successful read can also fail decoding before a failed close. Not returning the handle does not remove either failure. Program 08's manually written `read_all` already demonstrates the contradiction.

Consequently, `array<FileError | InvalidUtf8>` in program 04 cannot hold a `FileReadFailed & FileCloseFailed` or `InvalidUtf8 & FileCloseFailed` under the proposed parent-storage rule. Its skip/report code has no specified lossless path for those cases. Program 07's path helpers rely on the same unsupported exclusion. An API could wrap both failures in a declared domain error with a cause, but that would be an explicit abstraction policy, not evidence that no combination occurred.

Program 14 calls `commit() or_throw` but its alleged inferred result omits `CommitFailed & RollbackFailed`. If a failed commit retains the active transaction and automatic abandon runs, that pair is possible. If some commit failures terminate/consume the transaction, specify those states and when rollback remains required; do not assume either database policy universally.

**Fix:** define one-shot helpers' completion-error contract, preserve both values, and update the programs' collection element/result types accordingly. Choose and show either exact combinations or explicit domain wrapping. Add the failed-commit-plus-failed-rollback path and its owner state. Recheck all purported hover signatures after that choice.

### M5 — Reserving one cleanup slot per owner does not yet close the lossless-construction gate

**Location:** round1:373–386,432–435,523–524; programs 06:11–15 and 09:5–9; previous independent review N3.

Two named owners can plausibly reserve two failure slots inline. That is a useful route, not a general proof. Consider a body returning an already full dynamic `ErrorStack<FileCloseFailed>`, followed by cleanup of another file or owner array whose close fails. Rule 4 merges these into one stack. The body stack's allocation is full; the array's spare slots are a separate allocation. A contiguous array append may need a fresh allocation or copy precisely while preservation is required. Neither “one slot per owner” nor an inline outer combination supplies contiguous capacity in the surviving result.

The reservation must also survive transfer: return an owner from a helper, move it between arrays, detach/copy its enclosing value where permitted, or return the cleanup stack after the owner array dies. A refused array growth after acquisition of the new owner must still clean up that owner losslessly. Ordinary `stack & e` also appends and can allocate; it is not covered by a cleanup-array reservation by default.

**Fix:** retain the construction gate. Specify acquisition/reservation order, ownership and transfer of the reserved storage, growth-refusal cleanup, and merging of a pending dynamic body stack with new cleanup failures. A segmented/chained representation with a sound array view, transferred storage, or reservation for the whole pending result may solve it; each has a contract and cost. Do not claim fixed-size two-error combinations prove allocation freedom for generic/erased stacks or close the previous gate. Fixed pairs remain an advantage over allocating a group node for every pair.

### M6 — Enforce stack nonemptiness through the array interface, not only at construction

**Location:** round2:24–26; round1:424–440; programs 03:12,18 and 10:9,15–16.

The length guard is a good improvement, and existing finite facts can prove the shown guarded construction and push-before-construction cases. However, defining a stack as `type of error & array<E>` inherits an array surface. `let s = ErrorStack[e]; s.clear()` or a pop of the final element violates “never empty” unless the mutator is restricted. Passing mutable access through an ordinary array parameter can bypass restrictions on methods attached specifically to ErrorStack. A constructor-only proof does not establish a permanent invariant.

**Fix:** state the nonempty refinement/storage contract and check all shrinking mutations and mutable views against it, following `docs/design/refinement.md`'s existing ban on erasing invariants through mutable access. Alternatively expose a read-only iterable array view plus append operations, with no inherited shrinking surface. This need not add syntax. Define the generic element restriction excluding Canceled and composites carrying it, not merely the comment “Canceled is never an element.” Then the stack at program 10's last-element access really has the promised invariant.

## Should-fix and trade-offs

### S1 — Separate cancellation's accepted bypass from the new dominance rule

**Location:** round1:249–345,418–420; summary point 2; program 12:17–21.

The original failure is real. The integration dogfood's initial issue and section 1.1, the batch-4 decision at decisions:514–516, and concurrency v5's explicit-cancellation section describe repeated canceled waits and a default that can turn Ctrl-C into success. A and D avoid the retry spin; B permits it if its warning is ignored. The examples are fair demonstrations of that safety trade-off, and the author honestly says the fourteen programs barely measure defaulting cancellable I/O.

There are two corrections to the comparison:

1. B also deserves its **repaired** examples, using the same `or_throw<Canceled>` prefix as D. Its real alternative is a uniform default operator plus a warning people must heed, not only a deliberately spinning program. A warning at a potentially consuming default is actionable, not necessarily a warning on already-correct code. Show that annotation burden alongside A's invisible forwarding and D's compile-time requirement. None of these options makes consuming a cancellation value reset the task's canceled state.
2. D is a strictness layer atop the accepted A behavior: the accepted `$explicit_cancellation` turns an implicit bypass into an error and a fix-it. It does not itself change runtime behavior, family tests or the meaning of `??` to “any failure.” Decide separately whether a new dominance rule belongs under A, B or D.

The extra rule making `Canceled & FileCloseFailed is? FileCloseFailed` **false**, although projection to FileCloseFailed is legal, is substantially broader than D4 Q1's default bypass. It suppresses a cleanup-warning branch in round1:342 and contradicts the proposed description of `is?` as “can this be used as T?”. It also prevents a library from inspecting exactly the cleanup problem it is meant to report during cancellation. That cost is not inherent in keeping Ctrl-C out of `??`.

**Recommendation:** retain A's existing implicit cancellation forwarding provisionally; keep D available and teach its explicit form. Carry cancellation through combinations at the default/collector boundary. Prefer ordinary explicit part inspection, with a sound outstanding-cancellation obligation preventing an inspection branch from turning the whole result into success. M2 must be solved before relying on that alternative. If dominance is retained instead, call it an additional semantic choice, define family/union/generic tests completely, and acknowledge that inspecting a part may require first naming cancellation even when it is statically present. Hover marking is a required UX gate, not evidence already supplied here.

### S2 — The handler rule is safe in the local example but is not one common predicate

**Location:** round1:170–227,438–443; programs 01:18–26,02:14,05:15–20,12:17.

For distinct ordinary errors A and B, the proposed matrix is:

| Operation on A & B | Selector A | Selector A \| B |
|---|---|---|
| `is?` | true | true |
| `??<…>` | retain whole pair | default whole pair |
| `or_throw<…>` | forward whole pair | forward whole pair |
| `match` type arm | skip pair | take pair |

Universal coverage for a destructive default and existential coverage for lossless forwarding are a defensible dual: **consume all, forward any**. That should be taught explicitly rather than called mirrored matching. In particular, a function's continuing result after `or_throw<A>` excludes every compound containing A, not just the bare A alternative. A selector such as `A & B` must be evaluated as a type expression first: `??<A & B>` must not consume a bare A merely because A occurs textually in that expression. Define coverage for arbitrary unions/intersections/families, not “names” alone.

The additional `match` disagreement is expensive. Replacing `if x is? A` with `match x { a:A => … }` changes which paths execute. This is a realistic refactor bug even though totality prevents some missing-arm bugs: a later broad arm can make both versions total. A `FileError` pattern can also bind an actual compound whose `.path` is ambiguous, while an ordinary FileError parameter can hold only one failure. The annotation is therefore a selector, not the bound variable's declared storage type. Make that distinction visible in diagnostics and documentation.

**More uniform alternative:** keep `is?` and type-pattern selection aligned. An A arm can select a pair but binds the **whole narrowed value**, including B, rather than silently projecting it. Leaving that arm with a success requires explicitly handling/forwarding/dropping the remaining B obligation. The combination arm is an ordinary more-specific arm placed first; arm order remains source order. This respects David's existential `is?` sketch and can prevent swallowing without a second type predicate, provided M2's obligation contract is complete. It adds no spelling, but it does require checked match consumption and precise binder types.

If that analysis is rejected, all-parts `match` is a coherent conservative alternative. Keep the explicit `is?`/`match` warning and the lower discoverability grade; do not label the disagreement unavoidable or say the design is beyond further improvement. I prefer the aligned selection alternative, with the soundness condition stated, over silently consuming a projection in an A arm.

### S3 — Stack selectors need one stated level of matching

**Location:** round1:438–443; summary point 5; programs 03:18,04:18–19,10:15–16.

`ErrorStack<E> is? E` false is sensible: a collection is not an element, and there is no unique `as E`. It also makes the E type arm false under ordinary type-pattern semantics. Letting `??<E>` consume that same stack is then an explicitly leaf-aware handler policy, not ordinary type testing. Combined with existential `or_throw` and combination matching, it is a third concept a reader must learn.

Specify mixed stacks: for `ErrorStack<A | B>` containing only A on this execution, does `??<A>` use the runtime contents or the static upper bound? Runtime coverage requires a potentially linear scan and a precise continuing type; static coverage conservatively leaves it untouched even when all current elements are A. Also specify `ErrorStack<error>`, nested stacks and stacks inside combinations. A parent selector cannot be justified merely by the generic parameter's spelling.

**Fix:** choose and teach either explicit outer-stack selectors (`??<ErrorStack<E>>`, matching `is?`/type arms) or explicitly recursive leaf coverage for handlers. If retaining the latter, give `or_throw<E>` its corresponding leaf rule and state the scan/type-refinement cost; do not claim all three operations use the same match relation. The existing nonempty guard is workable once M6 is addressed.

### S4 — Bound demand-driven metadata to a compilation/ABI model

**Location:** round1:463–485; program 08:4,19 and program 09:14; GOALS:22–25.

In a closed fresh whole-program source build, a conservative backward demand closure can work. Ordinary return-type inference alone is insufficient: demand also crosses `cause:error`, erased exception values, `$parts` flattening, arrays, nominal children, generic instances, function handles and implicit formatting calls. An `exception` read may conservatively demand metadata for every reachable admitted failure type. Debug main reporting is another demand root. Specify that closure and its cost rather than promising a vague flow fact.

For separate compilation, library L cannot fix a unit E's return ABI with no origin field and later let application A's `$origin` read retroactively add four bytes and hidden caller arguments. The same issue affects trace capture in code compiled before the reader exists. LTO cannot recover an origin/trace that was not recorded when an opaque library constructed the value.

**Fix:** explicitly scope the zero-storage promise to closed source compilation, consistent with GOALS, and state the binary-library/FFI boundary policy: recompile/specialize from retained IR, use a stable metadata-capable ABI, or return an explicitly unavailable origin/trace. These are alternatives, not new required surface. No import should silently reinterpret an already fixed layout or fabricate a source site. Cross-module SourceLocation ids also need one link-time mapping. A four-byte raw site token is not a four-byte total union/ABI cost because alignment and enclosing result layouts can grow.

For traces, “captured only for demanded types” is implementable under that same closure, but 64-frame bounds, out-of-line ownership, task spawn provenance, optimized frames and capture failure still need a contract. An empty trace currently conflates unavailable capture and no recorded frames; disclose that limit. Retain the proposed representation/instruction-count gates. The lack of measurements is a gate, not by itself proof of a performance regression.

### S5 — Show a realistic declared signature and the abstraction choice

**Location:** round1:181–186,347–395,529–533; programs 06:13–15,08:23,12:17.

Per-operation names help a single file: FileWriteFailed and FileCloseFailed do not collide. They do not remove combinatorial possibilities from independent cleanup of different resource kinds, or repeated cleanup of one kind. FileError is a useful vocabulary parent, but this design deliberately prevents it from storing two file failures because of shared fields. Thus `FileError` in a declared result cannot serve the same abstraction role as `??<FileError>`.

Consider a realistic import/upload job with a staging file, socket, transaction and helper process all live. Assume six possible, disjoint body failures and four independently fallible completions, even ignoring acquisition failures. Here is a declared signature using ordinary aliases and the round's stated distribution of combinations over unions (illustrative error vocabulary, not a new API proposal):

```dewy
Body:type = ValidationFailed | FileReadFailed | FileWriteFailed | SocketSendFailed | QueryFailed | Canceled
Cleanup:type = FileCloseFailed | SocketCloseFailed | RollbackFailed | ProcessStopFailed
    | FileCloseFailed & SocketCloseFailed
    | FileCloseFailed & RollbackFailed
    | FileCloseFailed & ProcessStopFailed
    | SocketCloseFailed & RollbackFailed
    | SocketCloseFailed & ProcessStopFailed
    | RollbackFailed & ProcessStopFailed
    | FileCloseFailed & SocketCloseFailed & RollbackFailed
    | FileCloseFailed & SocketCloseFailed & ProcessStopFailed
    | FileCloseFailed & RollbackFailed & ProcessStopFailed
    | SocketCloseFailed & RollbackFailed & ProcessStopFailed
    | FileCloseFailed & SocketCloseFailed & RollbackFailed & ProcessStopFailed
upload = (job:Job):>void | Body | Cleanup | Body & Cleanup => { ... }
```

That is **112 alternatives**: 16 cleanup subsets times success-or-one-of-six-body-failures. It is a lower-bound example for the fully acquired path, not a claim every OS operation permits every correlation; a resource implementation may rule some out. Partial acquisition adds other primary failure kinds. Repeated files introduce stack shapes; a caller wrapping ordinary errors still has cancellation-plus-cleanup shapes to address, as program 08 shows. Inference saves typing the declaration; it does not remove the public contract or exported-type/checker complexity.

**Fix:** document the intended trade-off: exact inferred/local types; named aliases where stable; deliberate widening to `exception` when exact parts are unimportant; domain wrapping when a library must hide its implementation. `error` alone cannot hold cancellation. Choose an explicit policy for cancellation plus cleanup at abstraction boundaries. Do not promise that distinct operation names alone keep signatures small, or invent a stack of unrelated failure types solely to hide the problem. Compact type representation/hover is necessary but cannot be sold as semantic simplification.

### S6 — Success reporting must follow successful completion

**Location:** program 05:7–9.

The code prints “wrote … rows” before automatic final flush/close can fail. The caller receives the failure, but a user may already have been told the report was saved. Move the success message to the `<void>` arm in main, after `write_report` completes. This keeps D40 Q1's automatic cleanup and changes no language semantics.

## Notes

### N1 — The sketch syntax notes are substantially correct

The published precedence table at LANGUAGE:1531–1568 places comma above `as` and makes `as` left-associative. Thus the proposed warning about `result as E1, result as E2` is correct: abstractly it groups as `(result as (E1, result)) as E2`, rather than two projections. Two lets or separately parenthesized projections avoid it. This is precedence evidence from the language contract; I did not claim to compile that paper example with today's frontend.

The documented match syntax has typed arm bindings, not a scrutinee `as name` binder. Under ordinary expression grammar, `match expr as result` uses `as` with `result` as a type expression; it does not introduce a value named result. Binding the scrutinee first is a valid correction. However, David supplied the sketch as design direction: describe this as a syntax detail to reconcile, rather than an error that invalidates his semantic example or proof that a new match binder is impossible. The no-parentheses convention for value-returning zero-argument calls is also correct (batch 5); an explicit call is not evidence for a new operator feature. Operator sections already exist, and `&`/`and` are one operator as batch 10 requires.

### N2 — Match arm order is not generally irrelevant

round1:46 is true for its disjoint singleton/pair example. LANGUAGE:5568 onward and program 05's broad FileError arm show ordinary overlapping patterns remain source-ordered. Keep that qualification when teaching all-parts coverage, especially for broad families and stack selectors. Otherwise moving FileError before the explicit pair arm makes the latter unreachable.

### N3 — Keep extension boundaries explicit

The parallel block's multi-failure behavior is clearly identified as proposed, which is good. Failure combination does not settle sibling admission/cancellation races or cleanup timing. A sibling that reports a real independent failure just as another fails needs a concrete concurrency contract; this review does not approve it. Likewise the proposed lowest-code rule and Canceled exit priority are entrypoint integration choices, not consequences of an unordered set. They need their own examples. `or_throw(& previous)` remains the existing operator-section shape David described; it is not part of this implementation recommendation.

### N4 — Comparison with the previous ErrorGroup design

Typed fixed pairs convey useful information, project concisely, and can avoid per-pair allocation. Those are real advantages. A cause field also gives program 08 a smaller domain interface without a general recovery API. The previous proposal's “groups cannot be intersection typed because values cannot preserve order/multiplicity” rationale was correctly withdrawn; it must not return in the comparison.

The ErrorGroup design still has genuine advantages: one stable result alternative, uniform outer-kind `is?`/match behavior, and a common representation for heterogeneous dynamic collections. Its costs are runtime leaf inspection, allocation/resource guarantees and a cancellation-aware recovery protocol. The new design removes neither resource concerns for stacks nor cancellation/selector complexity; it moves them into exact types, dominance, coverage rules and a new consumption analysis. Neither direction earns an all-5 safety/completeness claim merely from short example source.

## Recommendation

Keep all-parts coverage for `??<E>` and whole-value existential forwarding for `or_throw<E>`; explain the dual explicitly. Prefer matching and `is?` to share selection semantics, with a match binding retaining the whole value and checked obligations preventing unacknowledged siblings from disappearing. That recommendation is conditional on a complete M2 contract; without it, the conservative all-parts match rule is safer than silently consuming an A projection from A & B.

Fix M1–M6 before another all-5 claim or implementation acceptance. Scope the metadata guarantee and show the declared-signature trade-off. The fixed independent floor is **2** in **11 and 13**; most ordinary pair/stack programs are still promising, but the deductions are not all outside this design's reach.
