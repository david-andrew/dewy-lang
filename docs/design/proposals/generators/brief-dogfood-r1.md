# Brief: dogfood the generator design, option A against option B

## Goal

Settle the open choices in Dewy's generator design (`lazy`, multi-values and `...` spreading) with evidence from realistic programs.

Read these first, in ``:
- `sketch.md`: the designer's sketch, with clarifications at the top;
- `round1.md`: the formal specification. It recommends option B, a group per advance, and admits packs whose arity varies at run time;
- `review-r1-a.md` and `review-r1-b.md`: two reviewers who both recommend option A, one value per advance, and cutting variable runtime arity;
- `audit-r1.md`: conflicts with existing decisions. Its finding 1 is the fixed-count binding rule.

For Dewy's conventions, skim `~/dev/dewy-lang/docs/LANGUAGE.md` as needed. Use `/usr/bin/grep`, not plain `grep`: here plain `grep` is ugrep, and it skips `.dewy` files.

Change no repository files. Write programs and results under `programs-r1/`. Time budget: about 2 hours.

## Task

1. Write **at least 10 realistic programs**, each 30–120 lines. They must use generators for real work, not toy demos. Cover at least:
   - an LLM token stream recording the full or partial reply when the consumer stops early;
   - a CSV or log reader with filtering and early exit;
   - a paginated API;
   - a recursive tree walk;
   - a tokenizer feeding a parser;
   - an infinite sequence with `take`;
   - a pipeline of map, filter and chain;
   - zip or enumerate-style pairing;
   - a game-loop event stream;
   - mixed-type output;
   - a resource (file or socket) that must be closed when the consumer abandons the stream.
2. Write each program **twice**: once under option A, and once under option B as `round1.md` specifies it. Where variable runtime arity appears, also write a version without it, using arrays, records or `match` on an explicit union instead.
3. **Grade each version 1–5** on five axes:
   - obvious;
   - discoverable;
   - concise;
   - safe by default;
   - complete, meaning nothing the programmer wanted to write is missing.

   Compare against Python, Rust, C#, Kotlin and Swift for the same task.
4. **Record every friction point:** the place, what went wrong, and which option caused it.
5. **Decide.**
   - Which option wins, A or B, and on which programs?
   - Does variable runtime arity earn its keep anywhere?
   - Is a cleanup hook (`defer` in a lazy body, or a `$__drop__` value) necessary? Which programs fail to be safe without one?
   - Does the `lazy i in xs body` shorthand earn its keep over `lazy loop i in xs body`?

## Output

`dogfood-r1.md`, with:
- a table of programs × option × the five grades;
- the friction list;
- the decisions with evidence, as program and line references.

Use no model or vendor names. Reply with a 10-line summary.
