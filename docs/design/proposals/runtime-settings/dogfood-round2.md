# Dogfood: runtime-chosen settings, round 2

Design: `round2.md`. Programs: `programs-r2/`. Axes: O obvious, D discoverable, C concise, S safe by default, P complete. A score under 5 names the line. Comparisons are Python `zoneinfo` / a `with` block, Go `GOMAXPROCS` and `debug.SetMemoryLimit`, Rust `rayon` pools, TypeScript worker counts and `Intl`, Swift task priority. None of those give a call-scoped core cap that tasks keep; several make the zone an argument, which is why the zone programs stay at 4.

## Grades

| Program | O | D | C | S | P | Lines under 5 |
|---|---|---|---|---|---|---|
| 01 laptop_server | 5 | 4 | 5 | 5 | 5 | D: `run()` (`01_laptop_server.dewy:5`). The cap is on `laptop`, and `run` gets it only by dynamic extent. |
| 02 checks_harness | 4 | 5 | 5 | 5 | 4 | O: `$runtime_checks` (`02_checks_harness.dewy:16`) wraps `sum_of`, which the loop already proves, so the block changes nothing a reader can see. P: `xs[i]` (`:9`) is the unproved index, and the file never calls it with checks off. That call is the compile error in round2.md; a file that contained it would not be a program. |
| 03 game_profile | 5 | 5 | 5 | 4 | 5 | S: `$program.max_memory = 256MiB` (`03_game_profile.dewy:5`). Past that cap the process ends. Shedding a load would be `$explicit_allocation_failure` on the module, which changes every allocation's type. |
| 04 request_memory | 5 | 5 | 5 | 5 | 4 | P: `serve("ping")` (`04_request_memory.dewy:16`). The handler returns `page` (`:12`) and the design charges those blocks to both budgets, but ping is four copies and the file never reads a byte count. |
| 05 user_zone | 4 | 4 | 5 | 5 | 5 | O and D: `printl"{user.name}: {today}"` (`05_user_zone.dewy:5`). `today` does not take the zone. The next line is in the same function, so it sees the zone too; that is the scope rule, and it is still ambient. Python, Rust, and Swift pass the zone into the call. |
| 06 bench_cores | 5 | 4 | 5 | 5 | 5 | D: `{ $program.max_cores = 1; work() }` (`06_bench_cores.dewy:6`). The three blocks are right, and the compiler still warns that `work`'s loop was not folded. The warning is the cost of comparing three caps. |
| 07 task_outlives | 5 | 4 | 5 | 5 | 5 | D: `app.spawn(@child(app done));` (`07_task_outlives.dewy:13`). `work` is a grandchild started from `child`, and the 2-core budget is `search`'s. `@child(app done)` is ordinary partial application; the `;` discards the task handle. |
| 08 library + app | 5 | 5 | 5 | 5 | 5 | |
| 09 nested_caps | 4 | 5 | 5 | 5 | 5 | O: `$program.max_cores = 16` (`09_nested_caps.dewy:4`). `server` allows 8, so this line runs at 8 and warns. The source still says 16. |
| 10 config_cores | 5 | 5 | 5 | 5 | 5 | |
| 11 fast_math | 5 | 4 | 5 | 5 | 5 | D: `$fast_math` (`11_fast_math.dewy:15`). `dot` is compiled twice. Nothing in the file says so; the warning does. |
| 12 wasm_entry | 4 | 5 | 5 | 5 | 5 | O: `$program.max_cores = 4` (`12_wasm_entry.dewy:4`). On `wasm32` the run is at 1. The print shows 1; the setting shows 4. |
| 13 fold_call | 5 | 5 | 5 | 5 | 4 | P: `$time.gap = 'next'` (`13_fold_call.dewy:9`). The string passed in is a fold (`01:30` on 1 November), so gap is never consulted. `zoned(text) or_throw` is what a runtime zone returns; the UTC literal stays a plain value. |
| 14 replay | 5 | 4 | 5 | 5 | 5 | D: `let n = ch.receive or_throw` (`14_replay.dewy:12`). Cooperative yield is why the sender on the earlier item can run. The line itself is only a receive. |
| R1 indexer + app | 4 | 4 | 5 | 5 | 5 | O: `$program.max_cores = 8` (`R1_indexer.dewy:4`), called under laptop's 2. D: `h(words)` (`R1_app.dewy:10`). The table is `@indexer.index` and `@indexer.index_quiet`; which cap applies is the declaration's cap, then the minimum with 2. |
| R2 debug_flag | 5 | 5 | 5 | 5 | 4 | P: `$fast_math` (`R2_debug_flag.dewy:10`). This is the runtime flag that has two legal bodies. `$runtime_checks = debug` around an unproved index is the error quoted in round2.md, and it is not a line in this file. |
| R3 zone_server | 4 | 4 | 5 | 5 | 4 | D: `printl"audit {r.user} {today}"` (`R3_zone_server.dewy:12`). The zone was set in `handle`, which has returned by the time a background task is obvious. O: `body="ping"` (`:31`) under a 32MiB cap. P: `let pages = [parallel r in reqs handle(r app)]` (`:25`). Shared 32MiB per handler, 512MiB above them, and charges kept on the returned arrays are specified and not visible here. |

## Floor

4. The 4s are the rule showing through the source: a callee does not repeat the cap (`01:5`), a looser literal is not what runs (`09:4`, `12:4`, `R1_indexer.dewy:4`), `today` does not name its zone (`05:5`, `R3:12`), and byte charges have no expression (`04:16`, `R3:25`). Closing those means a new spelling or making the looser line a compile error, which is the split behavior round 2 drops. Not a round 3.
