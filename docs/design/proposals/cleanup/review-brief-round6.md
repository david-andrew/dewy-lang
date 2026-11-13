# Independent review and regrade: cleanup round 6

You are checking a Dewy design before its owner, David, sees it. You did not write it. Read-only everywhere except your two output files in `~/dev/tmp/par10/cleanup6/`: `review-round6.md` and `regrade-round6.md`. The checkout is `~/dev/dewy-lang`.

The design: `round6.md`, `summary-round7.md`, `programs-r6/`, `dogfood-round6.md` (read the author's grades only after fixing yours). The brief it answers: `brief-round6.md`. Background: `~/dev/dewy-lang/docs/design/proposals/cleanup/` (rounds 1–5), D40 in `docs/design/open_decisions.md`, batch 9 in `docs/design/decisions.md` (binding).

David's asks this round answers (2026-11-12): (1) which cleanup timing, end of block or last use, gives programmers the fewest surprises (his gut said last use); (2) a cleanup failure on `break`/`continue`/an inner block's end must show a visible exit from the function, his spitball being `or_throw` after the loop; (3) steelman `defer`: can its best cases be written as straightforwardly without it.

## review-round6.md

For each finding: severity (must-fix / should-fix / note), rule or program line, a concrete scenario, a suggested fix. Check in particular:
- Is the timing comparison fair? Are there common surprises missing for either rule (e.g. memory held by large buffers, a lock held across a long tail by default, closures, early returns, generic code)? Does the recommendation follow from the evidence, and is the evidence presented honestly to David?
- The `loop … { … } or_throw` / `{ … } or_throw` acknowledgement: is it unambiguous with today's `or_throw` on a loop's value? Does it compose with nested loops, `parallel` blocks, `match` arms, labeled loops, and a loop whose body has no fallible owner? Is a missing marker always detectable at compile time? Would a reader see it as an exit? Compare with the alternatives in round6.md and say whether a better one was rejected.
- `defer` verdict: is the remaining case (a foreign global flag) real and strong, or would a small owner type be just as good?
- Anything that silently contradicts batch 9 or earlier decisions, or that is new syntax without saying so.

## regrade-round6.md

Grade each program in `programs-r6/` 1–5 on obvious, discoverable, concise, safe by default and complete against Python, Go, Rust, TypeScript and Swift, citing the line for every score under 5, before reading the author's grades. Then list differences of 2 or more from the author.

Final message: must-fix count with one line each, your floor and the programs at it, and whether you'd recommend block-end or last-use and why in two sentences. Budget about 90 minutes.
