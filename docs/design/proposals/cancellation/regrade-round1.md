# Regrade, cancellation round 1

**How the grades were made**

- The 13 programs in `programs-r1/` were graded before reading `dogfood-round1.md`.
- Each is graded 1–5 on obvious, discoverable, concise, safe by default and complete, against Python, Go, Rust, TypeScript and Swift.
- The grades assume round1.md's rules as written, including §2.4's loser-cleanup rule and Q1–Q5.
- Every score under 5 cites a line.

| # | Program | Obvious | Discoverable | Concise | Safe | Complete |
|---|---|---|---|---|---|---|
| 01 | crawler | 4 | 4 | 4 | 5 | 5 |
| 02 | CLI, save on Ctrl-C | 4 | 3 | 4 | 5 | 4 |
| 03 | `race` / `first_ok` | 4 | 4 | 5 | **3** | 5 |
| 04 | `within` | 4 | 4 | 5 | 4 | 5 |
| 05 | spinner | 4 | 5 | 5 | 5 | **3** |
| 06 | shared helper | 4 | 4 | 5 | 5 | 5 |
| 07 | CPU `check_cancel` | 5 | 5 | 5 | 5 | 4 |
| 08 | level-3 custom wait | **3** | **3** | 4 | **3** | 4 |
| 09 | server loop | 4 | 4 | 5 | 4 | 4 |
| 10 | library callers | 4 | 4 | 5 | 5 | 5 |
| 11 | cleanup failure on cancel | **3** | **3** | **3** | **2** | **3** |
| 12 | signal service | **3** | 4 | 4 | **3** | **3** |
| 13 | background task | 4 | 4 | 5 | 5 | 4 |

**Floor: 2**, program 11, for safe by default.

## 01 crawler: 4 / 4 / 4 / 5 / 5

- **Obvious 4, line 13.** `loop url in urls` ends silently on cancellation (Q4). It reads exactly like "the channel closed".
- **Discoverable 4, line 18.** `<Canceled> => break` is required although nothing in this program can cancel a worker:
  - the feeder's `or_throw` (line 30) can only forward a `Canceled` send, and nothing cancels the feeder;
  - you learn it from the exhaustiveness error.
- **Concise 4, line 18.** That same arm is boilerplate for a case that can't happen here.
- **Against the other languages.** Shorter than Go, Rust and asyncio, with no `ctx` and no tokens. Swift's task group is the closest.

## 02 CLI saves on Ctrl-C: 4 / 3 / 4 / 5 / 4

- **Obvious 4, line 22.** The handler's `return` leaves `optimize`, not `main`. The extra function exists only so the save still runs.
- **Discoverable 3, lines 18–24.**
  - The idiom "put the block in a small function" can't be guessed.
  - The tempting alternative, `break` in the handler, only ends the listener's own loop: `improve` keeps running and Ctrl-C is then ignored.
  - Python's `try/except KeyboardInterrupt` is found by everyone.
- **Concise 4, line 18.** The wrapper function costs a few lines. That is still about Rust's `select!` length.
- **Safe 5.** The atomic replace (line 16) protects the file if a second Ctrl-C lands during the save.
- **Complete 4, line 33.** After an interrupted run the program prints "saved" and exits 0. Reporting the interruption (130) needs an `exit` that the program doesn't write.

## 03 `race` and `first_ok`: 4 / 4 / 5 / 3 / 5

- **Obvious 4, line 12.** For resolvers, `race` returns a fast *failure* over a slower success. The comment on line 13 says so, but `first_ok` is what most readers expect here.
- **Discoverable 4, lines 23–25.** The element type differs inside and after the comprehension, and between callers. Only hover shows it.
- **Safe 3, lines 12–15 and 17–18.** Under §2.4, a canceled loser whose socket close fails *replaces the winner's success* with `AfterCancel<SocketCloseFailed>`.
  - Line 15 then prints "unresolved" after a successful lookup.
  - Line 17's `or_throw` fails the download that succeeded.
  - The program's stated types (lines 13 and 18) leave these members out, so either the program or §2.4 is wrong.

