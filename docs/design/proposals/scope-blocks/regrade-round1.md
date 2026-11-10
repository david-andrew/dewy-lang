# Independent regrade of round 1 (scope blocks)

Read: brief.md, round1.md, programs 01-12, LANGUAGE.md (blocks, multi-values, parallel), discussion_points.md.
dogfood.md not read. My programs are in `programs-regrade/` (13, 14, 15); lines marked `(?n)` are where the design says nothing.

Axes: O obvious, D discoverable, C concise, S safe by default, F complete. Comparison set: Python (try/except KeyboardInterrupt, with, asyncio.TaskGroup), Go (signal.Notify, errgroup, defer), Rust (tokio::select, scopeguard), TypeScript (AbortController), Swift (withTaskGroup, defer).

## Grades

| # | Program | O | D | C | S | F | Floor |
|---|---|---|---|---|---|---|---|
| 01 | repl | 4 | 4 | 5 | 5 | 4 | 4 |
| 02 | shell | 4 | 3 | 5 | 4 | 4 | 3 |
| 03 | search_save | 3 | 3 | 3 | 4 | 4 | 3 |
| 04 | early_return | 3 | 3 | 4 | 3 | 3 | 3 |
| 05 | nested_catch | 4 | 4 | 4 | 5 | 4 | 4 |
| 06 | game_loop | 3 | 3 | 4 | 4 | 3 | 3 |
| 07 | server_flush | 3 | 3 | 3 | 2 | 2 | 2 |
| 08 | cli_throw | 4 | 3 | 5 | 4 | 3 | 3 |
| 09 | break_loop | 3 | 3 | 3 | 4 | 3 | 3 |
| 10 | bracket | 4 | 3 | 3 | 5 | 4 | 3 |
| 11 | retry | 3 | 2 | 3 | 3 | 2 | 2 |
| 12 | dashboard | 4 | 3 | 5 | 4 | 4 | 3 |
| 13 | expr_value (mine) | 3 | 2 | 4 | 3 | 2 | 2 |
| 14 | parallel_comprehension (mine) | 3 | 2 | 3 | 3 | 2 | 2 |
| 15 | two_libraries (mine) | 2 | 2 | 3 | 3 | 2 | 2 |

