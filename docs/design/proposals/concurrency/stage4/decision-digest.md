# BLUF

- **#118: No to reusing `parallel` for waiting gather.** Approve `[concurrent x in xs work(x)]`; `concurrent` already exists. Serial execution remains legal for `parallel` and can deadlock waiting siblings.
- **#114: Prefer `$parallel_safe` to `$thread_safe`.** Put it before `let`/`const`, on the same line or the line above. Make it a checked callback-forwarding contract; infer requirements per callback parameter.
- Approve lossless `Unsent<P>` failures, including batches; omit `Unpublished<T>`. Approve the Channel migration separately.
- Keep unique SPSC endpoints, bounded MPMC, broadcast Sequencer, atomic-word SeqLock, and registered immutable Snapshot readers.
- Return `Busy` for a nonwaiting MPMC attempt obstructed by a reservation; withdraw the blanket lock-free claim.
- Keep operation-based `select`, ordinary `void` send success, and one cancellation/close/fallback resolution protocol.
- Preserve accepted noncanceling `Mutex.lock`; certify waits by protocol. Bound nightly exploration and calibrate performance targets against equivalent baselines.
- All stage-4 examples below are proposals. Pure naming approvals are separate from ownership, progress, failure, and lifetime approvals; no repository changes are requested here.

## Decision table

- **Reversibility:** “names easy” means before release; “semantics costly” means programs can depend on the guarantee. Design-named types are distinguished in the final inventory.

| # | Decision | Recommendation | New spellings needing approval | Reversibility |
|---|---|---|---|---|
| 1 | Transfer outcomes | One lossless envelope; distinct control outcomes | `Full`, `Empty`, `Unsent<P>`, members | Names easy; ownership costly |
| 2 | SPSC construction | Consuming split; unique queue and ends | `spsc`, `split`, endpoint types | Names easy; uniqueness costly |
| 3 | SPSC operations | Channel verbs; close then drain | Endpoint members | Names easy; lifecycle costly |
| 4 | MPMC | Separate bounded FIFO; contention `Busy` | `mpmc`, queue members | Algorithm replaceable; guarantees costly |
| 5 | Sequencer publication | Atomic batches; explicit subscriber lifecycle | Constructor and publishing members | Names easy; delivery costly |
| 6 | Sequencer reading | Copy then advance; slowest live reader gates | Reader type and members | Views additive later |
| 7 | SeqLock | Atomic-word snapshots; serialized replacement | Constructor and members | Eligibility can broaden |
| 8 | Snapshot management | Register readers; collect explicitly | Constructor and members | Algorithm replaceable |
| 9 | Snapshot access | One scoped pin per reader | Reader/version types and members | Transfer support additive |
| 10 | Deep immutability | Derive internally | None; defer `Freeze` | Public property additive |
| 11 | Selection surface | Operation arms; optional `_` | Contextual `select` grammar | Syntax easy; moves costly |
| 12 | Selection outcomes | Preserve ordinary `void | E` | Arm-binding grammar only | Semantics costly |
| 13 | Selection races | Whole-select cancellation before resolution | None beyond 11 | Semantics costly |
| 14 | Effects/certificates | Semantic wait analysis; no primitive exemptions | None | Internals flexible |
| 15 | Verification/gates | Actual-core exploration; calibrated benchmarks | None | Tools/targets adjustable |
| A | Mutex cancellation | Keep accepted exception | None | Changing it affects callers |
| B | Channel payload failure | Approve lossless migration now | Reuse 1 | Handler migration required |
| 118 | Task-result gather | Reuse `concurrent`, preserve `parallel` | New comprehension grammar; no keyword | Failure/progress costly |
| 114 | Callback forwarding | Checked tag now; per-parameter requirements | `$parallel_safe` | Tag easy; contracts sensitive |

## 1. Failed transfers and control outcomes

- **Recommend:** `void | Unsent<P>` for sends; `.value` recovers exactly the offered payload, `.reason` explains failure. Batches use `Unsent<array<T>>`.
- Example:

  ```dewy
  match tx.try_send(message) {
      failed:Unsent<Message> => save(failed.value)
      _ => {}
  }
  ```

- Try reasons: `Full`/`Closed`, plus MPMC `Busy`; waiting reasons: `Closed`/`Canceled`. Try operations do not observe cancellation.
- Reject flattened receive payload types overlapping control alternatives initially; wrap such payloads in ordinary records.
- Alternative: separate generic error types for each reason.
- Astra/Sol: agree after removing redundant `Unpublished`.
- **Unblocks:** move-only messages and unambiguous outcomes.

## 2. SPSC construction

