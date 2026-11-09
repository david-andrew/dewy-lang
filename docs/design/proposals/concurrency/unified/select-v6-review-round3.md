# Regrade: `select` by type, v6 round 3

Reviewed `proposal-v6-select-r3.md` and all 13 programs in `programs-r3/` against docs/LANGUAGE.md and concurrency proposal v5. Grades are strict: 5 means no one would think "it would be nice if the language let me…". The comparison is the shortest correct Go, Rust (tokio::select!), asyncio, TypeScript and Swift version. No program was compiled; this is a paper review.

## Grades (1–5)

| # | Program | Obvious | Discoverable | Concise | Safe | Complete | Floor |
|---|---|---|---|---|---|---|---|
| 01 | chat_command (`merged` + `.next`) | 4 | 4 | 4 | 4 | 4 | 4 |
| 02 | stdout_stderr (branded pipes) | 3 | 3 | 3 | 4 | 3 | 3 |
| 03 | two_tickers | 3 | 4 | 3 | 5 | 4 | 3 |
| 04 | selected_send (move-only job) | 4 | 4 | 4 | 4 | 4 | 4 |
| 05 | ctrl_c | 4 | 4 | 4 | 4 | 3 | 3 |
| 06 | merge / generic `forward` | 5 | 4 | 5 | 4 | 4 | 4 |
| 07 | worker_pool (`listed`, deadline) | 4 | 3 | 4 | 4 | 3 | 3 |
| 08 | single_timeout | 4 | 3 | 4 | 5 | 4 | 3 |
| 09 | drain_all | 5 | 4 | 5 | 5 | 4 | 4 |
| 10 | backpressure (`none` waits) | 3 | 3 | 3 | 3 | 3 | 3 |
| 11 | library_types | 4 | 4 | 4 | 3 | 3 | 3 |
| 12 | overlap_error | 4 | 4 | 3 | 5 | 3 | 3 |
| 13 | union_payload | 4 | 3 | 4 | 4 | 4 | 3 |

**Floor: 3.** Eight of 13 programs have a 3 somewhere. The design is not ready for David at "all 5s".

## Why each grade is below 5

