# Scope blocks

A call takes a brace only when it says `do { }` (nothing bound) or `with pattern { }` (names bound by the call, from values the callee passes in). The brace is the caller's code. `return`, `break`, `continue`, and `or_throw` target the function that wrote the brace, and the loop a plain block there would reach. An assignment does not catch them. The callee is an ordinary function with a `scope(…:>R)` parameter, checked once. The block runs at most once, on that function's task. `R` is the block's one normal result. A statement without `;` contributes the values it expresses. A second contribution is "this block expresses 2 values; the scope result is 1." `group.spawn(…)` contributes a task handle unless `;` discards it.

`or_throw` in the brace targets that function. A `??`, `match`, or `or_throw` on the call sees only the call's result. Two cases become the call's result anyway, and both are an `or_throw` from the scope function, so the caller resumes after the call. The type is not narrowed.

- A defer fails during an exit that carries no failure. For an ordinary function this `or_throw` leaves that function. It does not resume a loop. For a scope function the failure is the call's result. A pending failure is kept, and the defer's failure is dropped. One result. Reporting both is open.
- A cancel scope closes for its own reason (the deadline fired, or the group is failing fast) and the parent is not canceled. A pending `Canceled` exit, however it was spelled, becomes that reason: `Timeout`, or the group's `E`. Provenance is the scope's state. `Canceled` is a unit value. If the parent is canceled, the `Canceled` stays.

`Tasks<E>` carries `E`. `join` on `Tasks<E>` returns `void | E`. A wrapper is `<R E>(body:scope(group:Tasks<E>:>R)):>R | E | Canceled`. `.wait` on a child that has finished returns `void | E` even in a canceled scope. A failure-free `return`, `break`, or `continue` in a brace whose call is then defaulted (`??`) or discarded (`;`) warns.

`tasks` stops the group, then joins, on a non-normal exit and on a normal result that is an error or an exception. A normal success joins and does not stop. `join` is not under the 100 ms cleanup grace. `parallel` stays a keyword. Its items may wait. `return` still cannot leave a `parallel` body, and a borrowed group cannot be used from one.

## Changes from v5, v6, and earlier rounds

v5's three calls took callbacks. A `return` in the callback finished the callback. Here it leaves the function that wrote the brace. v5 stopped other children on an ordinary callback failure, and told the block to stop persistent children before a normal join. That stop on a failure value stays. A `return`, `break`, `continue`, or `or_throw` now stops too, then joins, which is what `concurrent` already did on an early return (LANGUAGE.md:3445). v5's `Tasks<E>` is the group type, not a result inferred from spawns the signature cannot see.

Operations still return `Canceled` inside a shield (proposal-v5.md:192). `Timeout` is the shield's result when its own deadline fired, not a change to `read_text`. v6's select tags stay: `<ctrl_c.CtrlC>` for several sources, `<CtrlC>` for one `next`. Batch 3 still lets `parallel` items wait. discussion_points.md:455 is about generator literals and is not the rule. Lines 465 and 502 are: `return` stops at functions and generators.

Cleanup is not decided. `#on_cleanup` (discussion_points.md:1193) and a scope call such as `bracket` both still fit. `scope` is not David's `Code` snippet (discussion_points.md:2760). A repeated block would be a new marker, in the direction of `#insert body(break=…)`, checked like a loop. Dropped from earlier rounds: callee-directed braces, `do with`, provenance on the `Canceled` value, subtracting `E` or `Canceled` at a call, and "resume at the block that owns the defer."

## Floors

The floor is 4. Each one stays if the rule above stays.

- `programs-r3/01_repl.dewy:8` — `Interrupted` is the console result under a catcher, not a type that changes inside the brace.
- `programs-r3/02_shell.dewy:2` — the child gets SIGINT from the process group. There is no spelling for that. A queued press is not drained; it does not become the next input.
- `programs-r3/03_search_save.dewy:25` — `<Timeout>` and `<Canceled>` both stay. The type is not narrowed when a deadline replaces a `Canceled`.
- `programs-r3/04_early_return.dewy:27` — a fresh `Canceled` becomes `WalkError` from the group's state. The value cannot show the origin.
- `programs-r3/06_game_loop.dewy:12` and `programs-r3/12_dashboard.dewy:8` — qualified and plain `CtrlC` are the v6 arms.
- `programs-r3/07_server_flush.dewy:34` — `return` stops `accept`. The stop is the rule that keeps the server from hanging.
- `programs-r3/08_cli_throw.dewy:22` and `programs-r3/16_return_replaced.dewy:28` and `programs-r3/17_failing_close.dewy:37` — a pending failure is kept and the defer's failure is dropped. An error with a cause is open, under cleanup.
- `programs-r3/09_break_loop.dewy:15` and `programs-r3/13_expr_value.dewy:20` and `programs-r3/17_failing_close.dewy:29` — `or_throw` in the brace leaves the function. A handler on the call does not see it. A deadline `Canceled` is the exception, and it is the scope's state.
- `programs-r3/10_bracket.dewy:24` — `bracket` is longer than Python `with`. The short resource form is the cleanup decision.
- `programs-r3/11_calling.dewy:19` — `scope(:>R)` is the function result mark, reused.
- `programs-r3/14_parallel_comprehension.dewy:16` — both `continue`s target the comprehension, as a plain block would.
- `programs-r3/15_two_libraries.dewy:53` — `return -1` leaves `crawl`. The assignment does not catch it.
- `programs-r3/16_return_replaced.dewy:16` — a failure-free `return` resumes after the call when the join fails. Line 20 warns.

## Spellings

Cold read: for each line, say what it means. On the third line, say whether `group` is bound by the call or passed in from the caller.

```dewy
task.catch_ctrl_c do { printl"ready" }
task.catch_ctrl_c with ctrl_c { ctrl_c.next }
task.tasks with group { group.spawn(@work); }
task.protect_from_cancel(5s) do { save(best) }
body:scope(group:Tasks<E>:>R)
body:scope(:>R)
interruptible with (ctrl_c group) { serve(ctrl_c group) }
```

`with group` binds `group`. The scope function passes the new group in. The caller does not already have it. `do { }` is the form that binds nothing. `do with` is not a spelling.
