# Independent regrade of round 2 (scope blocks)

Read: round2.md, programs-r2/01-17, round-1 regrade (mine), LANGUAGE.md and discussion_points.md for the citations. dogfood-round2.md was read only after the grades below were written.

## 1. Round-1 must-fixes

| # | Status | Evidence |
|---|---|---|
| 1 `{` ambiguity | Resolved | `do` / `with` marker, round2.md "Where the brace attaches"; 03 line 22 `match task.protect_from_cancel(5s) do { save(best) } {`, 13 line 15 `if verbose task.protect_from_cancel(1s) do {`. Parser needs no name lookup. Open cost: every call now carries `do`; `with` has two readings (see N6). |
| 2 `return` in an assigned block | Resolved | round2.md "Control flow"; 15 line 38 `let page = ... do { if url =? "quit" return -1`. Citations check out: discussion_points.md:455 is about generator literals, :465 says "return breaks out of function", :502 "returns stop at certain boundaries"; `concurrent` (LANGUAGE.md:3445) already cancels and joins on early return. |
| 3 children on early exit | Resolved | stop-then-join rule; 07 line 35 `return` no longer hangs. New cost: N4. |
| 4 `scope` result type / typing | Partly | `scope(... :> R)`, 11 line 18, 10 line 20. But the call's result type is still not what the signature says (N1, N2). |
| 5 defer replaces `return v` | Changed, not removed | now by value: failure-free exits are replaced, failures kept (16, 17). New problems N3 and N5. |
| 6 void / `;` rules | Resolved | round2.md "Statements and void"; 13 lines 15, 28-31. One regression (N7). |

## 2. New problems

**Must-fix**

- **N1. Does a block's `or_throw` leave the function or become the call's result? The design and the programs disagree.** round2.md says `or_throw` targets the enclosing function, but "The call's result is R, plus ... failures the block forwards, minus a `Canceled` this scope replaced". 09 lines 14, 17: `probe(port) or_throw` inside the shield, `??<Timeout> continue` after it; the header says a deadline `Canceled` becomes the call's `Timeout`, while "a file error does leave serve_until". 17 line 31: `append_file(log.path "x\n") or_throw;` inside the block of `replaced = ():>int`, with `??<FileError> -1` after; for that to type-check the forwarded `FileError` must be the call's result and handled by `??`, so it does not leave `replaced`. Under 09's reading the same line is a compile error in 17 (`:>int` has no `FileError`). One of those is wrong, and the "exactly as in a plain block" claim now has an exception that depends on provenance. Define one rule and show the typed result of 09 line 14 and 17 line 31.
- **N2. `E` of `tasks` cannot be written for a forwarding scope.** `tasks = <R E>(...) :> R | E`, `E` "inferred from those spawns", but spawns happen in the caller's block. 15 line 17-18: `interruptible ... :> R | Canceled` wraps `task.tasks` and has no `E`; a user block that spawns a failing child through `interruptible` has its failure typed nowhere, so "checked once, generically" fails for any helper that forwards a group. Either the group's failure type is an ordinary parameter the caller supplies, or `interruptible` must be a template.
- **N3. A child failure is silently dropped when the block returns a failure.** 16 line 26 `return Missing` (header: "so the same join does not replace it") and 17 line 36. The caller sees `Missing` and the `WalkError` / `FileError` is gone with no log. Round 1's complaint was that a failed child must not vanish; this rule makes it vanish exactly when the author returns an unrelated error. The rule is also by value, so `return cache_miss_error` and `return 0` take different paths for the same author intent. Report both (an error with a cause) or say why not.
- **N4. A statement without `;` expresses a value into the block.** 13 lines 28-31: `group.spawn(@size_of(paths[0]))` newline `0` (round 1 had `;` after the spawn; round 2 dropped it). Under LANGUAGE.md:280-310 that block expresses two values (handle, 0), but `R` is one type parameter. The same shape is in 04 line 21, 07 line 33, 14. Define the value count of a scope block with statements, or require `;`.

**Should-fix**