## 04 `within`: 4 / 4 / 5 / 4 / 5

- **Obvious 4, line 10.** You must know that `first_ok`'s cancellation reaches `within` as `Canceled`, which is dropped, while its own deadline gives `Timeout`. The comment (lines 12–14) is load-bearing.
- **Discoverable 4, line 11.** Whether `Timeout` can appear in `price`'s result at all depends on `first_ok`'s "first failure" rule. Only hover shows it.
- **Safe 4, line 11.** The same §2.4 omission as program 03: when the cache wins, the canceled `db_get`'s connection cleanup can replace the success.

## 05 spinner: 4 / 5 / 5 / 5 / 3

- **Obvious 4, lines 15 and 19.** Nothing shows that the spinner stops only *after* `count_lines` has printed.
- **Discoverable 5.** The §2.9 warning ("this block never ends … Mark it `$incidental`?") leads straight to the tag.
- **Complete 3, lines 7 and 15.** The output is wrong as written:
  - `count_lines`'s `printl` lands on the spinner's line, giving `| counting12345 lines`;
  - `print("\r")` returns the cursor but doesn't clear anything.

  The correct shape is to return the count and print after the block. The design makes that the only correct shape, without saying so.
- **Against the other languages.** Still far less plumbing than any of them.

## 06 shared helper: 4 / 4 / 5 / 5 / 5

- **Obvious 4, line 15.** `?? base` also absorbs the item's `Canceled`. That is harmless here, but invisible.
- **Discoverable 4, lines 8–10.** Two types for one function are visible only in hover. The hover text in the comment names the wrong call site: line 16 calls `load_theme`.

## 07 CPU loop with `check_cancel`: 5 / 5 / 5 / 5 / 4

