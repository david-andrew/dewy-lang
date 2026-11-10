# Scope blocks

A call takes a brace only with `inline { }` (nothing bound) or `inline with pattern { }` (names the call binds, from values the callee passes in). `with` does not appear without `inline`. The brace is the caller's code. `return`, `break`, `continue`, and `or_throw` target the function that wrote it. An assignment does not catch them. The callee is an ordinary function with a `scope(…:>R)` parameter, checked once. The block runs at most once, on that function's task. `R` is one value. A statement without `;` contributes what it expresses. A second contribution is an error. `group.spawn(…)` contributes a task handle unless `;` discards it.

A failure is an `error` or `Canceled`. `none` is a success. `tasks` stops, then joins, on a non-normal exit and on a normal failure. A normal success, including `none`, joins and does not stop. A defer's failure is an `or_throw` from the function that wrote the defer. In an ordinary function that leaves the function. In a scope function the caller resumes after the call. A pending failure is kept. The group's state rewrites a `Canceled` exit before those defers, when the group is failing fast and the parent did not reach the brace, so the defer then sees `E` and keeps it. A shield hides a pending parent cancel. Its own deadline is `Timeout` even if the parent is already canceled. `tasks` and `within` do not hide the parent, and a parent cancel that reaches them keeps `Canceled`.

`or_throw` in the brace is not the call's result. A handler on the call sees only the call. The type is the plain union: nothing is removed at the call site. `Tasks<E>` is a sink (`Tasks<E>` passes where `Tasks<X>` is wanted when `X ⊆ E`). `join` waits outside the 100 ms cleanup grace. The child a wait is blocked on wakes that waiter with its result first. A `??` or `;` warns only when the scope function has a defer that can fail and the brace has a failure-free `return`, `break`, or `continue`. `parallel` stays a keyword and its items may wait. `return` still cannot leave a `parallel` body, including from a scope block inside one.

## What changed from v5, v6, and the earlier rounds

v5's callbacks are these braces, and `return` leaves the enclosing function. v5 already stopped siblings on an ordinary failure. An early `return` now stops too, then joins, as `concurrent` does (LANGUAGE.md:3445). Operations stay `Canceled` inside a shield. `Timeout` is the shield's own deadline, including while a parent cancel is hidden. v6's tags stay: `<ctrl_c.CtrlC>` for several sources, `<CtrlC>` for one `next`. Batch 3 still lets `parallel` items wait. discussion_points.md:455 is about generator literals. Lines 465 and 502 are the rule: `return` stops at functions and generators.

`do` was the round-3 marker. Three of six cold readers (`cold-read-markers.md`) read it as a callback. `inline` was read as the caller's code by all three readers who saw it. Cleanup is still open: `#on_cleanup` (discussion_points.md:1193) for a binding, a scope call such as `bracket` for a region. `scope` is not the `Code` snippet (discussion_points.md:2760). A repeated block would be a new marker, checked like a loop.

## Deliberate trades

David should know these. They are not open bugs in the rules above.

- A child's failure is dropped behind `return Missing`. `Missing` is already a failure, so the join's error is not reported. One function returns one failure. An error with a cause is the cleanup question, not a second result on this call. The same drop happens for a failing `close` behind `return Missing`, and for a parent `Canceled` that reaches a group which has also failed: `Canceled` stays, and the child's error is dropped.
- A failure-free `return` inside `tasks` or `bracket` does not leave the function when that scope function's defer fails. Execution continues after the call, and the failure is the call's result. The call warns. `protect_from_cancel` does not, because its defer cannot fail.
- `or_throw` in the brace leaves the function that wrote the brace. `??` on the call does not see it. A deadline is the exception, and only because the shield's state rewrote that `Canceled` into `Timeout` before the function was left.
- `<Timeout>` and `<Canceled>` both stay on a shield's result. The deadline is `Timeout`. The `Canceled` arm is a cancel the block produced itself.
- `return` from `tasks` stops the children. The stop is not written at the `return`. That is what keeps a server from joining an `accept` loop forever.
- `bracket` is longer than Python `with`. The short resource form is the cleanup decision.
- There is no spelling for "this child is in the foreground process group." The child still gets SIGINT. A press during `child.wait` stays a `ctrl_c.next` value and does not become the next `Interrupted`.
- `input` under a catcher is `Interrupted`. That is the console rule, not a type that changes inside the brace.
- One press is `<ctrl_c.CtrlC>` on a `select` of several sources and `<CtrlC>` on a single `next`.
- The block runs once. A loop-shaped helper is a different marker, later.

## Spellings

Cold read: say what each line means. On the third, say whether `group` is bound by the call or passed in. The intended reading is that the call binds it.

```dewy
task.catch_ctrl_c inline { printl"ready" }
task.catch_ctrl_c inline with ctrl_c { ctrl_c.next }
task.tasks inline with group { group.spawn(@work); }
task.protect_from_cancel(5s) inline { save(best) }
body:scope(group:Tasks<E>:>R)
body:scope(:>R)
interruptible inline with (ctrl_c group) { serve(ctrl_c group) }
```

## Floor

The floor is 4. Program 03's `<Timeout>` arm is reachable: the shield hides the parent cancel. Program 04's fresh `Canceled` becomes `WalkError` because that rewrite happens before `join`. The 4s are the trades above, each cited in `dogfood-round4.md`.
