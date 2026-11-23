# Brief: a formal specification for Dewy generators (`lazy`) and multi-values, round 1

## Goal

David, Dewy's designer, has sketched generators built on `lazy`, with no `yield`, together with multi-value expressions. The sketch is in `sketch.md`; read it fully, including the clarification at the top. Turn it into a precise, structured specification at the standard of Dewy's other design proposals, and analyse the open questions.

Change no files in the repository. Write `round1.md`. Time budget: about 2–3 hours.

## Read first

The repository is `~/dev/dewy-lang`. Use `/usr/bin/grep` or `git grep`, not plain `grep`: here plain `grep` is ugrep, and it skips `.dewy` files when recursive.

- Dewy's goals: `docs/GOALS.md`. Python-like ease, C-like speed, safe by default with danger opt-in. Compile speed is a first-class goal.
- The language guide, `docs/LANGUAGE.md`:
  - blocks and multiple results, around line 280;
  - spreading and rest parameters, around lines 329–420;
  - loops and the provisional iterator protocol, around line 4925;
  - collectors and comprehensions.
- `docs/design/multi_expressions.md` and `docs/design/decisions.md`: binding decisions.
- `resources/discussion_points.md`, lines 315–460: David's earlier generator notes.
- Two examples of the expected standard: `docs/design/proposals/cancellation/round6.md` and `docs/design/proposals/errors/combined/round8.md`.
- `docs/design/open_decisions.md`: D40 (cleanup and `defer`) and D44 (cancellation). These interact with suspended generators.

A separate auditor is checking the sketch against existing decisions in parallel. Don't duplicate that work, but where you notice a conflict, resolve it in the spec and say so.

## What the spec must cover

1. **Model.**
   - What a multi-value (a "pack") is, compared with arrays, tuples and generators.
   - How packs flow: implicit expansion into calls and collectors, and explicit `...` for containers and generators.
   - What a generator value is. Give its type, its spelling, and how a length or element type appears in it.
2. **Syntax.**
   - `lazy <expr>`, `lazy ( ... )`, `lazy { ... }`, and the loop shorthand `lazy i in xs body`.
   - Postfix `...` spreading, and prefix `...` collecting.
   - Labeled termination (section 19 of the sketch). Check how labels and `$` metatags work in Dewy today.
   - Pack patterns in `match`.

   Mark every new spelling as new; David approves spellings separately.
3. **Evaluation and suspension semantics.**
   - When a lazy body runs, and where it suspends.
   - Eager function boundaries: section 17 of the sketch.
   - Delegation through `gen...`.
   - Private state, recursion and infinite generators.
   - Side-effect order.
   - What "done" means, and what happens on re-iteration. Is a generator single-pass? What does copying one do, given Dewy's value semantics?
4. **Types and compile-time checks.**
   - Heterogeneous and variable-arity outputs.
   - How a consumer is proven to handle every shape.
   - Inference of the generator's element type.
   - How `loop x in gen` types `x`.
5. **Interactions.** Each needs concrete rules:
   - ownership and borrowing: a lazy body capturing locals or places (section 24 of the sketch), and a generator outliving its creator's frame;
   - effects (`blocks`, `allocates`, `no panics`, …): whose effects these are, the creator's or the consumer's;
   - errors: `or_throw` inside a lazy body, and where the error surfaces;
   - cancellation (D44);
   - cleanup and `$__drop__` of a partly consumed generator (D40);
   - concurrency, including whether a generator can be sent to another task;
   - `return`, `break` and `continue` across the lazy boundary.
6. **Performance and lowering.**
   - How a lazy body compiles: a state machine, closure plus resume point, or full fusion into the consuming loop.
   - When it costs nothing: inlined into `loop x in gen`, with no heap allocation.
   - When it needs a heap frame: recursion, and generators stored or returned through unknown paths.
   - How the cost is made visible, consistent with the `$no_hidden_costs` lane.
   - The compile-time cost of the analysis. Dewy targets 200–250k lines/s, so the design must not need expensive whole-program analysis.
7. **The suspension-granularity question** (section 25 of the sketch). Analyse option A (one value per advance) and option B (a group per advance) seriously.
   - Consequences for typing, `zip`, `loop x in gen`, spreading, variable-arity branches, and performance.
   - Consider hybrids.
   - David leans towards B. Give a recommendation with reasons, whichever way it goes.
8. **Alternatives.** Compare this direction with the other ways Dewy could go, and say where each is better or worse for Dewy's goals:
   - Python and JS `yield` generators;
   - C# iterators;
   - Rust `Iterator` with closures and the proposed `gen` blocks;
   - Kotlin sequences;
   - Lua coroutines and stackful coroutines in general;
   - Haskell-style laziness;
   - pure library iterator adapters with no language support.
9. **`defer` steelmen.** D40 Q5 is open: does `defer` stay? Using these patterns, construct the strongest realistic cases for `defer`, especially a `defer` inside a lazy body that runs when the generator finishes or is dropped: exhaustion, an early `break` by the consumer, an error part-way, or cancellation. The motivating case was an LLM token stream that must record the full or partial reply however the consumer stops.

   Compare each case with the alternatives: a value with a `$__drop__` hook, a library `on_finish` adapter, or code after the loop. Say honestly which cases `defer` wins and which it doesn't.
10. **Open questions for David.** Each gets a minimal example, a recommended answer, and whether it's reversible. Flag every new name; names will be tested cold separately.
11. **Problems found in the sketch.** List where the sketch's examples are wrong, unclear or unidiomatic Dewy, with a corrected version of each.

## Style

Lead with what each rule does. Every rule gets a small Dewy example. Follow Dewy's example conventions:
- arguments are space-separated;
- `=?` is equality;
- value-returning zero-argument calls may drop their parentheses, and void calls keep `()`;
- `@f` is a handle;
- `$name` is a metatag prefixing what it attaches to.

Use no model or vendor names in the document.
