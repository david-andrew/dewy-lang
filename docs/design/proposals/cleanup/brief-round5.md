# Cleanup round 5: fix the review findings

You are continuing a design for the Dewy language: how resources clean up, and whether `defer` stays. Read-only everywhere except `~/dev/tmp/par9/cleanup/`, where you write `round5.md`, `programs-r5/`, `dogfood-round5.md`, and update `summary.md` and `names.txt` (never rewrite `round1.md`–`round4.md`, earlier programs, or the reviews).

## Read first

- `brief.md` (the original question and constraints), `round4.md`, `summary.md`, `programs-r4/`.
- `review-round4.md` (independent review: 2 must-fix, 7 should-fix) and `regrade-round4.md` (independent floor 2: programs 09 complete, 10 safe).
- Binding context: `~/dev/dewy-lang/docs/design/decisions.md` batches 3–8, D4 in `docs/design/open_decisions.md`, `docs/LANGUAGE.md` (loan rule ~1110–1161 and ~3571–3587; cancellation ~3653 and ~4693; `$__drop__` in "Records and collections"), `docs/design/ownership.md`.

## David's constraints (binding)

No callback-shaped scopes and no new block syntax: `return`, `break` and `or_throw` act on the enclosing function as usual. Correctness must not rely on remembering a second step. Unsafety is opt-in. Remove friction even if the compiler works harder; warn on performance cost. Start from existing constructs.

## What to fix

- **M1 (cancellation hidden in CleanupError).** A pair whose primary or cleanup is `Canceled` must still behave as cancellation: `??`, collectors and `?? return/break` must not default it away, and `$explicit_cancellation` must see it. Specify how, with the `save() ?? void` case.
- **M2 (transactions commit on any non-failing exit).** Separate guaranteed cleanup from permission to publish. Our suggestion, to weigh honestly: rollback is the automatic cleanup; commit is the operation's own explicit step (`tx.commit() or_throw`), not cleanup, so forgetting it is safe (nothing published) and the compiler can warn when no path commits. If that removes the need for the `successful:bool` hook parameter, drop it (less new surface); if process wait/stop still needs it, show why. Whatever you choose, include the `none`-return, early-return, `break` and `exit(0)` cases.
- **S1 (locks).** The helper-function workaround can't preserve the enclosing `return`/`break`. Weigh: lending guards (lock guards and similar protocol owners) hold to the end of their block, and braces shorten the region; storage owners keep last-use release. This changes the decided loan rule: say so plainly, show the costs (hold time, contention, deadlock checks extended to the longer interval, warnings on I/O or waits while held) and a protected region with an enclosing `return` and `break`.
- **S2–S7, N4:** address each as the review suggests (visible lifetime category in hover/docs for generic instances; ownership boundary for bindings lifted out of `parallel` blocks; dependent-field order with outcome-aware hooks, or note it goes away with M2's fix; the full D4 rewrite with the spsc reporter, moved into a once-run task and joined; program 09 marked blocked on the separate encapsulation question rather than graded as complete; the approval delta listing every semantic change, including the shielding/deadline clarification and the ownership docs that need updating; a real temp-file owner in program 06).

Keep what the review said works: direct owners, ordinary control-flow targets, checked non-failing one-off `defer`, exactly-once cleanup, optional explicit close, `CleanupError` pairing (names passed a cold read: `CleanupError`, `.primary`, `.cleanup` read correctly by three of three readers), and the shared-channel carve-out (explicit close stays for shared `Channel`/`mpmc`).

One cold-read lesson to act on: for a file whose final flush fails with no earlier error, only one of three readers was sure `save` returns that flush error itself (one expected a `CleanupError`). Make the diagnostic, hover or result type show it.

## Output

- `round5.md`: lead with the verdict and minimal before/after examples (5–10 lines each, no history): file write with a flush error, TCP early return, single-producer channel, mutex region with `return`/`break`, transaction, one-off "done". Then the rules, then each review finding and its resolution, then the list of semantic changes David must approve (each one sentence, saying what it changes).
- `programs-r5/`: revise the programs as needed and add the review's missing cases (generic owner with two instances, lifted `parallel` binding, transaction early exits, protected region with `break`, D4 rewrite).
- `dogfood-round5.md`: grade every program 1–5 on obvious, discoverable, concise, safe by default and complete against Python, Go, Rust, TypeScript and Swift, citing the line for every score under 5. Honest grades; an independent regrader will check them.

Dewy conventions: arguments are space-separated, `=?` is equality, `@f` is a function handle, `$name` is a metatag prefixing what it attaches to, `or_throw` forwards an error, `??` substitutes a default; value-returning zero-argument calls drop `()`, void ones keep it; strings are formatted only with `fmt`; imports use `.dewy` files. No model names in any file.

Final message: round5 path, the floor and why, and the list of semantic changes for David. Budget: about two hours.
