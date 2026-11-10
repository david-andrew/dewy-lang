# Scope blocks, round 4

Round 3's rules stand, with four corrections. The brace marker is `inline`, not `do`. A failure is an `error` or `Canceled`, never `none`. A shield's own deadline becomes `Timeout` even when the parent is already canceled, because the shield hides that cancel. And the group's state rewrites a `Canceled` exit before the scope function's defers run, so program 04's fresh `Canceled` really is the join's `WalkError`.

## The marker

`inline { }` binds nothing. `inline with pattern { }` binds. `with` is only legal after `inline`. `do { }` and a bare `with pattern { }` are not calls.

```dewy
task.catch_ctrl_c inline { printl"ready" }
task.catch_ctrl_c inline with ctrl_c { ctrl_c.next }
task.tasks inline with group { group.spawn(@work); }
task.protect_from_cancel(5s) inline { save(best) }
```

`inline` is the postfix at member and call precedence. It applies to the last call in the chain, whose callee is a statically named scope function or method. `with` and the brace continue that postfix. `??`, `or_throw`, and binary operators stay outside.

Cold read, six readers, no context (`~/dev/tmp/naming-1107/r17/`, `r18/`). Three of the six read `do { }` as a callback, so `return` would leave the callback. All three readers of `inline { }` and `inline with group { }` read the brace as the caller's code, and read `group` as a name the call binds. `do` is dropped for that reason. `inline` is not a keyword today.

## What a failure is

A failure is a value of the `error` family, or `Canceled`. `none` is not a failure. LANGUAGE.md:3800 puts `none` in `exception` beside `error`, and `none` is an ordinary success: optional results, "not found".

That one definition is used in both places that asked "is this a failure?":

- `tasks` stops, then joins, when the block's normal result is a failure. `none` does not stop the other children.
- A defer replaces an exit that is not a failure. `return none`, and a normal `none`, are not pending failures, so a failing defer still replaces them. `return Missing` is a pending failure and is kept.

```dewy
finished = result isnt? error and result isnt? Canceled
```

## A shield's deadline

A shield hides a pending parent cancel. That cancel does not reach the brace, so it is not a reason to keep `Canceled`. The shield's own deadline always becomes `Timeout`.

Program 03 is the case. Ctrl-C has already canceled the search. `protect_from_cancel` runs anyway, and the parent's cancel stays pending outside the brace. If the five seconds run out, the `<Timeout>` arm runs. The `<Canceled>` arm is only a `Canceled` the block itself produced. The type still lists both. Nothing is subtracted.

`tasks` and `within` do not hide the parent. A parent cancel that reaches those braces keeps `Canceled`.

## Where the group-state rule runs

Leaving a scope function happens in this order.

1. Defers written in the brace run. A failure there is an `or_throw` from the function that wrote the brace. It is not the call's result. A `??` on the call does not catch it. The exit then passes through the scope function's defers.
2. The cancel scope closes, before those outer defers decide. If its own reason fired, and no parent cancel reached the brace, a pending `Canceled` exit is replaced by that reason. A failing-fast group replaces it with `E`. A shield's deadline replaces it with `Timeout`. A parent cancel that reached the brace leaves the `Canceled` in place.
3. The scope function's defers run. A defer's failure is an `or_throw` from that function. It replaces an exit that is not a failure. It keeps a pending failure, including the `E` step 2 just wrote.

Program 04 throws a fresh `Canceled` while the group is failing fast and the parent has not reached the brace. Step 2 rewrites that exit to `WalkError`. Step 3's `join` fails with `WalkError` and keeps it. `find` returns `WalkError`, not `Canceled`. The signature still lists `Canceled`, for a parent cancel that did reach the brace.

A failure-free `return 0` is not a `Canceled` exit, so step 2 does not touch it. Step 3's join replaces it, and the caller resumes after the call. `return Missing` is already a failure at step 2. Step 3 keeps `Missing` and drops the join's error.

The child a wait is blocked on wakes that waiter with its own result before fail-fast cancellation. Program 16's `WalkError` test is that result, not a race with `Canceled`. A `void | E` success is what remains after `is? error` and `is? Canceled`. There is no `<void>` arm.

## The rest of the small points

`Tasks<E>` is a sink. A `Tasks<E>` passes where a `Tasks<X>` is wanted when `X ⊆ E`, because a spawn only puts errors in.

A `??` or a `;` warns only when it defaults or discards a call whose brace has a failure-free `return`, `break`, or `continue`, and the scope function has a defer that can fail. `protect_from_cancel` does not warn: its defer only pops the shield. `tasks` and `bracket` do, because `join` and `close` can fail. The warning is "this return does not leave the function if a defer in tasks fails; execution continues after the call with that failure."

A `??<E>` on a call whose brace also forwards `E` hovers "this handler sees only the call's failures." Program 17 uses a separate `Trailer` for the close, so the two routes are not the same type. The hover is for the general case.

A file operation's `or_throw` forwards every kind in LANGUAGE.md:3984 (`FileNotFound`, `FileAccessDenied`, `IsDirectory`, `FileExists`, `FileError`), plus `InvalidUtf8` from `read_text`, plus `Canceled`. A written result lists that whole set, or the result is left inferred. `problem:error` matches the error kinds. It does not match `Canceled`.

```dewy
tasks = <R E>(body:scope(group:Tasks<E>:>R)):>R | E => {
    let group = open_group()
    let finished = false
    defer {
        if not finished group.stop()
        join(group) or_throw
    }
    let result = body(group)
    finished = result isnt? error and result isnt? Canceled
    result
}

protect_from_cancel = <R>(limit:Time body:scope(:>R)):>R | Timeout => {
    let shield = push_shield(limit)
    defer pop_shield(shield)
    body()
}
```

`pop_shield` applies step 2 for the deadline only. It does not look at a parent cancel the shield hid.
