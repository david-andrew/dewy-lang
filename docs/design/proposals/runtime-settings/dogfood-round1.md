# Dogfood: runtime-chosen settings

Round: `round1.md`. Fourteen programs. Scores are judgments from writing them and from the same programs in Python, Go, Rust, TypeScript, and Swift. They are not a user study and not a compiler run.

A 5 means no line wants a different surface. The comparisons are the ordinary way each language would do the same job: Python `contextvars` / `resource` / `zoneinfo`, Go `runtime.GOMAXPROCS` and `debug.SetMemoryLimit`, Rust `rayon::ThreadPoolBuilder` (process-wide once it is built), TypeScript worker counts and `Intl` time zones, Swift task priority and no process core cap.

No line below costs a point.

## 01 laptop, server, or both

`programs/01_laptop_server.dewy`

| obvious | discoverable | concise | safe | complete |
|---|---|---|---|---|
| 5 | 5 | 5 | 5 | 5 |

The line above `laptop` is the cap of a call to `laptop`, and the same shape above `server`. `both` calls them in order; each `run` prints the cap of that call, so the second call is not stuck at 2. An unknown argument exits 2.

Python and Go can set a process cap, and the second setting replaces the first for the whole process, including a task the first call already started. Rust's pool is built once. The Dewy program is shorter than two entry files and does not have a process-wide assignment to undo.

## 02 checks harness

`programs/02_checks_harness.dewy`

| obvious | discoverable | concise | safe | complete |
|---|---|---|---|---|
| 5 | 5 | 5 | 5 | 5 |

`sum_of` is called with checks and without. The loop variable proves the body, so the two copies are the same and the design says they are merged with no warning. `probe` indexes with a parameter. That is unproved, so it lives under `checked`, whose prefix is `$runtime_checks`. There is no plain call of `probe`; a plain call would be the existing obligation error, not a run that skips the check.

Rust's `debug_assert` disappears in release. This program cannot do that, which is the safe default already decided for Dewy. Go has no equivalent split.

## 03 game profile

`programs/03_game_profile.dewy`

| obvious | discoverable | concise | safe | complete |
|---|---|---|---|---|
| 5 | 5 | 5 | 5 | 5 |

The file says `low` or `full`. Each word is a function with its own cores and memory. A bad word exits 2. Nothing is read from the environment.

A Python dict of configs is the same length and does not by itself cap the process. Go would set `GOMAXPROCS` for everyone. Two functions is the whole mechanism.

## 04 request memory

`programs/04_request_memory.dewy`

| obvious | discoverable | concise | safe | complete |
|---|---|---|---|---|
| 5 | 5 | 5 | 5 | 5 |

`serve` is 512MiB and holds `cache`. `handle` is 32MiB and is who allocates `chunks`. The cache is not the handler's budget, and the handler's cap does not stay in force after it returns. This run's body fits; a body whose array does not fit fails as an allocation already fails, inside the handler only.

Go's `SetMemoryLimit` would lower the server, cache included, and would still be lowered after the request. Rust has no standard request budget. The manual length check I almost added would have been a second, unexplained limit; the cap is the limit, so it is not there.

## 05 zone per user

`programs/05_user_zone.dewy`

| obvious | discoverable | concise | safe | complete |
|---|---|---|---|---|
| 5 | 5 | 5 | 5 | 5 |

`zone(text)` parses the name, and the `Zone` is what the prefix receives, so a bad name is `ValidationError` in `main` rather than a failure invented by the setting. `today` is inside the prefixed `printl`, so it reads that user's zone. The next report starts from whatever the caller had, which here is nothing.

Python `zoneinfo` passed down by hand is as safe and longer. Go's process-wide local is the wrong tool. Swift and TypeScript format with an explicit zone argument and have nothing that covers a whole call.

## 06 three core counts

`programs/06_bench_cores.dewy`

| obvious | discoverable | concise | safe | complete |
|---|---|---|---|---|
| 5 | 5 | 5 | 5 | 5 |

Three calls, three prefixes, one `work`. The parallel comprehension is under the cap of that call, then the cap pops. A small join may still run inline, which is the existing scheduler rule; `available_cores` in the line is the cap even when the clock barely moves.

Go can do this with three `GOMAXPROCS` assignments and will not restore a task from the first call. Rayon wants three pools or one pool built for the largest count.

## 07 task outlives the call

`programs/07_task_outlives.dewy`

| obvious | discoverable | concise | safe | complete |
|---|---|---|---|---|
| 5 | 5 | 5 | 5 | 5 |

