# Cleanup round 4 — direct owners, direct control flow

**Verdict: keep `defer` narrowly; choose automatic fallible completion at the owning ordinary block’s exit, plus whole-value operations for the common case.** Infallible owners keep last-use release. No acquisition callback, new block form, `inline`, mandatory close line, new lifecycle tag, or replacement channel API. Fallible cleanup extends the existing `$__drop__` protocol and participates in the enclosing function’s ordinary result union. This is a semantic proposal requiring approval, not implemented behavior. Minimal examples omit imports/application helpers; complete paper programs are in programs-r4/.

## File write: a late flush error

Before:

```dewy
write_body = (@out:File) => {
    out.write_bytes([1 2 3]) or_throw;
}
save = () => open(p"/dev/full" 'w' @write_body)
main = () => save or_throw
```

After:

```dewy
save = () => {
    let out = open(p"/dev/full" 'w') or_throw
    out.write_bytes([1 2 3]) or_throw;
    return                 # flush failure replaces this success
}
main = () => save or_throw
```

Before is the rejected round-3 callback. After uses one ordinary function. The three bytes are buffered; Linux /dev/full rejects the eventual flush. The result includes FileError; no success is delivered first.

## TCP: early return

Before:

```dewy
fetch = () => {
    let s = net.tcp_connect("127.0.0.1" 8080) or_throw
    defer net.tcp_close(s)
    let reply = net.tcp_receive(s)
    if reply is? none return
    printl((reply or_throw).length)
}
```

After:

```dewy
fetch = () => {
    let s = net.tcp_connect("127.0.0.1" 8080) or_throw
    let reply = net.tcp_receive(s)
    if reply is? none return
    printl((reply or_throw).length)
}
```

The stream owns infallible local release. EOF, error and cancellation need no paired close line. This does not promise peer acknowledgement.

## Channel closure: use the existing single-producer queue

Before:

```dewy
produce = (q:Channel<int64>) => {
    defer q.close()
    loop n in [0..10) { q.send(n) or_throw }
}
let q = channel<int64>(16)
parallel { produce(q) or_throw; drain(q) or_throw }
```

After:

```dewy
produce = (tx:SpscSender<int64>) => {
    loop n in [0..10) { tx.send(n) or_throw }
}
let [tx rx] = spsc<int64 16>.split
parallel { produce(tx) or_throw; drain(rx) or_throw }
```

This is an existing API choice for one producer/consumer, not a new Sender/Receiver redesign. Shared Channel/Mpmc still require explicit close coordination; the smaller last-handle rule fails below. Their broader automatic-close design remains a separate optional question.

## Mutex: the whole operation stays locked

Before:

```dewy
let state = mutex(State[100])
{
    let value = @(state.lock())
    value.balance += 10
    write_journal() or_throw  # value already had its last use
}
```

After:

```dewy
operate = (@value:State) => {
    value.balance += 10
    write_journal() or_throw
}
let state = mutex(State[100])
operate(@(state.lock())) or_throw
```

The before form unlocks too early for this requirement. The after form uses the existing lending-call statement: the lock lasts until operate returns, including its tail I/O. This helper is a protected operation, not an acquisition callback.

## One-off “done”

Before:

```dewy
scan = (rows:array<string>) => {
    if rows.length =? 0 { printl"done"; return }
    loop row in rows { if row =? "bad" { printl"done"; return Invalid } }
    printl"done"
}
scan(rows) or_throw
```

After:

```dewy
scan = (rows:array<string>) => {
    defer printl"done"
    loop row in rows { if row =? "bad" return Invalid }
    return
}
scan(rows) or_throw
```

Keep one checked non-failing defer. Arbitrary omitted program intent is not inferable; resource factories must not depend on this registration.

## Scope, authority and budget

This fourth round supersedes the **recommendation**, not the files, of rounds 1–3. Earlier rounds, programs/, dogfood.md, contracts.md and comparisons.md remain historical and unchanged. Current artifacts are this file, programs-r4/, dogfood-round4.md, summary.md and names.txt. The checkout is read-only; no commits, compiler builds, runtime executions or measured performance claims. Budget: about two hours. Acceptance: direct enclosing-function control flow; a complete normal/failure cleanup rule; all original resource cases; a reasoned (a)/(b)/(c) comparison; smaller channel attempts; at least twelve programs and honest cited grades.

