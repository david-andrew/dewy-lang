# Regrade: `select` by type, v6 round 6

Paper review of `proposal-v6-select-r6.md`, the 25 programs in `programs-r6/` and `questions-r6.md`. I checked them against `docs/LANGUAGE.md` and concurrency `proposal-v5.md`. Nothing was compiled. I graded before opening the round-3 and round-4 reviews. Grades are strict: 5 means no programmer would think "it would be nice if the language let me do X". The comparison is the shortest correct Go, Rust (tokio), asyncio, TypeScript and Swift version.

## Grades

| # | Program | Obvious | Discoverable | Concise | Safe | Complete | Floor |
|---|---|---|---|---|---|---|---|
| 01 | chat_command | 4 | 4 | 4 | 4 | 4 | 4 |
| 02 | stdout_stderr | 4 | 4 | 3 | 4 | 4 | 3 |
| 03 | two_tickers | 4 | 4 | 3 | 5 | 4 | 3 |
| 04 | selected_send (`send(timeout=)`) | 4 | 4 | 4 | 4 | 4 | 4 |
| 05 | ctrl_c | 4 | 4 | 4 | 5 | 4 | 4 |
| 06 | merge / generic `forward` | 5 | 4 | 5 | 5 | 5 | 4 |
| 07 | worker_pool (`listed`, `fair`) | 4 | 3 | 4 | 3 | 4 | 3 |
| 08 | single_timeout | 5 | 5 | 4 | 4 | 5 | 4 |
| 09 | drain_all (`idle_timeout`) | 5 | 4 | 5 | 5 | 4 | 4 |
| 10 | backpressure (`reserve`) | 4 | 4 | 3 | 3 | 3 | 3 |
| 11 | library_types | 4 | 4 | 5 | 5 | 4 | 4 |
| 12 | overlap_error | 4 | 4 | 3 | 5 | 4 | 3 |
| 13 | union_payload | 4 | 3 | 4 | 4 | 4 | 3 |
| 14a | mirrors, `select` cancels (rejected) | 3 | 3 | 4 | 2 | 2 | 2 |
| 14b | mirrors, `race` | 4 | 4 | 4 | 5 | 4 | 4 |
| 14c | mirrors, `@job.wait` | 2 | 3 | 2 | 2 | 1 | 1 |
| 15a | fetch or cache, `select` cancels (rejected) | 3 | 3 | 4 | 2 | 2 | 2 |
| 15b | fetch or cache, `race` | 3 | 3 | 3 | 5 | 4 | 3 |
| 15c | fetch or cache, `@job.wait` | 3 | 3 | 4 | 3 | 2 | 2 |
| 16a | work timeout, `select` cancels (rejected) | 3 | 3 | 4 | 2 | 2 | 2 |
| 16b | work timeout, `within` | 5 | 5 | 5 | 5 | 5 | 5 |
| 16c | work timeout, `@job.wait` | 3 | 3 | 3 | 3 | 2 | 2 |
| 17a | first success, `merged` | 3 | 3 | 3 | 4 | 4 | 3 |
| 17b | first success, `first_ok` | 4 | 5 | 5 | 5 | 4 | 4 |
| 17c | first success, `@job.wait` | 2 | 2 | 2 | 2 | 1 | 1 |

**Floor over the recommended forms** (01–13, 14b, 15b, 16b, 17b): **3**. The `a` and `c` variants are comparators. The `a` ones show the rejected design, and I grade them against the final rules. The `c` ones are low because they cannot do the job, which is the proposal's own point. 16b is the only all-5.

## Why each grade is under 5

