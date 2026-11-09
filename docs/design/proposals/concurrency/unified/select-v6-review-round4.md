# Regrade: `select` by type, v6 round 4

Paper review of `proposal-v6-select-r4.md`, the 13 programs in `programs-r4/` and `questions-r4.md`. I checked them against `docs/LANGUAGE.md` and `proposal-v5.md`. Nothing was compiled. Grades are strict: 5 means nobody would think "it would be nice if the language let me do X". The comparison is the shortest correct Go, Rust (tokio::select!), Python asyncio, TypeScript and Swift version.

I read the round-3 review in the same shell call as the other inputs, before I had finished grading. I graded from the programs, and several grades overlap with its points. The check of its top five is lower down.

## Grades

| # | Program | Obvious | Discoverable | Concise | Safe | Complete | Floor |
|---|---|---|---|---|---|---|---|
| 01 | chat_command (`merged` + `.next`) | 4 | 4 | 4 | 4 | 4 | 4 |
| 02 | stdout_stderr (library reader) | 4 | 4 | 3 | 4 | 4 | 3 |
| 03 | two_tickers | 4 | 4 | 3 | 5 | 4 | 3 |
| 04 | selected_send (move-only job) | 3 | 3 | 4 | 4 | 4 | 3 |
| 05 | ctrl_c | 4 | 4 | 4 | 4 | 4 | 4 |
| 06 | merge / generic `forward` | 5 | 4 | 5 | 5 | 4 | 4 |
| 07 | worker_pool (`listed`, deadline) | 4 | 4 | 4 | 3 | 4 | 3 |
| 08 | single_timeout (`receive(timeout=)`) | 5 | 4 | 5 | 5 | 4 | 4 |
| 09 | drain_all | 5 | 4 | 5 | 5 | 4 | 4 |
| 10 | backpressure (`none` waits) | 3 | 3 | 3 | 3 | 4 | 3 |
| 11 | library_types | 4 | 4 | 4 | 4 | 4 | 4 |
| 12 | overlap_error | 4 | 4 | 3 | 5 | 4 | 3 |
| 13 | union_payload | 4 | 3 | 4 | 4 | 4 | 3 |

**Floor: 3.** Same floor as round 3, but narrower: seven of 13 programs hold a 3, down from eight. Nothing is below 3. Not ready for "all 5s".

## Why each grade is under 5

