# Review: one `parallel`

## Verdict

- One `parallel` ("items start together; the construct ends when they all end") is the right surface. Pool versus tasks is an implementation fact. No colours, structured join, and per-item values unless `or_throw` should stay. The soundness check's conditions are load-bearing: a waiting task releases its worker, opaque blocking gets capacity or a hard error, and a weak target diagnoses. Skip those and inferred waiting deadlocks.
- Inferring whether a wait is **legal** is right. Using today's `blocks` bit as a binary strategy switch is the surprise factory. `& no blocks` already rejects I/O and unclassified calls, not only parks. A log, a file write, or an opaque helper then moves a compute loop onto one stack per item, drops GPU offload, and changes what cancellation can stop. Result order stays. Memory, placement, and cancellation do not.
- Unknown effects are top. They take the conservative scheduler and name the forcing call. That is also how a harmless helper flips the loop.
- No required tag:
  - Hover and explain always name the strategy (inline/chunked pool, windowed tasks, or one task per item) and the forcing call.
  - One note when a static trip count is large and the choice is per-item, or when the forcing call is not an obvious wait (`sleep`, `send`, `receive`, `lock`, `within`, `select`). Not a warning on every `parallel`.
  - `& no blocks` stays the hot-path lock, as on `frame`.
- Drive strategy off "may park, or unknown" (`Block`). Leave non-parking `IO` on the pool. If surface `blocks` stays one bucket, the log note is mandatory.

## Weaknesses

1. **Any `blocks` means one task per item.** Independent waits (URL fan-out) still overlap on a window. A body that may wait on a sibling (`step(i)`) cannot be windowed. A million stacks is a failed cost model. Decision 10 then defers the only cap, so the eight-worker channel idiom becomes "at most eight".
   - **Fix:** three strategies, no annotation. No park: pool, chunk, or inline. Parks, with no dependence on a sibling or a not-yet-admitted item: a documented window (cores, or a small multiple). Possible sibling dependence: admit the set, and attach the note. A metatag can wait.

2. **The brace stops meaning "in order".** A block is sequential everywhere else, and whitespace separates expressions, so a second statement is a second item. The producer is safe only inside an extra `{ }`. Remove it and `numbers.close` races the consumer. `spawn` is what keeps today's `concurrent` block sequential.
   - **Fix:** each item is a `let` or a `{ … }` group, with a fix-it on a bare expression. Inner braces stay sequential. A cross-item `let` read is an error naming both. Keep the loop spelling. `parallel([@a @b])` cannot bind heterogeneous results after the join.

3. **Abort and cancellation disagree.** §5.2 cancels siblings on `or_throw`. §5.4 says a non-waiting body runs to completion. Check at chunk and steal boundaries, as already adopted, so find-first and a parent `within` can stop a compute loop without a fake `sleep(0ns)`.
   - **Fix:** keep boundary checks on the pool path. The in-flight chunk finishes; later chunks do not start. Which error escapes is schedule-dependent. "As in a sequential `loop`" is only where it propagates.

4. **`parallel x in rx` is an uncapped accept loop**, one task per arrival, on top of weakness 1. And `loop x in rx` that stops on `Canceled` and yields nothing reports success after a partial consume.
   - **Fix:** window that `parallel` like other independent waits. `loop` ends on `Closed` with an empty result; on `Canceled` its result is `Canceled`.

## `select` and `tasks`

- `select(ops)` plus `match` is the clearest shape with no new grammar. Ops register nothing until `select`; exactly one commits; `race` stays for ordinary calls. `ch.receiving`, `ch.sending(v)`, and `timeout(d)` match the call conventions.
- Priority by argument order starves a later op that is always ready beside an earlier one. Choose fairly among ready ops; pin tests with a seed or one op. Same payload types cannot be told apart, nor can two `Closed`s, so `dispatch` cannot mean "break only when control closes". `v:void` is not a value: `void | E` expresses `E` or nothing. Ship library `op.then(f)` now, and make a committed send `Sent | Unsent<T>`.
- `tasks(body)` is the right lifetime. Effects cannot infer "this child outlives this call". A copyable `Tasks` passed into the body, as `serve` passes `Service`, is the owner. Return joins. A child failure cancels the group. A child that never returns pins the join until `cancel`. Lead with autosave.

## Decisions

1. **Agree** on one `parallel` that may wait. **Disagree** that any `blocks` means unbounded task-per-item.
2. **Disagree** that every statement is an item. Agree on a block, `let` after it, brace-grouped items, cross-item reads rejected.
3. **Agree** on per-item values unless `or_throw`. The escaping error is first-in-time, not first-in-order.
4. **Agree** on `tasks`, `Tasks`, `g.spawn(@f(x))`, `g.cancel`, with `parallel`'s failure rule.
5. **Disagree** on argument-order priority. Agree on `select` + `match` and the op methods. Do not defer `op.then`.
6. **Disagree** on uncapped `parallel x in rx`. Agree on `loop x in rx` until `Closed`, preserving `Canceled`.
7. **Agree.** Admission is allocation. Ordinary exhaustion ends the process, replacing "every spawn returns `OutOfMemory`".
8. **Agree.** Drop `parallel_map`, `parallel_range`, and `parallel_update`.
9. **Agree.** `$parallel_safe` is race-freedom. Cost stays on `& no blocks`.
10. **Disagree** that the worker-pool idiom is enough. Defer a metatag; add the default window now.
11. **Agree**, including the `race`/`select` split and placement as context.

## Examples

- `v:void` on the sending `select` does not match Dewy. Use `Sent`.
- `dispatch` has one `Closed` arm for two channels, so `jobs` closing takes the `break`.
- `parallel { a  b  c }` and an unbraced producer are one statement from an extra racing item.
- `let firsts = [parallel … or_throw]` never binds. The first `Timeout` leaves `main`.
- `loop n in numbers { total += n }` treats cancel as a normal end, so a partial `total` is success.
