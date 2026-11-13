# Independent review and regrade: cancellation round 1

You are checking a design for the Dewy language before its owner, David, sees it. You did not write it. Read-only everywhere except your two output files, `review-round1.md` and `regrade-round1.md`, under `~/dev/tmp/par13/cancel/`. Commit nothing.

## The design

`~/dev/tmp/par13/cancel/round1.md`, `programs-r1/`, `dogfood-round1.md`. The brief it answered is `brief.md` in the same folder; read it first, since it records what David said and decided in conversation (binding). Binding context: `~/dev/dewy-lang/docs/design/decisions.md` (batches 3–10), D40–D42 in `docs/design/open_decisions.md`, `docs/LANGUAGE.md` ~3600–3860.

## Output 1: `review-round1.md`

Test the rules for correctness and consistency. For each finding: severity (must-fix / should-fix / note), the rule or program line, a concrete self-contained scenario, and a suggested fix. In particular check:

- The inference rule: is it precise and decidable? Handles stored and called later, recursion, libraries, `parallel x in xs`, `task.tasks`, `select`, nested `within`/`race`. Is "one compiled body per function, types checked per context" sound, and what does a stored handle's type say?
- Q1: a written result type that leaves out `Canceled`, with the compiler adding it per context. Is that an exception to "an annotation fixes the error set", and does it earn its keep? Alternatives?
- The claim that every wait-produced `Canceled` is consumed by the group that caused it, and the three corrections round 1 needs for it (`Task.wait()`, canceled sends giving `Canceled` not `Unsent`, values read after a completed `parallel`). Are these changes to decided rules stated plainly?
- `$incidental` (or its alternative): semantics when every item is incidental, when incidental work holds a resource, when real work waits on incidental work, nesting; does the batch 9 signal rule really become an instance of it without behavior change?
- Q4 (iteration ends at cancellation instead of yielding `Canceled`) and Q5 (`AfterCancel<E>`): do they earn their keep, or are they new special cases? David's standing rule: every exception to Dewy's general rules must earn its keep and be unavoidable.
- Program 08's grade-3 gap (cancel requests passed between tasks through data): is there a better design within existing constructs?
- Anything here that is new syntax or changes a decided rule without saying so.

## Output 2: `regrade-round1.md`

Grade each program in `programs-r1/` 1–5 on obvious, discoverable, concise, safe by default and complete, against Python, Go, Rust, TypeScript and Swift, independently of the author's grades (read `dogfood-round1.md` only after grading). Cite the line for every score under 5. Then list where you differ from the author by 2 or more.

No model or tool names in any file. Final message: must-fix count, top three findings, your floor and the programs at it. Budget: about 90 minutes.
