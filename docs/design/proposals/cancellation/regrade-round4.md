# Regrade, cancellation round 4

**Scope.** The 23 programs in `programs-r4/`, graded before reading `dogfood-round4.md`.

**Method:**

- Five axes, against Python, Go, Rust, TypeScript and Swift.
- Under round4.md together with the round 3 rules it keeps.
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
| 11 | `first_ok` backups | 4 | 4 | 5 | 4 | 5 |
| 12 | queue, ticker, SIGTERM | 4 | 4 | 4 | 5 | 5 |
| 13 | background task | 4 | 4 | 5 | 5 | 5 |
| 14 | pairing comprehension | 5 | 5 | 5 | 5 | 5 |
| 15 | sequential collector in an item | 4 | 4 | 5 | 5 | 5 |
| 16 | shared cache, `map` | 4 | 5 | 4 | 5 | 5 |
| 17 | logging, catch-all | 4 | 5 | 5 | 5 | 5 |
| 18 | generic forwarding | 4 | 5 | 5 | 5 | 5 |
| 19 | `task.tasks` with a marked reporter | 4 | 4 | 5 | 5 | 4 |
| 20 | `Task.wait` under a deadline | 5 | 5 | 5 | 5 | 5 |
| 21 | partition writes | 4 | 4 | 4 | 5 | 5 |
| 22 | ingress into fresh requests | 4 | 4 | 5 | 5 | 5 |
| 23 | best move under a deadline | 4 | 4 | 5 | 5 | 5 |

**Floor: 3,** at program 08 (discoverable).

## Programs unchanged since round 3

Programs 01–10, 13–17, 19 and 20 are unchanged, and round 4's rules change nothing in them.

Program 09 is legal under rule 4: only `conn`, from `accept or_throw`, crosses into a group passed in. My round 3 grades and citations stand:

- **01:** obvious line 13, discoverable and concise line 18.
- **02:** obvious line 22; discoverable lines 18–24; concise line 18; complete line 33.
- **03:** discoverable lines 24–28.
- **04:** obvious line 10, discoverable line 11.
- **06:** obvious line 15.
- **07:** complete lines 25–27.
- **08:** obvious lines 17 and 19; discoverable line 29; concise lines 11–13; safe line 29.
- **09:** obvious line 26, discoverable line 17, complete lines 2 and 28.
- **10:** obvious lines 9 and 11, discoverable lines 15–18.
- **13:** obvious lines 5–7, discoverable line 11.
- **15:** obvious line 4, discoverable lines 18–19.
- **16:** obvious lines 6–7, concise line 5.
- **17:** obvious lines 11–13.
- **19:** obvious and discoverable line 18, complete line 21.

## 11 `first_ok` backups: 4 / 4 / 5 / 4 / 5

`backup_to` is one line again (line 3).

- **Obvious 4, line 1.** "Back up to whichever disk is faster" leaves the other disk silently on an older generation. A reader has to work out that this is the policy.
- **Discoverable 4, lines 4–7.** What `first_ok` discards is visible only in hover.
- **Safe 4, lines 4–6.** A loser's stray temp file goes unreported in a normal build.
- **Complete 5.** Under `$no_discarded_failures`, the fix (handle it in `backup_to` with a `match`) can now be applied.

## 12 queue, ticker, SIGTERM: 4 / 4 / 4 / 5 / 5

- **Obvious 4, line 8.** Protection's limit counts from cancellation, and that has to be known.
- **Discoverable 4, lines 7–8.** The two-line idiom has to be learned.
- **Concise 4, lines 7–8.** Those two lines.
- **Safe 5.** A job cut off or failing after SIGTERM is now `main`'s exit status (lines 28–31).

## 18 generic forwarding: 4 / 5 / 5 / 5 / 5

- **Obvious 4, line 24.** `or_throw` inside the argument exists only to make the type inspection agree between contexts.
- **Discoverable 5.** The default warning (lines 27–29) names the difference and the fix.

## 21 partition writes: 4 / 4 / 4 / 5 / 5

- **Obvious 4, line 7.** `or_throw<Canceled>` is required on every write, although nothing cancels this loop. That follows from "every item counts".
- **Discoverable 4, lines 11–13.** The error names both fixes, but the reason (a `break` could leave a `Canceled` behind) has to be learned.
- **Concise 4, line 5.** Pre-filling the array with placeholders. Line 15's comprehension is shorter.

## 22 ingress into fresh requests: 4 / 4 / 5 / 5 / 5

- **Obvious 4, lines 6–7.** Why a value that has just been tested can't itself be captured into the protected body isn't guessable.
- **Discoverable 4, lines 11–14.** The error at the capture names the fix.
- **Concise 5.** One `bool` line. Go and Rust need a context check or token passing to do the same safely.

## 23 best move under a deadline: 4 / 4 / 5 / 5 / 5

- **Obvious 4, line 14.** `within` returning a `Move` after its deadline reads like `Move | Timeout`. A reader has to know that a handled, `Canceled`-free result survives.
- **Discoverable 4, lines 17–19.** The three outcomes have to be learned:
  - a forwarded cancellation gives `Timeout`;
  - a handled one keeps the value;
  - a nested one is an error.

  The third is review MF2, which should be removed.
- **Safe 5.** This program handles cancellation by name (`<Canceled> => return best`), so it is unaffected by review MF1's `?? default` hazard.

## Where I differ from the author by 2 or more

**Nowhere.** My grades differ from the author's by 1 point in four places:

| Program | Axis | Author | Mine |
|---|---|---|---|
| 11 | Obvious | 5 | 4 |
| 18 | Discoverable | 4 | 5 |
| 22 | Concise | 4 | 5 |
| 23 | Obvious | 5 | 4 |

**Floors.** Mine is 3, at program 08. The author's is also 3, at program 08.

The programs don't exercise review MF1. None has a `within` child whose `?? default` consumes the deadline's cancellation. A program like review MF1's `price` would grade safe 2 under round 4 as written.
