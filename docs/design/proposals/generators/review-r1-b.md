# Gut read B (independent reviewer)

`lazy` as an expression is the right primitive. A generator is a value an ordinary function can return, and a call such as `eager_fn()` still runs to completion, so the continuation transform has a hard boundary. That is what makes C-like code generation plausible. `[loop i in xs i^2]` and `lazy i in xs i^2` are the same computation under two wrappers, and `inner()` versus `inner()...` draws a clear line between "this generator is one value" and "splice its outputs". Effects running only as far as the consumer pulls matches that model.

The pack story fights the rest of the sketch:
- **Parentheses.** `add((1 2))` is already `add(1 2)`, so parentheses don't build a tuple, and loops "express values" flatly into their context. Option B needs `(2 3)` to be a nested group, and only inside `lazy`.
- **Concrete break.** `let g = lazy (1 (2 3) 4)`, then `loop x in g`. Under B, `x` is an `int` and then a pack, so `map` and `filter` as written (`f(x)`, one binding) don't type-check. Under the flattening calls already use, the inner parentheses were a no-op, and B isn't expressible.
- **Dynamic arity makes it worse.** `let v = if c (1 2) else (3 4 5)` has type `(int int)|(int int int)`, and `add(v)` is illegal, as is any wrapper that forwards `v`. The diagnostic points at a branch the caller never wrote.
- **Resources are the safety hole.** A `lazy` that opens a file, then `break`s on the first empty line, never runs the rest, so the file stays open. There is no `finally`, and `defer` is explicitly open.
- **Places repeat Rust's hardest generator bug.** `loop @x in @values @x` suspends a borrow of the generator frame; storing `@x` and advancing again aliases or dangles.
- **An eager `(loop i in [0..n) i)`** is a runtime-sized pack that looks like grouping and has to allocate.
- **Layout does semantic work** the clarification says it doesn't. If juxtaposition is one pack, section 21's body is a single group, and the first advance runs every `printl`.

**Pick A, one value per advance.** Sections 6–21 already describe that, it matches flat expansion at calls, and `loop x in g` stays monomorphic. "These two belong together" is a product, which `zip` already writes as `[a b]`. Parentheses as suspension boundaries would mean a formatter changes the protocol, and effects would run for a group the consumer didn't ask for.

What to cut and what to keep:
- Cut runtime-varying arity. A heterogeneous stream is one union element per advance, `int|string|bool`.
- Keep `add(1 2)` as call sugar; a stored pack must not explode at `add(ab)`.
- Keep the `lazy i in xs body` shorthand and the eager-call boundary.
- A `lazy` that doesn't escape its consumer loop has to lower to that loop. Three unfused `map`/`filter` closures miss C speed the way LINQ does.
- Don't yield places in the first cut.
- Don't ship generators without a cleanup hook on exhaustion, `break`, error and drop.

Comparisons:
- **Python.** Generator functions, `yield` and `yield from` are the clumsier version of this expression. Python also yields one object per `yield` (a tuple is one object). Its `finally`/`close` path is the part this sketch lacks.
- **Rust.** `next() -> Option<Item>` is the same one-value protocol, and the reason chains can be C-fast. Copying its monomorphized adapter types will blow a 250k-lines/s compile budget.
- **C#.** The compiler rewrites the whole method, so a helper can't produce values unless it is also an iterator; the eager boundary here avoids that. `finally` on Dispose is again the missing piece.
- **Kotlin.** `sequence { yield; yieldAll }` is the closest prior art: one value per yield, explicit spread, suspension confined to the builder, and `try/finally` for cleanup. `lazy` plus `...` should be that, with a real product where Kotlin writes `yield(a to b)`.
