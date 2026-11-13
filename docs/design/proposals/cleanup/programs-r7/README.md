# Round-7 paper programs

27 full-function scenarios; **not compiled or runnable fixtures**. Standard APIs follow the paper contracts; `*_case.dewy` imports remain illustrative modules, not supplied implementations or approved public names. Negative programs are explicitly labeled; do not run intentional hangs from before-versions. No compiler, service, window or audio was launched.

The R6 program set is preserved. Files 01–19 retain their subject but update the chosen syntax, integer obligations, error integration or owner comparisons. Files 20–27 cover the review's missing cases. Full grades are in ../dogfood-round7.md; authoritative semantics for this revision are in ../round7.md. The supplied errors/round2.md plus round3.md governs grouping, splitting, borrowed observation, consuming transfer and cancellation.

## Trace index

| Review request | Programs |
|---|---|
| (a) Bare ParseError, no owner | 19:7–9 and ordinary outer form 21–23 |
| (b) Same body with File | 19:10–15 |
| (c) Body failure plus close failure | 19:16–19; deterministic model 20:8–15 |
| (d) Selective marker, incomplete selector, error-as-data | 20:8–34 |
| (e) if/else and loop/else | 21 |
| (f) braced match arms | 22 |
| (g) scoped versus unscoped parallel | 23; earlier lifted-owner example 09 |
| M2 fallible inline kept guard | 24 |
| S1 large owned-buffer retention and plain-buffer control | 25 |
| S2 concrete small owner versus foreign-toggle defer | 16; shared-channel owner 17; checked borrowed-place callback owner 27 |
| S3 conservative checking, consume/move on all paths versus maybe-live | 26 |
| S4 checked integer obligations | 01 uses exact int; 17 does too |
| Multiple crossed scopes | 11:39 onward |
| Compound recovery preserving cancellation | 12 |

## Operand and scope reminders

`loop … ({ … } or_throw)` marks its braced iteration body. An ungrouped suffix after the whole loop checks the loop's values but marks no nested body. The same grouping rule applies to if/else and match arms. `parallel { … }` itself introduces its top-level owning scope; `parallel ( … )` does not. Values are selected before cleanup, and an already-pending failure is joined with subsequent completion failures without selector re-testing. A selective marker must cover all direct completion alternatives. Unselected ordinary exceptions remain data; records/arrays are not scanned.

No artificial per-iteration buffering is promised. A failed result construction prevents the incomplete array from being returned; an externally observed prefix cannot be rolled back. Scalar owning results follow ordinary pending-handoff cleanup. No full-expression temporary magically gains coverage from a surrounding suffix: fallible/unknown inline kept guards are rejected, and their named-place replacement is shown.

## Library and environmental contracts

- **01:** Mutex lends its field while keeping an infallible guard. Exact int avoids unstated int64 overflow proofs, with the normal allocation policy. Path.append_text completes its own file. Tail I/O is intentionally inside the lock.
- **02/07:** Two distinct service protocols: one requires socket EOF before status completes, the other requires the session alive during a side-channel update. Socket release is infallible local release, not a delivery acknowledgement.
- **03/08/09/11/12/18–23:** Buffered File completion consumes and may fail; explicit close consumes even on failure. Standard whole-value path operations finish their own resources. The deterministic File in 20 is a model with exactly void|FileError cleanup, not an OS adapter. Program 18's transaction uses native methods, rolls back when abandoned, and publishes only at explicit consuming commit.
- **04:** The ticker owns an active timer/queue with infallible release; its long report does not use it. Raw terminal mode owns fallible restoration even though ambient reads do not name the owner. A discarded ordinary owner belongs to its lexical scope. Inline lending is a separate, now-infallible-only short boundary.
- **05/06:** File/Socket expose a common borrowed read_bytes operation; Pair owns both; closure owns its capture and borrows it on each call. Returned bytes are independent. EOF waits depend on actual stream release.
- **10:** Spsc drop closes that endpoint; a once-run spawned receiver lambda owns its capture. Waiting joins real completion; successful sending drains, cancellation need not.
- **13:** Finite tree under an application depth bound, preventing fixed-width depth/stack overflow. Failure is an ordinary return value. This is not a proof about unbounded recursion.
- **14:** Request/Response own no cleanup; serve completes its own internals before returning. Clock and bounded-ring metric observation are non-failing/nonblocking. The capture rewrite covers ordinary outcomes, not panic/process-exit timing.
- **15/27:** The busy field is a non-owning caller-owned/task-confined bool place. An explicitly shared callback is stored only in a local owner; its record/callable conversions retain borrow provenance and checked effects. It never escapes the function, and paint retains no conflicting loan after its call. Restoring bool is non-failing; paint may fail or participate in supported unwinding. Copying into SavedCopy is deliberately wrong. Returning the callback owner is rejected. Implement/prove this scoped case before deleting defer; no general escaping borrowed-owner/method-member facility or unsafe reference field is invented.
- **16:** Internal nominal SavedDiagnostics owner and defer use identical trusted foreign contracts. get/set are no-fail/no-panic/no-alloc/no-block; render may fail or participate in host unwind. All callers must use the same process-wide gate; arbitrary supplied gates prove nothing. Raw longjmp and outside unsynchronized foreign code are excluded. No real adapter has been verified.
- **17:** Shared Channel is bidirectional; one coordinator deliberately owns end-of-sending. close is infallible/idempotent. CloseSending is internal example code, not a new default Channel lifecycle. Removing registration still loses the protocol.
- **24:** Host.view returns a borrowed field while transferring its kept local guard duty to the caller's place. That guard may return FinishError. No guard is destroyed before publishing the loan. Inline fallible/unknown kept cleanup is rejected; named places are block-owned.
- **25:** Batch's hook reads all bytes through non-failing audit_bytes; decode returns a small independent Summary and no retained alias. long_tail does not use Batch. Freeing bytes before this particular hook would violate its actual reads. Hook-free arrays may be reclaimed early when unobservable, but no peak-memory bound follows.
- **26:** close has a checked consuming signature; finish takes ownership and completes on return. A local copy/move at the original owner's last use follows existing inferred-move rules. Unknown summaries never establish consumption/infallibility; exported/instantiated generics need sound summaries.

All hooks use assigned-function form. Every program has its enclosing functions; zero-argument value calls omit parentheses, side-effect calls retain them, and no SQL or interpolation-format shorthand is introduced. The example-only names/types have not been cold-read. This folder is a design test set, not naming approval or executed acceptance evidence.
