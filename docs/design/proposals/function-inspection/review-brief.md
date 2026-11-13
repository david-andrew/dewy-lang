# Independent review and regrade: inspecting a function as data, rounds 1–3

You did not write this design. Read-only everywhere except your two output files in `~/dev/tmp/par10/inspect/`: `review-round3.md` and `regrade-round3.md`. The checkout is `~/dev/dewy-lang`.

Read `brief.md`, `round1.md`–`round3.md`, `summary.md`, `programs/`, `names.txt`, then `dogfood.md` only after fixing your grades. Binding context: `docs/design/decisions.md` (all batches; David prefers comptime/library mechanisms over compiler magic, metatags as meta functionality, removing friction even if the compiler works harder with warnings on cost, existing constructs before new syntax), `docs/LANGUAGE.md` (comptime, functions, generics).

## review-round3.md

Findings with severity (must-fix / should-fix / note), rule or program line, concrete scenario, suggested fix. Check:
- Is `code.Function<F>` as a parameter type the smallest mechanism? Compare honestly with (a) typed field selectors, (b) tracing a lambda on symbolic values via operator overloading, (c) a metatag on the parameter. Which would you pick for Dewy, and what does each lose?
- Privacy and hygiene: can a library learn private captured values or change meaning; is fallback always to the original function; can translation change results silently?
- `$__collect__` for comprehensions: is it sound and predictable for readers; does it change evaluation order, laziness or error behavior?
- Cost: compile-time and binary-size effects; are warnings specified?
- Is this a reasonable first version, or should it be cut to one use (database filters, or test assertions) first?
- Anything contradicting decided rules or new syntax not declared.

## regrade-round3.md

Grade each program in `programs/` 1–5 on obvious, discoverable, concise, safe by default and complete against C#, Scala, Julia, Zig, Rust and Python, citing lines for scores under 5. List differences of 2 or more from the author.

Final message: must-fix count with one line each, your floor and programs at it, and your recommended mechanism in two sentences. Budget about 90 minutes.
