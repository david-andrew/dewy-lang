# Combined failures, round 5: fix the contract audit

You are continuing a design for the Dewy language: David's error-combination design (D42). Write only in `~/dev/tmp/par12/errors/`: `round5.md`, `programs-r5/` if programs change, `dogfood-round5.md` if grades change. Never rewrite earlier rounds, programs or reviews. The repo `~/dev/dewy-lang` is read-only; commit nothing.

**Save progress often:** write `round5.md` section by section as you go, so partial work survives if you are interrupted.

## Read first

- `round4.md`: Part 1 holds the decisions for David, Part 2 the implementation contracts C1–C7.
- `audit-round4.md`: an independent audit of Part 2, with 8 must-fix, 4 should-fix and 3 notes.
- `brief.md`, `summary.md`, and the earlier reviews, as needed.
- Binding context:
  - `docs/design/decisions.md` batch 10: David's design (`e1 & e2` typed `E1 & E2` as an unordered set; `as` extracts a part; `e1a & e1b` of one type is a compile error pointing to the error stack; `Canceled` is ordinary under `??`/`or_throw`, and `??<~Canceled>` excludes it);
  - D40 and D42 in `docs/design/open_decisions.md`;
  - `docs/LANGUAGE.md`.

## What to do

- **Resolve every must-fix (M1–M8), and the should-fixes where cheap.**
  - Prefer the fix with the fewest exceptions to Dewy's general rules. David's standing rule: every exception must earn its keep and be unavoidable.
  - For M6, ordered defaults vs commutativity: keep the established ordered-default rule unless removing it is clearly right. If you would remove it, it becomes a Part 1 question.
- **M8: move every observable policy out of Part 2 into Part 1,** as questions for David. Each gets a minimal example (enclosing function included when the question is about leaving it), the question, a recommendation, and whether it is reversible. Policies that are natural extensions of decided rules may instead be listed as one-line "taken, report only" items.
- **Out of scope:** cancellation semantics. A separate round is redesigning where `Canceled` can occur: it will appear only where something can cancel, inferred, and D42 Q2's spin warning is likely dropped. Leave D2, D3 and D7 of Part 1 as they are, except for one note that they await that round.

## Dewy conventions

- Arguments are space-separated; `=?` is equality.
- `@f` is a function handle; `$name` is a metatag that prefixes what it attaches to.
- `or_throw` forwards an error; `??` substitutes a default.
- `&`/`and`, `|`/`or` and `~`/`not` are each one operator: symbols in type expressions, words in value expressions.
- Strings are formatted only with `fmt`; imports use `.dewy` files.
- No model or tool names in any file.

## Final message

The `round5.md` path, any must-fix you could not resolve, and the new Part 1 questions. Budget: about 90 minutes.