**Inherent to telling waits apart by type** (a cost of the owner's choice, not a defect):
- **02, 03, 11, 12, Concise 3:** two sources of the same payload type need two minted names, and every send site wraps its value. Go, Tokio and Swift tell two `string` channels apart by channel identity and write nothing. This is the one place the choice is clearly more expensive. The proposal handles it as well as it can: the library mints `Stdout` and `Stderr`, and the clash error prints the fix. Two default tickers still cost two `type of Tick` lines. I see no cheaper form inside type-directed matching.
- **13, Discoverable 3:** `Closed<T>` exists only so two closes are distinct members of a type-keyed union. `<Closed<Event>>`, `or_throw<Closed<Event>>` and `or_throw<Closed>` are three spellings a reader has to learn, where Go has `v, ok`. Inherent. The proposal's "the whole family" rule keeps the common spelling short.
- **01, 09, 06, Discoverable 4:** the drain and the select are two calls (`merged`, `select`) because one hides which source fired and the other reports it. A Go or Rust migrant types `loop { select ... }` first and meets the spin error. The error names `merged`, which is the best remedy available. Inherent.

**Fixable inside this design:**
- **01, Safe and Complete:** the first `inbox.next(timeout=0s)` runs before any `loop inbox.open`. The proposal says `.next` without the `open` fact is an obligation error, so program 01 is rejected by its own rule. Say that `merged(...)` over at least one source establishes `open` until the handle is stepped, or put the first call in the loop. `merged` also takes only a static list. There is no N-way fan-in over an `array<Channel<T>>` (Go `reflect.Select`, Rust `select_all`). A worker pool, which program 07 is named after but is not, needs that.
- **02, Concise:** the file declares `Stdout:type` and `Stderr:type` itself, while the proposal says user code does not. Program 11 is the real user view and is shorter. `n` starts as `let n = 0` (an `int`), is passed to `n:int64`, and `n += 1` runs in an unbounded loop. Under the guide's rules that is a fit obligation, not obviously proven.
- **04, Obvious and Discoverable 3:** a timed send is spelled `select(@worker.send(first) timeout=0s)`, one wait with no `priority`. `try_send` already exists in the guide and returns the payload on `Full`. Tokio's `send_timeout` returns the value in its `Timeout` error. In 04, whether `first` is still mine depends on which arm runs, and it is maybe-moved at the join. That is more machinery than either alternative. Fix: `ch.send(value timeout=D)` returns `void | Unsent<T>` with reason `Timeout`. The payload always comes back, and the ownership-by-arm rule is needed only when sends are mixed with other waits. `receive` got `timeout=` in this round, and `send` and `tick.next` did not.
- **07, Safe 3:** a ready operation always beats an expired deadline, under `'fair'` too (rule 1). In a loop like `loop { select(@jobs.receive timeout=deadline) }` a channel that is always ready means the deadline never fires. Go picks randomly among ready cases, so its timer fires eventually. A deadline reads as a bound. Fix: under `'fair'` the deadline joins the rotation once it has expired, and only `'listed'` ranks operations above it. If that is too costly, state the starvation in the rule and add a warning for a deadline loop whose waits are all channels.
- **10, Obvious, Discoverable, Concise, Safe 3:** about 25 lines against Tokio's roughly 10 with `reserve()`. The `Sent<Job>` arm's `local.pop(0)` needs `local.length >? 0`. The proposal says facts travel with `sending` and `incoming`. It never says that an arm inherits the fact from the wait that produced its outcome. Without that, `pop(0)` is an unproven index. The slot claim ties the send in one place to a `pop` in an arm elsewhere. The rules do not say what happens when the arm forgets `pop`, calls `remove`, or clears. A forgotten `pop` leaves a moved-out hole that the next iteration sends again. A hole in an array is new machinery. Fix: Tokio's shape. `@outbound.reserve` gives a permit, and `permit.send(local.pop(0))` cannot fail or lose the payload. It adds one member, which needs David's approval and a cold name test.
- **12, Concise:** the file contains no failing `select`, only a comment. It repeats 02 and 11. The parameter `err` is shadowed by the arm `err:Stderr`. State that shadowing is allowed in an arm, or rename.
- **13, Concise:** `take` uses a one-wait `select` with no timeout, which is `events.receive or_throw<Canceled>`. Use that, so the program shows what people will write.
- **08, 09, Complete 4:** `loop item in merged(...)` takes `priority=` but no deadline. A "drain but give up after 30 s idle" loop must be rewritten as `.open` plus `.next(timeout=)`, as in 01. That is a rewrite, not a small edit. A `timeout=` on the iteration form could end the loop. It is new surface and needs the owner.
- **05, 11, 06, small:** the proposal calls `CtrlCListener` a prelude name, and program 05 writes `task.CtrlCListener`. Pick one. Program 11 names a function `spawn`, which the guide uses as a keyword in `concurrent` blocks. Rename it. Program 05's `<CtrlC>` and `<Timeout>`-after-close arms are only reachable by a keypress or a clock, so the demo cannot show them.

## Soundness

- **Match coverage:** every `match` covers exactly the union the rules give. After `or_throw<Canceled>` the `Canceled` alternative is gone. Program 07 writes `<Closed>` for both close types, which the proposal's family rule allows. Programs 01 and 13 write the two `Closed<_>` arms separately and are also exact.
- **Arms that cannot run:** 04's first `failed:Unsent<Job>` arm cannot happen on an open channel, but the type needs it. 05's `<CtrlC>` needs a press. Everything else runs. 12's `err:Stderr` placed first is deliberate and correct.
- **Contradictions between programs and proposal:**
  - 01's first `.next` against the `open` obligation (above).
  - 02, 11 and 12 declare `Stdout` and `Stderr` in user code, while the proposal says the library does.
  - 04's comment says `Job[9]` is dropped on `Timeout`, so `released` is 1 afterwards. The proposal says "at the end of the `select` statement". The `select` is a match scrutinee, and the arm that prints "temporary dropped" runs before or after that point depending on a reading the text does not settle. Say the temporary drops when `select` returns, before any arm runs.
  - The guide's channels section says a canceled direct send returns `Unsent` with reason `Canceled`. The proposal makes a canceled selected send top-level `Canceled`. Both are defensible, but a caller who moves from `send` to `select` sees a different result type for the same event. Say so.
- **Under-specified:**
  - **Spin check, transitivity:** waits are often variables (`sending`, `incoming` in 10). "A variable that occurs in the wait expressions" does not say whether `local`, which builds those variables, counts. Write that a variable counts when it occurs in a binding the wait variables were built from.
  - **Spin check, no-op writes:** a write that does not change the wait (`flag = flag`) satisfies "assigns a variable".
  - **Spin check, helpers:** it is lexical. A helper `step` with a `select` whose close arm falls out, called from `loop true { step(a b) }`, spins undetected. Say that a function whose close arm returns normally warns at its loops of callers, or accept the gap.
  - **`merged` creation:** whether `merged` over zero static `none` sources starts with `open` true.
  - **Same channel twice:** `select(@a.receive @a.receive)` is a clash, but the printed advice says to brand the types. The bug is the duplicate source, and the advice is wrong for it.
  - **Maybe-moved:** the proposal covers variables and temporaries. It does not say that `local[0]` in a wait expression other than the send call, such as `let w = @outbound.send(local[0])` earlier in the block and `local.push(...)` between, drops the claim.
- **Overflow and index obligations:** 07's `int(1) * int(1)` is fine. 11's `argv[0]` is guarded by `argv.length >? 0`. 10's `local[0]` is proven by the same condition. 10's `pop(0)` in arms is the open one.
- **Spelling of the drop-hook record:** 04 and 10 write `Job:type = [... $__drop__ ...]`. The guide's two examples write `Ticket = type of [... $__drop__ ...]` and `Held = type of [...]`. If `type of [` is the form that makes a move-only owner, programs 04 and 10 need it.

## Dewy rules

- **Formatting:** no `{x:.2f}` or any format spec. Interpolation prints names, ints and strings only. Pass.
- **Zero-arg calls:** void ones keep `()` (`heart.stop()`, `out.close()`, `commands.close()`, `watch()`, `release = ():>void`). Value-returning ones drop it (`outbound.receive`, `tick.next`, `inbox.open`, `now`, `local.length`). Pass. `inbox.next(timeout=0s)` has arguments, so it keeps its parentheses.
- **Environment variables:** none. Pass.
- **Generated surface:** the guide's channel examples write `out.close` without `()`. That predates the convention and the programs follow the convention.

## Round-3 top five

1. **Same-typed sources need minting and wrappers (02, 03, 11, 12): partly fixed.** The library mints `Stdout` and `Stderr`, `@Stdout` passes the constructor (new surface, Q1), and both clash errors print the exact fix, including `type of Tick`. The programs still declare the types in user code, still wrap every send, and tickers still cost two lines. That is the inherent cost, now lower.
2. **`merged` has two protocols and holes: mostly fixed.** Neither protocol applies the overlap rule. `.open` is the proof for `.next`. `priority=`, handle ownership, parent and child payloads and `loop ... or_throw` as new surface are all stated. The new hole is 01's `.next` before any `open` check.
3. **The spin check is syntactic and wrong both ways: mostly fixed.** The arm-based rule is the whole rule, and both review examples are rejected. Residual holes: transitive wait variables, no-op writes, helper boundaries.
4. **`none` waits and ownership under-specified: partly fixed.** `const cap` is used, the "at least one wait" proof is written, the slot claim and the temporary's drop are defined, and 10 now flushes `local`. The arm does not inherit the wait's fact, and the claim is still coupled to a `pop` elsewhere.
5. **Rule gaps: fixed.** Deadline against a ready operation is rule 1, covariance of `Unsent<T>` is stated, `CtrlCListener` is named, the v5 line 191 conflict is superseded, and unit arms are `<T>`. Rule 1 itself now causes 07's deadline starvation.

## Top 5 remaining issues

1. **A deadline can starve (07).** Fix: an expired deadline joins the `'fair'` rotation, or the rule and a warning say that it cannot interrupt always-ready sources.
2. **Selected-send ownership is heavier than the alternatives (04, 10).** Fix: `send(value timeout=D)` returning `Unsent` with reason `Timeout` and the payload, and a `reserve` permit for the pump in 10. Both need David's approval and a cold name test.
3. **Arms do not inherit the facts of their waits, and the slot claim is under-specified (10).** Fix: write "an arm's outcome proves the fact of the wait that produced it". Define a compile error when a `Sent` or `Unsent` arm does not remove or give up the claimed slot.
4. **Program 01 breaks its own `.next` rule.** Fix: `merged(...)` starts with `open` true, and the rule says when `.next` makes it false. Also take an array of waits (a spread of channels) so fan-in over N workers is expressible.
5. **Single waits are inconsistent.** `receive(timeout=)` exists, and a timed send, `tick.next` and `ctrl_c.next` need a one-wait `select`. Programs 03 (`pulse`), 04 and 13 show it. Fix: give `.next(timeout=)` to tickers and the listener, and move 13's `take` to plain `receive`. Then correct the smaller items: user-declared library types in 02 and 11, `task.CtrlCListener` against prelude, `spawn` as a function name, and the shadowed `err` in 12.
