# Soundness re-check: cancellation round 2

You are checking one well-scoped part of a design for the Dewy language. Read-only everywhere except your output file `~/dev/tmp/par13/cancel/soundness-round2.md`. Commit nothing; do not edit `~/dev/dewy-lang`. Another reviewer covers ergonomics and grades; your job is only soundness, decidability and cost.

## Read

1. `~/dev/tmp/par13/cancel/brief.md`: the owner's conversational decisions. These are binding.
2. `soundness-round1.md`: the earlier soundness check, which raised 4 must-fix.
3. `round2.md` and `programs-r2/`, both in the same folder.

Context: `~/dev/dewy-lang/docs/LANGUAGE.md` ~3600–3860 and decisions.md batches 3, 9 and 10. Use `/usr/bin/grep`; plain `grep` skips `.dewy` files.

## Questions

1. **Each round-1 must-fix (M1–M4).** Is it resolved by round 2's rule, "`Canceled` is control, not data"? That rule says no constructing, storing, collecting, capturing, sending or passing `Canceled`, and no writing it in a type. Find the strongest counterexample against each resolution, as a short self-contained Dewy program, or explain why none exists.
2. **The restriction itself.** Is it enforceable by a decidable, demand-driven check? Look for leaks through:
   - generics instantiated at a union containing it;
   - `match` arms binding it;
   - `&` combinations stored in an error stack;
   - closures;
   - compile-time type inspection;
   - foreign calls;
   - `task.tasks`.
3. **Round 2's §2.10 claim** that one compiled body is always sound under the rule. Is it true?
4. **Is there a strictly smaller restriction that is still sound?** The owner considers `Canceled` an ordinary error type and wants every exception to earn its keep. Say what each part of the restriction buys, and which parts could go.
5. **New unsoundness or contradictions** that round 2 introduced: the `$until_others_finish` interaction with the batch 9 signal rule, and Q6/Q7.

## Output

`soundness-round2.md`. Start with a five-line verdict. Then give each finding with:
- its severity: must-fix, should-fix or note;
- the rule or line it concerns;
- the program;
- a suggested fix.

No model or tool names. Final message: the verdict, the must-fix count, the top three findings, and the minimal sound restriction. Budget: about 75 minutes.