The controlling correction is David’s direct-scope requirement, recorded in `docs/design/proposals/scope-blocks/brief.md:13–17`: return/throw must work normally rather than be passed back out of a callback. Batch 7’s cleanup direction and batch 8’s rejection of inline do not authorize round 3’s acquisition callbacks. `resources/discussion_points.md:1193–1208` also favors lifetime-attached cleanup over explicit context wrapping. Ordinary declarations, braces, moves, places, error unions and drop hooks are the starting point.

## Choice among (a), (b), (c)

**Recommend (a) + (c).** The owner is acquired once. Whole-value `Path.write_bytes`, `copy_to`, `read_bytes`, `run` and `capture` already complete before returning; do not open a stream when a whole-value operation fits. Streaming uses a normal `let out = open(...) or_throw`, then ordinary statements, loops and returns. No second registration or finish call is required. Cleanup failure is a typed function result, even when the source exit was `return`, `break` or fallthrough.

**(b) is a credible, safer manual protocol, not the silent-loss design rejected in round 1.** Under (b), the compiler proves every normal path consumes/closes/moves a fallible owner. Forgetting close is an error at the unfulfilled exit, pointing back to acquisition; `close or_throw` and error-handled close count, provided the receiver is consumed even on failure. Failure paths automatically complete and pair errors. A successful transfer returns the duty to its new owner. This is materially better than “remember defer or leak.”

However, (b) still places a completion call before every successful early return, loop break and ordinary function end. A resource array requires consuming every live element or a consuming aggregate close. One successful branch added later produces another obligation. It moves the remembered second step into an edit/diagnose/fix cycle; it cannot give the shortest straight-line program. It also still needs failure-path cleanup, paired errors, ownership summaries and pending-return cleanup, so it does not avoid most hard compiler work. Its advantage is a visible local place to handle the failure and no automatic success-return replacement. This is a deliberate trade, not a correctness objection to (b).

```dewy
# Candidate (b), not the recommendation: the early normal return is rejected.
save = (bytes:array<uint8>) => {
    let out = open(p"result.bin" 'w') or_throw
    if bytes.length =? 0 return       # error under (b): out not consumed
    out.write_bytes(bytes) or_throw;
    out.close or_throw
}
```

Under (a), the same early return is safe without adding close. Under (b), inserting close only on the final line does not discharge the early branch. A loop jump leaving the owner’s block has the same proof obligation. Both candidates must still report completion failures on already-failing exits. This comparison does not rely on a permissive warning or silent fallback.


The recommended (a) keeps **optional** explicit consuming `close` for early release or local error recovery. It is not required on ordinary paths and adds no must-consume type/tag. If David rejects typed implicit failure at scope exit, (b) is the coherent fallback. Do not combine them by quietly requiring close for files while claiming acquisition alone completes them.

## 1. Which lifetime ends where

A concrete owner is **scope-bound** when its cleanup signature can fail, or its hook explicitly accepts the success flag described below. A zero-argument non-failing owner keeps today’s proven-last-use release. Classification follows the concrete type’s hook contract, including field/element/active-owner summaries; an optimizer proving one failure unreachable does not change its lifetime category.

The owning boundary is the innermost ordinary sequential block containing that owning binding: function body, loop body, branch/match arm or a plain `{ ... }`. It is not an array literal or a callback invented by the compiler. A scope-bound value stays owned there after its last source read. An existing brace can shorten its lifetime. No `using`, `with`, `defer acquire`, pin tag or unused-read trick.

- A whole-value call completes its own internal owners before giving its ordinary result; callers handle that value normally.
- An owning parameter belongs to its function body. An `@` parameter borrows; that call cannot complete the caller’s resource. An optimizer cannot elide an owning boundary as a borrow if doing so changes completion timing/errors.
- Moves transfer authority, including into an outer binding, record, array, function or once-run task. The old slot does not complete. A returned owner belongs to the receiver; it is not completed by the returning function.
- Structural records/arrays containing scope-bound owners are scope-bound. Conservative retention can keep sibling resources alive longer; warn when material. Partial field moves retain their existing restrictions beneath an outer hook.
- A discarded owning temporary completes at its full-expression boundary. `;` discards the value, not a newly produced implicit cleanup failure. An initializer error explicitly discarded by the programmer remains governed by existing result-discard rules.
- Replacement, removal and clear necessarily complete the removed value at that operation, not at a later brace. They follow the mutation rule below. Do not allocate a hidden list of removed resources to postpone their release.

