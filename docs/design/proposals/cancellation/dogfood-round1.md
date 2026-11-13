# Dogfood, round 1: `Canceled` only where something can cancel

Thirteen programs are in `programs-r1/`. Each one is graded 1 to 5 on five axes: obvious, discoverable, concise, safe by default and complete. The comparison is Python (asyncio and threads), Go (`context`), Rust (tokio with `CancellationToken`), TypeScript (`AbortSignal`) and Swift (structured concurrency).

- Every score under 5 cites the line responsible.
- The grades assume the round's recommendations: Q1 to Q5, and the diagnostics in round1.md §2.9.
- A grade that depends on one of those says so.
- Line numbers refer to the files as committed in `programs-r1/`.

| # | Program | Obvious | Discoverable | Concise | Safe | Complete |
|---|---|---|---|---|---|---|
| 01 | crawler: feeder, four workers, collector | 4 | 4 | 5 | 5 | 5 |
| 02 | CLI that saves on Ctrl-C | 4 | 4 | 4 | 4 | 5 |
| 03 | `race` and `first_ok` lookups | 5 | 4 | 5 | 5 | 5 |
| 04 | `within`, and `within` nested in `first_ok` | 4 | 5 | 5 | 5 | 5 |
| 05 | progress spinner as incidental work | 4 | 5 | 5 | 5 | 5 |
| 06 | one helper in both kinds of context | 4 | 5 | 5 | 5 | 5 |
| 07 | CPU loop with `check_cancel` | 5 | 5 | 5 | 5 | 5 |
| 08 | custom wait at level 3 (request passed in a job) | **3** | **3** | 4 | 4 | 4 |
| 09 | server loop with SIGTERM drain | 4 | 4 | 5 | 4 | 4 |
| 10 | library function whose callers differ | 4 | 5 | 5 | 5 | 5 |
| 11 | canceled loser whose cleanup fails | 4 | 4 | 4 | 5 | 4 |
| 12 | queue processor with incidental ticker and SIGTERM | 4 | 4 | 4 | 5 | 5 |
| 13 | background task stopped and waited | 5 | 4 | 5 | 5 | 5 |

**Lowest grade: 3**, for program 08, on two axes:

- **Obvious.** Two arms of one type do opposite things: one keeps serving and the other stops.
- **Discoverable.** Forgetting to pass the request is silent.

Both come from carrying cancellation between tasks through data. Every peer language has the same gap there, but Dewy doesn't close it either.

## 01 Crawler — 4 / 4 / 5 / 5 / 5

The feeder and the collector are block items, and the workers are a `parallel` loop nested in a third item.

- `main` is not cancellable, so `seeds` is `string | FileError` (line 24) and `total` is a plain `int` after the block (line 42).
- Inside the items, every wait carries `Canceled`.
- Workers' `loop url in urls` ends on cancellation (Q4).

Grades:

- **Obvious 4, lines 33–36.** The nested `{ parallel i in [0..4) worker(urls pages) or_throw; pages.close() }` exists only so that the collector's loop ends. That is channel lifetime rather than cancellation, but a reader has to work it out.
- **Discoverable 4, line 18.** `<Canceled> => break` is required only because `worker` runs as an item. The exhaustiveness error names line 34 as the cancellable call site, so it can be found, but nobody writes it first.

Against the peers:

- **Go** threads `ctx` through `fetch_page` and `worker`, and selects on `ctx.Done()` beside every receive.
- **Rust** needs a `JoinSet` and a `CancellationToken` passed to each worker.
- **Python asyncio** needs a `TaskGroup` and queue sentinels.
- **Swift's** task group comes closest, but channels need an `AsyncChannel` package.
- Dewy is shorter than all of them, and no failure is lost.

## 02 CLI saves on Ctrl-C — 4 / 4 / 4 / 4 / 5

Ctrl-C lands in a `signals.ctrl_c` item. Its `return` leaves `optimize`, which cancels `improve`, and then `main` saves. Without the item, Ctrl-C would end the process (the OS default).

- **Obvious 4, line 22.** The `return` leaves `optimize`, not `main`. The block has to sit in a small function so that the save after it still runs. Written directly in `main`, the same `return` would skip the save. The idiom is C3's ("`or_throw` leaves the function"), but a reader thinking "stop the work" may not expect that.
- **Discoverable 4, line 20.** Nothing at the site shows that a signal wait doesn't keep the block alive. When `improve` finishes, the listener ends by itself; hover says so.
- **Concise 4, lines 18–24.** Python's `try: improve() except KeyboardInterrupt: pass`, then `save()`, is four lines with no helper. Go needs `signal.NotifyContext` plus `ctx` in `improve`, which is longer than Dewy. Rust's `tokio::select!` on `ctrl_c()` is about as long. Dewy is between them.
- **Safe 4, line 32.** A Ctrl-C during the final save ends the process at once. The atomic replace keeps the old file, but the new route is lost. Python's second KeyboardInterrupt also interrupts its save, and Go and Rust are the same here.