**Inherent to type-directed arms and cancel-as-a-value** (a cost of the owner's choices, not a defect):
- **02, 03, 12, Concise 3.** Two same-typed sources need two minted names, and every send site wraps. Go, Tokio and Swift tell two `string` channels apart by identity at no cost. I see no cheaper form inside type-directed matching. The library minting `Stdout` and `Stderr` is the best case (see 11).
- **13, Discoverable 3.** `<Closed<Event>>`, `or_throw<Closed<Event>>` and `or_throw<Closed>` are three spellings where Go has `v, ok`.
- **01, 06, 09, Discoverable 4.** A Go or Rust migrant types `loop { select }` first and meets the spin error. The error names `merged`, which is the best remedy.
- **Every wait, Concise 4.** `or_throw<Canceled>` plus an exhaustive `match` has no counterpart in Go, Tokio, asyncio or Swift. It comes with cancellation as a value.
- **16b.** `within` returns after the work has joined, so a non-cooperating call overshoots the deadline. This is the structured-concurrency cost, and Go's abandoned goroutine is the alternative. I kept it at 5.

**Fixable inside this design:**
- **07, Discoverable and Safe 3.** The `fair` rotation is hidden state kept per `select` site and carried across calls. `fair_pair` returns `value 4`, then `timeout` while 5 is still buffered, from the same code. Nothing in the source shows why. It also contradicts the proposal's other rule (issue 1).
- **08, Safe 4.** The comment "a buffered value beats `timeout=0s`" is false under rotation. Call a function like `read_reply` twice with two buffered replies and the second call times out.
- **10, Concise, Safe and Complete 3.** The `reserve` close and the `receive` close are the same `Closed<Job>` arm, so the pump cannot tell inbound closed from outbound closed (issue 2). The `if cond @x else none` waits are clunky but acceptable (tokio has the same `if` precondition).
- **04, Safe and Complete 4.** `or_throw<Canceled>` on a direct send contradicts the rule that a canceled send is `Unsent` with reason `Canceled` (issue 4). No program reads `.reason`, and "retry on `Timeout`, give up on `Closed`" is the whole point of the call.
- **01, Safe 4.** `inbox.next(timeout=0s)` in a loop is a busy poll when the channels are open and empty. The spin rule only covers `Closed` arms. A `<Timeout>` arm that reaches the backedge under a zero timeout is unchecked.
- **05, Complete 4.** Neither `<CtrlC>` nor the final `line:Line` arm can run in the demo. The program has no `Interrupted` stdin path, which is the real Ctrl-C use.
- **09, Complete 4.** The loop ends the same way on idle and on completion, and the `merged` handle is a temporary, so the caller cannot ask `open`. Bind it: `let inbox = merged(...)`, iterate `inbox`, then check `inbox.open`. The proposal doesn't say whether a handle iterates.
- **11, Complete 4.** `Child` holds plain `Channel<string>`, so the user cannot tell the pipes apart. If the library minted `Stdout` and `Stderr`, `merged(...)` would yield `Stdout | Stderr`, and a user who doesn't care still just prints it. That also removes 02's user-declared types.
- **14b, Complete 4 and 17b, Obvious 4.** `race([loop url in sources @load(url)]...)` is three ideas for fan-out over a list: comprehension, thunk, spread. Go and Python are no shorter, but this is the most common concurrency call. `race(sources load)` (an array and a function) is one idea. That is new surface for David.
- **15b, 3.** The proposal says "race cannot take `@cache.receive` bare". v5 says a bound method handle keeps its callable interface, so `race(@cache.receive @load(url))` should work. It would be 8 lines, not 11 with a wrapper lambda. The same program uses a comma between arguments, which no other program does. State that a bound handle is valid race work, and a canceled receive consumes nothing.
- **17b, Complete 4.** `first_ok` says "the failure alternatives, only when every one failed". It doesn't say which failure comes back (first, last, or all). It also doesn't say what "success" is when `R` has no error member.
- **14c, 15c, 16c, 17c.** See issue 3. They cannot return the page, they print "fetch ended", and 17c's comment describes a loop the code doesn't have. They are also the same body as 14c.
- **14a, 15a, 16a.** They contradict "select never cancels" and use `Selectable`, while the proposal says `Waitable`. Delete them or mark them rejected in the file.

## Soundness

- **Match coverage is exact** in every program I checked, with `Canceled` gone after `or_throw<Canceled>`. 07's `<Closed>` is the family arm, which the rules allow. 10's single `<Closed<Job>>` arm covers two real outcomes by design (issue 2).
- **Arms that never run:** 05's `<CtrlC>` and the last `line:Line`. 13's closed `wait_alarm` is only reachable by history (below). The `err:FetchError` arms in 14c, 15c, 16c and 17c are dead or racy (issue 3).
- **Group fail-fast vs `@job.wait`.** v5 says a scoped group fails fast. A child failing with `FetchError` stops the siblings and the callback and returns the failure from `tasks(...)`. A `select` over `.wait` then gets `Canceled`, not `err:FetchError`, and in 14c and 17c the first mirror failing aborts the whole group even when another mirror succeeds. The proposal doesn't say how `@job.wait` meets fail-fast. The arm only makes sense for a `BackgroundTasks` child, or for a task that handles its own error.
- **Rotation is under-specified.** Where does the state live: per site, per task, per generic instance? What does a spread of a runtime-length array rotate over? 13's `wait_alarm` third call picks `Closed` only because the second call picked the deadline. Run the same three calls in another order and it prints `deadline`.
- **Union normalization.** `string | string` collapses. `string | Stdout`, a parent and its child from `merged(@plain.receive @stdout.receive)`, is not stated. The round-3 reviewer asked this and it is still open. Arm order and overlap then matter.
- **`type of string` is not yet supported.** `LANGUAGE.md` ("Errors as values") lists "other nominal parents (`type of int64`)" as unsupported, and only `type of any` families are documented. Q10 calls it "the existing family rule". It is a new capability: a child of `string`, plus a `Stdout(s)` constructor from a string. `ticker<Heartbeat>` is a generic parameter on `ticker` that appears in no question item.
- **Permit on a closed channel.** `permit.send(v)` is "cannot return `Unsent`". What happens if the receiver closes the channel after the slot is reserved? Say the value is delivered to the buffer, or the permit's send becomes fallible.
- **Selected send.** No program uses `@ch.send(x)` in a `select`. The claim, `Sent`, and temporary-drop rules (proposal lines 76 and 93) are untested prose. `reserve` replaces them: `select(@out.reserve @stop.receive)` then `permit.send(job)` covers "send or stop" without a prepared send.
- **The "at least one wait" rule** is no longer in the proposal. Only a program comment covers it (10, `length >? 0 or length <? cap`). The signature allows `none` waits, so the rule for variables that may all be `none` belongs in the text.
- **`LANGUAGE.md` vs the "no value" premise.** `LANGUAGE.md`'s `concurrent` keeps task results (`let a = spawn work(21)`). v5's `Task<E>` does not. The proposal's reason for no `.result` is "the value would be lost", and a reader of the guide will ask why `group.spawn` can't keep it.

## Dewy rules

- **Formatting:** only `printl"{x}"` with strings and ints. No `{x:.2f}`. Pass.
- **Environment variables:** none. Pass.
- **Zero-arg calls:** `stop()`, `close()` and `release()` keep `()`. `receive`, `next`, `open`, `length` and `now` drop it. Pass, with one violation: **`@job.wait`**. v5 line 24 lists `Task.wait()` as a void zero-argument call that keeps `()`, and the proposal's line 4 writes `.wait()`. The programs write `@job.wait`. Write `@job.wait()`, or say why the waitable form differs.
- **Shape:** `reserve` and `ticker<T>` are new spellings and need approval items (`reserve` has Q4; `ticker<T>` has none). `@Stdout` is correctly withdrawn.

## Earlier top issues

Round 4:
1. **Deadline starvation (07): partly.** The expired deadline now joins the rotation, but it introduces cross-call hidden state and contradicts "a ready value beats an expired deadline" (Q7, 08).
2. **Selected-send ownership: fixed for the common cases.** `send(timeout=)` and `reserve` replace it. A new gap: direct send's `Canceled` shape (issue 4).
3. **Arm inherits the wait's fact, slot claim: fixed for `reserve`.** The `local.length >? 0` inheritance is stated. The claim rules for a selected send remain unexercised.
4. **01 breaks its own `.next` rule; array fan-in: fixed.** `open` starts true, and `merged(array)` is there.
5. **Single waits inconsistent: fixed.** `tick.next(timeout=)` and `ctrl_c.next(timeout=)` exist, and 13 uses plain `receive`. `task.CtrlCListener`, `launch`, and 12's shadowed `err` are all fixed. The `Canceled` shape of a direct send is still open.

Round 3:
1. **Same-typed sources need minting: partly.** It is the inherent cost, now at its lowest.
2. **`merged` two protocols: fixed.**
3. **Syntactic spin check: fixed.** The arm-based rule covers transitive bindings, no-op writes and one level of helpers.
4. **`none` waits and ownership: mostly fixed.** The "at least one wait" text was dropped.
5. **Rule gaps: fixed**, except the ones above.

## Top 5 remaining issues

1. **The `fair` deadline rotation is stateful and contradicts the one-wait rule.** Fix: drop the cross-call state. An absolute deadline already in the past wins under `fair`, since a deadline is a bound and a reused absolute deadline is the only way to starve. A relative `timeout=` restarts at each call, and `0s` is a poll in which a ready operation wins. Then 08's comment and Q7 are true and 07's `fair_pair` is deterministic. `'listed'` keeps deadline-last.
2. **10's pump cannot tell its two closes apart, and loses jobs on a normal shutdown.** When `inbound` closes, `local` still holds jobs, and the arm `try_send`s into a capacity-1 outbound, so the rest spill. Fix: give `reserve` its own close type (for example `Closed<Reserved<T>>`) so receive-closed and send-closed are separate arms. On inbound-closed the arm drains `local` with waiting sends. On outbound-closed it spills and returns. Cold-read the new spelling. Also say what a held permit does when the channel closes.
3. **`@job.wait` earns no slot as written.** Every program using it loses the value, hits group fail-fast (the `FetchError` arm), or both, and the proposal recommends `race` for each. Either add a real program (worker done, or Ctrl-C, or a deadline, with a `BackgroundTasks` child or an error handled in the task) and spell it `@job.wait()`, or drop it this round. Delete 14c and 17c, and state the fail-fast interaction.
4. **Direct send's cancellation shape contradicts 04, and selected send is dead machinery.** Fix: make `send(timeout=)` return top-level `Canceled` like `receive`, with `Unsent` reasons `Timeout` and `Closed` only. Add a program that reads `.reason` (retry on `Timeout`, stop on `Closed`). Drop selected sends, the claim rules and `Sent<T>`, now that `reserve` covers "send or stop".
5. **Unapproved or unspecified surface under the names.** `type of string` and its constructor are not supported by `LANGUAGE.md`, and `ticker<T>` has no item. Normalization of `string | Stdout` is unstated. `first_ok` doesn't say which failure returns. The "at least one wait" rule is gone. A bound handle as race work (15b) is unstated. Fix: add the approval items and write each rule once. Have the library mint `Stdout` and `Stderr` so 11 and 02 stop declaring them.
