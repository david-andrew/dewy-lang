# Dogfood: runtime-chosen settings, round 3

Rules: `round2.md`. This round only replaces `02` and `13`. Every other program is graded from `programs-r2/`, on the same lines as `dogfood-round2.md`. Axes: O obvious, D discoverable, C concise, S safe by default, P complete. A score under 5 names the line.

Python `zoneinfo` and a `with` block, Go `GOMAXPROCS` and `debug.SetMemoryLimit`, Rust `rayon`, TypeScript worker counts and `Intl`, and Swift task priority all make the zone or the pool an argument. None of them give a call-scoped core cap that a task keeps after the call returns. That is why the zone lines and the callee lines stay at 4.

## What changed

| Program | O | D | C | S | P | Lines under 5 |
|---|---|---|---|---|---|---|
| 02 checks_harness | 5 | 5 | 5 | 5 | 4 | P: `probe(xs 1)` (`programs-r3/02_checks_harness.dewy:13`). This is the only call, and it sits under `$runtime_checks` (`:11`). A call of `probe` with checks off is the compile error in round2.md. Putting that call in the file would make the file not a program. |
| 13 fold_call | 5 | 5 | 5 | 5 | 5 | The fold is `user_stamp` on `2026-11-01T01:30` (`programs-r3/13_fold_call.dewy:15`). The gap is the same function on `2026-03-08T02:30` (`:16`). |

## Unchanged, still under 5

| Program | O | D | C | S | P | Lines under 5 |
|---|---|---|---|---|---|---|
| 01 laptop_server | 5 | 4 | 5 | 5 | 5 | D: `run()` (`programs-r2/01_laptop_server.dewy:5`). The cap is written on `laptop`. `run` gets it by dynamic extent. |
| 03 game_profile | 5 | 5 | 5 | 4 | 5 | S: `$program.max_memory = 256MiB` (`programs-r2/03_game_profile.dewy:5`). Past that the process ends. |
| 04 request_memory | 5 | 5 | 5 | 5 | 4 | P: `serve("ping")` (`programs-r2/04_request_memory.dewy:16`). `page` (`:12`) stays charged to both budgets, and ping is four copies. There is no expression for bytes charged. |
| 05 user_zone | 4 | 4 | 5 | 5 | 5 | O and D: `printl"{user.name}: {today}"` (`programs-r2/05_user_zone.dewy:5`). `today` does not take the zone. The next line is the same function, so it sees the zone too. |
| 06 bench_cores | 5 | 4 | 5 | 5 | 5 | D: `{ $program.max_cores = 1; work() }` (`programs-r2/06_bench_cores.dewy:6`). The three blocks are right. The compiler still warns that `work`'s loop was not folded. |
| 07 task_outlives | 5 | 4 | 5 | 5 | 5 | D: `app.spawn(@child(app done));` (`programs-r2/07_task_outlives.dewy:13`). `work` is started by `child` after `search` returns, on `search`'s budget. `@child(app done)` is ordinary partial application, and the `;` discards the handle. |
| 08 library + app | 5 | 5 | 5 | 5 | 5 | |
| 09 nested_caps | 4 | 5 | 5 | 5 | 5 | O: `$program.max_cores = 16` (`programs-r2/09_nested_caps.dewy:4`). `server` allows 8, so the call runs at 8 and warns. The line still says 16. |
| 10 config_cores | 5 | 5 | 5 | 5 | 5 | |
| 11 fast_math | 5 | 4 | 5 | 5 | 5 | D: `$fast_math` (`programs-r2/11_fast_math.dewy:15`). `dot` is compiled twice. The warning says so. The file does not. |
| 12 wasm_entry | 4 | 5 | 5 | 5 | 5 | O: `$program.max_cores = 4` (`programs-r2/12_wasm_entry.dewy:4`). On `wasm32` the run is at 1. |
| 14 replay | 5 | 4 | 5 | 5 | 5 | D: `let n = ch.receive or_throw` (`programs-r2/14_replay.dewy:12`). The sender runs because a waiting receive yields. The line is only a receive. |
| R1 indexer + app | 4 | 4 | 5 | 5 | 5 | O: `$program.max_cores = 8` (`programs-r2/R1_indexer.dewy:4`), called under laptop's 2. D: `h(words)` (`programs-r2/R1_app.dewy:10`). The table is the two handles. The cap is the declaration's cap, then the minimum with 2. |
| R2 debug_flag | 5 | 5 | 5 | 5 | 4 | P: `$fast_math` (`programs-r2/R2_debug_flag.dewy:10`). This is the runtime flag with two legal bodies. `$runtime_checks = debug` around an unproved index is the error in round2.md, and it is not a line here. |
| R3 zone_server | 4 | 4 | 5 | 5 | 4 | D: `printl"audit {r.user} {today}"` (`programs-r2/R3_zone_server.dewy:12`). The zone was set in `handle`. O: `body="ping"` (`:31`) under 32MiB. P: `let pages = [parallel r in reqs handle(r app)]` (`:25`). One 32MiB budget per handler, 512MiB above them, charges kept on the returned arrays. None of that is an expression. |

## Floor

4. It is `run()` in `programs-r2/01_laptop_server.dewy:5`, and the same kind of line elsewhere: the cap, the zone, or the charge is in force and not written at the use. Making the looser literal a compile error, or giving `today` a zone argument, or adding a bytes-charged spelling, is a different design. Not a further round.