This chooses **completion at block exit**, not “release at last use, carry a deferred error until block exit.” The latter can allow irreversible tail work after an earlier flush already failed, needs a hidden pending-error state throughout the block, and has to invent when outcome-sensitive cleanup learns success. Lexical completion has a simpler observable order and a direct brace/return to inspect. Costs of holding descriptors/buffers longer are real and disclosed.

## 2. Existing hook, extended result; no new cleanup tag

Today `$__drop__` is compiler-only, zero-argument and non-failing void. Keep that form unchanged for infallible owners. Extend it to admit an ordinary `void | E` result for fallible completion. `E` consists of non-none failure alternatives; the driver’s possible cancellation/deadline outcomes are also present in the concrete lifecycle error summary. A hook does not return a success payload. Hooks remain uncallable/unreferenceable directly; public consuming close may share their private implementation or simply let its owned receiver complete on exit.

A scope-bound binding that is intentionally never read still owns meaningful completion. Do not issue an unused-binding fix that removes it or rewrites it to immediate discard: `let mode = terminal.raw(...)` must keep the mode until the brace. A concrete lifecycle summary makes that duty visible to diagnostics/hover.

Hook failure returns to the compiler’s cleanup driver; it does not abandon the remaining fields or sibling resources. Outer hook first, fields in reverse declaration order, arrays in reverse live-element order, and only initialized subobjects on partial construction. Defer-before-local ordering remains. Thus an ad hoc defer printing done runs before local owner completion; it is not a certificate that all final flushes succeeded. Advance ownership/phase state before invoking an action whose native effect may already have occurred; never retry a possibly successful native close.

A hook may return/forward an error **from the hook**. It may not panic, call exit or escape to a user loop/function. Its residual effects must admit safe cleanup; unproved opaque externs are not automatically safe because C says void. Allocation either follows the existing fallible allocation policy with an admitted error or is rejected where it could panic during cleanup. This proposal does not relax no-fail move hooks or allow duplicate owner construction.

### Outcome-sensitive protocols: one ordinary boolean parameter

Files close independently of the body’s result. Transactions and stop-versus-wait process ownership need one bit: is the current requested exit successful? A zero-argument drop plus fields cannot discover a later or_throw without a remembered flag update; a global current-exception query adds hidden task-local state and another API name. Allow an **optional one-parameter bool form** of the same hook:

```dewy
$__drop__
complete = (successful:bool):>void | CommitError | RollbackError | CleanupError => {
    # Private helper attempts rollback on commit failure and keeps both errors.
    if successful return commit_with_rollback_on_failure()
    return rollback_transaction()
}
```

This is a new hook protocol contract, explicitly proposed, not existing behavior. Zero parameters remain sufficient for ordinary resources. The bool is an ordinary by-value parameter: true for a currently successful return/fallthrough/break/continue (including successful none), false for a pending failure/cancellation/abnormal failure. A preceding cleanup failure flips it to false for later actions. The hook neither owns nor borrows the pending error object; it cannot erase or retain that object through the parameter. All cause pairing remains in the cleanup driver. The local name successful is not a keyword or a proposed library member.

This needs no new pending-error type, readonly-borrow rule, context getter or error-specialized generic hook. One bit is sufficient for the requested transaction/process policies; do not pass the whole error just because the compiler has it. An ordinary call made during cleanup still has its own function result. The flag describes the boundary whose owner is being completed, not an ambient global exception in every called helper.

Using this form makes the owner scope-bound even if its result is void: the outcome does not exist at last use. The guarantee follows the declared signature, not whether optimization sees a read of the bool. This is justified by transaction/process protocols, not added as a general keep-alive tag. It can support a library scope guard, but defer printl"done" remains the shorter one-off.

## 3. Exact control flow: one function exit, no callback hop

All failure propagation here is a typed return of an ordinary error union. There is no independent exception stack or continuation that resumes after a failed return.

