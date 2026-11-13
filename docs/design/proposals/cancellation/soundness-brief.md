# Soundness check: inferring where `Canceled` can occur (cancellation round 1)

You are checking one well-scoped part of a design for the Dewy language. Read-only everywhere except your output file `~/dev/tmp/par13/cancel/soundness-round1.md`. Commit nothing; do not edit `~/dev/dewy-lang`. Another reviewer is covering ergonomics and grades; your job is only whether the inference is sound, decidable and cheap.

## Read

`~/dev/tmp/par13/cancel/brief.md` (what the language owner decided in conversation, binding), then `round1.md` and `programs-r1/` in the same folder. Context: `~/dev/dewy-lang/docs/LANGUAGE.md` ~3600–3860 (tasks, cancellation, channels, signals), decisions.md batches 3, 9, 10. Use `/usr/bin/grep` (plain `grep` skips `.dewy` files).

## The rule being checked

`Canceled` appears in a result type only where something can cancel: inside items of `race`, `first_ok`, `within`, `parallel` (every item counts) and everything they call. A function used in both kinds of context is type-checked per context; round 1 claims one shared compiled body suffices.

## Questions

1. State the inference as a precise fixed-point over the call graph. Is it decidable and monotone? Complexity, and is it demand-driven?
2. Try to break it, each with a short self-contained Dewy program: function handles stored in records or collections and called later from a different context; handles crossing task boundaries over channels; recursion and mutual recursion through both contexts; generic functions; library modules compiled once and used from both contexts; `task.tasks` started one by one; `select`; `within` nested in `race` and vice versa; a `parallel` inside a non-cancellable function; cleanup hooks (shielded). For each: what type does the rule give, and is any runtime `Canceled` possible where the type says it is impossible (unsound), or any type including it where it is impossible (merely imprecise)?
3. Is "one compiled body, types per context" sound? When does a single body observe a `Canceled` its non-cancellable instance's type excludes, and what does the generated code do then?
4. Round 1's claim that every wait-produced `Canceled` is consumed by the group that caused it, plus its three corrections: true? Counterexample if not.
5. What does a stored function handle's type say, and does that leak context into types the programmer writes?

## Output

`soundness-round1.md`: a five-line verdict first; then each finding with severity (must-fix / should-fix / note), the rule or line, the program, and a suggested fix. No model or tool names. Final message: verdict, must-fix count, top three findings. Budget: about 90 minutes.