`search` returns, `main` prints that, and only then receives the task's message. The message was formatted in the task, so the `2` it reports is the cap `search` pushed, not a cap of `main`. The handle is discarded with `;` because the background group owns the task.

Python `contextvars` copy into a task is the same idea and more machinery. A Go `GOMAXPROCS(2)` around the spawn does not stay on that goroutine after the function sets it back.

## 08 library defaults

`programs/08_library.dewy`, `programs/08_app.dewy`

| obvious | discoverable | concise | safe | complete |
|---|---|---|---|---|
| 5 | 5 | 5 | 5 | 5 |

Importing the library does not install its `main`. That `main` is the 8-core cap for `dewy 08_library.dewy` only. The app's `main` is 2. `search` uses the caller's program cap. `index_one` says its parallel work is at most 1, which is still true under either main. No line asks for more program cores than the caller allows, so there is no error and no warning.

A Go library that calls `GOMAXPROCS` changes the server. A Rust library that builds the global pool first wins. This library does neither.

## 09 nested caps

`programs/09_nested_caps.dewy`

| obvious | discoverable | concise | safe | complete |
|---|---|---|---|---|
| 5 | 5 | 5 | 5 | 5 |

`server` is 8 and says so by calling `leaf` first. `handler` is 2, and 2 is inside 8, so the second line is 2. An inner program cap of 16 would not be in this file: it is a compile error at the call, which is why it is not an example that runs.

Python's inner `setrlimit` can be rejected by the operating system with a different error. The Dewy error is at the call, naming both lines, before it runs.

## 10 cores from a file

`programs/10_config_cores.dewy`

| obvious | discoverable | concise | safe | complete |
|---|---|---|---|---|
| 5 | 5 | 5 | 5 | 5 |

The file is an integer. `to_int` can fail, and `cores <? 1` exits 2. The `else` is what makes `play`'s prefix a proved positive int, so the push is not a runtime check. No new spelling: the prefix's value is an ordinary expression.

Go's `GOMAXPROCS(n)` is one call and sticks. This is one prefix and does not stick.

## 11 fast and plain

`programs/11_fast_math.dewy`

| obvious | discoverable | concise | safe | complete |
|---|---|---|---|---|
| 5 | 5 | 5 | 5 | 5 |

`fast` and `plain` both call `dot`. The length mismatch is a value, so neither vector is rejected. The copies differ, so the design's warning fires once on `dot`. Direct calls do not dispatch.

Rust would write two functions or a generic `const FAST`. The Dewy source is the two prefixes. A flag choosing `$fast_math` at run time is legal and warned; this program does not need it, so it does not pay the branch.

## 12 wasm entry

`programs/12_wasm_entry.dewy`

| obvious | discoverable | concise | safe | complete |
|---|---|---|---|---|
| 5 | 5 | 5 | 5 | 5 |

`$target` is a header, fixed for the build. The profile is still a call, `game.low_power()`, with that function's caps. A runtime `$target` is not in the file because it would be the compile error the design names; the fix is this entry file.

Python, Go, Rust, TypeScript, and Swift all split targets by build, not by `argv`. Dewy matches them there and does not make cores join that list.

## 13 fold and gap for one call

`programs/13_fold_call.dewy`

| obvious | discoverable | concise | safe | complete |
|---|---|---|---|---|
| 5 | 5 | 5 | 5 | 5 |

Zone, fold, and gap are one prefix on the `printl` that parses the wall time. The zone is a runtime `Zone`, so the literal is parsed when the call runs. The caller's zone, if it had one, is back on the next line.

Passing `fold=` and `gap=` and `zone=` on `zoned` is the other legal spelling and is longer once more than one call should share them. Python's `zoneinfo` does not carry fold and gap for the dynamic extent of a call.

## 14 replay

`programs/14_replay.dewy`

| obvious | discoverable | concise | safe | complete |
|---|---|---|---|---|
| 5 | 5 | 5 | 5 | 5 |

`replay` is `$parallel.off`: the three steps run in source order, including if a later edit makes one of them call another `parallel`. The second block in `main` has no prefix, so it keeps the normal schedule. `$program.max_cores = 1` is not used, because that would cap cores and still not promise order.

Go's `GOMAXPROCS(1)` is the cap, not the order. Rust tests that want a deterministic schedule serialize by hand. The prefix is the shorter of those.

## Floor

5. The nearest miss was a length check beside the memory cap in an earlier draft of program 04. It read as a second policy. The cap is the only limit, and that draft is not the program above.