Floor: 2. No program of the fifteen is a clean 5 on any axis I would defend; 05 and 01 are closest (the plain REPL shapes the design was made for do read well, better than Python's try/except KeyboardInterrupt around a loop).

## Why each score is under 5

**01 repl.** `input("> ") ??<Interrupted> { printl(""); continue } ?? break` (line 7): O/F. One line carries three jobs (Ctrl-C, EOF, loop exit) and the reader must know `input` returns `Interrupted` only because a catcher is up; nothing at the line says so (D). `task.catch_ctrl_c {` looks like a call followed by a block; only knowledge of the library says `return` below leaves `repl` (O). F: nothing shows what a real Ctrl-C does during a non-input wait in the loop body.

**02 shell.** `child.wait or_throw` (line 14): a Ctrl-C during the wait is queued on the listener and never seen by anyone; the comment is the only documentation that the child gets SIGINT (D). `let last = 0` mutated inside the block works silently, which is right, but the design never shows the user that this is a deliberate difference from a callback (D). F: a `spawn` that fails after partial output has no cleanup story.

**03 search_save.** Lines 18-22: `match task.protect_from_cancel(5s) { save(best) } or_throw<Canceled> {` is a `{` that is a scope block followed by a `{` that is the match body, on one line. A reader cannot tell which is which without knowing the callee (O, C: five lines plus a three-arm match to save a file; Python's `finally: save()` is one). Why `or_throw<Canceled>` is needed at all when the design says "there is no cancel thrown at the caller afterwards" is unexplained (D); every protect call will carry it (see should-fix 5).

**04 early_return.** `return hit` (line 24) inside `task.tasks`: the group joins first, and if a child failed, "a pending successful exit is dropped" so the function returns the child's `WalkError` instead of `hit`. The line says one thing and does another (O, S, F). `let hit = hits.receive or_throw` then `if hit is? Closed return none`: if `Closed` is an error `or_throw` forwards it (type error, `find` does not list `Closed`); if it is not, `or_throw` is wrong. The program does not say, and the design does not either (F). `group.stop()` before `return` shows the author knew the join waits for the child (see must-fix 3).

**05 nested_catch.** `let line = input(prompt) ??<Interrupted> { printl"cancelled"; return none } ?? return none` (line 7) is dense but readable. D: that the inner catcher "wins" is only in the round text, never at the call.

**06 game_loop.** Line 12 `<ctrl_c.CtrlC>`, line 13 `<frames.Tick>` versus 12_dashboard `<CtrlC>`: the tag spelling is not defined in round1 at all, and the two programs disagree (O, D, F). `return` in a match arm in a `loop` in a block: right, but the viewer has to know that `ctrl_c` is the block's name from the `with` three lines earlier.

**07 server_flush.** Defect: after the flush the block does `return`, which joins the group before leaving; `accept` is `loop true { tcp_accept ... }`, nothing stops it, and the catcher means no cancel arrives. The program hangs after printing "flushed" (S, F). The design's rule says only "joins before ... a `return` ... leaves". Whether a non-normal exit cancels children is undefined (must-fix 3). Also nested `task.catch_ctrl_c ... task.tasks ... task.protect_from_cancel` is three levels of borrowed names and one `return`; `return` position tells nothing about which scopes are unwound (C).

**08 cli_throw.** `if text =? "" return Missing` (line 21): if the sibling `warm` failed, `load` returns `FileError`, and `Missing` is lost. The design calls this deliberate, but the line reads as a plain early return (O, S). The `Missing` type used as a value (`return Missing`) is existing convention, fine.

**09 break_loop.** The header comment says "break inside the shield leaves the loop". It does not: `continue`, `break` and `problem or_throw` are in `match` arms outside the `{ probe(port) }` block. The program never exercises `break`/`continue` out of a scope block, so the headline feature is untested here (O, F). Same `match ... { } or_throw<Canceled> {` shape as 03 (C).

**10 bracket.** Call line `bracket(@open_log(p"app.log") @close_log) with log {` needs `@f(args)` partial application, a generic `<T E>` library, and a scope parameter to be understood (D). Python's `with open_log(path) as log:` is shorter and Rust's/Swift's `defer` is two lines (C). `with` here reads like Python's `with` (it binds the resource) while in `task.tasks with group` it names a value the callee made: the same keyword has two readings (O).

**11 retry.** `retry = (times:int body:scope):>string | Attempts` hard-codes `string` because `scope` has no result type: a generic retry cannot be written (F, the design promises "any library can define its own scope"). `match body() { page:string => ...; problem:error => ... }` is not exhaustive for a block that yields `none` or an int (S). The last attempt's cause is thrown away: `Attempts[tries=i]` (S). How a library author learns what `body()` returns is undefined: no `scope(...):>T` (D, O).

**12 dashboard.** `ctrl_c.next(timeout=2s)` is a call with an argument written like the zero-argument `ctrl_c.next` in 06. Tag `<CtrlC>` against 06's `<ctrl_c.CtrlC>` (D).

**13 expr_value (mine).** (?2) `if verbose task.protect_from_cancel(1s) { ... }`: is that `{` the call's block or the `if` body? Undefined. (?1) `let total = task.tasks with group { ... } or_throw`: precedence of `with`, `or_throw` and `??` after a block undefined. (?3) A call split across lines (`task.catch_ctrl_c` newline `with ctrl_c {`): newline termination undefined. (?4) A block that yields a value used as a statement: `:>void` bodies reject values and `void | E` results must be handled, so `task.tasks with group { ...; 0 }` needs `};` or an error; the design shows only the `;` after the block's last line.

**14 parallel_comprehension (mine).** (?5) `[loop f in files task.protect_from_cancel(1s) { if ... continue ... } ??<Timeout> continue]`: does `continue` in the block skip the comprehension element or continue an outer loop? (?6) `return` inside `parallel` is already an error; the message must say why now that the surrounding block allows `return`. (?7) A `Tasks` group read from a `parallel` body (worker threads): the borrow rule only forbids storing; "invoked from a spawned task is a compile error" covers `body`, not the borrowed value. A scope call (`protect_from_cancel`) in a parallel body is blocking? Undefined.

**15 two_libraries (mine).** (?8) `with (ctrl_c group)`: the spec says the pattern is "whatever `let` allows", but the scope parameter passes two values, not one pattern; `with a b`, `with (a b)` and `with [a b]` all read plausibly. (?9) `let page = task.protect_from_cancel(2s) { if url =? "quit" return -1; fetch(url) or_throw }`: `return -1` leaves `crawl`, so `page` is never -1. David's own note (discussion_points.md, "the rule with return will be that the thing gets returned up until the nearest thing that catches it, which could be an assignment") says the opposite for an assigned block. The design should say what a plain `{ }` in `let x = { ... return v }` does and show that the scope block matches it. Forwarding through two scopes (`body(ctrl_c group)` inside two inner blocks) works by the rules, but each exit crosses four defers (two scope functions, plus `span`), and the reader of the call site cannot see any of it.

## Must-fix (contradictions, undefined cases, understated costs)

1. **`{` is ambiguous without name resolution.** `match task.protect_from_cancel(5s) { save(best) } or_throw<Canceled> {` (03, 07, 09) and `if verbose task.protect_from_cancel(1s) { ... }` (13): the parser must know the callee is a scope function to decide whether `{` is a block, match arms, an `if` body or a `loop` body. That is context-sensitive parsing, against "no context sensitivity". The only rule given (`{` after `;` is an ordinary block) does not cover it. Fix: require parentheses or a marker in scrutinee/condition position, or mark the call site itself.
2. **`return` in an assigned block contradicts David's note and is not stated for plain blocks.** `let page = task.protect_from_cancel(2s) { if url =? "quit" return -1 ... }` (15). The design says "exactly as in a plain block" but never states the plain-block rule for an assigned block, and `discussion_points.md` says the nearest catcher may be the assignment. State the rule and check it against that note.
3. **Exit from `task.tasks` is undefined: do children get canceled?** 07 hangs as written (infinite `accept`, `return` joins forever); 04 needs a manual `group.stop()` before `return`. Define the cancel-on-abnormal-exit (`return`, `break`, `continue`, `or_throw`) for groups, as Trio/Swift do for errors, and say what a normal fall-through does.
4. **`scope` has no result type, so scope functions cannot be typed where defined.** `retry` (11) hard-codes `string`; the call's result type comes from "the block's value", and the failures the block forwards versus the failures the scope function adds (the `join` failure) are not combined by any stated rule. Specialization per call site means library bodies are only checked at callers (errors surface in user code) and "cost: linear" omits that every nested forwarding scope (15) is inlined into every call site.
5. **A `defer` failure silently replaces `return v`.** 04 `return hit` and 08 `return Missing` return a child's failure instead. This contradicts "`return` inside the scope returns from the enclosing function, exactly as in a plain block", asymmetrically (a failing defer does not replace an `or_throw` already started). The declared return type of every function calling `tasks` must then include join failures with no warning at the `return`.
6. **Value and `;` rules for a scope call used as a statement** (13 ?4, ?1). The call's result is the scope function's result; a valued block and a `void | E` result (`Timeout`) as a statement hit the existing "`:>void` bodies express nothing / handle or `;`" errors. The design shows none of these combinations.

## Should-fix

1. `with`: multi-value patterns (`with (a b)`, 15), newline continuation (13 ?3), and precedence against `??`/`or_throw` (13 ?1). `with` also reads as Python's resource binding in 10 and as a callee-made borrow in 06/07.
2. Tag spelling for `Ctrl-C` and ticker events: `<ctrl_c.CtrlC>` (06, 07), `<CtrlC>` (12), `<frames.Tick>`; never defined in round1.
3. `continue`/`break` inside a block that sits in a comprehension or `parallel` body (14 ?5, ?6, ?7): name the target and the error text.
4. Editor/diagnostic marking: nothing at `task.catch_ctrl_c {` says the braces share the function's `return`. Hover alone is weak; syntax highlighting for scope calls, or a visible marker, is needed to read `return` safely.
5. Drop the `or_throw<Canceled>` boilerplate on `protect_from_cancel`: if no cancel is thrown after the call, a result without `Canceled` would remove a line from 03, 07, 09.
6. Retry (11): show a `scope(...):>T` spelling and a generic `retry<T>` that keeps the cause of the last failure; add a non-exhaustive `match` check.
7. Programs 04 and 09: fix `Closed` handling and the false "break inside the shield" comment; add a real `break`/`continue`-out-of-block test (still missing in the set). The set also has no test of `defer` ordering, a failing `close` on `return` (10), or a `tasks` child failing while the block returns.