| Requested source exit | Completion succeeds | Completion fails |
|---|---|---|
| Function return/fallthrough of success R | Return R | Return completion failure instead; release withheld R if it owns resources. |
| Function return/or_throw of failure E | Return exact E | Return CleanupError retaining E and completion failure(s). |
| Leave an inner block normally | Continue after its brace | Return failure from the enclosing function; do not run the next statement. |
| Break/continue crossing owner scopes | Take the requested loop jump | Return failure from the enclosing function instead; do not resume after the loop. |
| Move/return owner successfully | Transfer duty; skip its local cleanup | If a different cleanup blocks the handoff, complete the withheld owning result and retain any further failure. |

A scope-bound owner’s cleanup behaves like an implicit `or_throw` at its exit boundary. Consequently `({ ... }) ?? fallback` does not catch one of these implicit forwards, just as it does not catch an explicit `or_throw` inside that block. To recover locally, explicitly consume `out.close` and handle that ordinary result **before** the brace; otherwise handle the containing function call. There is no alternate success/failure behavior depending on whether the same braces happen to be assigned a result. This choice avoids the rejected scope proposal’s failed-return-resumes-after-call bug.

Returning an exception other than none counts as failure; errors inside a successful record/array are data. A failure value merely stored in a local is not automatically a pending failure. `break`/`continue` without a failure payload start as successful control transfers. A failure from an inner cleanup propagates through all remaining crossed scopes, including outer function owners. The compiler reports missing declared error alternatives at the exit, with the acquisition and hook as notes. Inferred function results include reachable completion and pairing failures.

Parallel follows existing control targets. A cleanup failure inside an inline `parallel` item acts like `or_throw` there and leaves the enclosing function, stopping/joining siblings. A real spawned task body is its own function: its cleanup failure is that task’s result, observed through existing Task/group policy. A normal call returning a cleanup failure is still an ordinary value until its caller forwards/handles it; nothing scans nested data for errors.

### Mutation and failed handoff

For replacement, evaluate/own the new value first, complete the old value, and publish the new value into the destination **before forwarding any old-completion error**. Publication is a checked no-fail ownership transfer. Thus a borrowed destination remains initialized and valid if its caller handles the error; the mutation has happened, like other nontransactional failed operations. On unwind the new owner is completed by whichever scope now owns it. Clear/remove make their structural mutation consistent, attempt every removed live element, then forward the folded failure; a failed clear leaves the array empty. Pop transfers its result and does not close that payload.

A return candidate is owned pending handoff, not already escaped. If another cleanup fails, it is completed with that failure pending and its errors join the same ledger. Keep live/consumed bits so a resource moved into the candidate is not also completed from its former local. Generic/callable/container conversions must retain cleanup summaries just as they retain move-only facts; an unknown erased owner cleanup cannot silently become void.

## 4. Both failures, exactly once

Use the ordinary error `CleanupError = type of error & [primary:exception cleanup:exception message:string="cleanup also failed"]`. No new cause-field mutation of arbitrary nominal errors. The driver owns the pending value and updates it after each completed action; hooks receive only the success bit when they request it.

| Pending | New completion outcome | New pending |
|---|---|---|
| Success/control jump | Success | Same success/jump |
| Success/control jump | F | F; replace the proposed success/jump |
| E | Success | E |
| E | F | CleanupError[primary=E cleanup=F] |

For several cleanup failures, fold in execution order: `pair(pair(E F1) F2)`. When a pending success R is canceled/replaced, disposal of R may add F3; retain that too. A resource implementation with multiple phases (flush and close) also keeps both; it cannot `or_throw` from flush and omit close. Completed raw fields still run after an outer hook error. Do not repeatedly add a pending Canceled as though observing the same cancellation were a new completion failure.

The function type includes a possible CleanupError when a pending failure and another completion failure can coincide, or a reachable resource hook itself reports multiple failures. Use a cached zero/one/many failure bound and error-kind union for inference, conservatively widening when necessary. A declared `void | FileError` must explicitly admit CleanupError/driver outcomes if reachable; the compiler does not silently widen annotations. Bare FileError matching does not match a pair. Existing `error` family matching does. A paired cancellation is a real CleanupError, not normal canceled-task shutdown; its primary preserves Canceled and a Ctrl-C cleanup failure no longer exits as plain 130.