- **Complete 4, lines 25–27.** Stopping this loop on Ctrl-C from `main` needs a `parallel` block with a `signals.ctrl_c` item and a wrapper function (program 02's shape). Python's KeyboardInterrupt needs no code at all.

## 08 level-3 custom wait: 3 / 3 / 4 / 3 / 4

- **Obvious 3, lines 17–18.** Two arms of one type, `<job.cancel.Canceled>` and `<Canceled>`, do opposite things. Only source qualification separates them.
- **Discoverable 3, line 25.** Nothing leads you to put `task.cancel_request` in the job, and leaving it out is silent.
- **Concise 4, lines 8 and 25.** It costs an extra field and an extra argument, the same as Go's `ctx` or a token in Rust.
- **Safe 3. Three problems.**
  - Line 13 starts the codec for a job whose caller already gave up while it was queued.
  - Line 14 depends on `select` accepting non-channel waits (`@codec.finished`, `@job.cancel.wait`), which batch 7 didn't decide.
  - Forgetting line 25 leaves the worker decoding for callers that have gone.
- **Complete 4, line 13.** There is no check before the expensive start.

## 09 server loop: 4 / 4 / 5 / 4 / 4

- **Obvious 4, line 26.** The drain works only because spawned connections belong to `group` and not to the race item. That is right, but it has to be learned.
- **Discoverable 4, line 17.** `_ => {}` silently takes end-of-input, `Timeout` and `Canceled` together.
- **Safe 4, line 28.** The drain depends on `task.tasks` *joining* on the body's normal return. round1.md §2.1(3) says "the body leaves" closes the children's requests, which would cancel every connection at SIGTERM.
- **Complete 4, lines 9 and 28.** The drain has no overall deadline. A client sending a line every 29 s keeps the server up forever after SIGTERM.

## 10 library function whose callers differ: 4 / 4 / 5 / 5 / 5

- **Obvious 4, line 11.** A library reader sees an `or_throw` that does nothing in one instance. Line 9's `done => return done` silently forwards `Canceled`.
- **Discoverable 4, lines 15–18.** A caller learns where `retry` can be canceled only from hover or generated prose.

## 11 cleanup failure on a canceled loser: 3 / 3 / 3 / 2 / 3

- **Obvious 3, lines 14–15.** `AfterCancel<…>`, a combined pair arm, and an arm meaning "succeeded, but the other close failed" are a lot for a two-way race.
- **Discoverable 3, lines 14 and 22–23.** Both are hard to find:
  - the pair arm must come first, or it is an error;
  - the `.failure` member (line 15) is new and is not in the kit.
- **Concise 3, lines 13–16.** It takes four arms. No other language reports this case at all, but none needs four arms for it either.
- **Safe 2. Two hazards.**
  - Line 12 uses `race`, which returns the first result *even a failure*. If `/mnt/a` fails at once (unmounted), the race cancels the good write in progress on `/mnt/b` and reports "backup failed". `first_ok` is meant.
  - Line 6 opens with `'w'`, which truncates. The canceled loser has already destroyed the previous good backup on its disk, leaving a partial file (line 24).

  This is the design's own showcase for Q5, so the pattern it teaches is unsafe.
- **Complete 3, line 24.** The partial `backup.bin` is left behind, with no atomic write and no removal.

## 12 queue processor with an incidental ticker and SIGTERM: 3 / 4 / 4 / 3 / 3

- **Obvious 3, lines 19 and 24.**
  - `heart.next or_throw;` reads as leaving `main`, but in an incidental item it ends only the item.
  - Line 24 says "stopping after the current job", while line 25's `return` cancels `process_queue` immediately, aborting `run_job` mid-job.
- **Discoverable 4, line 23.** That the SIGTERM loop is incidental comes from a mark inside the library. Nothing at the call site shows it.
- **Concise 4, lines 17–21.** A ticker loop needs `let`, `loop true` and `next or_throw;`.
- **Safe 3, lines 24–25.** The obvious graceful stop aborts in-flight jobs. Finishing the current job needs two things the program doesn't write:
  - `check_cancel() or_throw` at the top of the loop;
  - `protect_from_cancel(limit @run_job(file))`.
- **Complete 3, line 24.** The behaviour the program announces isn't what it does.

## 13 background task stopped and waited: 4 / 4 / 5 / 5 / 4

- **Obvious 4, line 6.** `.wait()` gives the same `void` whether the watcher finished or was stopped.
- **Discoverable 4, line 10.** `loop change in dir.watch` ends silently when the task is stopped (Q4).
- **Complete 4, line 6.** The comment claims `void | WatchError`, but `watch_assets` handles every reload failure itself and loops over `dir.watch` without `or_throw`, so nothing produces `WatchError`.

## Where I differ from the author by 2 or more

| Program | Axis | Author | Mine | Why |
|---|---|---|---|---|
| 03 | Safe | 5 | 3 | Under §2.4, a loser's cleanup failure replaces the winner's success, and the stated types omit it. |
| 05 | Complete | 5 | 3 | The output is garbled: the result prints on the spinner's line, and `\r` doesn't clear it. |
| 11 | Safe | 5 | 2 | `race` lets a fast failure cancel a good backup, and `'w'` truncates the old backup on the losing disk. |
| 12 | Safe | 5 | 3 | The SIGTERM `return` aborts jobs mid-run, despite the message. |
| 12 | Complete | 5 | 3 | Same cause: the announced behaviour isn't implemented. |

**Smaller differences (1 point):**

- 01: concise.
- 02: discoverable, safe and complete, in both directions.
- 03: obvious.
- 04: discoverable and safe.
- 06: discoverable.
- 07: complete.
- 08: safe.
- 10: discoverable.
- 11: obvious, discoverable, concise and complete.
- 12: obvious.
- 13: obvious and complete.

**My floor: 2,** program 11 (safe by default). **The author's floor is 3,** program 08.
