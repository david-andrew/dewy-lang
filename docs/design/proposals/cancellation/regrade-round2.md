# Regrade, cancellation round 2

- **Scope:** the 13 programs in `programs-r2/`.
- **Method:** graded before reading `dogfood-round2.md`, on five axes against Python, Go, Rust, TypeScript and Swift.
- **Basis:** round2.md's rules as written.
- **`protect_from_cancel`'s limit:** read as v5 defines it, a deadline that starts when the scope is entered. Round 2 does not change it.
- **Citations:** every score under 5 names its line.

| # | Program | Obvious | Discoverable | Concise | Safe | Complete |
|---|---|---|---|---|---|---|
| 01 | crawler | 4 | 4 | 4 | 5 | 5 |
| 02 | CLI, save on Ctrl-C | 4 | 4 | 4 | 5 | 4 |
| 03 | `race` / `first_ok` | 4 | 4 | 5 | 4 | 5 |
| 04 | `within` | 4 | 4 | 5 | 5 | 5 |
| 05 | spinner | 5 | 5 | 5 | 5 | 5 |
| 06 | shared helper | 4 | 5 | 5 | 5 | 5 |
| 07 | CPU `check_cancel` | 5 | 5 | 5 | 5 | 4 |
| 08 | level-3 request in a job | 4 | **3** | 4 | 4 | 5 |
| 09 | server, SIGTERM drain | 4 | 4 | 5 | 5 | 4 |
| 10 | library, differing callers | 4 | 4 | 5 | 5 | 5 |
| 11 | `first_ok` backups | 4 | 4 | 5 | 4 | 4 |
| 12 | queue, ticker, SIGTERM | **3** | 4 | 4 | **3** | **3** |
| 13 | background task | 4 | 4 | 5 | 5 | 5 |

**Floor: 3**, at two programs:

- **08**, discoverable;
- **12**, obvious, safe and complete.

## 01 crawler: 4 / 4 / 4 / 5 / 5

Unchanged from round 1, and still legal under §2.2: no possible `Canceled` is stored, passed or interpolated.

- **Obvious 4, line 13.** The loop ends at cancellation and reads like the channel closing (Q5).
- **Discoverable 4, line 18.** `<Canceled> => break` is required only because every item counts.
- **Concise 4, line 18.** That arm is boilerplate for a case that can't happen here.

## 02 CLI saves on Ctrl-C: 4 / 4 / 4 / 5 / 4

- **Obvious 4, line 22.** The `return` leaves `optimize`, and the helper exists only so the save after it runs.
- **Discoverable 4, lines 18–24.** The §2.7 warning on `break` now points the way. The helper idiom must still be learned.
- **Concise 4, line 18.** The wrapper function. Python's `try/except` is shorter.
- **Complete 4, line 33.** An interrupted run exits 0.

## 03 `race` / `first_ok`: 4 / 4 / 5 / 4 / 5

- **Obvious 4, lines 1–2 and 13.** The comment justifies `race` for an authoritative NXDOMAIN. A reader still has to realise that a fast *transport* failure wins the same way.
- **Discoverable 4, lines 23–27.** The comprehension's type depends on the caller, and only hover shows it.
- **Safe 4, line 13.** An unreachable resolver that fails fast makes `ip` "unresolved" (line 16) while the other would have answered. `first_ok` is the safe choice. Under Q6 the loser's close no longer corrupts the result.

## 04 `within`: 4 / 4 / 5 / 5 / 5

- **Obvious 4, line 10.** You have to know that `first_ok`'s cancel reaches `within` as a `Canceled` that is discarded, while `within`'s own deadline gives `Timeout`. Lines 12–14 carry it.
- **Discoverable 4, line 11.** Whether `Timeout` appears depends on `first_ok`'s first-failure rule. Only hover shows it.
- **Safe 5.** Losers are discarded whole (Q6), so the stated type is true.

## 05 spinner: 5 / 5 / 5 / 5 / 5

The result is printed after the block (line 24), after the spinner has blanked its line (line 11). `$until_others_finish` reads correctly, and the never-ends warning leads to it. This is shorter than any of the five languages, none of which can do it without a done flag.

## 06 shared helper: 4 / 5 / 5 / 5 / 5

- **Obvious 4, line 15.** `?? base` silently also absorbs the item's `Canceled`. That is harmless, but invisible.
- **Discoverable 5.** The hover (lines 8–10) is now correct and names each call site.

## 07 CPU `check_cancel`: 5 / 5 / 5 / 5 / 4