The displayed exception fields are the logical failure-family interface, not permission to erase an owning payload. LANGUAGE.md’s channel section currently warns that generic Unsent<T> is not storable by erasing it into fixed exception storage. A production CleanupError therefore needs lossless owned cause cells retaining concrete TypeId, payload, live state and lifecycle/transfer summary, including the exact Unsent.value. No pending failure is passed to a hook: its optional bool carries no payload. The cleanup driver itself retains the live failure until pairing/handoff, without an owning copy into fixed exception storage. This is an explicit implementation requirement of pairing, not a claim that current exception storage already supports every case. Do not silently drop a returned job/resource to make the pair fit.

Cause fields follow existing partial-move rules with active-state bookkeeping; reading can borrow, and an extraction at proven last use transfers the exact owner. Generic/family erasure must preserve move-only and fallible-cleanup qualifiers; an unknown parent-typed value cannot be copied when its concrete payload may be move-only. A loop’s arbitrary number of failures uses recursive cause cells, not a new infinitely nested static generic type per iteration. Retaining this information can require boxed storage and qualifier work; warn/diagnose its cost under the existing strict lane. If the implementation cannot preserve a generic/owning cause, the mixed channel/file failure acceptance gate has not passed.

Default reports recursively show safe kinds and existing message fields for both causes, with bounded depth and a notice of additional causes; full payloads stay behind the ordinary debugging policy. Pair storage follows the existing allocation-failure policy. Known unit causes can be stored inline as tags with no payload allocation; the ordinary two-unit pair in program 13 uses that case. Composite/owning causes may need boxes. If a user hook constructs an allocating pair under a fallible-allocation policy, its own result/effects must admit that allocation failure; do not infer no-panic merely from the pair’s name. A nonallocating emergency report path preserves the initial failure and reports truncation/secondary failure if the environment cannot store another cause; no false success is returned.

## 5. Resource-by-resource policy

- **Files:** open returns an owner. A writer’s hook flushes, performs sync only where promised, then closes; a failed flush does not skip close. A reader also reports close errors. A direct streaming write may leave partial bytes on failure; it is not silently upgraded to an atomic replace. Existing Path.write_bytes retains its atomic/durable contract, and copy_to reports completion errors before success. Intermediate buffered writes accept bytes, not final persistence. The /dev/full demo buffers three bytes before its late failing flush.
- **Sockets/listeners/tickers:** own non-failing local release/registration retirement, with last-use lifetime. Protocol-level graceful shutdown/acknowledgement remains an explicit operation whose result matters. Task and PlayingSound handles observe execution owned elsewhere; dropping them does not automatically stop/release that work.
- **Locks:** existing Mutex lending rule. `operate(@(m.lock()))` holds the acquisition through that full call. A `let` loan ends after its last use; braces alone do not extend it. No new lock helper, pin tag or local-type extension. Holding a lock across I/O still costs/warns and must obey existing deadlock checks.
- **Terminal mode:** ordinary raw-mode acquisition returns a task-affine, scope-bound restoration owner. The fallible hook restores the exact saved mode, including partial-acquisition rollback; failures pair. With signal generation retained, Ctrl-C follows normal task cancellation. With fully raw POSIX ISIG disabled, Ctrl-C is byte 3, not SIGINT; the paper example says which mode it requests. No acquisition callback or hidden signal listener.
- **Temporary directory/file:** return an owner with a Path; the fallible cleanup removes its owned tree/entry and reports a leftover identity on refusal/deadline. The path text can outlive the entry without owning it. Removal anchors to the created directory identity, does not follow a swapped symlink, and does not promise the OS obeys. A temp file inside the temp directory in program 06 exercises both cleanup duties.
- **Child process:** an owned interactive Child uses outcome-sensitive completion: on normal scope completion, finish/wait/reap; on failure/cancellation, request stop and reap. Actual wait/stop/reap errors are values; successful lifecycle completion is not a promise of exit status zero. Whole-value run/capture return status as before. An intentional child that outlives its launching function must move into its supervisor, not detach through drop.
- **GPU/audio:** asset owners retire native resources; submissions/fences and active voices retain storage until safe. Reserve retirement bookkeeping at acquisition so a claimed no-fail drop does not allocate or wait secretly. Material deferred memory/waits warn. Dropping a PlayingSound observer still does not truncate D11’s one-shot sound. An explicit state record is owned/borrowed through the engine loop, not an unused setup-local assumed to survive main.
- **Transactions:** an outcome-sensitive owner commits when invoked with successful=true; rolls back when the flag is false. A failed commit attempts rollback if the driver still has an active transaction; a failed rollback pairs. Unknown commit state remains an ordinary driver error, not a promise of safe retry. Acquire a transaction before resources it depends on so their later-acquired owners complete first. This is not global atomicity: a transaction already committed cannot be undone because a later independent cleanup failed. Explicit commit remains available for a deliberately earlier publication point.
- **Arrays/records/closures:** compose exactly-once lifecycle plans and their error sets, including partial initialization, replacements, nonescaping borrows, returns and once-run captures. Resource arrays remain move-only where their elements are. Fallible owner captures make closure cleanup fallible/scope-bound; callable conversion must not erase that fact. No special collection callback/finalization stack is required.