## 03 `race` and `first_ok` — 5 / 4 / 5 / 5 / 5

- In `main`, `race` gives `Ip | DnsError` and `first_ok` gives `array<uint8> | HttpError`, with no `Canceled` (lines 12 and 17).
- `from_mirror`'s hover lists `first_ok` as the place it can be canceled.
- `prefetch` shows the same calls inside comprehension items.

Grades:

- **Discoverable 4, line 17.** `@from_mirror.(mirrors "pkg.tar")...` (one handle per mirror, spread) is batch 7's surface and not new, but a newcomer won't find it.

Against the peers:

- **Go** has no `race` or `first_ok`. Each is about 15 lines of goroutines, a channel and `cancel()`.
- **TypeScript's** `Promise.race` and `Promise.any` don't cancel the losers.
- **Swift** needs a task group with `cancelAll()`.

## 04 `within` — 4 / 5 / 5 / 5 / 5

- **Obvious 4, line 10.** In `first_ok(@within(50ms @cache_get(key)) @db_get(key))`, a reader has to know that `first_ok`'s cancel reaches `within` as `Canceled`, which is dropped, while `within`'s own deadline gives `Timeout`. The comment carries it, and hover would too.
- No `<Canceled>` arm in `main` (line 21). Under today's rule it would be required, or an `error` arm would have to be checked for not covering it.

## 05 Spinner — 4 / 5 / 5 / 5 / 5

- `$incidental spin("counting")` stops the spinner when `count_lines` ends.
- `spin` clears its line by handling the `Canceled` from `sleep` (line 6).
- Line 20 shows David's warning: the `or_throw` forwards nothing.

Grades:

- **Obvious 4, line 19.** `$incidental` hasn't been cold-read yet. If a better name passes, this becomes a 5.
- **Discoverable 5.** This depends on the §2.9 hint. Without `$incidental`, the block would never end, and the compiler says so: "spin stops only when canceled, and nothing here cancels it. Mark it `$incidental`?" Without that hint it would be a 4.

Against the peers:

- **Python, Go, Rust and TypeScript** all spell this with a done flag, an event or a token checked by the spinner.
- **Swift** uses `async let` with `cancel()`.
- Dewy's version has no plumbing at all.

## 06 Shared helper — 4 / 5 / 5 / 5 / 5

- `load_config` is called once from `main` (line 13) and twice from items of an unscoped `parallel ( … )` (lines 15 and 16).
- Hover lists both types and the three call sites.

Grades:

- **Obvious 4, line 15.** `?? base` also covers the item's `Canceled`. That is harmless: it can only happen when line 16 is already leaving `main`. Still, a reader sees one function with two types on adjacent lines and has to hover to learn why.
- After the block, `local` is a plain `Config` (line 18, §2.3 narrowing).

## 07 `check_cancel` — 5 / 5 / 5 / 5 / 5

- One `check_cancel() or_throw` serves both instances: `void` at line 18 and `void | Canceled` under `within` at line 19.
- Neither instance warns, because one of them needs the check.
- **Discoverable 5** depends on the §2.9 warning that a `within` item with no cancellation point runs to the end.
- Against the peers: Go needs `select { case <-ctx.Done(): … default: }`, Rust needs `token.is_cancelled()` with the token passed in, and Swift's `try Task.checkCancellation()` is equivalent to this.

## 08 Custom wait, level 3 — 3 / 3 / 4 / 4 / 4

A codec worker serves jobs. Each caller puts `task.cancel_request` in its job (line 25), and the worker selects on the codec or the job's request (line 14).

- **Obvious 3, lines 17–18.** `<job.cancel.Canceled> => codec.abort()` and `<Canceled> => break` are the same type with opposite actions: keep serving or stop. They are told apart only by batch 7's source qualification. Swapping their order would still compile.
- **Discoverable 3, line 25.** If the caller doesn't pass its request, nothing complains. The worker just keeps decoding after the caller's 2 s `within` has expired. No analysis can see the link, because it travels through a channel.
- **Concise 4, lines 8 and 25.** It takes an extra field and an extra argument. Go (`ctx` in the request), Rust (a token in the message) and TypeScript (a `signal` field) need the same.
- **Safe 4, line 15.** `?? void` on the reply send also consumes the worker's own `Canceled`. That's correct here, because the loop's next iteration ends. Under `$explicit_cancellation`, though, it would have to say `??<~Canceled> void`, and a later edit that put a retry loop here would spin until the closed-source progress rule caught it.
- **Complete 4, line 14.** `select`'s signature is still open. The program uses only what batch 7 decided.