- **Complete 4, lines 25–27.** Stopping the loop cleanly on Ctrl-C from `main` needs program 02's scaffold. Python needs nothing.

## 08 level-3 request in a job: 4 / 3 / 4 / 4 / 5

- **Obvious 4, line 16.** The arms now have distinct types. A reader must still learn that the request's `Closed` means "this caller gave up, or ended".
- **Discoverable 3, line 25.** Nothing leads you to put `task.cancel_request` in the job, and leaving it out is silent.
- **Concise 4, lines 7, 12 and 25.** An extra field, a poll and an extra argument. That matches Go's `ctx` and Rust's token.
- **Safe 4, line 25.** Leaving the request out silently keeps the worker decoding for callers that are gone. Line 12 also misses the worker's own cancellation (`is? Closed` is false for `Canceled`), so it starts one more decode.

## 09 server, SIGTERM drain: 4 / 4 / 5 / 5 / 4

- **Obvious 4, line 26.** The drain depends on connections belonging to `group`, not to the race item.
- **Discoverable 4, line 17.** `_ => {}` takes end of input, idleness and cancellation together.
- **Safe 5.** A normal body return joins without canceling (§2.1). A second SIGTERM during the drain gets the OS default, which is the expected escalation.
- **Complete 4, lines 2 and 28.** There is no overall drain deadline: a client that writes every 29 s keeps the server alive.

## 10 library, differing callers: 4 / 4 / 5 / 5 / 5

- **Obvious 4, lines 9 and 11.** `done => return done` forwards `Canceled` unseen. The `or_throw` on line 11 is a no-op in `cli`'s instance.
- **Discoverable 4, lines 15–18.** Where `retry` can be canceled is visible only in hover and docs.

## 11 `first_ok` backups: 4 / 4 / 5 / 4 / 4

- **Obvious 4, line 9.** "Back up to whichever disk is faster" is an odd backup policy. The other disk silently keeps an older generation, and the reader has to work that out.
- **Discoverable 4, lines 14–16.** What `first_ok` discards is visible only in hover.
- **Safe 4, lines 4–5 and 14–16.** In a release build the discarded `FileRemoveFailed` is reported nowhere, and a stray temporary file stays on the losing disk.
- **Complete 4, lines 17–18.** Under `$bulletproof` the program can't be written. The fix-it "handle it inside `backup_to`" is not actionable, because the removal happens inside the library's atomic `write_bytes`.

## 12 queue, ticker, SIGTERM: 3 / 4 / 4 / 3 / 3

- **Obvious 3, line 8.** `protect_from_cancel(30s @run_job(file))` reads as "after a stop, give the job 30 s". By v5's contract the limit starts when protection is entered, so it means "every job gets at most 30 s".
- **Discoverable 4, lines 7–8.** The pair of lines for "finish the current job" (a checkpoint between jobs, protection around one) has to be learned. No diagnostic leads to it.
- **Concise 4, lines 7–8.** "Finish the current job" takes two lines.
- **Safe 3, line 8.** In normal operation, with no SIGTERM, any job longer than 30 s is canceled.
  - Its `Timeout` is forwarded by line 8's `or_throw`, then by line 16's, out of `main`, and the processor exits.
  - The comment on line 2 describes a different program.
- **Complete 3, line 8.** It doesn't do what lines 1–2 announce. Fixing it needs protection whose limit starts at cancellation (review MF2), and the design doesn't offer that today.

## 13 background task: 4 / 4 / 5 / 5 / 5

- **Obvious 4, lines 5–7.** Telling "finished" from "stopped" takes `.running` read before `stop()`, because `.wait()` gives `void` either way.
- **Discoverable 4, line 11.** `or_throw` after the iterable forwards both `WatchError` and the task's `Canceled`. That double duty has to be learned.

## Where I differ from the author by 2 or more

| Program | Axis | Author | Mine | Why |
|---|---|---|---|---|
| 12 | Complete | 5 | 3 | The author reads the 30 s as counting from SIGTERM. Under v5's `protect_from_cancel` contract it counts from entry, so every job longer than 30 s is cut off in normal operation and ends the program. |

**One-point differences:**

- 03: safe.
- 05: obvious.
- 06: discoverable.
- 08: complete.
- 09: safe.
- 11: obvious.
- 12: obvious and safe.

**Floors.** Mine is 3, at programs 08 (discoverable) and 12 (obvious, safe and complete). The author's is 3, at program 08.
