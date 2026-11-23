# Brief: audit the generator sketch for conflicts with Dewy's existing design

## Goal

David, Dewy's designer, has sketched a design for generators, `lazy` and multi-values in `sketch.md`. Read it first. Your job is to find every place where the sketch conflicts with Dewy's existing decided or documented design, or is wrong about how Dewy works today, so that the conflicts can be settled.

This is a read-only audit: change no files in the repository. Write your report to `audit-r1.md`.

## Where the design lives

The repository is `~/dev/dewy-lang`. Use `/usr/bin/grep` or `git grep`, not plain `grep`: here plain `grep` is ugrep, and it skips `.dewy` files when recursive.

- `docs/design/decisions.md`: David's accepted decisions. Treat these as binding.
- `docs/LANGUAGE.md`: the language guide for user-visible behavior. Relevant parts include:
  - blocks: `{ }` is scoped and `( )` is unscoped, around line 288;
  - multiple values from a function, around line 280;
  - spreading `xs...` and rest parameters `...parts`, around lines 329–420;
  - loops, `loop x in @xs`, and the provisional iterator protocol, around line 4925;
  - `break`, `continue` and `return`;
  - `match`, comprehensions and collectors;
  - grouping and the gap levels of line breaks, `;` and blank lines, around line 3195.
- `docs/design/multi_expressions.md`: expressions producing several values, collectors, and loops that make generator-like functions.
- `docs/design/*.md`: other design specs. In particular:
  - `value_semantics.md`, `ownership.md` and `effects.md`;
  - `safety_and_concurrency.md`;
  - `contained_paths.md`, for places;
  - `match.md` and `precedence.md`.
- `docs/design/open_decisions.md`: pending questions. Two touch this design directly:
  - D40, cleanup timing and whether `defer` stays;
  - D44, cancellation, including "loops over sources end at cancellation".
- `resources/discussion_points.md`: David's own earlier notes. Lines 315–460 sketch generators: `generator<Y R>`, `yield`, `yield from`, `.next`, and `gen.result`. The file also has notes on labels and `$`.
- The pre-restart reference documentation: `git show archive/master-pre-restart:site/reference/src/...` (list it with `git ls-tree -r --name-only archive/master-pre-restart site/reference/src`).

## What to look for

1. **Conflicts with decided design.** Name the decision, quote it with its file and line, and say exactly how the sketch disagrees. Examples to check (not an exhaustive list):
   - `(...)` is an unscoped block in Dewy, so names declared inside stay visible after it. David has clarified that `lazy` creates its own implicit scope whatever delimiter follows it. So `lazy ( ... )` is scoped; this is settled, not a conflict, but check that it doesn't contradict anything else.
   - `$name` is a metatag that prefixes what it attaches to. The sketch uses `$done` as a label (section 19), and Dewy may have no labeled `break` today.
   - How function results with several values, tuples ("tuples are per-position arrays") and `:>(int64 int64)` result types relate to the sketch's value packs.
   - The rest-parameter and `...` separator rules, compared with the sketch's prefix `...args` collection.
   - The decision that comprehensions are eager, and how collectors and multi-expressions are decided today.
   - Iteration: the provisional iterator protocol (`next` returning a value or `none`), and the decided `loop x in @xs` place iteration.
   - Whether `lazy` is reserved or already used, for example in `IntRange` or regex.
   - Indentation-only bodies such as `loop i in [0..5)` followed by an indented body: is that valid Dewy, or must the body be on the same line or in a block?
   - Effects (`blocks`, `allocates` and so on) and when they are reported for code that runs later inside a lazy body.
   - Ownership and places: section 24 produces `@x` places from a generator.
   - D44 cancellation and D40 cleanup timing, as applied to a suspended generator.
2. **Places where the sketch is wrong about today's Dewy:** spelling, operators (`isnt?`, `=?`, ranges), `match` syntax, handles (`@double`), and so on.
3. **Gaps the sketch leaves open** that an existing decision already answers. Say which decision answers each one.
4. **Real tensions,** where both the sketch and the existing design are reasonable and David must choose. For each, give the two sides concretely and a recommendation.

## Output

`audit-r1.md`, with one numbered entry per finding. Each entry gives:
- the sketch section;
- the existing design, with file:line and a short quote;
- the conflict;
- its severity: **must settle** (contradiction), **adjust sketch** (sketch wording or example), or **note**;
- a suggested resolution.

Order the entries by severity. End with a short list of existing decisions that the sketch fits well. Keep it factual: cite, don't speculate. Time budget: about 90 minutes.