## 09 Server — 4 / 4 / 5 / 4 / 4

`task.tasks` owns the connection tasks.

- A `race` runs the accept loop against `signals.sigterm.next`.
- When SIGTERM wins, the accept loop alone is canceled, and the body prints "draining".
- `tasks` then waits for the open connections.
- `serve_one` logs connection failures, so one bad client never fails the group (line 15).

Grades:

- **Obvious 4, line 26.** The graceful drain depends on knowing that the race cancels `accept_all` but not the tasks it spawned, which belong to `group`. That is right by structure, but has to be learned.
- **Discoverable 4, line 25.** `task.tasks((group:Tasks) => { … })` is D41 Q3's form, and nothing in it suggests the race.
- **Safe 4, line 28.** The drain has no deadline. A client that sends a line every 29 s keeps the server alive after SIGTERM indefinitely. Bounding it needs a `within` around the join, which `tasks` doesn't offer. Go's `srv.Shutdown(ctx)` takes a deadline.
- **Complete 4, line 28.** Same cause.

## 10 Library with differing callers — 4 / 5 / 5 / 5 / 5

- `retry` is called from `cli` (not cancellable: `string | HttpError`, line 21) and from `batch`'s comprehension items (line 25).
- Its `sleep(...) or_throw` (line 11) is needed in one instance and harmless in the other, so there's no warning.
- The generated docs say where it can be canceled.

Grades:

- **Obvious 4, line 9.** `done => return done` also takes `Canceled` and returns it. That is the right behaviour, but a reader has to know that `Canceled` isn't an `error` (LANGUAGE.md line 4001), so it isn't retried.

Against the peers: Go's `retry` would take `ctx` explicitly, every caller would have to pass one, and the CLI would pass `context.Background()`. That is the colouring §2.8 argues against.

## 11 Cleanup failure on a canceled loser — 4 / 4 / 4 / 5 / 4

A race of two backup writes. The loser is canceled mid-write, and then its close fails.

- The race drops the loser's `Canceled` and keeps `AfterCancel<FileCloseFailed>` (Q5).
- A failed winner can no longer be reported as "backed up".

Grades:

- **Obvious 4, line 15.** You have to learn that a loser's failures come back wrapped.
- **Discoverable 4, line 12.** Nothing in the `race` call shows that a loser's cleanup can affect the result. Hover lists it.
- **Concise 4, line 14.** D42 Q1 requires the pair arm `FileError & AfterCancel<FileCloseFailed>` before the `AfterCancel` arm.
- **Complete 4, line 24.** The loser's half-written `backup.bin` stays on its disk, because plain files have no `$__abandon__`.

No peer reports a loser's close failure at all:

- **Go** drops it unless the goroutine sends it somewhere.
- **Python** prints "Task exception was never retrieved".
- **Rust** drops the `JoinHandle` result.

## 12 Queue processor — 4 / 4 / 4 / 5 / 5

- The `$incidental` ticker and the SIGTERM listener both end with `process_queue`.
- Under today's signals rule, this block never ends, because the ticker is ordinary activity. That is the signals proposal's counterexample, now fixed.

Grades:

- **Obvious 4, line 23.** The SIGTERM loop is incidental because the library marks its wait, and nothing at the site shows that. Hover does.
- **Discoverable 4, line 16.** The tag hasn't been cold-read.
- **Concise 4, lines 17–21.** A ticker loop needs `let heart = ticker(10s)` and `heart.next or_throw;` inside `loop true`. A ticker that iterates like a source would make this two lines, but that is out of scope here.

## 13 Background task — 5 / 4 / 5 / 5 / 5

- `watcher.stop()` is followed by `watcher.wait() or_throw`, which gives `void | WatchError` (line 6). The `Canceled` the stop caused isn't reported back.
- The v5 idiom `worker.wait() ??<Canceled> { check_cancel() or_throw }` disappears.

Grades:

- **Discoverable 4, line 10.** `loop change in dir.watch` ends silently when the task is stopped. That depends on Q4, and a reader has to know that iteration ends on cancellation.

## What would raise the floor

- **Program 08** stays at 3 unless cross-task cancellation becomes structural. For example, a channel could carry the sender's request automatically. That would be a new and much larger mechanism, and it isn't proposed.
- **Program 09's** drain deadline needs a bounded join for `task.tasks`, which is D41 Q3 territory.
- **Programs 05 and 12** move to 5 when a name for `$incidental` passes the cold read.
- **Program 02's** obviousness depends on readers knowing C3. A teaching note in the guide would help, and the semantics needn't change.
