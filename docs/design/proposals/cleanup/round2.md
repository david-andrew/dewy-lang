# Cleanup round 2 — close the holes in the first candidate

**Verdict remains keep `defer` narrowly.** Round 1's copyable-sender sketch and unspecified simultaneous-failure handling are insufficient. This round changes those rules, keeps ordinary callbacks, and makes the limitations explicit. Round 1 remains historical.

## Review findings and repairs

1. **A sender copy can keep a consumer waiting forever.** A closure environment might hold a sender across the same callback's receive or group join. Last-use optimization is not a sound public shutdown protocol when implicit copies are permitted. Repair: `channel<T>(n)` and `mpmc<T>(n)` return a pair of move-only sending and receiving endpoints. A sender's consuming `.split` gives two independently owned sending endpoints; a receiver's `.split` gives two receivers for MPMC. No implicit copies. `spsc<T N>.split` keeps its existing unique endpoints and has no endpoint split. This uses ordinary moves, consuming methods, tuple-shaped arrays and drop hooks. It changes the channel API, not move inference. A retained explicit sender can still keep a channel open; diagnose proven deadlocks and warn for unresolved wait cycles under the existing policy.
2. **One failure must not erase another.** Add the ordinary library error `CleanupError = type of error & [primary:exception cleanup:exception]`, with a fixed, non-secret `message` suitable for main's existing report. The existing `&` can build this error record; it cannot attach fields to every arbitrary nominal error while magically preserving its exact type. No such claim is made.
3. **A callback is not an inline scope.** Its return targets itself, and `break`/`continue` cannot cross its function boundary. Put the loop inside the callback, or return a domain outcome and handle it in the outer loop. This is a real ergonomic cost versus Python `with`, C# `using` and Swift defer. Adding rejected `inline` syntax would not be a repair within this brief.
4. **Ordinary callback code is not implicitly cleanup-shielded.** The wrapper explicitly runs completion through existing `task.protect_from_cancel(100ms @finish(...))`. This gives a concrete implementation using existing mechanisms, without a compiler rule that spots a callback and changes its cancellation behavior. The standard scoped APIs take existing-style `timeout=` to override this finalization deadline. The deadline applies on normal completion too. Timeout is a returned failure, never permission to pretend flush or deletion succeeded.
5. **Do not imply that many 100 ms cleanups total 100 ms.** Defers/drops keep the established task-cleanup grace. Each ordinary scoped finalizer additionally gets its own explicitly established shield. Two nested or batched finalizers can take two budgets. Default per-action 100 ms is a policy trade, not a task-wide latency bound. A caller who writes `timeout=5s` has authorized a longer cooperative finalizer. A blocking foreign call can exceed any such deadline. Diagnostics must expose these waits.
6. **Raw fallback release can have observable failures.** In the normal result path the finalizer records all flush/sync/close failures and disarms its raw owner exactly once. A no-fail backstop may release native storage on compiler-controlled panic, but if that release can itself produce a meaningful OS failure it must report it through the runtime's existing emergency diagnostic path. This is not a result on normal exit and cannot become the default path for file saves. A verified hook cannot allocate, panic, rethrow, terminate, or run arbitrary fallible formatting to report it. An adapter without a proven/trusted non-failing emergency report/release routine is not admitted as a safe owner.

## Result composition

A callback's `none` is success. Any other exception-valued final outcome is failure, including `Canceled` and channel failures forwarded explicitly. An error stored inside a successful record/array is data, not an implicit rollback request.

| Body outcome | Finalizer outcome | Acquisition call result |
|---|---|---|
| Success `R` | Success | `R` |
| Success `R` | Failure `F` | `F`; destroy the withheld `R` normally |
| Failure `E` | Success | Exact `E` |
| Failure `E` | Failure `F` | `CleanupError[primary=E cleanup=F]` |

