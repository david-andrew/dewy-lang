# Gut read A (coordinator)

The core is right: `lazy` defers an expression Dewy can already write. Delegation and recursion follow from `...`. Side effects follow consumption. Fusion into the consuming loop is plausible. A lazy body's scope is the most natural home for `defer` so far.

Changes:
1. **Drop eager packs whose arity varies at run time** (`let v = if c (1 2) else (3 4 5)`). They contradict the fixed-count binding decision and push shape unions through every binding and call, which costs compile speed and diagnostic quality. Allow a varying count only where a collector, a generator or an explicit `match` consumes it.
2. **Option A, one value per advance.** In an eager context `(1 (2 3) 4)` is four values, so a lazy body should yield the same stream. That keeps `loop x in lazy(...)` consistent with `loop x in [...]`. Under B every consumer must handle "maybe a pair, maybe a triple", and generic adapters inherit that. Grouping, when wanted, is explicit: `[a b]` or a record.
3. **A generator is single-owner.** Copying a suspended computation either repeats its effects or forks its state. Move it; an explicit `.copy` could fork it.
4. **Drop the shorthand `lazy i in xs body`** in favour of `lazy loop i in xs body`.
5. **No places produced from a generator** unless the compiler proves the place can't outlive its container.

The risk is implementation cost: a state machine across nested loops, conditionals and spreads, and work proportional to depth for recursive delegation. Each is local per function.
