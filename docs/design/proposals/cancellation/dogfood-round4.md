# Dogfood, round 4

There are 23 programs in `programs-r4/`:

- **Unchanged from round 3:** 01–10, 13–17, 19 and 20. Each was re-checked against round 4's four rules. None carries a possible `Canceled` into a protected body, a cleanup hook or a spawned task, and none builds a failure with `Canceled` inside a facet. Programs 09 and 19 spawn into `serve`'s group from inside a race item, which is not a descendant request, so rule 4 applies there. What crosses is `conn`, which comes from `accept or_throw` and so can't hold `Canceled`.
- **Revised:** 11, 12 and 18.
- **New:** 21 (partition writes), 22 (ingress into fresh requests) and 23 (best result under a deadline).

Grades:

- **Axes:** obvious, discoverable, concise, safe by default and complete.
- **Compared against:** Python, Go, Rust, TypeScript and Swift.
- **Citations:** every score under 5 names its line.
- **Calibration:** where the round 3 regrade differed, its reading is taken.

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
| 11 | `first_ok` backups | 5 | 4 | 5 | 4 | 5 |
| 12 | queue, ticker, SIGTERM | 4 | 4 | 4 | 5 | 5 |
| 13 | background task | 4 | 4 | 5 | 5 | 5 |
| 14 | pairing comprehension | 5 | 5 | 5 | 5 | 5 |
| 15 | sequential collector in an item | 4 | 4 | 5 | 5 | 5 |
| 16 | shared cache, `map` | 4 | 5 | 4 | 5 | 5 |
| 17 | logging, catch-all | 4 | 5 | 5 | 5 | 5 |
| 18 | generic forwarding | 4 | 4 | 5 | 5 | 5 |
| 19 | `task.tasks` with a marked reporter | 4 | 4 | 5 | 5 | 4 |
| 20 | `Task.wait` under a deadline | 5 | 5 | 5 | 5 | 5 |
| 21 | partition writes | 4 | 4 | 4 | 5 | 5 |
| 22 | ingress into fresh requests | 4 | 4 | 4 | 5 | 5 |
| 23 | best move under a deadline | 5 | 4 | 5 | 5 | 5 |

**Floor: 3,** program 08, discoverable, line 29.

A caller that forgets to put `task.cancel_request` in its job gets no diagnostic, and the worker keeps decoding for a caller that has gone. The link travels through a channel, which no analysis follows. Go's `ctx` in a message, Rust's token and TypeScript's `AbortSignal` field have the same gap.

Program 11's 3s and program 18's 3 are gone.

## Unchanged programs

Programs 01–10, 13–17, 19 and 20 keep round 3's grades and citations, with the regrade's readings taken where it differed:

- 16 is concise 4 and discoverable 5;
- 20 is discoverable 5.

Two of them have new readings:

- **08.** Concise is 4, at lines 11–13: three cancellation checks in a row.
- **09.** Under rule 4 it is legal: only `conn` crosses into the spawned task, and it can't hold `Canceled`.

## 11 `first_ok` backups: 5 / 4 / 5 / 4 / 5

`backup_to` is one line again (line 3).

- **Discoverable 4, lines 4–7.** That a loser's failed temp-file removal is discarded shows only in hover, and under `$no_discarded_failures`.
- **Safe 4, line 5.** In a release build, a stray temporary file on the losing disk goes unannounced. The backups themselves are safe: the atomic replace keeps the old one, and `first_ok` stops a fast failure from canceling a good write.

## 12 queue, ticker, SIGTERM: 4 / 4 / 4 / 5 / 5

- **Obvious 4, line 8.** A reader has to know that protection's limit counts from cancellation.
- **Discoverable 4, lines 7–8.** The two-line "finish the current job" idiom has to be learned.
- **Concise 4, lines 7–8.** Those two lines.
- **Safe 5.** A job that fails, or is still running 30 s after SIGTERM, is now `main`'s result (lines 28–30), so the exit status reports it.

## 18 generic forwarding: 4 / 4 / 5 / 5 / 5

- **Obvious 4, line 24.** `or_throw` before the call keeps the two contexts in agreement, but it is needed only because of inspection.
- **Discoverable 4, lines 27–30.** The default warning leads to it; otherwise only hover shows the difference.

## 21 partition writes: 4 / 4 / 4 / 5 / 5

- **Obvious 4, line 7.** `or_throw<Canceled>` is required on the write even though nothing in this program cancels the loop. That follows from "every item counts".
- **Discoverable 4, lines 11–13.** The error names both fixes.
- **Concise 4, line 5.** Pre-filling the array. The comprehension form, line 15, is shorter and is what the fix-it suggests.

## 22 ingress into fresh requests: 4 / 4 / 4 / 5 / 5

- **Obvious 4, line 6.** Carrying `paused is? Canceled` instead of `paused` is the price of rule 4. It is natural once known, but not guessed.
- **Discoverable 4, lines 11–16.** The error at the capture names the fix.
- **Concise 4, lines 5–9.** One extra line for the `bool`.
- **Against the peers.** Go and Rust would let a stale cancellation flag ride into a background task unchecked. That is round 3's unsound case, now refused.

## 23 best move under a deadline: 5 / 4 / 5 / 5 / 5

- **Discoverable 4, line 14.** That `within` keeps the handled `Move` depends on `Move`'s type being free of `Canceled`. Hover says so; the program's text alone doesn't.
- **Against the peers.** Python's `asyncio.timeout` and Trio's `move_on_after` keep a body's value that handled its cancellation, as here. Go needs a channel or a shared variable.
