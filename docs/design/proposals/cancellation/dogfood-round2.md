# Dogfood, round 2

Thirteen programs are in `programs-r2/`. Programs 01, 02, 04, 07 and 10 are round 1's sources unchanged: each still type-checks under round 2's rules, and the §2.2 storage and argument rules were checked line by line. The rest were rewritten for the findings.

- **Axes:** obvious, discoverable, concise, safe by default and complete.
- **Compared against:** Python, Go, Rust, TypeScript and Swift.
- **Citations:** every score under 5 names its line.
- **Calibration:** grades take the regrade's harsher readings where it argued better.

| # | Program | Obvious | Discoverable | Concise | Safe | Complete |
|---|---|---|---|---|---|---|
| 01 | crawler | 4 | 4 | 4 | 5 | 5 |
| 02 | CLI, save on Ctrl-C | 4 | 4 | 4 | 5 | 4 |
| 03 | `race` / `first_ok` | 4 | 4 | 5 | 5 | 5 |
| 04 | `within` | 4 | 4 | 5 | 5 | 5 |
| 05 | spinner (`$until_others_finish`) | 4 | 5 | 5 | 5 | 5 |
| 06 | shared helper | 4 | 4 | 5 | 5 | 5 |
| 07 | CPU `check_cancel` | 5 | 5 | 5 | 5 | 4 |
| 08 | level 3: request in a job | 4 | **3** | 4 | 4 | 4 |
| 09 | server, SIGTERM drain | 4 | 4 | 5 | 4 | 4 |
| 10 | library, differing callers | 4 | 4 | 5 | 5 | 5 |
| 11 | `first_ok` backups, loser cleanup | 5 | 4 | 5 | 4 | 4 |
| 12 | queue, ticker, SIGTERM | 4 | 4 | 4 | 4 | 5 |
| 13 | background task | 4 | 4 | 5 | 5 | 5 |

**Floor: 3.** Program 08 scores 3 on discoverable, at line 25. If a caller forgets to put `task.cancel_request` in its job, nothing reports it, and the worker keeps decoding for a caller that is gone.

The link travels through a channel, so no analysis can see it. Go (`ctx` in the message), Rust (a token) and TypeScript (an `AbortSignal` field) have the same gap.

Round 1's other 3 in program 08, for obvious, is gone. Its two arms are now different types: `<Closed<task.CancelRequest>>` and `<Canceled>`.

## 01 crawler — 4 / 4 / 4 / 5 / 5

- **Obvious 4, line 13.** `loop url in urls` also ends when the worker is canceled (Q5), and that reads like the channel closing. Hover says "ends early when canceled". Nothing is published after the loop, so here the hazard is only one of reading.
- **Discoverable 4, line 18.** `<Canceled> => break` is required because every `parallel` item counts. You learn it from the exhaustiveness error, which names line 34.
- **Concise 4, line 18.** That arm is boilerplate in a program where nothing actually cancels a worker. Hover says so, but the arm is still required.
- **Against the peers:** shorter than Go, Rust and asyncio, with no `ctx` and no token.

## 02 CLI saves on Ctrl-C — 4 / 4 / 4 / 5 / 4

- **Obvious 4, line 22.** The handler's `return` leaves `optimize`. The block lives in a helper only so the save after it runs.
- **Discoverable 4, line 22.** It was a 3 in the regrade. The tempting `break` now warns: "Ctrl-C stays intercepted until the block ends … `return` from a function that holds the block" (round2 §2.7). The helper idiom still has to be learned.
- **Concise 4, lines 18–24.** Python's `try/except KeyboardInterrupt` is shorter.
- **Complete 4, line 33.** An interrupted run exits 0. Reporting 130 takes an `exit(130)` the program doesn't write.

## 03 `race` / `first_ok` — 4 / 4 / 5 / 5 / 5

- **Obvious 4, line 13.** `race` returns a fast failure over a slower success. The comment says why that is right for DNS (an authoritative "no such host"), but many readers would expect `first_ok`.
- **Discoverable 4.** Line 18's per-mirror spread is batch 7 surface. Lines 23–27: the comprehension's type depends on its caller, and only hover shows it.
- **Safe 5.** The loser's failed close is discarded with its result (Q6), so the stated types (line 14) are now true. A successful lookup is never reported as "unresolved".

## 04 `within` — 4 / 4 / 5 / 5 / 5

- **Obvious 4, line 10.** A reader has to know two things: `first_ok`'s cancel reaches `within` as `Canceled`, and `first_ok` then discards it, while `within`'s own deadline gives `Timeout`.
- **Discoverable 4, line 11.** Whether `Timeout` reaches `price`'s result depends on `first_ok`'s first-failure rule, which only hover shows.

## 05 spinner — 4 / 5 / 5 / 5 / 5

