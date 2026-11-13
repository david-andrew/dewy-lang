# Independent check: cleanup round 7

You did not write this design. Read-only everywhere except your output file `~/dev/tmp/par10/cleanup6/review-round7.md`. The checkout is `~/dev/dewy-lang`.

Read `round7.md`, `programs-r7/`, `dogfood-round7.md`, `summary-round7.md`, and the previous review `review-round6.md` (M1, M2, S1–S4) that round 7 answers. Background: batch 9 in `docs/design/decisions.md` (binding) and D40 in `docs/design/open_decisions.md`.

1. Are review-round6's M1 and M2 actually resolved? Say yes/no per finding with the line that shows it.
2. Readability: the visible-exit form is now `loop path in paths ({ … } or_throw)`, while `loop … { … } or_throw` is rejected when the body owns a fallible resource. Would a programmer write this correctly unaided? Propose up to three simpler alternatives that still make a possible function exit visible (for example requiring an explicit `out.close() or_throw` inside such loops, or binding the owner outside the loop, or a compile error with a fix-it), and grade each against the round-7 form on obvious, concise and safe by default.
3. The recommendation to drop `defer`: is the small owner type really as good in every program where `defer` was used (programs 16, 27 and any others)? Name any case where `defer` is still clearly better.
4. Regrade every program in `programs-r7/` 1–5 on obvious, discoverable, concise, safe by default and complete against Python, Go, Rust, TypeScript and Swift, citing lines for scores under 5, before reading the author's grades; list differences of 2 or more.

Final message: must-fix count with one line each, your floor and the programs at it, your best alternative to `({ … } or_throw)` if any, and your verdict on dropping `defer`. Budget about an hour.
