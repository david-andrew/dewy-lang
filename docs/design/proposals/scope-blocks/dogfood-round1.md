# Dogfood, round 1

Scores are obvious, discoverable, concise, safe by default, complete. A 5 means that column needs no change. The other columns are the same five scores for the usual spelling in Python, Go, Rust, TypeScript, and Swift.

| Program | Dewy | Python | Go | Rust | TypeScript | Swift |
|---|---|---|---|---|---|---|
| 01 REPL | 5 5 5 5 5 | 5 5 4 4 5 | 3 3 3 4 3 | 3 2 3 3 3 | 4 4 4 3 4 | 2 2 2 3 2 |
| 02 shell | 5 5 5 5 5 | 4 4 4 4 4 | 4 3 3 4 4 | 3 3 3 4 3 | 4 3 4 3 3 | 2 2 2 3 2 |
| 03 save on Ctrl-C | 5 5 5 5 5 | 4 4 3 4 4 | 4 3 3 4 4 | 3 3 3 4 4 | 4 3 3 3 4 | 2 2 2 3 3 |
| 04 early return | 5 5 5 5 5 | 4 4 4 4 4 | 3 3 3 4 3 | 4 4 4 5 4 | 3 3 3 4 3 | 4 3 4 4 4 |
| 05 nested catch | 5 5 5 5 5 | 5 4 4 4 5 | 3 3 3 4 3 | 3 2 3 3 3 | 4 3 3 3 4 | 2 2 2 3 2 |
| 06 game loop | 5 5 5 5 5 | 4 4 4 4 4 | 3 3 3 4 3 | 3 3 3 4 3 | 4 3 4 3 3 | 3 2 3 3 3 |
| 07 server flush | 5 5 5 5 5 | 4 3 3 4 4 | 4 3 3 4 4 | 3 3 3 4 4 | 4 3 3 3 4 | 2 2 2 3 3 |
| 08 CLI throw | 5 5 5 5 5 | 5 5 4 4 5 | 4 4 4 4 4 | 4 4 4 5 4 | 4 4 4 4 4 | 4 3 4 4 4 |
| 09 break | 5 5 5 5 5 | 5 5 4 4 5 | 4 4 4 4 4 | 4 4 4 5 4 | 4 4 4 4 4 | 3 3 3 4 3 |
| 10 bracket | 5 5 5 5 5 | 4 4 3 4 5 | 4 4 4 3 4 | 4 3 3 5 4 | 4 3 3 3 4 | 4 3 3 4 4 |
| 11 retry | 5 5 5 5 5 | 5 4 4 4 5 | 4 4 4 4 4 | 4 4 4 5 4 | 4 4 4 4 4 | 4 3 4 4 4 |
| 12 dashboard | 5 5 5 5 5 | 4 3 4 4 3 | 4 3 3 4 4 | 3 3 3 4 3 | 4 3 4 3 3 | 2 2 2 3 2 |

## Why the Dewy scores stay at 5

No line asks the reader to pass a `return` or an `or_throw` along by hand. The braces are not a function literal: there is no `=>`. That is the whole difference from the callback shape, and it holds in every program.

- **01, line 8.** `return` is written in `repl`. Line 12 runs only when the loop `break`s on end of input. `continue` on line 7 targets that loop. Ctrl-C during `input` is `Interrupted`, which the console type already has.
- **02, lines 11–13.** `exit` returns the status from `shell`. The catcher is the brace, so the next prompt still runs after a command. The child receiving SIGINT is the existing process-group rule, not a new fact this syntax hides; Python's `subprocess` call doesn't show it either.
- **03, lines 20–25.** The shield is the brace around `save(best)`. `Timeout` is a result of that call, matched beside the path and the file error. `return Canceled` on line 25 is in `main`, outside the shield, so exit 130 stays put.
- **04, lines 22–24.** `return none` and `return hit` leave `find`. Line 22 runs only after `Closed`, which `scan` sends once the walk has succeeded, so that return is none. A `WalkError` fails the child; the blocked `receive` then sees the group's cancellation, and the join's error replaces that `Canceled` rather than becoming a fake miss. The signature already lists `WalkError`.
- **05, lines 6 and 14.** The password `return none` leaves `confirm`, which is the function that wrote that brace. `quit` leaves `repl`. Nesting is two calls, and the inner one restores the outer catcher on both paths.
- **06, lines 11 and 15.** Ctrl-C returns from `play` to the menu. Clearing the count `break`s the loop and prints `cleared` before the catcher ends with the brace. `defer frames.stop()` is inside the brace, so both exits stop the ticker.
- **07, line 35.** `return` leaves `serve`. The inner `tasks` defer joins first, then the catcher pops. The flush is its own shield, so its deadline is `Timeout` in the match and a parent cancel would be masked for those five seconds.
- **08, lines 15 and 18.** A missing argument returns `Missing` from `load`. `read_text or_throw` forwards the file error from `load` after the group joins. `warm` is a child of that group, so it is joined too.
- **09, lines 11–13.** `continue`, `break`, and `or_throw` are the three exits, each aimed at `serve_until`'s loop or `serve_until` itself. The shield pops before any of them land.
- **10, lines 12–24.** `bracket` is a normal function with a `scope` parameter. `quit` returns from `dump`, and `close_log` runs first because it is the scope function's `defer`. Line 25 does not run on quit. A failing close becomes `dump`'s `FileError` instead of a silent success.
- **11, lines 31–32.** The brace is written in `load`. `return` leaves `load`. `or_throw<Canceled>` leaves `load`. `NetDown` is a value, so `retry` sees it and tries again. Nothing in the call catches a failure the block already forwarded.
- **12, line 8.** One source, so the arm is `<CtrlC>`. `return` leaves `watch`, and line 16 runs.

Safe by default is 5 throughout because the brace is the extent: the listener and the group are borrowed and cannot be stored past it, protection does not clear a parent cancel, three rapid presses still force exit, and none of this is an unsafe opt-in.

## Other languages, in short

Python's `with` and `try` already give `return` and `break` the enclosing function, which is why 05, 08, 09, and 11 score well there. What they don't give is a Ctrl-C region whose end restores the previous handler without `signal.signal`, or a deadline that shows up as `Timeout` on the call. Go and Rust can return from the outer function only by writing the body in that function; a callback or a goroutine cannot. Their Ctrl-C tools are process-wide (`signal.Notify`, `ctrlc::set_handler`) and the deregistration is a second step. TypeScript's `readline` `'SIGINT'` is the same shape, with `removeListener` to remember. Swift has no scoped Ctrl-C; `DispatchSource` is a long way from a block. Rust's `scope` and Swift's `defer` score well on the early-return and break programs, where the problem is control flow rather than the signal.

## Floor

5. No line needs a different spelling. Round 1 stands.
