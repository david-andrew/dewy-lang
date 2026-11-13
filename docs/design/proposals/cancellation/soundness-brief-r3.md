# Soundness re-check: cancellation round 3

Check one well-scoped part of a design for the Dewy language. You may write only `~/dev/tmp/par13/cancel/soundness-round3.md`. Everything else is read-only: commit nothing and do not edit `~/dev/dewy-lang`.

**Read, in order:**
1. `~/dev/tmp/par13/cancel/brief.md`, which is binding;
2. your earlier `soundness-round2.md`, which had 3 must-fix (R1–R3) and its N4, the minimal sound restriction;
3. `round3.md` and `programs-r3/`.

Round 3 adopts confinement in place of the blanket ban:
- `Canceled` is ordinary inside its own work;
- creating one is ruled out;
- storing a value that may hold one anywhere that outlives that work is ruled out;
- boundaries clear the `Canceled` flag and publish the rest;
- types are per context, and machine code is duplicated only where a type argument, a local layout or type inspection differs.

**Questions:**
1. Is each of R1–R3 resolved? Give the strongest remaining counterexample for each, as a short self-contained Dewy program.
2. Is confinement as stated sound and enforceable by a decidable, demand-driven check? Probe at least:
   - the "outlives that work" boundary;
   - captured places and closures;
   - error fields;
   - `task.tasks`;
   - generics;
   - the flag representation of `Canceled` inside `&` combinations and stacks.
3. Is "`Canceled` as a flag on a failure value" consistent with `E1 & E2` being an unordered set of typed parts (decisions batch 10)?
4. List any new unsoundness or contradiction round 3 introduced.

**Output:** `soundness-round3.md`.
- Start with a five-line verdict.
- Then give each finding with:
  - its severity: must-fix, should-fix or note;
  - its location;
  - the program;
  - the fix.
- No model or tool names.
- Write the verdict first and save it early, in case you are interrupted.

Final message: the verdict, the must-fix count and the top three findings. Budget: about 60 minutes.