- **N5. Handling a child failure does not clear it.** 16 line 17-18: `<WalkError> => return 0` has matched the failure from `job.wait`, and the join still fails the group with it. Users expect an observed failure to be consumed (Python `TaskGroup` aside).
- **N6. `with` means two things.** `bracket(...) with log` (10) and `task.tasks with group` (15) read as Python's `with` binding the thing before it; in `interruptible with (ctrl_c group)` the bound values come from the callee. `do with pattern` is also permitted and "not required", so two spellings exist for one call.
- **N7. The defer rule is a language semantic decided here for a feature not in the front end.** round2.md "Defer failures, for every defer" changes what `return` means for every function with a `defer` that can fail (Go, Swift and Rust keep the return). That belongs in David's queue, not inside a scope-block round.
- **N8. Tag spelling is two spellings of one event.** 06 line 11 `<ctrl_c.CtrlC>`, 12 line 8 `<CtrlC>`. v6 spelling, but the user must know "one source or several" to choose.
- **N9. `retry` and every repeated block are out.** 11 is now `traced`, a once-only wrapper. No scope helper can iterate (`for_each_line with line {}`), the commonest trailing-block use in Ruby, Kotlin and Swift. The cost is stated; the design should say what the future marker is (round2.md only cites `#insert`).
- **N10. Cost: stop-then-join** adds a flag and a defer body into every `tasks` call; the library shows `finished = true` hand-managed (round2.md `tasks`), which is exactly the kind of "remember a second step" David disliked.

## 3. Programs rewritten to dodge their case

- **07.** Round 1 had the protected flush inline in the `select` arm inside `tasks` inside `catch_ctrl_c`, with `return` in the arm. Round 2 moves it into `flush` (lines 22-26), so the shield block no longer contains `return` or a match. The nesting the program was written for is gone.
- **08.** Added a channel `done` and `done.receive or_throw;` (lines 20, 29-30) only so the child's `FileError` is not lost behind `return Missing` (N3). The workaround is hand synchronization; the 4s and 5s hide that cost.
- **11.** `retry` replaced by `traced`; nothing here needs a scope (a function with `defer` does the same).
- **14.** The `parallel` return and `group.spawn`-from-`parallel` lines (my ?6, ?7) became comments (lines 3-5); neither case is written.
- **02.** Added six lines draining `ctrl_c.next(timeout=0s)` (lines 19-22). round2.md says a queued press never becomes `Interrupted`, so the drain does nothing the rules need.
- **04.** `if hit is? Closed` became `<Canceled> => Canceled or_throw` (line 24-26): works, but reads as a forward of a value, which the author's own dogfood flags.
- **15.** `ctrl_c.pending` replaced by `url =? "stop"` (line 35); the original line tested the borrowed listener inside the block's loop; the name is now unused.

## 4. Grades (O D C S F)

| # | Program | O | D | C | S | F | Floor |
|---|---|---|---|---|---|---|---|
| 01 | repl | 4 | 4 | 4 | 5 | 4 | 4 |
| 02 | shell | 3 | 3 | 3 | 4 | 3 | 3 |
| 03 | search_save | 4 | 3 | 4 | 4 | 4 | 3 |
| 04 | early_return | 3 | 3 | 4 | 4 | 3 | 3 |
| 05 | nested_catch | 4 | 4 | 4 | 5 | 4 | 4 |
| 06 | game_loop | 4 | 4 | 4 | 4 | 4 | 4 |
| 07 | server_flush | 3 | 3 | 4 | 4 | 3 | 3 |
| 08 | cli_throw | 3 | 3 | 3 | 3 | 3 | 3 |
| 09 | break_loop | 3 | 3 | 4 | 4 | 3 | 3 |
| 10 | bracket | 4 | 4 | 3 | 4 | 4 | 3 |
| 11 | traced | 4 | 4 | 4 | 5 | 3 | 3 |
| 12 | dashboard | 4 | 4 | 5 | 4 | 4 | 4 |
| 13 | expr_value | 3 | 3 | 3 | 3 | 3 | 3 |
| 14 | parallel_comprehension | 3 | 3 | 3 | 4 | 3 | 3 |
| 15 | two_libraries | 3 | 3 | 3 | 3 | 3 | 3 |
| 16 | return_replaced | 3 | 3 | 4 | 3 | 3 | 3 |
| 17 | failing_close | 3 | 3 | 4 | 3 | 2 | 2 |

Floor: **2** (17, complete).

## 5. Every score under 5

