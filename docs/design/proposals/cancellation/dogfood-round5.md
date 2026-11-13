# Dogfood, round 5

There are 26 programs in `programs-r5/`:

- **Copied from round 4:** 01–22. They keep the round 4 regrade's grades. The round 5 rule changes affect them in one place only: programs 12 and 26 forward the failures that their early exits now keep.
- **Revised:** 23, whose comment now states the named-branch rule.
- **New:** 24, 25 and 26.

Grades:

- **Axes:** obvious, discoverable, concise, safe by default and complete.
- **Compared against:** Python, Go, Rust, TypeScript and Swift.
- **Citations:** every score under 5 names its line.

| # | Program | O | D | C | S | Co |
|---|---|---|---|---|---|---|
| 01–22 | as `regrade-round4.md` | | | | | |
| 23 | best move under a deadline | 4 | 4 | 5 | 5 | 5 |
| 24 | `within`: a default vs a named branch | 4 | 4 | 5 | 5 | 5 |
| 25 | a pair under one deadline | 5 | 4 | 5 | 5 | 5 |
| 26 | repeated sibling failures | 4 | 4 | 4 | 5 | 5 |

**Floor: 3,** program 08, discoverable (line 29).

A caller that forgets to put `task.cancel_request` in its job gets no diagnostic. The link travels through a channel, which no analysis follows. Go, Rust and TypeScript have the same gap.

## 23 best move under a deadline: 4 / 4 / 5 / 5 / 5

- **Obvious 4, line 7.** The value survives the deadline because it comes from a `<Canceled>` arm. That is right, and it is what a reader writes anyway, but the reason is a rule to learn.
- **Discoverable 4, line 14.** Hover on `within` says which of its child's handlers keep a value.

## 24 `within`: default vs named: 4 / 4 / 5 / 5 / 5

- **Obvious 4, line 2.** `?? none` gives `Timeout` under a deadline rather than `none`. That is safe, but a reader has to learn it.
- **Discoverable 4, line 5.** Hover on the `within` call says "a default in from_cache gives Timeout after the deadline".
- **Safe 5.** A missed deadline can no longer pass for a cache miss, so `first_ok` still waits for the database.

## 25 a pair under one deadline: 5 / 4 / 5 / 5 / 5

- **Discoverable 4, lines 14–15.** Only hover shows that a canceled record gives `Timeout` while an uncanceled one is published narrowed.

## 26 repeated sibling failures: 4 / 4 / 4 / 5 / 5

- **Obvious 4, line 14.** `run`'s `return` gives a stack of the workers' stops instead of `void`, because they forwarded them. That is correct under D40 Q1, but surprising at first.
- **Discoverable 4, lines 23–25.** Only hover shows which failures a block keeps.
- **Concise 4, lines 18–22.** Three arms to cover "none", "one" and "several".
