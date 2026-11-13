# Regrade, cancellation round 3

**Scope.** The 20 programs in `programs-r3/`, graded before reading `dogfood-round3.md`.

**Method:**

- Five axes, against Python, Go, Rust, TypeScript and Swift.
- Under round3.md's rules as written.
- Every score under 5 cites its line.

| # | Program | Obvious | Discoverable | Concise | Safe | Complete |
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
| 11 | `first_ok` backups, abandon | **3** | 4 | **3** | 5 | 4 |
| 12 | queue, ticker, SIGTERM | 4 | 4 | 4 | 4 | 5 |
| 13 | background task | 4 | 4 | 5 | 5 | 5 |
| 14 | pairing comprehension | 5 | 5 | 5 | 5 | 5 |
| 15 | sequential collector in an item | 4 | 4 | 5 | 5 | 5 |
| 16 | shared cache, `map` | 4 | 5 | 4 | 5 | 5 |
| 17 | logging, catch-all | 4 | 5 | 5 | 5 | 5 |
| 18 | generic forwarding | **3** | 4 | 5 | 5 | 5 |
| 19 | `task.tasks` with a marked reporter | 4 | 4 | 5 | 5 | 4 |
| 20 | `Task.wait` under a deadline | 5 | 5 | 5 | 5 | 5 |

**Floor: 3,** at three programs:

- 08 (discoverable);
- 11 (obvious and concise);
- 18 (obvious).

## Programs unchanged since round 2

Programs 01, 02, 04, 06, 07, 09 and 10 are unchanged since round 2, and confinement changes nothing in them. My round 2 grades and citations stand:

- **01:** obvious line 13, discoverable and concise line 18.
- **02:** obvious line 22; discoverable lines 18–24; concise line 18; complete line 33.
- **04:** obvious line 10, discoverable line 11.
- **06:** obvious line 15.
- **07:** complete lines 25–27.
- **09:** obvious line 26, discoverable line 17, complete lines 2 and 28.
- **10:** obvious lines 9 and 11, discoverable lines 15–18.

## 03 `first_ok` lookups: 5 / 4 / 5 / 5 / 5

- **Discoverable 4, lines 24–28.** The comprehension's type depends on its caller, and only hover shows it.
- **What changed.** `first_ok` for DNS removes round 2's fast-failure hazard, so obvious and safe are now 5.

## 05 spinner: 5 / 5 / 5 / 5 / 5

Unchanged, and still all 5.

## 08 level 3: 4 / 3 / 4 / 4 / 5

- **Obvious 4, lines 17 and 19.** The arms are distinct types, but *why* they differ rests on the hover text (lines 23–25).
- **Discoverable 3, line 29.** A forgotten `task.cancel_request` is silent.
- **Concise 4, lines 11–13.** Three cancellation checks in a row: the loop's `or_throw`, a `check_cancel`, and a poll.
- **Safe 4, line 29.** Forgetting the request leaves the worker decoding for callers that have gone.

## 11 `first_ok` backups, abandon: 3 / 4 / 3 / 5 / 4

- **Obvious 3, lines 9–11.** Two things a reader can't guess:
  - `left:FileRemoveFailed` binds the *whole* value, which may also hold `Canceled` and a write failure;
  - `left as ~FileRemoveFailed` passes on everything else.
- **Discoverable 4, lines 24–26.** The compile error leads you there.
- **Concise 3, lines 6–15.** Nine lines replace round 2's one-line `backup_to`. Any `race` or `first_ok` over an atomic write pays this cost.
- **Safe 5.** Nothing is lost:
  - `first_ok` keeps a fast failure from canceling a good write;
  - the atomic replace keeps the old backup;
  - the left-over temp file is reported.
- **Complete 4, line 11.** `as ~FileRemoveFailed` has nothing to return if the removal failure is the only part. It also relies on an undecided extension of `as` with `~`.

## 12 queue, ticker, SIGTERM: 4 / 4 / 4 / 4 / 5

- **Obvious 4, line 8.** You must know that protection's limit now counts from cancellation. It otherwise reads as a per-job cap.
- **Discoverable 4, lines 7–8.** The pair of lines for "finish the current job" has to be learned.
- **Concise 4, lines 7–8.** Those two lines.
- **Safe 4, lines 28–29.** A job cut off 30 s after SIGTERM is dropped silently, by the program's own reading. round3 §2.2's principle would publish it (review MF3).
- **Complete 5.** No cap in normal operation, 30 s after a stop: it does what lines 1–2 say.

## 13 background task: 4 / 4 / 5 / 5 / 5

- **Obvious 4, lines 5–7.** "Finished" versus "stopped" rests on a one-instant `.running` read.
- **Discoverable 4, line 11.** `or_throw` after the iterable does double duty.

## 14 pairing comprehension: 5 / 5 / 5 / 5 / 5

The commonest shape is now ordinary. After the join, `r.page` is `string | HttpError` (line 11). Python and Go both need a separate zip or index.

## 15 sequential collector in an item: 4 / 4 / 5 / 5 / 5

- **Obvious 4, line 4.** After its item is canceled, the loop keeps calling `get_text`, which returns `Canceled` at once. A reader expects it to stop.
- **Discoverable 4, lines 18–19.** The early-stop form, `or_throw<Canceled>`, has to be learned.

## 16 shared cache, `map`: 4 / 5 / 4 / 5 / 5

- **Obvious 4, lines 6–7.** That a shared cache can take only a forwarded result is learned from the error (lines 10–14).
- **Discoverable 5.** That error names both the store and the cancellable call.
- **Concise 4, line 5.** The check-then-read takes the lock twice. This is the program's choice, not the design's, but the idiom shown isn't minimal.

## 17 logging, catch-all: 4 / 5 / 5 / 5 / 5

- **Obvious 4, lines 11–13.** The catch-all arm logs "failed: Canceled" for a canceled item and forwards it as the result. That is correct, but it takes a moment to see.

## 18 generic forwarding: 3 / 4 / 5 / 5 / 5

- **Obvious 3, lines 21 and 24.** The same expression prints 2 in `main` and 3 in the item. A reader can't predict line 24 without knowing the type is per context.
- **Discoverable 4, lines 27–29.** That two bodies exist shows only under `$no_hidden_costs` or `explain`.

## 19 `task.tasks` with a marked reporter: 4 / 4 / 5 / 5 / 4

- **Obvious 4, line 18.** The marker prefixes the `spawn` statement but applies to the spawned task.
- **Discoverable 4, line 18.** You have to find the marker. The never-ends warning helps.
- **Complete 4, line 21.** There is no drain deadline, as in program 09.

## 20 `Task.wait` under a deadline: 5 / 5 / 5 / 5 / 5

Exactly the intended behaviour: the indexer keeps running after `Timeout` (line 9). It is clearer than Go's select on a done channel or Python's `wait_for`, which cancels the task.

## Where I differ from the author by 2 or more

**Nowhere.** My grades differ from the author's by 1 point in five places:

| Program | Axis | Author | Mine |
|---|---|---|---|
| 11 | Obvious | 4 | 3 |
| 16 | Discoverable | 4 | 5 |
| 16 | Concise | 5 | 4 |
| 18 | Obvious | 4 | 3 |
| 20 | Discoverable | 4 | 5 |

Program 12's safe grade is 4 from both of us, but for different reasons. The author treats the silent drop of a cut-off job as intended; I count it against review MF3.

**My floor is 3,** at programs 08, 11 and 18. **The author's floor is 3,** at 08 and 11.
