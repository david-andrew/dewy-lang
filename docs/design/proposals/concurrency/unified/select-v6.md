# `select` by type, v6 round 7

- **BLUF:** Same-typed waits are one alternative. `select` never cancels. `race`, `within`, and `first_ok` do. A deadline is not remembered across calls. `reserve` and `send(timeout=)` are the sends. There is no selected send and no `@job.wait`.
- **Task results.** v5's child task is `void | E`, and the call is `wait()` with parentheses (`proposal-v5.md` line 24). `LANGUAGE.md`'s `concurrent` block still has `let a = spawn work(21)`. Those are different constructs. This round does not make a task completion selectable. A scoped group fails fast, so a child exception never arrives as a `select` arm.
- **Delivery:** design only. Programs are in `programs-r7/`.

## What type-directed matching costs

Paid only when the program asks which source fired. The library mints `Stdout` and `Stderr`. A user file does not.

| You need | Dewy | Go / Tokio |
|---|---|---|
| The first `string` | One arm. Program 02. | One case per channel when the bodies match. |
| To know stderr from stdout | The library's two children. The user who does not care prints the line. Program 11. | The case label is the identity. |
| To know which of two application strings | Two children the user declares, and every send wraps. Program 12. | The case label. |
| Which close, on one channel | `Closed<Event>`, `or_throw<Closed<Event>>`, and `or_throw<Closed>`. Program 13. | `v, ok`. |

`string | Stdout` normalizes to `string`. A child satisfies the parent, so the child does not survive beside it. Brand both sources, or don't mix them. Arm order cannot get the child back.

`type of string` is not in `LANGUAGE.md`. "Errors as values" allows `type of error`, `type of exception`, and `type of any`. Other nominal parents, including `type of int64`, are not supported yet. A child of `string`, and `Stdout(text)`, are a question. `ticker<T>` is a question.

## Deadline

Nothing about a deadline is stored across calls.

- A `Duration`, including `timeout=0s`, restarts at every call. `0s` is a poll: a ready operation wins, and an empty wait is `Timeout`. Program 08. The same poll on the next call still takes a buffered value.
- A `MonoPoint` is an absolute deadline. Under `'fair'`, a deadline already in the past wins, and a buffered value stays buffered. That is the whole rule. A reused absolute deadline cannot be starved, because it wins. Program 07, both `fair_past` calls.
- Under `'listed'`, the written waits come first and the deadline is last. A ready `Stop` beats an already-past deadline. The caller who wants that deadline first writes `if now >=? deadline` before the call. No third priority value.

`priority=` with fewer than two waits is a warning. One-wait methods do not take `priority=`.

## Signature

```text
select(
    ...waits : each Waitable<R_i> or none, or a spread of array<Waitable<R>>,
    keyword-only timeout : Duration | MonoPoint = none,
    keyword-only priority : 'fair' | 'listed' = 'fair'
) -> union of the R_i, with duplicates collapsed
     | Canceled
     | Timeout, when timeout is not only none
```

No arguments, a known-empty spread, or a spread whose length is zero at run time is "select needs a wait". The same obligation when every argument is `none`. `race` and `merged` use that rule. Program 10 keeps one wait by `length >? 0` or `length <? cap`.

`string | string` is `string`. `Closed<string> | Closed<string>` is `Closed<string>`. A homogeneous spread adds `R` once. `LANGUAGE.md` requires a spread to match a fixed parameter count. This rest is the exception, shared with `race` and `first_ok`.

`channel<T>` is rejected when `T` overlaps `Canceled` or `Closed<T>`. A payload `Timeout` beside `timeout=` is one `<Timeout>` arm. Brand the payload, or hold it in a record, when they must differ.

## Send and reserve

`send(value timeout=D)` returns `void | Unsent<T> | Canceled`. `Canceled` is the call's result, as on `receive`, and `or_throw<Canceled>` forwards it. `Unsent.reason` is only `Timeout` or `Closed`. `.value` is the job on both. Hover says that. The job comes back. `try_send` stays the non-waiting `Full`. A `send` with no deadline has no `Timeout`.

`@ch.reserve` waits for a free slot. Its outcome is `Reserved<T> | Closed<Reserved<T>>`. `Closed<Job>` stays the element's close, so a pump drains `local` on inbound close and spills only on outbound close. `permit.send(value)` is `void`. A held permit is a slot already taken: if the channel closes before `permit.send`, the value is still delivered into that slot. The close is visible to a `reserve` that has not won.

`select(@out.reserve @stop.receive)` then `permit.send(job)` is "send or stop". The job stays with the caller until that arm.

Selected sends are dropped, and `Sent<T>` with them. No program used `@ch.send(value)` inside `select`. What is lost: the value cannot sit in the buffer while a stop is also racing, because it is sent only after the reserve has won. A stop that wins means the job was never offered. That is the call to write.

An arm inherits the fact of the wait that produced it. `local.length >? 0` on the `reserve` wait proves `pop(0)`.

### Outcomes

| Operation | Direct |
|---|---|
| receive | `T \| Closed<T> \| Canceled`, plus `Timeout` when `timeout=` is set |
| `send(timeout=)` | `void \| Unsent<T> \| Canceled`. Reasons: `Timeout`, `Closed` |
| `try_send` | `void \| Unsent<T>`, reason `Full` or `Closed`. No wait, no `Canceled` |
| reserve | `Reserved<T> \| Closed<Reserved<T>>`, plus `Canceled` and `Timeout` when it waits |
| `tick.next` | `E \| Canceled`, plus `Timeout` |
| `ctrl_c.next` inside the callback | `CtrlC \| Canceled`, plus `Timeout` |