## 6. Cancellation, deadlines and abnormal exits

Keep shielding and cooperative joining. Normal uncanceled completion has **no new 100 ms timeout**. If cleanup runs under a canceled task, or cancellation reaches a waiting finalizer, shield the remaining release work with the existing 100 ms cleanup grace. Share the remaining grace through nested cleanup calls in that unwind episode; do not restart 100 ms for each element. Existing explicit protection scopes may establish their own documented budget; this round adds no `timeout=` or cleanup-grace parameter to acquisition APIs.

A cancellation-aware finalizer can finish its normal work during grace. If the requested exit was successful and cancellation was actually observed at a cleanup cancellation point, pending becomes Canceled; completing successfully under the shield does not turn that observation back into success. If E was already pending, keep E primary. Do not create a new cancellation point in compute-only code or non-failing zero-argument release hooks. The concrete lifecycle summary includes any Canceled/Timeout the driver can expose, so inference stays honest.

The finalizer records phase progress and native errors independently of its deadline result. On grace expiry the driver retains recorded errors, attempts remaining immediate local release, records timeout/failure for unfinished work, and joins real executing calls. Fields’ release plans still run; an outer flush cancellation cannot skip a raw handle’s release. There is no detached reaper, retry of an ambiguously successful close, or forced termination of arbitrary C. Uncooperative foreign waits may exceed the grace and must warn at acquisition/destruction sites. Remaining safe immediate release is attempted even with no waiting budget left.

Task moves transfer scope-bound duty to the task. Captures canceled before task-body entry are still completed; their failures belong to that task result before group join. A returned owner transfers only after successful result handoff. Expected bare child Canceled may be handled, but a CleanupError containing Canceled is not consumed as ordinary stop, so failed socket/file/mode cleanup is visible. Existing group policies for selecting among independent child failures are not redesigned; every child’s own result retains its cleanup pair, and secondary child failures remain subject to existing group reporting/inspection policy.

Compiler-controlled panic/exit uses the same ownership/phase plan, but has no normal return candidate. Panic and nonzero exit supply a false success flag; explicit exit(0) starts true. Cleanup failure during exit(0) changes process status to a failure code (as at main), rather than reporting success after a failed flush. An already nonzero/abnormal reason remains primary and its cleanup failures are reported alongside it, without starting another panic. No function call resumes after exit. Hooks must not panic/terminate; emergency diagnostic storage must not require allocation. Forced kill, power loss, foreign longjmp/fault and the forced third Ctrl-C remain outside guaranteed cleanup.

## 7. Channels: first try the smaller rules

**No changed Channel, Mpmc, constructor, .close or split contract is recommended here.** Spsc already solves the single-owner producer/consumer examples, including D4’s single reporter. For shared channels, retain today’s explicit idempotent close and preserve drain/Unsent/reservation semantics. A non-failing `defer q.close()` remains a protocol signal at a chosen producer/coordinator boundary; it is not needed to free the buffer, but forgetting it can hang a consumer. That limitation is part of the final floor, not hidden under “all owners clean themselves.”

Smaller attempts, written with the decided API:

```dewy
let q = channel<int64>(4)
parallel {
    { q.send(1) or_throw }              # producer returns
    { loop value in q { printl(value) } or_throw }
}
```

