# Soundness re-check: cancellation round 4

Check one well-scoped part of a design for the Dewy language. You may write only `~/dev/tmp/par13/cancel/soundness-round4.md`. Everything else is read-only: commit nothing, and do not edit `~/dev/dewy-lang`.

**Read, in order:**
1. `~/dev/tmp/par13/cancel/brief.md`. It is binding.
2. Your earlier `soundness-round3.md`, which found 4 must-fix.
3. `round4.md` and `programs-r4/`.

**What round 4 changed:**
- It adds a fourth confinement rule: a value that may hold `Canceled` can't be carried into a protected body, a cleanup hook, or a task spawned from outside the work. The fix-it is to capture `x is? Canceled` instead.
- Inside a failure, `Canceled` may sit only in its cancellation facet.
- A boundary publishes a canceled work's success value when that value's type can't hold `Canceled`.
- A sibling canceled by an early exit keeps its whole failure.
- Round 3's idempotent `Canceled & Canceled` is withdrawn.

**Questions:**
1. Is each of your four round 3 must-fixes resolved? Give the strongest remaining counterexample for each, as a short self-contained Dewy program.
2. Are the four confinement rules together sound, and enforceable by a decidable, demand-driven check?
3. What new unsoundness or contradiction does round 4 introduce, if any? Check especially the "published when its type can't hold `Canceled`" rule and the `within` change that keeps a handled value.

**Output:** `soundness-round4.md`.
- Put the five-line verdict first, and save it early.
- Then give each finding with its severity (must-fix, should-fix or note), its location, the program, and the fix.
- Use no model or tool names.

Final message: the verdict, the must-fix count and the top three findings. Budget: about 45 minutes.