- **01:** Two protocols for one thing. Iteration uses `loop item in merged(...)`, with no overlap rule. Adding a timeout means `.open` plus `.next`, which does have the overlap rule. A program that works as iteration can become a compile error when a timeout is added. Go needs flags and nil channels, about 25 lines. Tokio needs a `biased` loop with `else`. Dewy is shorter than both, so a 4.
- **01 safety:** `.next` on an empty set is "an obligation failure", but nothing links `loop inbox.open` to that obligation. Today it is a convention, not a fact the checker holds.
- **02:** The reader needs a `wrap:(string:>T)` parameter and a call-site lambda `(s) => Stdout(s)`. Go, Tokio and Swift need no wrapper to tell two string channels apart. The reader sends one chunk and closes, so it is not a real pipe reader. `read_chunk` can never return `Ended` or `Canceled`, so the `<Ended>` arm never runs.
- **02 fix:** Where a parameter is `(string:>T)` and `T` is a child of `string`, let the type name stand for its constructor: `read_pipe(1 stdout Stdout)`. The proposal says a type name is not a function value, but the expected function type here picks one constructor, so the exception is narrow. Alternatively the process library mints `Stdout` and `Stderr`, and users never see this.
- **03:** Two tickers need two minted types (`Heartbeat`, `Sweep`) before they can share a `select`. In Tokio, Go and Swift, `a.tick()` and `b.tick()` need nothing. Two default tickers clash, which is an error on the most obvious program. Also, the loop exits after 5 one-second beats, so the 10 s sweep never fires and the `<Sweep>` arm never runs.
- **03 fix:** Make `ticker<Heartbeat>` mint inline when the name is unbound, or document `Heartbeat:type = type of Tick` as the one-line idiom. Make the clash error say exactly this.
- **04:** Correct, and the best treatment of ownership. It is only a 4 because the demo never reaches the `Timeout` arm: capacity 1, so the send always succeeds and prints `sent`. A temporary in `@worker.send(Job[7])` is lost on `Timeout`, because the arm cannot name it.
- **05:** `serve = (lines:Channel<Line> ctrl_c)` has an untyped parameter. v5 says the listener type needs no user-facing name, so a helper cannot annotate it. That is a missing capability, so a 3 on complete.
- **06:** The best program. `forward` with two `Channel<string>` works. Remaining doubt: `out.close()` is skipped when `or_throw` exits early, so a reader of `out` hangs unless cancellation reaches it. Also see the `Unsent` variance question below.
- **07:** It is not stated what wins when the deadline has expired and a receive is also ready. `priority='listed'` lists arguments, and `timeout=` is not one. In this program the answer decides whether `total` is complete. The `stop` channel is never sent to, so `listed` is never exercised.
- **08:** `select` with one wait is the only spelling for "receive with a deadline". Nobody looks in `select` for that. `priority='fair'` on a single wait is meaningless noise and should be a warning, not a documented example. Python's `wait_for` and Go's `time.After` are one line each.
- **08 fix:** If `replies.receive(timeout=2s)` exists, use it here. If not, add it with the same result union as `select`.
- **09:** Near-perfect. Not 5 on discoverable: a Go or Rust migrant types `loop { select ... }` first and meets the spin error. The message does point to `merged`, which helps.
- **10:** Matches Go's nil-channel trick plus type obligations. Tokio's per-branch `if` precondition is shorter. Problems are listed under issue 4 below. Also `return failed` drops everything else still in `local`.
- **11:** Nearly a copy of 02 and 12. `argv[0]` is an unproven index (needs `argv.length >? 0`), which breaks safe-by-default. A factory that sends before returning also forces `Unsent<Stdout>` into its result for no reason.
- **12:** The file contains no failing `select`; the clash exists only in comments. The fix costs minting two types and wrapping every sender. Complete: 3. It does not mention that a `merged` of `Channel<string>` and `Channel<Stderr>` is legal and yields a hazardous payload union.
- **13:** `Closed<Event>` not splitting is sound but new to every reader. `Late:type = type of any` as the cure for a `Timeout` payload is obscure. Readers see `or_throw<Closed<Event>>` beside `_:Closed<Event>` and wonder how that differs from `or_throw<Closed>`.

## Soundness: do the matches cover exactly the rule's outcomes?

- **Complete and non-redundant in all 13.** I checked each `match` against the union rule: 01, 03, 04, 05, 07, 08, 10 and 13 cover `R` plus `Timeout` where a timeout is present. After `or_throw<Canceled>`, `Canceled` is gone.
- **Arms that can never run, by construction of the demo:** 01 `<Timeout>` and the two `Closed` arms are racy and prefilled. 02 `<Ended>`, 03 `<Sweep>`, 04 `<Timeout>` and 07 `Stop` never fire. They are type-correct, but the demos do not exercise what they claim to show.
- **Contradiction with v5:** v5 (line ~191) says that after `catch_ctrl_c` ends, the listener's `.next` gives `Closed`. Program 05 and the proposal say `@ctrl_c.next` has no `Closed` because the listener is "borrowed for the callback and cannot be stored past it". That requires an escape rule v5 does not have. State which wins.
- **Nothing in 06 and 13 declares the `Unsent<int64>` and `Unsent<string>` their bodies forward.** `nums.send(one) or_throw` forwards `Unsent<int64>`, but `main` declares `Unsent<int64 | string>`. It only compiles if `Unsent<T>` is covariant in `T`. Same in 13 (`Unsent<Event>` against string and int64 sends). The proposal does not say.
- **Union of parent and child.** `merged(@a.receive @b.receive)` with `Channel<string>` and `Channel<Stdout>` gives the payload `string | Stdout`. If that normalizes to `string`, the child is silently lost. If it does not, an arm `s:string` placed before `o:Stdout` makes the second unreachable, which the match rules catch. Say which.
- **Ownership of a losing send of a temporary.** The proposal covers variables only. For `@ch.send(Job[7])`, the value is built once. On `Timeout` or when another operation wins, is the temporary dropped, with its `$__drop__` hook, at the end of the statement? Say so.
- **Per-arm move state.** After 04's match, `job` is live in the `Timeout` arm, moved in the `Sent` and `Unsent` arms. The proposal should say that the post-match state is "maybe moved" and later use is an error. It should also say a copyable payload never moves.