- **Last overall handle closes:** the receive task still owns q while waiting for Closed, so no last drop occurs. This program remains stuck after draining 1. Automatic buffer release is not end-of-input detection.
- **Last handle that can send closes:** every copy is Channel<T>, and every copy exposes send/reserve/close, including the receiver’s. The rule is identical unless “can send” introduces new inferred/static capability state. A type-preserving library drop hook cannot see future method calls.
- **Close when a producer function returns:** a producer may call another producer with a copied handle, and other producers may still be alive. Closing globally on every such return closes too early. Counting those copies requires identifying which ones really own sending rights.
- **Close after the last actual send:** a loop may send again, a receive may compute the next outbound request, or a permit may be held for later. Neither the queue nor an ordinary destructor knows the last future send from the absence of activity. Idle timeout is not closure.
- **Infer sending rights from use summaries:** promising, but now it is a new capability/liveness analysis and runtime lease counter. Unknown calls, callbacks, stored handles, dynamic aliases and bidirectional request/reply loops must conservatively retain a sending right, leaving real hangs unless diagnosed. It cannot be sold as a one-line library change.

**Separate optional question, not in the approval packet:** should shared channels gain explicit endpoint capabilities, inferred sending leases, or remain explicit-close protocols? Round 3’s proposed public Sender/Receiver API is one possible answer, not a decided prerequisite of file cleanup. Any such task needs its own complete surface brief, measured compiler-cost bound and D4 compatibility/design review. This round does not launch it or add it to open_decisions.md. Existing proven-deadlock errors/unresolved warnings continue; no claim that every forgotten shared close is caught today.

Reservations keep their decided semantics, including sends that cannot fail after explicit close and readers waiting for held permits before Closed. Spsc’s existing endpoint release rules apply; changing when shared channels implicitly close must not silently change permits. No inference shortcut is introduced here.

## 8. What actually changes and what does not

Required semantic approval:

1. `$__drop__` may return ordinary failures; fallible owners complete at their owning block exit, and completion failures affect the enclosing function result/control flow.
2. The optional ordinary bool parameter on that same hook, for success-versus-failure protocols.
3. Existing aggregate/temporary/destructive-operation cleanup composes those failures; declarations and generic/callable summaries retain the error duty.
4. Narrow defer remains checked non-failing void with no escaping control transfer/panic/exit.
5. Ordinary CleanupError pairing/reporting.

Only **CleanupError and its primary/cleanup fields** are newly proposed names. `message` follows existing error reporting. Existing `$__drop__`, `exception`, none, `@`, `$__consume__`, `or_throw`, ordinary braces and result unions do the surface work. Ordinary stream/terminal/temp/process factories in the programs are library-contract illustrations, not an additional naming ballot. Their final names can follow existing library decisions; there is no callback overload or new timeout parameter to approve here. No new endpoint names, lifecycle tag, annotation, effect-row spelling or visibility keyword.

### Existing-construct failure before each extension

- A zero-argument **void** hook cannot return a flush failure to a successful caller. Extend its existing result union; no new hook name.
- Last-use cleanup alone can precede tail work/return decisions and would need a hidden carried error. Scope-bound lifetime instead gives an ordinary brace boundary; no new block syntax.
- A zero-argument hook cannot select commit versus rollback without a manually updated flag or hidden context getter. One bool passed by the existing parameter syntax carries the minimum necessary information; the whole pending error is unnecessary.
- A caller-selected acquisition callback changes the return/break target. Remove it; do not rename it or mark it inline.
- Explicit must-consume succeeds at omission detection but adds a normal-path finish obligation. Keep it as the coherent alternative (b), not an unacknowledged requirement in (a).
- Last shared-channel handle cannot identify last sender while receivers are waiting. Keep the larger change optional; use already decided spsc where it fits.

### Implementation notes, not new main-design requirements

The current compiler admits only proven no-fail drops for resource containers and cannot implement these rules unchanged. Reuse indexed OwnerId/PlaceId/live-state cleanup plans and add cached concrete lifecycle failure unions, scope-bound/outcome-aware flags and zero/one/many bounds. Generate cleanup failure edges before result-type inference, definite-assignment and return/control-flow verification, not as an untyped late codegen surprise. Error inference over reachable function instances uses the existing call-graph/SCC machinery; no analysis runs for types without a cleanup obligation. Destructive operations generate valid-state publication before their failure edge. Preserve pending-return ownership and the driver’s pending error; erase neither in generic/callable conversion. Complexity is linear in generated live cleanup actions, plus bounded existing ownership dataflow; failure-set union propagates monotonically across reachable summary edges. No optional sending-lease solver is included.

