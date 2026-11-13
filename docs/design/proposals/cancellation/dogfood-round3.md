# Dogfood, round 3

There are 20 programs in `programs-r3/`:

- **Unchanged from round 2:** 01, 02, 04, 05, 06, 07, 09 and 10. Each was re-checked against round 3's confinement rules and needed no change.
- **Revised for the round 2 findings:** 03, 08, 11, 12 and 13.
- **New:** 14–18 exercise the patterns review MF3 said round 2 rejected; 19 marks a spawned task; 20 waits on a task under a deadline.

Grades:

- **Axes:** obvious, discoverable, concise, safe by default and complete.
- **Compared against:** Python, Go, Rust, TypeScript and Swift.
- **Citations:** every score under 5 names its line.
- **Calibration:** where the round 2 regrade argued better, its reading is taken.

| # | Program | O | D | C | S | Co |
|---|---|---|---|---|---|---|
| 01 | crawler | 4 | 4 | 4 | 5 | 5 |
| 02 | CLI, save on Ctrl-C | 4 | 4 | 4 | 5 | 4 |
| 03 | `first_ok` lookups | 5 | 4 | 5 | 5 | 5 |
| 04 | `within` | 4 | 4 | 5 | 5 | 5 |
| 05 | spinner | 5 | 5 | 5 | 5 | 5 |
| 06 | shared helper | 4 | 5 | 5 | 5 | 5 |
| 07 | CPU `check_cancel` | 5 | 5 | 5 | 5 | 4 |
| 08 | level 3: request in a job | 4 | **3** | 4 | 4 | 5 |
| 09 | server, SIGTERM drain | 4 | 4 | 5 | 5 | 4 |
| 10 | library, differing callers | 4 | 4 | 5 | 5 | 5 |
| 11 | `first_ok` backups, abandon failure | 4 | 4 | **3** | 5 | 4 |
| 12 | queue, ticker, SIGTERM | 4 | 4 | 4 | 4 | 5 |
| 13 | background task | 4 | 4 | 5 | 5 | 5 |
| 14 | pairing comprehension | 5 | 5 | 5 | 5 | 5 |
| 15 | sequential collector in an item | 4 | 4 | 5 | 5 | 5 |
| 16 | shared cache, `map` over a waiting callback | 4 | 4 | 5 | 5 | 5 |
| 17 | logging and a catch-all arm | 4 | 5 | 5 | 5 | 5 |
| 18 | generic forwarding | 4 | 4 | 5 | 5 | 5 |
| 19 | `task.tasks` with a marked reporter | 4 | 4 | 5 | 5 | 4 |
| 20 | `Task.wait` under a deadline | 5 | 4 | 5 | 5 | 5 |

**Floor: 3,** in two places:

- **Program 08, discoverable (line 29).** If a caller forgets to put its `task.cancel_request` in a job, nothing reports it. The link travels through a channel, where no analysis sees it. Go (`ctx` in the message), Rust (a token) and TypeScript (an `AbortSignal` field) share this gap.
- **Program 11, concise (lines 6–15).** Handling an abandoned temporary file inside each backup takes a nine-line `match`, because Q6 never discards an abandon failure. That is the price of not losing a failed undo. No peer reports it at all, so it's a 3 against their brevity, not their safety.

Round 2's floor at 12 is gone: under round 3, protection's limit counts from cancellation, so the program does what it says.

## The patterns round 2 rejected (MF3)

These five programs are the evidence for Q2.

| # | Pattern | Round 2 | Round 3 | Grade |
|---|---|---|---|---|
| 14 | `[parallel u in … [url=u page=http.get_text(u)]]` | an error in each element | fine; the join narrows the element type | 5/5/5/5/5 |
| 15 | `[loop u in links http.get_text(u)]` in an item; the array is passed to `digest` | an error | fine | 4/4/5/5/5 |
| 16 | `.map(@http.get_title)`; a cache in a shared mutex | an error | `map` is fine; the store is an error until the result is forwarded (it already is, line 6) | 4/4/5/5/5 |
| 17 | `report(host r)`, `{e}`, `e:exception =>` | an error | fine | 4/5/5/5/5 |
| 18 | `identity(sleep(0ns))`, `count_alternatives` | an error | fine; two tiny generics get a second body | 4/4/5/5/5 |

