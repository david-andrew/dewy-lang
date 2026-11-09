# Dogfood of `select`, round 7

Programs in `programs-r7/`. Scores are obvious, discoverable, concise, safe, complete. Nothing was compiled. `17a` is the long way and is not in the floor. The strawman selects and `@job.wait` programs are not carried forward.

## Recommended programs

| # | Program | Obvious | Discoverable | Concise | Safe | Complete | Floor |
|---|---|---|---|---|---|---|---|
| 01 | chat, no poll | 4 | 4 | 4 | 5 | 5 | 4 |
| 02 | one `string` arm | 5 | 5 | 5 | 5 | 5 | 5 |
| 03 | two tickers | 4 | 4 | 3 | 5 | 4 | 3 |
| 04 | `send`, `.reason` | 5 | 4 | 4 | 5 | 5 | 4 |
| 05 | Ctrl-C | 4 | 4 | 4 | 5 | 4 | 4 |
| 06 | forward | 5 | 4 | 5 | 5 | 5 | 4 |
| 07 | past deadline, poll | 5 | 4 | 4 | 5 | 5 | 4 |
| 08 | two polls | 5 | 5 | 5 | 5 | 5 | 5 |
| 09 | `open` after the loop | 5 | 4 | 5 | 5 | 5 | 4 |
| 10 | two closes | 4 | 4 | 4 | 5 | 5 | 4 |
| 11 | library `Stdout` | 5 | 4 | 5 | 5 | 5 | 4 |
| 12 | user brands | 4 | 4 | 3 | 5 | 4 | 3 |
| 13 | three `Closed` spellings | 4 | 3 | 4 | 4 | 4 | 3 |
| 14b | `race(@load.(sources)...)` | 5 | 4 | 5 | 5 | 5 | 4 |
| 15b | `race(@cache.receive @load(url))` | 5 | 4 | 5 | 5 | 5 | 4 |
| 16b | `within` | 5 | 5 | 5 | 5 | 5 | 5 |
| 17b | `first_ok(@load.(sources)...)` | 5 | 5 | 5 | 5 | 5 | 5 |

Floor of this table: **3**. It is 03, 12, and 13.

05 is still complete 4. The `<CtrlC>` arm does not run, and there is no `Interrupted` read. That was left.

## What type-directed matching costs

These are the 3s. They are not defects of the calls around them.

- **03 and 12, concise 3.** Telling two same-typed sources apart takes two minted names and a wrap at every send. Go, Tokio, and Swift use the case label. The library owning `Stdout` and `Stderr` is the best case, and program 11 is that case: the user prints the line. Program 02, which does not need to know, is one arm.
- **13, discoverable 3.** `<Closed<Event>>`, `or_throw<Closed<Event>>`, and `or_throw<Closed>` are three spellings. Go has `v, ok`.

A migrant who writes `loop { select }` and hits the spin error is pointed at `merged`. That is the 4 on discoverable for 01, 06, and 09.

## Checked

- A past absolute deadline wins under `'fair'` on both calls in 07, and the following polls take 4 and then 5. `timeout=0s` in 08 takes both buffered replies.
- 10's inbound close drains with `send`. Its outbound close is `Closed<Reserved<Job>>` and spills.
- 04 reads `.reason` and forwards `Canceled` with `or_throw`.
- 09 binds `merged`, iterates the handle, and prints `gave up` while `open` is true.
- `LANGUAGE.md` line 385: every argument group in an ungrouped `@` chain partially evaluates. `.( )` is an argument group. 14b and 17b use `@load.(sources)`.
- v5 line 24: `Task.wait()` keeps `()`. It is not a wait in `select`.
- `type of int64` is unsupported (`LANGUAGE.md`, "Errors as values"). `type of string` is the same gap.
