# Combining failures, David's design: summary (round 3)

Current design: round1.md, amended by round2.md and round3.md (round 3 replaces where they differ). Programs: programs-r3/ (fifteen). Grades: dogfood-round3.md, an author regrade starting from regrade-round2.md. Lowest grade 3, all on discoverability; the independent round-2 floor of 2 (programs 11 and 13) came from contradictory rules, now removed. Nothing compiled. Values combine with `and`, types with `&` (one operator).

1. **Selecting and handling.** `is?`, `match` arms and `or_throw<E>` select a failure with an E part; an arm binds the whole value. `??<E>` consumes only failures whose every part it names. A part can disappear only through an action that names it, or a `;` drop, checked as an obligation on owned compound failures where whatever holds the value ends. Parameters are borrowed, so a callee may read any part. The check runs only where compound failures occur, is linear, and is capped at 64 part types per function.
2. **Cancellation (David's decision).** `Canceled` is an ordinary failure. `??<~Canceled>` doesn't consume `Canceled & E1`. `$explicit_cancellation` requires naming or excluding `Canceled`. A warning targets `?? continue` on a cancellable wait. A canceled run exits 130.
3. **`A & B`.** Minted types are facets; plain records merge as today; aliases mean what their expression means. `as error` takes every error part.
4. **No generic stack lifting.** The duplicate-type error applies at each generic use.
5. **Vocabulary.** Per-operation types under per-resource families; `FileError` becomes a parent. One-shot reads never combine; a failed commit rolls back at scope end. Library boundaries wrap failures and keep `Canceled` as its own part.
6. **Cleanup storage.** Each fallible owner carries its own failure slot; stacks are chains of segments; automatic cleanup never allocates. Gate open.
7. **The stack.** `ErrorStack<E>` = `type of error & array<E length>?0>`, nonempty through every mutation, handled as itself.
8. **Origins.** `$origin`, `$trace`, `$parts`, `$origin_at_caller`, scoped to the whole-program source build GOALS.md sets.

Still to do: an independent review of round 3; the obligation check's cost; owner slots built and tested with allocation refused; origin and trace sizes measured.