Confinement leaves one pattern from the review's table rejected: publishing a value that may hold `Canceled` beyond its work. Every program that needs to store something wants to store a success, so forwarding first is what it would write anyway (program 16, line 6).

## 01 crawler: 4 / 4 / 4 / 5 / 5

- **Obvious 4, line 13.** The loop ends at cancellation and reads like the channel closing.
- **Discoverable 4, line 18.** The `<Canceled> => break` arm is required because every item counts.
- **Concise 4, line 18.** That arm is boilerplate where nothing cancels a worker.

## 02 CLI saves on Ctrl-C: 4 / 4 / 4 / 5 / 4

- **Obvious 4, line 22.** The handler's `return` leaves the helper, not `main`.
- **Discoverable 4, line 22.** The idiom must be learned, though the `break` warning points to it.
- **Concise 4, lines 18–24.** Python's `try`/`except` is shorter.
- **Complete 4, line 33.** An interrupted run exits 0.

## 03 `first_ok` lookups: 5 / 4 / 5 / 5 / 5

- **Discoverable 4.** Line 19's per-mirror spread is batch 7 surface. The comprehension's type depends on its context (lines 24–28), which only hover shows.
- **Safe 5.** A fast transport failure no longer beats a slower answer, now that DNS uses `first_ok`.

## 04 `within`: 4 / 4 / 5 / 5 / 5

- **Obvious 4, line 10.** You must know that `first_ok`'s cancel reaches `within` as a `Canceled` that is discarded, while the deadline gives `Timeout`.
- **Discoverable 4, line 11.** That `Timeout` can appear only shows in hover.

## 05 spinner: 5 / 5 / 5 / 5 / 5

This takes the regrade's reading. The `$until_others_finish` marker reads correctly cold, the tidy-up is `if sleep(100ms) is? Canceled break`, and the count prints after the line is blanked. Nothing else here needs no flag.

## 06 shared helper: 4 / 5 / 5 / 5 / 5

- **Obvious 4, line 15.** `?? base` also absorbs the item's `Canceled`.

## 07 CPU `check_cancel`: 5 / 5 / 5 / 5 / 4

- **Complete 4, lines 25–27.** Stopping the loop on Ctrl-C from `main` needs program 02's shape.

## 08 level 3: 4 / 3 / 4 / 4 / 5

- **Obvious 4, lines 17 and 19.** The arms are different types, but why they differ rests on the hover and doc lines (lines 23–25). Only 1 of 3 cold readers saw it unaided, so the round 3 re-read is pending.
- **Discoverable 3, line 29.** See the floor.
- **Concise 4, lines 7, 12–13 and 29.** It takes a field, a checkpoint and a poll, and an argument.
- **Safe 4, line 29.** A forgotten request leaves the worker decoding for callers that have gone. The worker's own cancellation is no longer missed, because `check_cancel` now comes before the poll (line 12).

## 09 server: 4 / 4 / 5 / 5 / 4

- **Obvious 4, line 26.** The drain depends on connections belonging to `group`.
- **Discoverable 4, line 17.** `_ => {}` takes several outcomes at once.
- **Complete 4, line 28.** The drain has no overall deadline.

## 10 library, differing callers: 4 / 4 / 5 / 5 / 5

- **Obvious 4, line 9.** `done => return done` forwards `Canceled` without showing it.
- **Discoverable 4, lines 15–18.** Where `retry` can be canceled shows only in hover and docs.

## 11 `first_ok` backups: 4 / 4 / 3 / 5 / 4

- **Obvious 4, lines 9–11.** The `left` arm has to log the temporary file and then pass on everything else with `left as ~FileRemoveFailed`.
- **Discoverable 4, lines 24–26.** You learn the arm from the compile error. The error names the abandon failure and the fix.
- **Concise 3, lines 6–15.** Nine lines per backup call (see the floor).
- **Safe 5.**
  - A failed write can't cancel a good one: `first_ok`.
  - The old backup survives: atomic replace.
  - A failed undo is never lost: Q6.
  - A loser's failed ordinary close goes with its result, which is visible in hover.
- **Complete 4, line 11.** `as ~FileRemoveFailed` relies on D42 Q4's `as` taking batch 10's complement. That is a natural extension, flagged, not yet decided.