- **Obvious 4, line 9.** The marked item is canceled through its waits, so it tidies up by handling `sleep`'s `Canceled`. A reader has to know that being canceled means "your next wait says so".
- **Discoverable 5.** An unmarked spinner gets the "this block never ends … mark it `$until_others_finish`?" warning.
- **Complete 5.** The regrade's finding is fixed. The count is returned and printed after the block (line 24), which is after the spinner has blanked its line (line 11).
- **The name.** `$until_others_finish` was read correctly cold (3/3).

## 06 shared helper — 4 / 4 / 5 / 5 / 5

- **Obvious 4, line 15.** `?? base` also absorbs that item's `Canceled`. That is harmless, because line 16 is then already leaving `main`, but you can't see it.
- **Discoverable 4, lines 8–10.** The two types of one function are shown only in hover. The hover lines are now correct.

## 07 CPU `check_cancel` — 5 / 5 / 5 / 5 / 4

- **Complete 4, lines 25–27.** Stopping this loop on Ctrl-C from `main` needs program 02's shape. Python needs nothing.

## 08 level 3 — 4 / 3 / 4 / 4 / 4

- **Obvious 4, line 16.** The arms are distinct types now. A reader still has to know that the request's `Closed` means "the caller gave up".
- **Discoverable 3, line 25.** See the floor above.
- **Concise 4, lines 7, 12 and 25.** It takes an extra field, a poll that skips jobs whose caller has gone, and an extra argument. That matches the peers.
- **Safe 4, line 15.** `?? void` also takes the worker's own `Canceled`. That is correct here, because line 11's `or_throw` loop leaves at the next turn. Under `$explicit_cancellation` it must say `??<~Canceled>`.
- **Complete 4, line 13.** The codec has to report through a channel, because `select` over arbitrary waits (`Waitable<R>`) is undecided.

## 09 server — 4 / 4 / 5 / 4 / 4

- **Obvious 4, line 26.** The drain works only because the connections belong to `group` and not to the race item.
- **Discoverable 4, line 17.** `_ => {}` takes end of input, idleness and cancellation together.
- **Safe 4, line 28.** It now drains correctly: a normal body return joins without canceling (round2 §2.1). But there is no overall drain deadline. A client sending a line every 29 s keeps the server alive after SIGTERM. Go's `Shutdown(ctx)` takes a deadline.
- **Complete 4, line 28.** Same cause.

## 10 library, differing callers — 4 / 4 / 5 / 5 / 5

- **Obvious 4, line 9.** `done => return done` forwards `Canceled` unseen. A reader must know that `Canceled` isn't an `error`, so it isn't retried.
- **Discoverable 4, lines 15–18.** Callers learn where `retry` can be canceled only from hover and docs.

## 11 `first_ok` backups — 5 / 4 / 5 / 4 / 4

- **Obvious 5.** `first_ok` with an atomic write says what it does: the first disk to take the write wins, and the others keep their old backup.
- **Discoverable 4, line 9.** That `first_ok` discards a loser's failed temp-file removal shows only in hover, and under `$explicit_cancellation`.
- **Safe 4, line 9.** In a release build the discarded `FileRemoveFailed` is reported nowhere, so a stray temporary file stays on the losing disk unannounced. The good backups are safe. Round 1 scored 2: it truncated a good backup and could cancel a good write.
- **Complete 4, line 5.** The stray temporary file on that path.
- **Against the peers:** none reports a loser's cleanup at all. Python warns "exception was never retrieved", at run time.

## 12 queue, ticker, SIGTERM — 4 / 4 / 4 / 4 / 5

- **Obvious 4, line 21.** The SIGTERM loop ends when the queue does, by batch 9's rule. Nothing at the site shows it, though hover does.
- **Discoverable 4, line 17.** You have to find the marker. The "never ends" warning points to it.
- **Concise 4, lines 7–8.** "Finish the current job" takes two lines: a checkpoint between jobs, and protection around one.
- **Safe 4, line 8.** If a job is still running 30 s after SIGTERM, its `Timeout` is the result of a canceled sibling. It is dropped when `main` returns (line 23), so a cut-off job is reported nowhere unless `run_job` logs it.
- **Complete 5.** It does what line 22 announces: it finishes the current job and stops.

## 13 background task — 4 / 4 / 5 / 5 / 5

- **Obvious 4, line 5.** Telling "finished" from "stopped" takes `.running` read before `stop()`, because `.wait()` gives `void` either way.
- **Discoverable 4, line 11.** `or_throw` on the iteration forwards both `WatchError` and the task's own `Canceled`. The stop's `Canceled` is then consumed by `.wait()`, and that path has to be learned.
- The regrade's `WatchError` finding is fixed: `dir.watch or_throw` now produces it.

## What would raise the floor

- **Program 08's 3** needs a cancellation link that travels with a channel message on its own, a sender's request attached implicitly. That is a larger mechanism, not proposed.
- **Programs 09 and 12** need a bounded join or drain for `task.tasks`, and a place to report work cut off by protection's deadline. Both are D41 territory.
