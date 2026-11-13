# Independent review: combined failures round 5

You are checking a design for the Dewy language before its owner, David, sees it. You did not write it. Read-only everywhere except your output file `~/dev/tmp/par12/errors/review-round5.md`. Commit nothing; do not edit `~/dev/dewy-lang`.

## Read

`~/dev/tmp/par12/errors/round5.md` (answers `audit-round4.md`, an audit of round 4's Part 2 contracts with 8 must-fix), then `round4.md`, `brief-round5.md`, `brief.md` as needed. Binding: `docs/design/decisions.md` batch 10 (David's error-combination design), D40 and D42 in `docs/design/open_decisions.md`, AGENTS.md rule 6 (the two-question test).

## Questions

1. Is each audit must-fix (M1–M8) actually resolved? Strongest remaining counterexample for each, as a short self-contained Dewy program, or "resolved".
2. Round 5 adds nine Part 1 questions (D9–D17). Apply the two-question test to each: a semantic question reaches David only if (1) the common path isn't easy, ergonomic and fast, or (2) adjusting it when it doesn't fit isn't straightforward; otherwise the semantics are taken and only new syntax or spellings go to him. For each, say: keep as a question (and why it fails a test), or take it as "report only". David has asked that open_decisions carry no trivia; be strict.
3. For questions that stay: does each lead with a minimal example (with the enclosing function when it's about leaving the function), the question, a recommendation and reversibility? Are any recommendations wrong?
4. Anything that conflicts with D40 (cleanup at block end; cleanup failures become the function's result) or with the separate cancellation round (`Canceled` appears only where something can cancel; may be restricted as control, not data). D2, D3, D7 are deliberately left for that round.

## Output

`review-round5.md`: five-line verdict; then findings with severity (must-fix / should-fix / note), location, scenario, fix; then a table of D9–D17 with keep/take and a one-line reason. No model or tool names. Final message: must-fix count, top three findings, and how many of D9–D17 should stay as questions. Budget: about 75 minutes.