## Ambiguities in the proposal

- **Spin check.** The rule is "the wait expressions do not mention a variable the loop writes". It is syntactic. False positive: `loop n <? 3 { select(@a.receive @b.receive) …Closed => {} }` terminates but is rejected. False negative: `select(@a.receive if flag @b.receive else none)` where the loop writes `flag` but the `Closed` arm never changes it still spins.
- **Timeout versus ready operation.** Both ready at once: which wins, under `fair` and under `listed`? It is unspecified (see 07).
- **`merged` fairness.** No `priority=` on `merged`. Fairness is not stated, so a program cannot say "stop first".
- **`loop item in X or_throw {`.** `or_throw` after an iterable is not in LANGUAGE.md. The proposal needs to name this as new surface or give the existing form.
- **`_:Closed<Job>`.** LANGUAGE.md documents `_` as a catch-all and `<T>` for a binding-free arm. `_:T` with a binder is not documented.
- **Mixed spellings.** The same `match` writes `<Timeout>` and `_:Closed<Job>` for two unit outcomes (04, 05, 10). Pick one spelling.
- **`merged` handle.** `let inbox = merged(...)` is mutated by `.next`. The proposal does not say whether the handle is movable and whether the channels it borrows can be closed while it is alive (01 does exactly this).
- **Generic per-instance check.** "Inferred and checked at the instance, like an effect": the error location is unspecified. It should name the instance and the match that needs `A` versus `B`.
- **At least one wait.** "Present" is a compile-time proof, but `sending`/`incoming` are variables. The proposal does not say how the facts (`local.length >? 0`) travel with the variable to the `select`.

## Dewy rules from section 3

- **Formatting.** No program formats numbers. `printl"{x}"` with strings and ints is the only use. No `{x:.2f}` anywhere. Pass.
- **Zero-arg calls.** All void ones keep `()` (`heart.stop()`, `out.close()`, `watch()`, `release = ():>void`). All value-returning ones drop it (`outbound.receive`, `inbox.next`, `inbox.open`, `tick.next`, `now`). Pass.
- **Environment variables.** None. Pass.
- **Not covered by those rules:** 10 uses `let cap:int64 = 32` at module level. `let` there is mutable, so "cap positive" cannot be proved. It must be `const cap = 32`. Also `argv[0]` in 11 and `id * id` in 07 are overflow or index obligations that this safe-by-default language would reject unguarded.

## Top 5 issues, most important first

1. **Same-typed sources need nominal minting and a wrapper at every send site (02, 03, 11, 12).** This is the one place Go, Tokio and Swift are clearly shorter. Fix: the process library mints `Stdout`, `Stderr` and similar so users never write them; let a child-of-`string` type name pass where `(string:>T)` is expected; make the clash error show the exact two-line fix for tickers (`Heartbeat:type = type of any`).
2. **`merged` has two protocols with different rules, and a hole in each.** Fix: apply no overlap rule to `.next`, or apply one to both. Define `inbox.open` as the fact that proves `.next` is on a non-empty set. State fairness (and add `priority=`), the ownership of the handle, and how parent and child payloads normalize. Name `loop … or_throw` as new surface if it is.
3. **The spin check is syntactic and can be wrong both ways.** Fix: make it arm-based. A `Closed<T>` arm that can reach the backedge must write a variable the select's waits mention, or exit. Say that this is the whole rule. Do not let the loop's other writes count.
4. **`none` waits (10) and ownership (04, 10) are under-specified.** Fix: use `const cap`. Say that "at least one wait present" is a proof obligation over the conditions that built each `none` and that the facts travel with the variable. Define how a send of `local[0]` consumes the slot for a move-only element. Make 10 flush `local` on `Unsent` instead of dropping it. Say what a losing send of a temporary does.
5. **Rule gaps that make programs ambiguous.** Fix: state the winner when a deadline and a ready operation tie, `Unsent<T>` covariance (06, 13), a user-nameable listener type for helpers like 05's `serve`, the `Closed`-after-scope contradiction with v5, and one spelling for unit arms (`<Closed<Job>>`, not `_:Closed<Job>`).
