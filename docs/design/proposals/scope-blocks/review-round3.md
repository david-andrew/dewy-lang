# Correctness review: scope blocks, round 3 (bounded final check)

I checked only round 2's must-fixes, M3's stop on a failure value, and soundness problems the new text introduces. I did not re-review settled parts.

Abbreviations: **R3** `round3.md`, **P/NN** `programs-r3/NN_*.dewy`, **L** `docs/LANGUAGE.md`, **V5** `docs/design/proposals/concurrency/unified/proposal-v5.md`.

## Round-2 must-fixes

| Item | Status | Evidence |
|---|---|---|
| N1. Provenance comes from the scope's state | **Resolved**, except for the shield case in new must-fix X1 | R3:136–145. A fresh `Canceled`, `return Canceled` and a `Canceled` value are all decided by the scope's state. `.wait` on a child that has finished returns its result (R3:145). P/04:27 now gives `WalkError`. |
| N2. `Tasks<E>` | **Resolved** | R3:149, :166. `join:(group:Tasks<E>):>void | E`. Wrapper P/15:20–22 carries `<R E>` and returns `R | E | Canceled`. The variance of `Tasks<E>` is a nit (below). |
| N3. No subtraction of types at the call site | **Resolved** | R3:102, :107, :147, :254. The type is the plain union. P/03:25 keeps `<Canceled>`. P/16:24 `kept` lists `WalkError`. |
| N4. Defer rule wording | **Resolved** | R3:119–121, :130. A defer's failure is an `or_throw` from the function that wrote it, so a `break` in a loop body leaves the function and doesn't resume the loop. |
| M3. A failure value stops the group | **Resolved in intent; the test is wrong** (new must-fix X2) | R3:155, :174. |

## New must-fixes

### X1. The parent condition makes `Timeout` unreachable in save-on-Ctrl-C

R3:138–142 replaces a pending `Canceled` only "when … the parent has not been canceled". If the parent has been canceled, "the `Canceled` stays". A shield exists to run while the parent is canceled. In save-on-Ctrl-C (R3:239–251, P/03:21–28) the root has been canceled by Ctrl-C, so when the shield's 5 s deadline fires, the `Canceled` stays:
- the `<Timeout>` arm ("save deadline expired") never runs;
- the `<Canceled> => Canceled or_throw` arm leaves `main` instead.

That contradicts V5:211 (a cancellation caused by this deadline becomes `Timeout`) and P/03's own comment. The parent condition is right for `tasks`, where a parent cancel reaches the group's body. It is wrong for a scope that masks the parent.

**Fix:** "…and no parent cancellation reaches the brace." A shield masks the parent, so its own deadline is the only reason, and it becomes `Timeout` whatever the parent's state. For `tasks` and `within`, a visible parent cancel still keeps `Canceled`.

### X2. `isnt? exception` counts `none` as a failure

R3:174 uses `finished = result isnt? error and result isnt? exception`. R3:119 also keeps "a normal result that is an error or an exception" as a pending failure. But L:3800 says "`none` also belongs to `exception`", and `none` is an ordinary success value: optional results, "not found". So:
- **The group is stopped.** `task.tasks with g { g.spawn(@writer(x)); lookup(key) }` stops the writer before joining whenever `lookup` returns `none`, so the writer's work is cut off.
- **A child failure is lost.** The same block keeps `none` as a pending failure, so a failed join drops the child's error, and the call returns `none` as if all went well.
- **The same rule reaches ordinary functions.** `f = ():>int | none => { defer close() or_throw; none }` loses `close`'s failure.

**Fix:** define the failures once, as the `error` family plus `Canceled`, never `none`. Use that definition in `tasks` (`result is? error or result is? Canceled`) and in the defer rule's "carries a failure".

## Non-blocking

- **Wake order.** R3:145 settles a wait on a child that has already finished. But when a waiter is blocked on the very child whose failure starts the fail-fast, it can see either the child's result or the cancel. Say that the awaited child's completion wakes its waiter with its result first. Without that, P/16's `<WalkError>` arm and `kept`'s observed `Missing` (P/16:3–4) depend on timing.
  - For `replaced`, both arms end in `-1`.
  - For `kept`, the result is `Missing` or `WalkError`; both are typed, so this is sound.
- **Variance of `Tasks<E>`.** A helper with `group:Tasks<NetError>` given a group whose `E` also gains `FileNotFound` from another spawn is a conflict unless `Tasks<E>` is contravariant (a sink). Say it is a sink: a `Tasks<E>` passes where `Tasks<X>` is wanted when `X ⊆ E`. Or write helpers generic, `<E>(group:Tasks<E>)`.
- **A defer written inside the brace.** By R3:119 its failure leaves the function that wrote the brace, passing through the scope function's defers; it is not the call's result. That follows from the rule. One sentence at R3:111 would stop readers expecting `??` on the call to catch it.
