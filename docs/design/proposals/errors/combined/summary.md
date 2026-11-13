# Combining failures, David's design: summary

Final design: round1.md amended by round2.md; programs in programs/; grades in dogfood.md (author's, not independent). Floor 4; safe by default 5 in every program.

1. **Handlers.** Using a part is always allowed: `is? E1` is true for `E1 & E2`; `as E1` or an `E1` parameter takes the part. Handling consumes the whole failure: `??<E>` and `match` arms take a combination only when `E` names every part; otherwise `??<E>` passes it through unchanged. `or_throw<E>` forwards a combination when any part matches. A declared type holds a combination only if it lists it, or is `error`/`exception`. A compile error stops a variable silently dropping a part nobody named; `;` drops on purpose. Plain `??` takes everything except cancellation.
2. **Cancellation.** Original D4 Q1 reasoning recovered (level-triggered cancellation: `?? continue` spins forever; `?? 10` turns Ctrl-C into 10 and can exit 0). Options A (keep), B (`??` catches it with a warning), D (explicit everywhere), each with examples. Recommends A, with the editor marking every `??` that passes cancellation on. Under A, `Canceled & E1` behaves as `Canceled` for any test not naming `Canceled`; `as E1` still takes the part.
3. **Error types per operation.** Files: `FileError` family with `FileReadFailed`, `FileWriteFailed`, `FileCloseFailed`. Sockets: `NetError` with `SocketConnectFailed`, `SocketListenFailed`, `SocketSendFailed`, `SocketReceiveFailed`, `SocketCloseFailed`. Processes: `ProcessError` with `SpawnError`, `ProcessWaitFailed`, `ProcessStopFailed`. Transactions: `DbError` with `QueryFailed`, `CommitFailed`, `RollbackFailed`. Changes LANGUAGE.md: `FileError` becomes a parent, not a catch-all sibling. Automatic cleanup gives `body & cleanup`; several live owners of one type give an `ErrorStack` whose shape is fixed by the code; arrays of owners reserve room ahead so cleanup never allocates; generic `T & U` at `T == U` becomes `ErrorStack<T>`.
4. **`as` in general.** Takes the one part of type T; proven on a combination type, needs a guard on a union, ambiguous when several parts are T. Records: a field in several parts needs `as`; declared record intersections keep their one merged field.
5. **The stack.** `ErrorStack<E>` is `type of error & array<E>`, nonempty, in push order; `&`/`&=` push; `is? E` is false on a stack while `??<E>` consumes one. In a loop: build an array, then `if xs.length >? 0 return ErrorStack[xs...]`.
6. **Origins and traces.** `$origin` (a `SourceLocation`), `$trace`, `$parts`, `$origin_at_caller` for library functions (no spellings found in discussion_points.md). A type stores a 4-byte site number only if some `$origin` read can see it; a trace is captured only for types some `$trace` read can see. Costs unmeasured.

**Better than the ErrorGroup proposal:** the type says exactly which combinations come back; `??<E>`, `match` and `as` handle them without a recovery helper; a combination needs no allocation (clears round 4's out-of-memory gate).

**Worse:** result types grow with each resource whose cleanup can fail; different-kind failures keep no order (exit codes need a rule: lowest code wins); `match` arms and `is?` disagree on combinations; the dropped-part check is a new analysis; option A keeps `Canceled` special in one more place.

**Notes on David's sketch:** `match combined_fn() as result` would be new syntax clashing with `as`; `e1, e2 = result as E1, result as E2` parses wrongly because `,` binds tighter than `as`; `f1()` should be `f1`.

**For David:** handler rule (b) plus the dropped-part check (yes); cancellation A/B/D (A); `FileError` as a parent and the new error types (yes, after a cold read); `ErrorStack<E>` (yes, after a cold read); metatag names (cold-read first). Reported only: a `parallel` block could return `A & B` when two items fail independently (concurrency design).

Still to do: cold read of names.txt, independent review, cost measurements.
