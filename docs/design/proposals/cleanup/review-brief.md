# Independent review and regrade: cleanup round 4

You are checking a design for the Dewy language before its owner, David, sees it. You did not write it. Read-only everywhere except your two output files under `~/dev/tmp/par9/cleanup/`.

## The design

`~/dev/tmp/par9/cleanup/round4.md` (and `summary.md`, `programs-r4/`, `dogfood-round4.md`). Earlier rounds (`round1.md`–`round3.md`) are history; round 3 used acquisition callbacks, which David rejected. The original brief is `brief.md`. Verdict of round 4: keep `defer` only for infallible one-off actions; resources clean themselves up; a fallible owner (a file being written) completes when its owning block exits, and its failure becomes the enclosing function's result (paired with an earlier failure as `CleanupError`); `$__drop__` may return `void | E` and take an optional `successful:bool`.

David's constraints (binding): no callback-shaped scopes, no new block syntax; `return`, `break` and `or_throw` act on the enclosing function as usual; correctness must not depend on remembering a second step; unsafety is opt-in; remove friction even if the compiler works harder, but warn on performance cost; start from existing constructs. Decided designs: `docs/design/decisions.md` (batches 3–8), D4 in `docs/design/open_decisions.md`, `docs/LANGUAGE.md` (ownership drops at last use near line 3999; cancellation near 3653; `$__drop__` in "Records and collections").

## Output 1: `review-round4.md`

Test the rules for correctness and consistency. For each finding: severity (must-fix / should-fix / note), the rule or program line, a concrete scenario, and a suggested fix. In particular check:

- Mixed timing: infallible owners release at last use while fallible owners complete at block exit. Is this predictable from the code? Can a reader tell which kind a value is? What about a generic function holding a `T`?
- Locks: the plain block form releases at the guard's last use, so `{ let v = @(state.lock()); v.balance += 10; write_journal() }` unlocks before the journal write, and the design asks for a helper function instead. Is that the right default, or should a lock (or any guard) hold to block end? What would that cost?
- Implicit failure at exit: a function with no visible failing call can now fail at its closing brace. How does a reader see this (result type, hover, a warning)? Does it interact badly with `??`, `match`, inferred result types, `parallel` blocks, `loop` bodies (does a file opened inside a loop body complete each iteration?), and `break` (round 4 says a failed cleanup crossing `break` returns from the enclosing function: check that).
- `successful:bool` on drop: what counts as success (a `none` result? an error value returned as data?). Transactions that commit at scope exit on success: is silently committing on any non-failing exit safe?
- Channels: is the explicit-close gap for shared channels acceptable, and is the spsc substitution in D4 sound?
- Whether anything here is new syntax or changes a decided rule without saying so.

## Output 2: `regrade-round4.md`

Grade each program in `programs-r4/` 1–5 on obvious, discoverable, concise, safe by default and complete, against Python, Go, Rust, TypeScript and Swift, independently of the author's grades (read them only after grading). Cite the line for every score under 5. Then list where you differ from the author by 2 or more.

Final message: must-fix count and the top three findings, your floor and the programs at it. Budget: about 90 minutes.
