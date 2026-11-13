# Independent review and regrade: combining failures, rounds 1–3

You are checking a Dewy design before its owner, David, sees it. You did not write it. Read-only everywhere except your two output files in `~/dev/tmp/par10/errors/`: `review-round3.md` and `regrade-round3.md`. The checkout is `~/dev/dewy-lang`.

The design: `round1.md`–`round3.md`, `summary.md`, `programs/`, `names.txt`, `semantics_model.py`, `comparisons.md`, `dogfood.md` (read the author's grades only after fixing yours). The brief: `brief.md`, which quotes David's request: combine multiple errors into one thing, maybe `E1 & E2`, split them back out, an accumulator to fold errors into, and where each error came from on request (ideally a metatag member). Binding context: `docs/design/decisions.md` (D4 Q1: `Canceled` passes through `??`; `&` is type intersection; batch 9), D40 in `docs/design/open_decisions.md`, `docs/LANGUAGE.md` "Errors as values".

## review-round3.md

Findings with severity (must-fix / should-fix / note), rule or program line, concrete scenario, suggested fix. Check in particular:
- The rejection of `E1 & E2`: is the reason (intersection can't keep order, duplicates or competing fields) sound, or could `&` work as a value-level combination whose type is the intersection, with order kept in the value? Present the strongest case for David's idea before judging it.
- Is two group types (`ErrorGroup` vs `ExceptionGroup`) more than a programmer should have to know? Would one group type with the cancellation rule suffice?
- `??<FileError>` not matching a group that contains a `FileError`: is that the least surprising rule? Compare with Python's `except*`.
- Is the surface too large (join, split, leaves, with_context, caused_by, $origin, $context, $cause, $trace, report, trace settings)? What could be cut for a first version?
- Is the default-on `$origin` cost acceptable and warned about?
- Anything contradicting decided rules or introducing syntax without saying so.

## regrade-round3.md

Grade each program in `programs/` 1–5 on obvious, discoverable, concise, safe by default and complete against Python, Go, Rust, TypeScript and Swift, citing the line for every score under 5. Then list differences of 2 or more from the author.

Final message: must-fix count with one line each, your floor and programs at it, and your verdict on `E1 & E2` in two sentences. Budget about 90 minutes.