- **Recommend:** unique, noncopyable unsplit queue and ends; split consumes the queue; each endpoint has one exclusive operator. Positive compile-time capacity is exact, not necessarily stack storage.
- Example: `let [tx rx] = spsc<Message 64>().split()`
- Alternative: shared handle with runtime producer/consumer leases.
- Astra/Sol: agree; round 0 omitted unsplit uniqueness.
- **Unblocks:** safe single-producer specialization.

## 3. SPSC operations

- **Recommend:** `try_send`, `send`, `try_receive`, `receive`, `close`; FIFO. Sender close/drop drains; receiver drop wakes failed senders and destroys unread items once. Waiting operations check established cancellation even when ready.
- Example: `tx.send(message) or_throw` followed by `tx.close()`.
- Alternative: `push`/`pop`/`finish` vocabulary.
- Astra/Sol: agree; bounded bookkeeping excludes arbitrary payload hooks.
- **Unblocks:** familiar bounded transfers and explicit polling.

## 4. MPMC

- **Recommend:** copyable shared handle, positive runtime capacity, linearizable FIFO transfers; concurrent sends may order either way. Explicit close; drain committed items before `Closed`.
- Example: `let queue = mpmc<Message>(64)`; `queue.try_send(message) or_throw`.
- A stalled earlier reservation means `Busy`, not a false `Empty`; bound try retries. Waiting wrappers retry cancellably. No initial lock-free guarantee.
- Alternative: helping algorithm with independently verified stronger progress.
- Astra/Sol: agree; retract round-0 lock freedom and per-producer-only ordering.
- **Unblocks:** truthful nonwaiting queue API.

## 5. Sequencer publication

- **Recommend:** all-or-nothing nonempty batches fitting capacity; serialize publisher admission initially. Prove subscriptions precede publication; require initial subscribers. Reader drop removes its gate; last reader departure closes publication. Last publisher drop closes independently of reader references.
- Example:

  ```dewy
  let events = sequencer<Message 64>()
  let audit = events.subscribe()
  events.publish([first second]) or_throw
  ```

- Success guarantees every live subscriber the batch; no tombstone may erase accepted data. Prepare before reservation; reserved installation cannot fail or call user code.
- Alternative: public reservation/acknowledgment tokens.
- Astra/Sol: agree after tightening commit/drop rules.
- **Unblocks:** safe bounded broadcast batching.

## 6. Sequencer readers

- **Recommend:** `try_next`/`next` return ordinary copied values; advance only after copying. Require `Send`, copyability, and proven simultaneous source-read safety; initially exclude unsupported fallible copy hooks. Copying identity handles still shares identity.
- Example: `let event = audit.next() or_throw`
- Alternative: scoped ring view plus explicit acknowledgment.
- Astra/Sol: agree; retract round-0 promise of universally independent copies.
- **Unblocks:** fan-out without exposed slot lifetimes.

## 7. SeqLock

- **Recommend:** eligible fixed-size atomic-word layouts only. One `try_read` attempt yields value/`Busy`; retrying reads and writer acquisition are cancellation points. Compute replacements privately; install only after validation. Prove memory ordering and counter-wrap safety.
- Example:

  ```dewy
  Position:type = [x:int64 y:int64]
  let position = seqlock(Position[0 0])
  let old = position.try_read() ??<Busy> previous
  ```
- Initially require nonblocking, nonreentrant update callbacks; their external effects are not rolled back.
- Alternative: immutable versions for arbitrary payloads.
- Astra/Sol: agree; narrow callback eligibility and add wrap proof.
- **Unblocks:** coherent cheap reads of small records.

## 8. Snapshot management

- **Recommend:** explicit registration and collection. Publication prepares storage, swaps, and retires; collection/final owner teardown runs destruction. Owner outlives readers; collection never waits for pins. State retention bounds and resource-policy obligations.
- Example: `let reader = state.reader()`; `state.publish(next_config)`; `state.collect()`.
- Alternative: hidden registration and opportunistic reclamation.
- Astra/Sol: agree after keeping destruction off publish initially.
- **Unblocks:** predictable registered reads and reclamation ownership.

## 9. Pinned Snapshot values

- **Recommend:** one scoped `Version<T>` per reader; read-only `.value`. Copying out pays ordinary costs. Initially transfer readers only while unpinned; no cross-task live-version transfer. Scheduler migration must preserve pin identity.
- Example:

  ```dewy
  {
      let version = reader.load()
      inspect(version.value)
  }
  ```

- Alternative: copy `T` on every load.
- Astra/Sol: agree after narrowing transfer promises.
- **Unblocks:** stable nontrivial reads without per-load allocation.

## 10. Deep immutability

