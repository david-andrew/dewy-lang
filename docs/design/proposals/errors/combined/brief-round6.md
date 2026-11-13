# Combined failures, round 6: fix the round 5 review

You are continuing a design for the Dewy language: David's error-combination design (D42). You may write only in `~/dev/tmp/par12/errors/`: `round6.md`, plus `programs-r6/` and `dogfood-round6.md` if programs or grades change. Never rewrite earlier rounds, programs or reviews. The repo `~/dev/dewy-lang` is read-only. Commit nothing. Save `round6.md` section by section as you go.

## Read first

- `round5.md` and `review-round5.md`: an independent review with 3 must-fix, its should-fixes, and a table that sorts D9–D17 into keep or take.
- `audit-round4.md` and `round4.md`, as needed.
- `brief.md` and `summary.md`.
- Binding context:
  - `docs/design/decisions.md` batch 10. This is David's design: `e1 & e2` is typed `E1 & E2` and is an unordered set; `as` extracts a part; combining two failures of one type is a compile error that points to the error stack; `Canceled` is ordinary under `??`/`or_throw`, and `??<~Canceled>` excludes it.
  - D40 and D42 in `docs/design/open_decisions.md`.
  - AGENTS.md rule 6, the two-question test.

## What to do

1. **Resolve MF1–MF3.**
   - MF1: a cleanup failure discards a success value that carries combined failures.
   - MF2: an allocation refusal's early exit under `$explicit_allocation_failure` drops a local variable that holds a combination.
   - MF3: `FileError` appears beside its own child. Use a concrete leaf such as `FileOpenFailed`, and add it to the list of names to cold-read.
2. **D10's real policy goes into D1 as the question.** D1 currently amounts to: "a combined failure held in a variable must be handled, while a single failure needn't be." Weigh it against the narrower option, where only `match` arms carry the duty:
   - The review says the narrower option removes MF1 and MF2 and most of the whole-program check.
   - David's own batch 10 sketch must compile under whichever option you recommend.
   - Prefer the option with fewer exceptions to Dewy's general rules. David's standing rule: every exception must earn its keep and be unavoidable.
3. **Trim D9–D17 per the review's table.**
   - Only D17 stays a question. Merge D16's rule on how handlers see a stack into it.
   - Show the caller in D17, and both shapes it can see. Don't assume block-end cleanup, since D40 Q2 is still open; show both answers.
   - Fold D14 into D5 as a `FileSyncFailed` name, to be cold-read.
   - Move D13 to the database round. List it in a short "for D43" note.
   - The other questions become one-line "taken, report only" items.
4. **The remaining partial fixes from the review:**
   - M4: state a cost bound for the analysis that actually ships, not the exponential reference version.
   - M8: reading `$trace` makes every call on the path reserve memory on entry. Either remove that, or state it as a Part 1 question.
5. **The cancellation round is separate and already decided its direction:**
   - `Canceled` appears only where something can cancel; this is inferred.
   - It is confined to its own work: it can't be created, and can't be stored where it outlives that work.
   - D2, D3 and D7 stay unchanged. Fix only D4's `wrap` example, which uses `Canceled` as data in a parameter type.

## Dewy conventions

- Arguments are space-separated, and `=?` is equality.
- `@f` is a function handle. `$name` is a metatag that prefixes what it attaches to.
- `or_throw` forwards an error, and `??` substitutes a default.
- `&`/`and`, `|`/`or` and `~`/`not` are each one operator: symbols in type expressions, words in value expressions.
- Strings are formatted only with `fmt`, and imports use `.dewy` files.
- No model or tool names appear in any file.

## Output

`round6.md`, in this order:
1. Part 1, the decisions for David. Each has a minimal example (with the enclosing function when it is about leaving one), the question, a recommendation, and whether it can be reversed.
2. The taken items.
3. Part 2, the contracts.
4. A finding-by-finding resolution table.

`names-r6.txt`: any new names, shuffled, one per line.

Final message: the round6 path, any unresolved must-fix, and the Part 1 questions. Budget: about two hours.