Every attempted finalization records all failures in attempt order. For flush `F1` then close `F2`, use `CleanupError[primary=F1 cleanup=F2]`. If the body had `E`, the outer pair is `[primary=E cleanup=that_pair]`. Nested wrappers compose identically. The primary spine retains the earliest body/operation failure; later failures remain inspectable. An optional `none` does not enter this tree as a failure.

This is a plain error alternative, not a hidden exception list. A declared function result that might encounter it must admit it (or inference will). Existing code matching only `FileError` will not match a joint error; handle `CleanupError` and inspect both fields, or forward it. A `Canceled` plus cleanup failure becomes a `CleanupError` with `Canceled` in `.primary`: it still fails and cannot be mistaken for success, but is no longer a bare cancellation. Default main reporting uses the cleanup error's code, not Ctrl-C's 130. That makes failed restoration visible; it is a deliberate trade requiring documentation, not an automatic change to the task runtime's cancellation classifier.

The public `message` says that cleanup also failed and names a safe operation category; it does not format arbitrary payloads or paths. By default a runtime reporting a `CleanupError` prints the contained kinds and their already safe `message` fields too, without debugging payloads. That reporter behavior is a library diagnostic improvement, not a new error channel. Explicitly defaulting or discarding such a result is still explicit error handling under Dewy's normal rules.

## The owner / scoped-view boundary

Safe factories with infallible release may return owners, and those owners can move into tasks, function returns, records and arrays. Fallible completion resources are owned internally by their acquisition call and passed as `@` parameters to the callback. The wrapper uses that owner again to finish, so moving it out is not a last-use transfer. Its borrowed place cannot escape. A callback that starts a task which would outlive that place is rejected; perform the entire task group inside the callback, or acquire inside the task. A Path naming a temp directory can escape as text, but not as a promise that the directory still exists.

The wrapper is not required to retain arbitrary closure captures until the protected region finishes: callback invocation itself holds its `@` arguments through the call statement. For loops or multi-resource streaming, use named callbacks with an explicit context argument rather than rely on unsupported generic closure captures of owners. No new "once callback" contract is introduced for ordinary higher-order functions. They call the supplied callback directly once and their checked bodies prove nonescape.

## Scoped API implementation, not compiler magic

The logical skeleton is ordinary Dewy (concrete raw adapters and generic type inference omitted here; final contracts spell them out):

```dewy
let owner = acquire_raw(...) or_throw
let result = body(@owner)              # do not or_throw before finalizing
let finished = task.protect_from_cancel(timeout @finish(@owner))
return combine(result finished)
```

The raw owner's existing drop hook provides a no-fail emergency backstop. `finish` records phase progress before crossing any operation that could transfer native ownership. A close that invalidates its descriptor even while returning failure disarms the descriptor before returning that failure. Do not retry a possibly successful close; a reused descriptor might belong to something else. A timeout during flush does not skip nonblocking local release. Failure of the body does not skip close. A finalizer cannot call `or_throw` after the first failure and thereby skip remaining resources.

`protect_from_cancel` is cooperative and joins its call; a timeout does not detach an unfinished close. Residual resources that cannot be released promptly remain owned by the executing finalizer until its real return. There is no hidden background reaper or fabricated guarantee of completed deletion by 100 ms. An uninterruptible foreign cleanup may exceed the deadline, and must warn at the wrapper's call site (existing unknown-extern wait policy), including on the default path.

## Changes relative to round 1

- Replace Channel's shared bidirectional handle with move-only endpoints returned by construction; explicit endpoint split is the only duplication of capabilities.
- Specify paired failures, none-as-success, exact inspection and cancellation behavior.
- Specify default finalization timeout, explicit override, additive budgets and cooperative limits.
- Separate normal completion from the panic backstop's emergency reporting.
- Keep non-failing `defer` and last-use destruction. No `with`, pinning tag, error-dropping destructor, linear resource protocol, implicit finishing effect or nonlocal callback return.

The programs will use this rule set. Round 3 will record the actual dogfood review and any final corrections. Public library names have not been cold-tested; names.txt is the requested packet for that next review, and no acceptance is implied.