- **Recommend:** internal derived predicate; `Sync` and `const` do not establish immutable reachable state. Reject mutable shared handles in published values.
- Example: `let state = snapshot([name="production" retries=3])`
- Alternative: approve public `Freeze` now.
- Astra/Sol: agree to defer that spelling.
- **Unblocks:** safe eligibility without another public property.

## 11. Selection surface

- **Recommend:** channel-operation arms initially; prepare operands once in source order. Only winning sends consume existing sources; losing fresh temporaries clean up. Reject unprovable alias/conditional-move cases. Arm bodies run outside internal locks.
- Example:

  ```dewy
  let answer = select {
      item = inbox.receive() => describe(item)
      _ => "nothing ready"
  } or_throw
  ```

- Alternative: first-class operation values combined with `match`.
- Astra/Sol: agree; fallback needs a validated observation across all arms.
- **Unblocks:** atomic choice without partially executed calls.

## 12. Selection outcomes

- **Recommend:** bind ordinary operation outcomes; successful send remains `void`, with ordinary arm-body value/arity rules.
- Example after B:

  ```dewy
  select {
      sent = outbox.send(message) => match sent {
          failed:Unsent<Message> => save(failed.value)
          _ => {}
      }
  } or_throw
  ```

- Alternative: convert send success to `none` only here.
- Astra/Sol: agree; retract that round-0 conversion.
- **Unblocks:** consistent local failure recovery.

## 13. Selection cancellation and closure

- **Recommend:** established cancellation wins before operand preparation. Later cancellation, transfer, closed-arm resolution, and fallback arbitrate once; winner stands. Cancellation runs no arm. Close readies sends; receives drain first. Remove losing registrations before return.
- Example: `let value = (select { x = inbox.receive() => x }) or_throw`
- Alternative: cancellation as an ordinary competing arm.
- Astra/Sol: agree; one arm resolves, at most one payload transfers.
- **Unblocks:** precise close/cancel/fallback ownership tests.

## 14. Effects and certificates

- **Recommend:** waiting for peer progress is `blocks`, including spins. Nonwaiting attempts require reviewed implementations; `_` alone cannot remove internal lock waits. Allocation, panics, latency, and deadlock freedom are separate obligations. Extend existing demanded analysis and protocol certificates, including ranked services accepted in #72.
- Example: `poll = () => queue.try_receive()` can exclude `blocks` only with a proved nonwaiting core.
- Alternative: exempt all “lock-free” primitives from wait analysis.
- Astra/Sol: agree; retract blanket syscall exclusion.
- **Unblocks:** honest hot-path rows and `$no_deadlocks`.

## 15. Verification and performance

- **Recommend:** actual-core bounded exploration, capacities 1–3, forced wrap, reservation stalls, ownership/close/cancel/pin races; timeout fails completion. Initial nightly budget: 30 minutes, at most four workers. Finite exploration supplies bounded evidence, not an unbounded theorem.
- Example: `tx.try_send(7) or_throw`; `let value = rx.try_receive() or_throw`; `$runtime_assert(value =? 7)`.
- Match SPSC/Rigtorp, MPMC/Crossbeam, broadcast/Disruptor, channel/Go semantics. Calibrate throughput and tail targets; old 0.9×/1.25× ratios remain candidates.
- Alternative: randomized stress alone.
- Astra/Sol: agree after staging numeric gates.
- **Unblocks:** reviewable implementation acceptance.

## A. Mutex cancellation — already answered

- **Recommend:** preserve #63: `lock` does not cancel; `lock_all` may. Level triggering applies to designated cancellation points.
- Example: `let payload = @(m.lock())`; `let [a b] = @(lock_all(m n)) or_throw`.
- Alternative: reopen `lock`'s result contract.
- Astra/Sol: agree; my round-0 flag was stale.
- **Unblocks:** consistent implementation without another approval.

## B. Failed Channel sends

- **Recommend:** explicitly approve `Channel.send` → `void | Unsent<T>` alongside expert sends. Typed catches stay flat: `??<Canceled>` does not catch an envelope; inspect `.reason`. Preserve #80 causal-child-error reporting for canceled send failures.
- Example: `match out.send(message) { failed:Unsent<Message> => save(failed.value) _ => {} }`
- Alternative: retain current `void | Closed | Canceled`; reject move-only selected sends meanwhile.
- Astra/Sol: agree to decide migration now; round 0 deferred it.
- **Unblocks:** coherent recovery for selected move-only payloads.

## #118. Can gathering reuse `parallel`?

- **Recommend: no under its accepted contract; yes to reusing existing `concurrent`.**
- Example of the proposed reuse and its failure:

  ```dewy
  let ch = channel<int>(1)
  step = (i:int) => if i =? 0 (ch.receive() or_throw) else {
      ch.send(42) or_throw
      0
  }
  let proposed_reuse = [parallel i in [0..2) step(i)]  # rejected today
  # Relaxing the check permits inline iteration 0 to wait forever for 1.
  let results = [concurrent i in [0..2) step(i)] or_throw
  ```