`Unsent<T>` is covariant. `Closed<T>` is invariant. `or_throw<Closed>` is every close. `or_throw<Closed<Event>>` is that one. `Closed<Reserved<T>>` is not `Closed<T>`.

A ticker's `stop()` consumes it. The listener type is `task.CtrlCListener`. Storing it past `catch_ctrl_c` is an error, so it has no `Closed`. This supersedes v5 line 191.

A temporary passed to `send(timeout=)` is owned by the `Unsent` when the call fails, and by the channel when it returns `void`.

## `merged`

Closes of the same type are one alternative. `merged` retires by operation.

It starts `open` when it has at least one source. `.next` is legal while `open` is true. The `.next` that retires the last source returns that `Closed<T>` and then sets `open` false. The loop checks `open` first. Zero sources, or a known-empty array, is "merged needs a source".

A `merged` value iterates. `loop item in inbox` is the same loop as `loop item in merged(...)`. After either, `inbox.open` is false when every source closed, and true when `stop_when_idle=` ended the loop. The channels stay open in that case. Program 09.

`merged(workers)` for `array<Channel<T>>`, or an array of those receives, yields `T`. `priority='listed'` uses source order, then index order for an array.

`stop_when_idle=` is the gap with nothing new, restarted after each value. Cold-read: all three readers read it as idle, a normal stop, channels left open. `.next(timeout=)` is one step, the same deadline as `receive(timeout=)`. It is not the iteration gap. A `<Timeout>` arm with `timeout=0s`, or with a deadline already in the past, that reaches the backedge is the spin error. Program 01 does not poll.

`loop item in merged(...) or_throw` is the v4 §12 binding. It is not in `LANGUAGE.md`.

## Spin

A `Closed<T>` arm, or a `Timeout` arm under a poll or an already-past deadline, that reaches the loop's backedge must assign a variable the waits depend on, or leave the loop. A variable counts when a wait expression reads it, or when a wait binding was built from it. `flag = flag` does not count. A finite `n <? 3` around an empty close arm is still rejected.

A function whose close arm returns normally is marked may-spin. One level of callers. The same operation listed twice is "this operation is listed twice".

## Patterns

Unit arms are `<T>`: `<Closed<string>>`, `<Closed<Reserved<Job>>>`, `<Timeout>`, `<Tick>`, `<CtrlC>`. `<Closed|Stop|Timeout>` is the existing grouped arm.

## `race`, `within`, `first_ok`

```text
race(...work : each () -> R_i, or a bound handle, or a spread of array<() -> R>)
    -> union of the R_i, duplicates collapsed | Canceled

within(duration, work: () -> R) -> R | Timeout | Canceled

first_ok(...work) -> the first success
    | the first failure, only when every one failed
    | Canceled
```

`@load.(sources)` is the fan-out. `LANGUAGE.md`: "Every argument group in an ungrouped `@` chain partially evaluates". `f.(values)` is an elementwise argument group. Parentheses end the chain. `.( )` does not. So `@load.(sources)` is an array of partials. Scalar arguments would be repeated. Nothing is called, and nothing fuses, because nothing runs. `race(@load.(sources)...)` and `first_ok(@load.(sources)...)` are that array spread into the rest.

A bound handle is work. `race(@cache.receive @load(url))` runs `receive` and `load`. The receive that loses is canceled and takes nothing. The one that wins returns what `receive` returns, including `Closed`.

Success for `first_ok` is an alternative that is not an exception. The call returns the first of those. If every result is an exception, it returns the one that finished first, and cancels the rest. If the result type has no exception alternative, `first_ok` is `race`. A loser that was canceled is not a result. The caller's own `Canceled` is the call's `Canceled`. `first_success` was read the same way. The programs keep `first_ok`.

`within` joins the work before it returns, so a call that does not check cancellation can pass the deadline. That is the structured-concurrency cost.

## Language features

| Feature | What it is |
|---|---|
| Same-typed waits collapse | The arm is the granularity. `string \| Stdout` is `string`. |
| `type of string`, `ticker<T>` | Not supported yet. Questions. |
| Deadline | No cross-call state. Past absolute deadline wins under `'fair'`. `0s` is a poll. |
| `race` pack, `within`, `first_ok` | The words that cancel. `@load.(sources)` is the array of partials. |
| Bound handle as work | `race(@cache.receive @load(url))`. A losing receive takes nothing. |
| `send(timeout=)`, `reserve` | `Canceled` is top-level. `Closed<Reserved<T>>` is the reserve close. |
| `merged`, `stop_when_idle=` | The handle iterates. `open` tells idle from done. Cold-read. |
| At least one wait | "select needs a wait". |

## Compiler cost

Union collapse is the ordinary union of that one call, including a parent absorbing its child. The spread is linear in the array. No overlap pass. The spin check is one look at a `select` or a zero-timeout `next` in a loop. Programs that never wait pay nothing. Measure on the flagship panel before it lands. `$no_deadlocks` still rejects `select`, `race`, `merged` and `within` until certificates understand alternatives.