The C example’s local nominal helper remains an **isolated implementation/encapsulation dependency**, not a recommendation to expand local declarations in this cleanup design. Current reader source rejects local nominal methods (`dewy_reader_seed.jo:5848–5856,6544–6557`, `dewy_reader.dewy:6847`, local_type fixture). A production library can use its approved encapsulation facility when settled; the paper PCRE example marks that packaging dependency. Do not require a global local-type extension or pretend a public raw pointer record is an opaque safe interface. C cleanup summaries remain reviewed unsafe ABI claims; default-allocator PCRE free is the bounded example, not C void in general.

## 9. Cost, warnings and gates

A no-fail zero-argument scalar owner keeps its known last-use release, no required allocation/virtual call. Scope-bound resources retain storage/descriptors until a brace; loops should acquire inside their body rather than accidentally accumulate in an outer array. Warn on material retention, waits, GPU/audio delayed memory, atomic shared counts and new failure-storage allocation, once per source operation/instance. An unverified foreign completion may block beyond cancellation grace; no wall-clock guarantee is invented.

Normal return adds a cleanup plan branch/failure merge only when a reachable finalizer can fail. Concrete error discriminants/phase state and owner live bits are reused; no heap registration per owner is required. Aggregate cleanup is O(live elements), including all failed-prefix cleanup; outcome access is one ordinary bool, not an error-payload copy or borrow. Actual failure pairing can allocate; apply existing environmental/strict allocation policy and provide an emergency diagnostic path. `$no_hidden_costs`/proof modes reject unknown or disallowed cost/extern claims, not quietly permit them because cleanup is automatic.

A compiler implementation must measure the flagship instruction-count panel and run the project’s focused/quick, full, independent bootstrap and fixed-point gates before landing. This design has measured no compile/runtime cost and changed no compiler code. Keep acceptance tests on return/break/continue/fallthrough, failed return-candidate disposal, partial aggregates, destructive mutation through @, pair order, outcome-aware hooks, annotation diagnostics, cancellation before spawn entry and known channel hangs. Do not benchmark the desktop by wall clock.

## 10. Documentation changes and remaining floor

LANGUAGE.md ownership/records (2088–2199): extend the hook signatures and concrete cleanup summaries; distinguish last-use and scope-bound owners; lift no-failure-only container restriction when implemented. Places/locks (1108–1161,3569 onward): retain the lending-call whole-operation example. Error section (4140 onward): add implicit cleanup failure edges, normal exit replacement, break/continue behavior, explicit-close local recovery and CleanupError. Cancellation (3625–3655): define normal-versus-canceled completion, shared grace and phase/error preservation. Files/processes/networking (4323–4510): self-cleaning owner contracts and whole-value fast path; socket examples lose mandatory closes. Existing references to defer in effect/refinement/liveness rules remain meaningful; do not delete all mentions.

D4: remove ticker stop and socket close defers. Its single producer/reporter may use existing spsc and join progress before main ends when all reports must finish. Keep shared chat/command Channel close coordination until the separate channel question is decided; do not silently replace Channel types/constructors or Closed/Unsent/reserve behavior. Batch 7’s temporary cleanup direction changes only after David approves this proposal. Batch 8’s rejected inline form stays rejected. No design decision, proposal history or open_decisions.md file in the checkout was edited.

The whole-packet floor is **3/5**, with the exact scores in dogfood-round4.md: shared close coordination, the isolated C packaging gap, and replacement-on-error surprise. Streaming cleanup itself has no callback floor; its remaining scores are 4s for implicit completion/error behavior. Straight-line file cleanup no longer pays a callback/control-flow boundary. Remaining costs include implicit completion errors at return/break, late completion/retention, concrete driver/FFI dependencies, and a **shared-channel automatic-close gap** kept out of the main change. It is not honest to grade that gap as solved merely because spsc fits the small example. All sub-5 scores have source-line citations. Names are a minimal approval/cold-read packet, not a claim that fresh cold readers ran.