- Keep `[parallel x in xs x*x]` for independent compute. Gather evaluates a finite source once, returns ordered results, cancels siblings on first child exception, and joins cleanup. For child `T | E`: `array<T> | E | Canceled | OutOfMemory`. Admission cannot wait behind children needing unadmitted siblings.
- Renaming gather to `parallel` would replace per-item exception values with fail-fast group errors, add task-admission failure, and require concurrency support on targets currently using serial fallback. These are semantic changes, not scheduler optimizations.
- Preserve errors per item with `[concurrent x in xs [value=work(x)]]`; outer cancellation/admission can still fail.
- Alternative: redefine **all** `parallel` to guarantee structured concurrency. Coherent, but loses permission for arbitrary serial fallback and changes failure/admission/target contracts. Effect-based dual meanings make those contracts change with helper implementations.
- Astra/Sol: agree; no round-0 position existed on this later question.
- **Unblocks:** many ordered task results without Channel/Mutex scaffolding.

## #114. Tag spelling and `let`/`const`

- **Recommend:** checked `$parallel_safe` as the immediate explicit forwarding mechanism; infer which callback parameters acquire obligations. It verifies supplied callbacks' writes, captures, transfers, and nonwaiting invocation; it never asserts safety by trust.
- Example:

  ```dewy
  $parallel_safe myfn = () => 42
  $parallel_safe const apply = (xs f) => [parallel x in xs f(x)]
  $parallel_safe let local_apply = (xs f) => [parallel x in xs f(x)]
  $parallel_safe
  const apply_again = (xs f) => [parallel x in xs f(x)]
  square = (x:int) => x*x
  let ys = apply([1 2 3] @square)
  ```

- Order: **tags → optional `let`/`const` → name → optional type → `=` → function**. Tag applies to one declaration; no callback means no extra obligation. Serial-only callback parameters stay unrestricted.
- Initial direct-call restriction may remain until callable metadata carries requirements through partial application/indirection; later assignments must preserve them. `& no blocks` alone does not prove race or transfer safety.
- Alternative: automatic forwarding inference without any required tag.
- Astra/Sol: agree on spelling/meaning; Astra prefers inference first and a redundant optional tag. I favor the requested explicit bridge now, with automatic forwarding later.
- **Unblocks:** checked higher-order parallel helpers without Sloppy's `@parallel`.

## Spelling approvals — complete inventory

- **Pure spelling choices:** constructors/type/member names below and `$parallel_safe` versus alternatives. **Separate semantic approvals:** transfer ownership/error shape; close/order/progress; pin lifetime/immutability; selection evaluation/races; gather failure policy; callback forwarding. Renaming does not settle these.
- **Already design-named types; approve concrete APIs, not a second type vocabulary:** `Spsc<T N>`, `Mpmc<T>`, `Sequencer<T N>`, `SeqLock<T>`, `Snapshot<T>`.
- **New outcome/handle types:** `Full`, `Empty`, `Unsent<P>` (`reason`, `value`); `SpscSender<T N>`, `SpscReceiver<T N>`, `SequenceReader<T N>`, `SnapshotReader<T>`, `Version<T>` (`value`).
- **Constructors:** `spsc`, `mpmc`, `sequencer`, `seqlock`, `snapshot`.
- **Members, including reused words on new receivers:** SPSC queue `split`; SPSC ends/MPMC `try_send`, `send`, `try_receive`, `receive`, `close`; Sequencer `subscribe`, `try_publish`, `publish`, `close`; SequenceReader `try_next`, `next`; SeqLock `try_read`, `read`, `store`, `update`; Snapshot `reader`, `publish`, `collect`; SnapshotReader `load`.
- **Grammar/metatag:** contextual `select`, operation-arm binding and `_` readiness fallback; `[concurrent …]` comprehension; `$parallel_safe` with both placements. `concurrent` is an existing keyword; `select` was design-named but its concrete grammar is pending.
- **Deferred/rejected names:** `Unpublished<T>`, `Freeze`, `$parallel`, `$thread_safe`, new effect atoms `parallel_safe`/`thread_safe`, public `claim`/`ack`, and queue aliases `push`/`pop`/`finish`. None is approved by this digest.
- **Existing names reused:** `Busy`, `Closed`, `Canceled`, `OutOfMemory`, `Send`, `Sync`, `Channel`, `Mutex`, `lock_all`, `parallel`, `concurrent`, existing effect rows/settings. Application helper/type names in examples are illustrative locals, not library proposals.
