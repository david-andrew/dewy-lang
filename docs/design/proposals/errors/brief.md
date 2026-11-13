# Design round: combining several errors into one value

You are designing one piece of the Dewy language. Read-only everywhere except `~/dev/tmp/par10/errors/`. The checkout is `~/dev/dewy-lang`. Read first: `docs/LANGUAGE.md` "Errors as values" and "Loops, text and optional values" (`or_throw`, `??`, `??<E>`, `or_throw<E>`), `docs/design/decisions.md` (all batches; `&` is type intersection; `Canceled` passes through `??`, D4 Q1), D40 in `docs/design/open_decisions.md`, and `docs/design/proposals/cleanup/` (round5.md, where `CleanupError[primary cleanup]` pairs a body failure with a cleanup failure). Search `resources/discussion_points.md` with `/usr/bin/grep` before proposing any name.

David (2026-11-12), on the two-field `CleanupError`:

> I think for multiple failures, dewy should support something like a sort of error stack. e.g. basically a common way to combine multiple errors into a single thing. I wonder about just letting you do `E1 & E2` and pass around that composite object? But also perhaps having some facility that could possibly tell you where in the code either error came from (I think that ought to be a thing errors support anyways, probably a metatag member of the error, on request). My one concern is if you just do `E1 & E2`, is there a straightforward way to split them back out into the separate errors? (Ideally yes). And then for more complex cases perhaps there could be some sort of structure you can just fold new errors into as you are going along.

Settle, starting from existing constructs:
- How several failures combine into one value (`E1 & E2` or otherwise; check what `&` already means for types and values and whether this fits it), its type, and how `match`, `??`, `??<E>`, `or_throw<E>` and `is?` see it (does `??<FileError>` catch a combination containing a `FileError`?). `Canceled` inside a combination must still pass through `??` (David's D4 Q1 rule).
- Splitting a combination back into its parts, in order.
- An accumulator for many failures (validation of a form, a batch of files, `parallel` items), folding errors in as you go.
- Where an error came from: a source location (and maybe a trace) available on request, ideally a metatag member; its cost and when it's recorded.
- Error context/cause wrapping ("failed to load config" caused by a `FileError`), if it falls out of the same mechanism.
- How cleanup uses it (replacing `CleanupError[primary cleanup]`).

Deliver `round1.md` (lead with minimal examples, each in its enclosing function), `programs/` (at least 10 realistic programs: cleanup pair, form validation, batch file processing, `parallel` items failing, a library adding context, a CLI printing the full chain with locations, retry with accumulated failures, and so on), `dogfood.md` (grade 1–5 on obvious, discoverable, concise, safe by default, complete against Python, Go, Rust, TypeScript and Swift, citing lines for every score under 5; iterate with round2.md/round3.md while anything under 5 is fixable), `names.txt` (every new name as a usage line, for a cold read), and `summary.md`. Dewy conventions: space-separated arguments, `=?` equality, `@f` handle, `$name` metatag, `or_throw`, `??`, value-returning zero-arg calls drop `()` and void ones keep it, strings formatted only with `fmt`, `.dewy` imports. No model names in files. Budget about three hours.