## 12 queue, ticker, SIGTERM: 4 / 4 / 4 / 4 / 5

- **Obvious 4, line 8.** A reader has to know that the limit counts from cancellation. The comment (lines 8–9) and the hover say so; a deadline from entry would be `within`.
- **Discoverable 4, lines 7–8.** "Finish the current job" is a learned pair of lines: a checkpoint between jobs, and protection around one.
- **Concise 4, lines 7–8.** Those two lines.
- **Safe 4, line 28.** A job still running 30 s after SIGTERM gets `Timeout`. As a canceled sibling's result, it is dropped when `main` returns, so it is reported nowhere unless `run_job` logs it.
- **Complete 5.** The program does what lines 1–2 say: there is no cap in normal operation, and up to 30 s after SIGTERM.

## 13 background task: 4 / 4 / 5 / 5 / 5

- **Obvious 4, line 5.** `.running` reads one instant. Telling "stopped" from "finished" isn't atomic, and the comment says so.
- **Discoverable 4, line 11.** `or_throw` after the iterable forwards both `WatchError` and the task's own `Canceled`. `.wait()` never reports the latter.

## 14 pairing comprehension: 5 / 5 / 5 / 5 / 5

The record shape every peer writes is now allowed. After the join, `r.page` is `string | HttpError` (line 11). Python's `gather(return_exceptions=True)` needs a separate `zip` with the URLs, and Go needs an indexed slice and a `WaitGroup`.

## 15 sequential collector in an item: 4 / 4 / 5 / 5 / 5

- **Obvious 4, line 4.** Once its item is canceled, `fetch_all` keeps looping: each further `get_text` returns `Canceled` at once. That costs nothing, but a reader may expect it to stop.
- **Discoverable 4, lines 18–19.** The early-stop form, `or_throw<Canceled>` on each element, has to be learned.

## 16 shared cache, `map`: 4 / 4 / 5 / 5 / 5

- **Obvious 4, lines 6–7.** Only a forwarded result may enter the cache, which outlives every item. That is natural for a cache of successes, but it is the one place where confinement is felt.
- **Discoverable 4, lines 10–14.** The error comes at the store. It names the cancellable call (line 19) and offers a fix.
- Line 21's `map` over a waiting callback is ordinary in every context.

## 17 logging and a catch-all arm: 4 / 5 / 5 / 5 / 5

- **Obvious 4, line 13.** The catch-all arm returns `e`, so `check` forwards `Canceled` through it. That is correct, but a reader must see that `e` is the result.
- Logging (line 8) and interpolation (line 12) are ordinary.

## 18 generic forwarding: 4 / 4 / 5 / 5 / 5

- **Obvious 4, lines 21 and 24.** `count_alternatives(sleep(0ns))` prints 2 in `main` and 3 in the item. That is correct per context, but surprising.
- **Discoverable 4, lines 27–29.** That `identity` and `count_alternatives` get two bodies shows only under `$no_hidden_costs` or `explain`.

## 19 `task.tasks` with a marked reporter: 4 / 4 / 5 / 5 / 4

- **Obvious 4, line 18.** The marker prefixes the `spawn` statement but marks the spawned task. That follows the prefix rule (batch 8), but a reader may wonder which one it marks.
- **Discoverable 4, line 18.** You have to find the marker. A never-ending spawned task in `task.tasks` gets the same "never ends … mark it" warning as a `parallel` item.
- **Complete 4, line 21.** As in program 09, the drain has no deadline.

## 20 `Task.wait` under a deadline: 5 / 4 / 5 / 5 / 5

- **Discoverable 4, line 4.** `@indexer.wait` is the method handle. The call itself keeps `()`, as a void call, and the handle drops it. That is existing surface, but it trips readers.
- The indexer keeps running after `Timeout` (line 9), which is exactly what the review's MF1 asked for.

## What would raise the floor

- **Program 08** needs cancellation that travels with a channel message on its own. That would be a larger mechanism, and it isn't proposed.
- **Program 11** would be shorter with a library helper that reports an abandoned temporary file itself. One example is `write_bytes(data on_abandon_failure=…)`, but that is new surface for the files module. Alternatively, David could choose to let abandon failures replace the result. That gives a shorter item but brings back the round 1 arms that confused winners with losers.