01. O4 line 8-11: one `??<Interrupted> {...} ?? break` carries Ctrl-C, EOF and exit. D4 line 8: `Interrupted` appears because a catcher is up; nothing on the line says so. C4: 15 lines against Python's `try/except KeyboardInterrupt` around the loop. F4: no Ctrl-C during the loop body outside `input`.
02. O3 line 19-22: a 4-line `match` with two empty arms to drain; rules say it is not needed. D3 line 1-3: SIGINT to the child only in a comment. C3 same lines. S4: `spawn` failure after output. F3: no way to say the child is in the foreground group.
03. O4 line 24: `match ... do { save(best) } {` reads as two blocks. D3 line 15: `or_throw` in `save` forwards `Canceled` that the shield makes `Timeout`: the reader must know provenance. C4: the five-line match. S4: the save error arm. F4: the call's type (N1).
04. O3 line 26 `<Canceled> => Canceled or_throw`. D3 same. C4 line 21 (`group.spawn(...)` statement). S4: `return path` while the scan fails is replaced by `WalkError` (rule, not visible). F3: value count (N4).
05. O4 line 6, 17: `do {` with a bare return inside. D4: that the inner catcher wins is in comments only. C4 line 6-9. F4: restoring the outer catcher is in a comment, never exercised.
06. O4, D4 line 11-12: qualified `<ctrl_c.CtrlC>` versus 12's `<CtrlC>` (N8). C4 line 11. S4: `play(10) or_throw` leaves `main` on a genuine `Canceled`. F4: the tick drain.
07. O3 line 35: `return` also stops `accept`; the line does not say it (the author agrees). D3 same. C4 line 31-36 (three nested blocks). S4: after `<lines.Closed> => break` a fall-through join does not stop `accept`. F3 line 22: flush moved to a helper (dodge); N4 at line 33.
08. O3 line 20, 29: `done` channel exists for ordering only. D3 line 30. C3: 15 lines for a 4-line job in Python. S3 line 31: `return Missing` loses a child failure unless the author adds the channel (N3). F3.
09. O3 line 14: `or_throw` that leaves for one error and becomes `Timeout` for another. D3 same (N1). C4 line 12-18. S4: `check_cancel` line 12 is needed to avoid hiding a parent cancel. F3: typing (N1).
10. O4, D4 line 24: `@open_log(p"app.log")` partial application plus `<T E R>`. C3 line 24: Python `with open_log(path) as log` is shorter. S4 line 27: a failing close replaces `return` silently. F4: no spelling for a non-failing close.
11. O4, D4 line 18: `scope(:> R)`. C4. F3: no scope in this program is needed; the generic helper case is gone (N9, dodge).
12. O4, D4 line 8: `ctrl_c.next(timeout=2s)` against `ctrl_c.next` in 06. S4: `return` in `<CtrlC>`. F4: nothing for a long non-waiting body.
13. O3 line 15-17: shield, block, `??<Timeout> {}`, `or_throw;` in one unbraced `if`. D3 line 15, 21: `do with` required nowhere but accepted. C3 same. S3 line 28-31 (N4). F3: no case with `with` on its own line after a call (multi-line `if` at line 21 works only because of the marker).
14. O3 line 16-18: two `continue`s that mean the same loop. D3 same. C3 line 15-19. S4. F3 lines 3-5 (parallel cases are comments).
15. O3 line 36-38: `return -1` three scopes deep leaves `crawl`, `page` never -1. D3 line 17-18 (N2). C3 line 34-40. S3 (N2: a spawned failure through `interruptible` is untyped). F3: `ctrl_c group` unused.
16. O3 line 17-18: `return 0` that the join turns into `-1`. D3 line 26: `return Missing` kept. C4. S3 line 15: the author wrote `return` and the function continued, and the handled failure still fails the group (N5). F3 line 26: `WalkError` dropped (N3).
17. O3 line 29-31: `return 1` becomes `-1`. D3 line 31: where the failing `or_throw` goes (N1). C4. S3 line 36: `FileError` dropped (N3). F2 line 31: `append_file(...) or_throw;` forwards `FileError` out of `replaced = ():>int`, or is the call's result: the design says both.

## 6. Comparison with dogfood-round2.md (floor 4)

Its floor 4 does not hold. The author graded every `5` on safe and complete for 03, 04, 07, 08, 09, 13-17; the lines it cites cost points are all "a rule this round kept on purpose", which is not a reason to give a 4 for the user but a reason not to iterate. The rest of its table reads the rules as settled when they conflict (N1), when the helper cannot be typed (N2), and when a program was rewritten to avoid the trap (08, 07, 14). It also gives 11 a 5 on complete after removing the case the program existed for. Its own 16 and 17 grade `safe` 4 while describing a `return` the function does not obey and a failure it throws away.

## 7. Are the remaining 4s inherent?

Mostly. 01 D, 05 D/F, 12 O/D and 06 are limits of decided v6 surface (`Interrupted` on console reads, `<CtrlC>` tag spellings, qualified `select` arms) and of two events in one loop; they are fine. The 3s are not inherent: N1-N4 are design gaps and 08, 07, 14, 15, 16, 17 depend on them. 10 C3 is inherent until cleanup is decided.
