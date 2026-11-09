# Concurrency design, round 1 (independent pass)

## BLUF

- Keep the two lanes and adopt `[concurrent x in xs work(x)]`: `parallel` permits sequential execution; `concurrent` promises independently progressing tasks. Effects can select an implementation, but should not silently select different cancellation, failure, and admission semantics.
- Infer the callback requirements in #114. A function-wide tag is an optional explicit contract, not the permission that makes code safe. If David wants that tag, prefer `$parallel_safe` to `$parallel` or `$thread_safe`, and put it **before** `let`/`const`, on either line.
- Keep lossless failed transfers; use one `Unsent<P>` envelope, including `Unsent<array<T>>` for a batch. Do not add `Unpublished<T>` without a distinct need.
- Keep consuming SPSC split and channel-like verbs. Tighten MPMC ordering and progress: a reserved-but-unpublished slot can stall peers; CAS alone does not establish lock freedom. Reuse `Busy` for a nonwaiting contention result.
- Keep atomic batch publication, but forbid silent tombstone loss after acceptance. Specify subscriber removal, registration closure, and publication-versus-close ordering.
- Keep atomic-word seqlock snapshots and registered Snapshot readers. Require a real counter-wrap argument, explicit reclamation ownership, and bounded storage proofs where strict settings require them.
- Keep contextual `select` and `_`. Preserve ordinary `void | E` outcomes instead of inventing send-success `none`; define ownership and a real linearization point for commit, close, cancellation, and fallback.
- `Mutex.lock` is **already an accepted non-cancellation exception** (#63, accepted 10-26). Preserve it. `Channel.send` payload recovery is still a substantive design question; settle it before extending send selection to move-only payloads.
- Keep nightly exploration of the implementation and matched benchmarks. Bounded exploration is evidence, not an unbounded proof or a substitute for `$bulletproof` obligations.

## Review contract

- **Scope/acceptance:** independently review the round-0 decisions 1–15, both flags, #118 and #114; distinguish accepted rules, current code, and new recommendations; list candidate spellings. All 19 sections follow below.
- **Owned file:** this scratch document only. **Non-goals:** implementation, repository edits, commits, a new scheduler, a new general proof system, or running performance experiments. **Budget:** one focused read-only session.
- **Authority:** David's 10-26 answers supersede older status prose. In particular #63 accepts noncanceling `lock`, #65 the certificate spellings, #72 layered services, #80 preservation of a child's causal error, and #110 the provisional task-backend setting. The opening ordinary-runtime-check language in `effects.md` predates the ledger's no-traps decision.
- **Evidence:** source inspected at HEAD `42a7ce9b1`; no compiler or benchmark runs. Examples of stage-4 APIs, collection, and tags below are proposed Dewy, not claims of current acceptance. Application helper names in examples are illustrative local functions, not proposed library members.

## 1. `Full`, `Empty`, and failed-transfer payloads — improve

- **Recommendation:** approve `Full`, `Empty`, and a lossless `Unsent<P>` with `reason` and `value`; reuse it for batches instead of adding `Unpublished<T>`.
- **Dewy example:**

  ```dewy
  match tx.try_send(message) {
      failed:Unsent<Message> => save_for_later(failed.value)
      _ => {}
  }
  # A failed batch returns Unsent<array<Message>>, with the entire batch.
  ```

- `try_send` can fail with `Full` or `Closed`; an MPMC contention attempt can additionally report `Busy` (decision 4). A waiting send reports `Closed` or `Canceled`, never ordinary transient `Full` to the caller. Preserve these operation-specific reason facts even if the envelope uses a wider common representation.
- Treat `Full` and `Empty` as exception outcomes, like existing `Busy`, so callers handle or explicitly discard them. For an initial flattened `T | Empty | Closed` API, reject a `T` that itself overlaps its control alternatives; a record such as `[value:T]` removes the ambiguity. This explicit eligibility restriction needs approval; nested error fields are allowed. Do not pretend choosing names other than `none` solves all sentinel collisions.
- Failure returns precisely the offered owned value, with no clone, hidden drop, or partial acceptance. Handling the envelope may deliberately drop it; “lossless” means recovery is available, not that the language forbids disposal.
- An envelope containing `Canceled` is **not** itself the `Canceled` alternative. `??<Canceled>` will not automatically catch `Unsent<P>`; document explicit inspection of `reason`, and retain the scope's cancellation flag. Do not invent automatic nested-error matching.
- **Alternatives considered:** `Unpublished<T>` — redundant if its sole distinction is an array payload.
- **Alternatives considered:** `Full<T>`/`Closed<T>`/`Canceled<T>` — pollutes established error identities and still needs deliberate error matching.
- **New spellings needing approval:** `Full`, `Empty`, `Unsent<P>`, its `.reason` and `.value`; `Unpublished<T>` is explicitly not recommended. `Busy`, `Closed`, `Canceled` already exist.
- **What it unblocks:** move-only transfers and explicit retry/storage without payload loss.
- **Reversibility:** envelope names easy before release; ownership and error-matching semantics expensive afterward.
- **Where I disagree with round 0 and why:** one envelope suffices; the proposal needs to explain that wrapping cancellation changes catch behavior and that `try`/waiting failure sets differ.

## 2. SPSC construction and consuming split — agree, tighten uniqueness

- **Recommendation:** keep `spsc<T N>()`, consuming `.split()`, and noncopyable sender/receiver endpoints; require exclusive use of each endpoint, not merely a `not Sync` label.
- **Dewy example:**

  ```dewy
  let q = spsc<Message 64>()
  let [tx rx] = q.split()
  # q is consumed; each endpoint can move to one task.
  ```

- An unsplit queue must also be noncopyable, or copying it before consuming either copy defeats the split guarantee. Reject aliases, closure copies, or two live uses that could operate one endpoint concurrently. Permit liveness-proven moves.
- `N >? 0` is a caller proof obligation. Capacity means exactly `N` available payload slots; internal padding/rounding does not change it. Construction must account for size arithmetic and the current allocation policy.
- Compile-time `N` is useful for specialization, but does **not** promise inline or stack storage: movable endpoints require a stable shared backing allocation or a proven enclosing lifetime.
- **Alternatives considered:** runtime endpoint leases — safe if checked, but unnecessary hot-path state and a weaker API.
- **Alternatives considered:** runtime-only capacity — useful later as an additional construction form; not necessary to undo the existing static-size direction.
- **New spellings needing approval:** `spsc<T N>()`, `.split()`, `SpscSender<T N>`, `SpscReceiver<T N>`; confirm the concrete API of already design-named `Spsc<T N>`.
- **What it unblocks:** a statically single-producer/single-consumer specialization.
- **Reversibility:** names easy; unique endpoint ownership fundamental.
- **Where I disagree with round 0 and why:** the unsplit queue's copyability and the backing-storage lifetime must be explicit; endpoint `Send`/`Sync` facts alone do not establish either.

## 3. SPSC verbs and closure — agree

- **Recommendation:** use `.try_send`, `.send`, `.try_receive`, `.receive`, `.close`, with FIFO draining and separate cancellation behavior for try versus waiting operations.
- **Dewy example:**

  ```dewy
  tx.send(message) or_throw
  tx.close()
  let last = rx.receive() or_throw
  ```

- A sender close/drop prevents future sends; accepted items drain before `Closed`. Receiver drop makes future sends fail with their payload, wakes waiters, and eventually destroys unread queued items exactly once.
- A waiting operation observes already-established cancellation even when ready. Try operations neither observe nor clear it. Full/empty observations are transient outcomes, not durable capacity facts usable without synchronization.
- “Wait-free” may describe the bounded ring bookkeeping for eligible payloads; whole-call guarantees include payload preparation, copy/drop hooks, and endpoint teardown. Do not charge arbitrary destruction to a supposedly bounded receive.
- **Alternatives considered:** `push`/`pop`/`finish` — adds vocabulary without improving transfer semantics.
- **Alternatives considered:** explicit-close-only endpoints — risks stranded waiters when the sole peer leaves scope.
- **New spellings needing approval:** `.try_send`, `.try_receive`, and the five members on these new endpoint types; `.send`, `.receive`, `.close` reuse existing channel vocabulary. Rejected aliases: `push`, `pop`, `finish` in this API.
- **What it unblocks:** familiar expert transfers with an explicit nonwaiting path.
- **Reversibility:** names easy; drain/drop behavior costly.
- **Where I disagree with round 0 and why:** no surface disagreement; qualify the whole-operation progress claim and specify cleanup of unread values after receiver loss.

## 4. MPMC — improve progress and ordering contract

- **Recommendation:** keep a separate bounded `Mpmc<T>` expert API, require linearizable FIFO transfers, and allow `Busy` on nonwaiting contention rather than promise lock freedom from a per-slot CAS design.
- **Dewy example:**

  ```dewy
  match queue.try_receive() {
      <Busy> => use_cached_result()
      <Empty> => no_work_yet()
      <Closed> => stop()
      value:Message => consume(value)
  }
  ```

- Concrete problem: producer A reserves the next slot and pauses before publishing; producer B publishes a later slot and returns. A consumer cannot truthfully report `Empty` after B's completed send, cannot preserve FIFO by skipping A, and cannot meet `no blocks` by waiting for A. Return `Busy`, or implement a genuinely helping algorithm with a proved contract.
- Crossbeam's actual source separates reservation from publication and contains stamp-wait loops. My conclusion is that directly porting that algorithm cannot establish round 0's stronger nonwaiting contract. [Crossbeam ArrayQueue source](https://docs.rs/crossbeam-queue/latest/src/crossbeam_queue/array_queue.rs.html)
- For the first implementation, bound contention retries and return `Busy` without consuming the payload. Strong CAS can avoid spurious-failure ambiguity. Reuse decision 1's envelope with `reason=Busy` for sends. Blocking wrappers retry/park and expose cancellation.
- Concurrent sends may linearize in either order; a send completed before another begins must retain that order. Per-producer FIFO alone is unnecessarily weaker and complicates the meaning of readiness and selection.
- Keep copyable `Send`/`Sync` handles when `T: Send`; explicit `.close()` while handles remain. Close must participate in the commit protocol, so a stalled reservation cannot make a receive announce final `Closed` before a committed item appears.
- **Alternatives considered:** add try operations only to `Channel` — worthwhile ordinary convenience later, but does not establish the expert representation/progress contract.
- **Alternatives considered:** call a try-locked ring “lock-free” — incorrect; it can be nonwaiting with `Busy`, but its useful transfer progress still depends on its holder.
- **New spellings needing approval:** `mpmc<T>(capacity)`, the five queue members on `Mpmc<T>`; confirm `Mpmc<T>`'s concrete API. `Busy` is reused with new documented outcomes.
- **What it unblocks:** truthful `no blocks`, stable ordering, and a benchmark with explicit contention semantics.
- **Reversibility:** implementation can improve; weakening shipped progress/order claims is hard.
- **Where I disagree with round 0 and why:** its lock-free assertion is unsupported, and “FIFO per producer” underspecifies a queue otherwise discussed in linearization terms.

## 5. Sequencer publishing — improve atomicity and lifecycle

- **Recommendation:** keep whole-batch `.try_publish`/`.publish`; make successful publication irrevocable for every active subscriber, with no silent loss through internal tombstones.
- **Dewy example:**

  ```dewy
  let events = sequencer<Message 64>()
  let audit = events.subscribe()
  let strategy = events.subscribe()
  events.publish([first second]) or_throw
  events.close()
  ```

- Concurrent writers are allowed. A simple initial implementation can serialize publisher admission: try returns `Busy` before reservation; waiting publish waits cancellably. Prepare values before admission; the interval from reservation through commit must be finite, nonallocating, nonfailing, and free of user callbacks. This is not a lock-free claim.
- Publish success means the complete batch is committed and readable in order; physical wrap may occupy two spans. “Contiguous” means sequence positions, not necessarily contiguous addresses.
- Before commit, cancellation/close wins or publication wins through one arbitration protocol. Failure returns the entire batch. After commit, cancellation cannot turn success into failure. Tombstones may repair an unpublished reservation only if ownership is returned and **none** of that batch became visible; they may not erase accepted data.
- Subscription is a setup operation: require proof it precedes publication, initially through exclusive setup use/alias analysis. Unknown ordering is a diagnostic, not a hidden assertion. Do not add a surprise registration error or runtime flag that callers cannot prove.
- Dropping a reader removes its gate and wakes publishers; it deliberately abandons that subscription's unread values. Require at least one subscriber at initial publication; after the last reader leaves, publication fails `Closed`. Explicit close and last publisher drop close the stream, but reader references must not count as publisher ownership.
- **Alternatives considered:** public `.claim`/`.ack` — valuable for zero-copy later; prematurely exposes reservation cancellation and reuse lifetimes.
- **Alternatives considered:** returning success before preceding reservations publish — introduces a hidden peer-progress dependency and weakens the advertised commit.
- **New spellings needing approval:** `sequencer<T N>()`, `.subscribe`, `.try_publish`, `.publish`, `.close`; confirm `Sequencer<T N>`. `.claim`/`.ack` deferred; no public sequence-number spelling proposed.
- **What it unblocks:** bounded broadcast batches with a complete failure/closure contract.
- **Reversibility:** names and writer serialization easy; accepted-data delivery semantics hard.
- **Where I disagree with round 0 and why:** “complete or tombstone on internal failure” is not enough to guarantee all-or-nothing delivery; registration and subscriber disappearance also need enforceable rules.

## 6. Sequencer readers — agree, tighten copy requirements

- **Recommendation:** keep `.try_next`/`.next` returning a value and advancing only after a successful copy, without public acknowledgment tokens.
- **Dewy example:**

  ```dewy
  let event = audit.next() or_throw
  record(event)
  ```

- Each live subscriber receives every committed item in sequence order; reading one does not dequeue it for another. `.try_next` returns `Empty` only when no committed next item exists, and `Closed` only after draining.
- Concurrent readers copy from the **same** ring value. `Send` plus mere copyability is insufficient for arbitrary copy hooks. Require safe concurrent read/copy access (`Sync` or an equivalent compiler-proven rule), with copy effects visible. A failed copy must retain the cursor so the item is not silently skipped; initially reject layouts with unsupported fallible copy hooks.
- Copies preserve Dewy's ordinary semantics: ordinary values are independent, but copying a `Mutex` or another identity handle still shares that identity. Do not promise deep independence for every copyable `T`.
- The reader is noncopyable, exclusively operated, and moveable between tasks only with its cursor and lifetime intact. Backpressure is the slowest **live** subscriber.
- **Alternatives considered:** ring views and `.ack` — avoids copies but changes the programming and reclamation contract; additive later.
- **Alternatives considered:** work sharing — use MPMC; it is a different capability.
- **New spellings needing approval:** `SequenceReader<T N>`, `.try_next`, `.next`; acknowledgment and sequence-access members deferred.
- **What it unblocks:** safe fan-out without exposed slot lifetimes.
- **Reversibility:** names easy; broadcast and copy semantics costly.
- **Where I disagree with round 0 and why:** `T: Send` and copyable does not alone justify simultaneous source-side copying, and copied identity handles are not deeply independent values.

## 7. SeqLock — agree with explicit representation and wrap obligations

- **Recommendation:** keep snapshot-by-value reads, atomic-word eligible layouts, and serialized whole-value writers; prove validation and counter reuse rather than relying on “64 bits will never wrap.”
- **Dewy example:**

  ```dewy
  Position:type = [x:int64 y:int64]
  let position = seqlock(Position[0 0])
  match position.try_read() {
      <Busy> => use_previous_position()
      value => draw_position(value)
  }
  ```

- `.try_read` performs one validation attempt and returns `Busy`; `.read` retries and is a cancellable wait. `.store` and `.update` wait cancellably for writer serialization; no published mutation on cancellation before commit.
- Keep the prior complete version readable while `.update(f)` computes a private replacement under writer serialization. Enter the odd/write phase only for the prepared atomic-word installation. Callback failure leaves the old version; callback side effects are not rolled back. A cancellation check before installation may likewise leave external callback effects intact.
- Initially require `.update` callbacks to be nonblocking and reject reentrant writer acquisition. Include their other effects and hidden hooks. Do not let a callback hold the sequence odd while it calls the reader that is waiting for evenness.
- Atomic payload words eliminate ordinary data races; they do not by themselves prove a coherent snapshot. Specify fences, validation, padding/representation validity, and no interpretation of a torn tentative value before validation.
- A paused reader can span a complete version-counter cycle. Require a wrap-safe design or an established bound preventing that cycle during a read attempt. An elapsed-time plausibility claim does not pass `$bulletproof`; if proof is unavailable, reject that strict instantiation or use a verified fallback with honest effects.
- **Alternatives considered:** ordinary non-atomic memcpy followed by validation — unsafe; failed validation does not erase a data race.
- **Alternatives considered:** immutable double buffers for arbitrary `T` — possible, but a different reclamation/latency design already served by Snapshot.
- **New spellings needing approval:** `seqlock(value)`, `.try_read`, `.read`, `.store`, `.update` on design-named `SeqLock<T>`; reuse `Busy`. No public atomic-copyable trait proposed.
- **What it unblocks:** safe, allocation-free attempts for small read-mostly records.
- **Reversibility:** eligibility can expand; coherent-value and cancellation promises costly.
- **Where I disagree with round 0 and why:** its wrap and callback phase contracts are incomplete; starting with arbitrary waiting callbacks under writer serialization expands the deadlock surface unnecessarily.

## 8. Snapshot registration, publication, reclamation — improve separation

- **Recommendation:** keep explicit `.reader()` and `.collect()`; make `.publish()` prepare and swap, with payload destruction concentrated in collection/final teardown.
- **Dewy example:**

  ```dewy
  let state = snapshot(initial_config)
  let reader = state.reader()
  state.publish(next_config)
  state.collect()
  ```

- Registration acquires pin storage before hot use; publication acquires new-version and retirement bookkeeping before commit. Allocation and failure follow the decided resource policy, including `OutOfMemory` in explicit-allocation-failure mode. Failed preparation leaves the current version intact and must not lose an owned candidate.
- Prefer per-reader hazard protection initially: a long-lived pin then retains its own version, rather than necessarily holding every later retirement behind an epoch. Whichever algorithm is chosen, state the retention bound; `collect()` alone does not make memory bounded.
- `.collect()` does not wait for pins, but it may scan many slots/retirements and run user destructors. Its cost and effects must be visible; no universal real-time or `no blocks` claim. A scan can use indexed hazard membership rather than repeatedly checking every retired node against every reader.
- Require a live owner to outlive registrations and a reader to outlive its pin. Thus pin release/unregistration can be bookkeeping-only; final owner teardown is the explicit place for remaining destruction. No orphaned retirement list, hidden reclaimer thread, or accidental last-reference destructor on the hot `load` path.
- Migration must preserve pin identity; do not use worker-thread-local protection for movable M:N tasks. Close the publish/pin/reclaim race with the actual hazard protocol, not “an acquire load” alone.
- **Alternatives considered:** automatic per-load registration — easier surface, but hidden allocation and unpredictable first-read cost.
- **Alternatives considered:** opportunistic destructor execution inside publish — legal with effects, but weakens useful predictability without improving the surface.
- **New spellings needing approval:** `snapshot(value)`, `.reader`, `.publish`, `.collect` on design-named `Snapshot<T>`; no extra preparation or reclamation members proposed in this round.
- **What it unblocks:** a cheap registered read with explicit lifetime and reclamation ownership.
- **Reversibility:** reclamation machinery replaceable if costs/contracts hold; lifetime guarantees expensive.
- **Where I disagree with round 0 and why:** keep reclamation off publish initially, and make the last-owner case explicit; bounded pin release is otherwise defeated by hidden final destruction.

## 9. `SnapshotReader.load` and `Version.value` — agree, narrow transfer initially

- **Recommendation:** keep one live scoped `Version<T>` per reader; initially move readers only while unpinned and do not transfer a live version to another task.
- **Dewy example:**

  ```dewy
  let reader = state.reader()
  {
      let version = reader.load()
      inspect(version.value)
  }
  let newer = reader.load()
  ```

- The reader is unavailable for a second load while its first version remains live. Last-use release may shorten that interval; lexical blocks give a predictable explicit limit. Two simultaneous versions use two readers.
- `.value` provides ordinary read-only value access, never a mutable place into published storage. Borrowing for a nonescaping read can avoid copying; materializing an independent `T` incurs its normal copy/lifecycle effects. A saved value must remain valid after the pin ends.
- Hazard retries may be unbounded under continuous publication; `no blocks` is not wait-free or bounded latency. Progress must not depend on a stopped publisher completing a private reservation.
- A version's immutable data may be shareable, but that does not make a borrowed pin capability safely transferable independently of its reader. Cross-task pin transfer can be added with a checked joined lifetime or an owning pin design.
- **Alternatives considered:** `Snapshot.load() -> T` — useful convenience later; hides registration and can impose expensive copies.
- **Alternatives considered:** unconditional `Send` on a scoped live version — requires more lifetime machinery than the proposal specifies.
- **New spellings needing approval:** `SnapshotReader<T>`, `.load`, `Version<T>`, `.value`; approve the scoped semantics separately from those names.
- **What it unblocks:** stable reads of nontrivial values without per-load allocation.
- **Reversibility:** permitting more proven transfers later is easy; accepting dangling pins first is not.
- **Where I disagree with round 0 and why:** its move-only `Send` version plus reader-bound lifetime needs an additional proof rule. The initial safe subset should not promise it implicitly.

## 10. Public `Freeze` property — agree to defer

- **Recommendation:** derive deep immutability internally; defer a public `Freeze` spelling until generic signatures need to name it.
- **Dewy example:**

  ```dewy
  let config = snapshot([name="production" retries=3])
  # snapshot([counter=mutex(0)]) is rejected: the counter can change in place.
  ```

- `Sync` means safe simultaneous holding/access, not an unchanging logical value. Mutexes and atomics illustrate the difference. `const` on a handle binding likewise does not freeze its referent.
- Eligibility must cover reachable state, lifecycle hooks, and publication isolation from mutable aliases. Ordinary COW values can qualify when their semantics preserve the published value.
- A compiler-private predicate is still a real obligation with a useful diagnostic. Do not silently let `$sync`, `$send`, or a generic unsafe escape stand in for proof in the strictest configuration.
- **Alternatives considered:** publish `Freeze` now — commits trait/bound vocabulary without a demonstrated user need.
- **Alternatives considered:** define snapshot as a snapshot of handles only — valid weaker abstraction, but not the immutable-version promise being proposed.
- **New spellings needing approval:** none recommended now; `Freeze` explicitly deferred, not reserved or approved by this review.
- **What it unblocks:** correct eligibility without a second public property vocabulary.
- **Reversibility:** adding a public predicate later easy; weakening immutability costly.
- **Where I disagree with round 0 and why:** no directional disagreement; require diagnosable proof and strict-mode handling, not an invisible convenience assumption.

## 11. Contextual `select` and `_` — agree, tighten evaluation/ownership

- **Recommendation:** adopt operation-based contextual `select { … }`, initially for Channel operations, with `_` as the optional readiness fallback.
- **Dewy example:**

  ```dewy
  let answer = select {
      item = inbox.receive() => describe(item)
      _ => "nothing ready"
  } or_throw
  ```

- Receivers and payload-producing expressions evaluate once, in source order, before operation registration. Their ordinary effects remain visible and are not undone if another arm wins. Arm bodies run after resolution, outside runtime locks.
- For an existing move-only variable, form a pending transfer without consuming its source until the winning commit. Losing arms preserve it. Freshly produced temporaries are still owned and cleaned up if they lose. Reject conflicting aliases or operand mutations that cannot satisfy these obligations.
- Losing a send must not silently consume its source. One source offered to several arms is allowable only with a proved mutually exclusive transfer; a conservative first implementation may reject that shape with a specific diagnostic.
- `_` needs a defensible global observation of no ready eligible arm, not merely a sequence of stale individual probes. Channel locks or a validated registration protocol can establish it; complexity includes synchronization, not just O(k) allocated arm records.
- **Alternatives considered:** `match select(operations)` — needs first-class operation descriptors; add when composition warrants them.
- **Alternatives considered:** select arbitrary calls/futures — includes irreversible work before the winner and defeats atomic choice.
- **New spellings needing approval:** contextual `select`, operation-arm grammar, and `_`'s readiness meaning. Existing `match`, `=>`, `_`, and `=` tokens are reused; `select` is the sole new contextual word recommended here.
- **What it unblocks:** multi-channel waits without cancel-unsafe partially executed operations.
- **Reversibility:** syntax easy before adoption; evaluation/move semantics hard.
- **Where I disagree with round 0 and why:** its source-order preparation is right, but “stable temporary” does not itself solve conditional moves or prove a simultaneous fallback observation.

## 12. Arm binding and send success — replace the `none` conversion

- **Recommendation:** bind the operation's ordinary outcome, including its existing `void | E` success/failure behavior; do not turn send success into `none` only inside select.
- **Dewy example:**

  ```dewy
  let label = select {
      sent = outbox.send(message) => match sent {
          <Closed> => "closed"
          _ => "sent"
      }
      item = inbox.receive() => describe(item)
  } or_throw
  ```

- The example uses today's Channel result. If David adopts lossless Channel failures (flag B), its send branch instead handles `failed:Unsent<Message>` and `failed.value`. That is an API decision, not a select-specific conversion.
- Bind/select the same outcome representation ordinary `let result = operation` / `match operation` use. A `void` success contributes no expressed value of its own; the arm body may still produce `"sent"`. If ordinary outcome binding has an implementation gap, fix that generally or initially require an unbound send arm; do not create a select-only `none` rule.
- Arm bodies follow the existing sink/arity rules. A collector gathers their values; a one-value context requires one on every completing path; multi-value bindings require compatible fixed counts. No wrapper record is mandated.
- **Alternatives considered:** Round 0's success `none` — visually simple, but confuses absence with successful no-value completion and violates substitution expectations.
- **Alternatives considered:** send failures always escape the whole select — simpler, but removes useful arm-local recovery of the failed payload.
- **New spellings needing approval:** arm-local `name = operation()` binding rule; no new outcome type/value. Proposed local `none` conversion rejected.
- **What it unblocks:** consistent local error handling and ordinary multi-expression composition.
- **Reversibility:** binding syntax easy; special conversions become costly to remove.
- **Where I disagree with round 0 and why:** the existing language already has `void | E`; a second meaning for success inside one construct is unnecessary.

## 13. Select cancellation and close — agree, define the race precisely

- **Recommendation:** `Canceled` is a whole-select outcome before commit; close resolves one selected arm; a transfer that commits first remains committed.
- **Dewy example:**

  ```dewy
  let chosen = select {
      x = left.receive() => use_left(x)
      y = right.receive() => use_right(y)
      _ => use_cached()
  } or_throw
  ```

- Already-canceled entry resolves without communication or an arm body. Operand evaluation may itself have effects/cancellation points; it cannot be rolled back. Recheck/arbitrate cancellation at selection resolution after preparation.
- Include fallback in the resolution race: if fallback resolves first, a later cancellation does not retroactively replace its result. If cancellation wins first, no arm, including `_`, runs. This remains a cancellation point even though `_` removes waiting.
- Close makes sends ready with failure and receives ready with `Closed` only after committed values drain. Cancel-versus-close uses the same resolution rule. Remove losing registrations before returning or destroying any referenced temporary.
- Exactly one **arm resolution** wins; at most one actual data transfer occurs. A closed arm or `_` commits no channel data. Randomized/rotated probing avoids fixed source bias but is not a starvation-freedom theorem.
- **Alternatives considered:** explicit cancellation arm — lets a ready data arm mask established level-triggered cancellation.
- **Alternatives considered:** one early cancellation flag check — leaves the later selection/commit race underspecified.
- **New spellings needing approval:** none beyond decision 11; cancellation, fallback, and close arbitration are semantic approvals.
- **What it unblocks:** cancellation/close litmus tests with an unambiguous ownership outcome.
- **Reversibility:** costly after users rely on commit behavior.
- **Where I disagree with round 0 and why:** agree in direction; add a resolution point for fallback and distinguish arm resolution from data transfer.

## 14. `no blocks` and `$no_deadlocks` — agree, remove blanket primitive exemptions

- **Recommendation:** classify waits by semantic dependencies, including spin waits; give strict certificates only to proved compositions, never to a primitive's name or “lock-free” label.
- **Dewy example:**

  ```dewy
  poll = (q:Mpmc<Message>):>Message | Empty | Busy | Closed & no blocks => {
      q.try_receive()
  }
  # loop waiting for another task to change q still needs wait analysis.
  ```

- `no blocks` is not bounded time, no allocation, no panic, purity, cancellation immunity, or deadlock freedom. Conversely a cancellable nonwaiting select can exclude `blocks`. Allocation and panics use their separate rows; failures remain result alternatives.
- Do not categorically ban every syscall: implementation already permits certain nonwaiting clock/process queries. A may-wait syscall is blocking; externally waiting I/O stays blocking even if M:N suspends a task instead of a kernel thread.
- Distinguish CAS retry under active interference from waiting for one stopped reservation owner. Audit MPMC, sequencer, Snapshot, close, drop, and hidden hooks individually. A `_` arm removes selection waiting only if its registration/probe path is itself nonwaiting; today's locked Channel core does not automatically provide that implementation.
- Select contributes a disjunctive dependency. A closed deadlocked set requires every alternative to depend on that set; alternatives need not all depend on the **same single task**. Do not infer a cycle from one blocked arm when another can progress.
- Reuse existing demanded call/identity summaries. Add O(k) arm facts, then separately budget the OR-dependency solver; do not claim O(k) total proof complexity. Unknowns warn ordinarily and reject required strict certificates.
- Respect #72's accepted nested-service ranking, not older text banning every service request inside a handler. New expert waits still need a real certificate; a timeout is recovery only.
- `$bulletproof` must reject missing capacity, memory-model, wrap, progress, or trusted-hook proof where its settings demand it. `$no_deadlocks` alone retains its stated fairness, terminating-local-work, and cooperative-peer assumptions; do not silently advertise an unconditional theorem.
- **Alternatives considered:** spin means nonblocking — hides task dependencies and can starve M:N workers.
- **Alternatives considered:** every lock-free operation is certified — memory progress is not protocol progress or per-task fairness.
- **New spellings needing approval:** none; reuse `& no blocks`, `& no allocates`, `& no panics`, `$no_deadlocks`. Positive `& blocks` remains disallowed. This review proposes no new strictness opt-out tags.
- **What it unblocks:** stage-4 APIs that do not bypass existing safety analyses.
- **Reversibility:** analysis representation flexible; shipped effect/certificate guarantees costly.
- **Where I disagree with round 0 and why:** its categorical syscall ban is too broad, and some proposed try/read/select implementations need more than “does not park” to exclude `blocks`.

## 15. Nightly and performance gates — agree on verification, stage thresholds

- **Recommendation:** gate a fixed bounded suite against the actual atomic core and wrapper state machines; keep numeric performance ratios provisional until matching semantics and initial baselines are established.
- **Dewy example:**

  ```dewy
  let [tx rx] = spsc<int64 1>().split()
  tx.try_send(7) or_throw
  match rx.try_receive() {
      n:int64 => $runtime_assert(n =? 7)
      _ => $runtime_assert(false)
  }
  # The harness interleaves publication, close, cancellation and destruction.
  ```

- Keep capacities 1–3, reduced counters to force wrap, duplicate select arms, close/cancel races, ownership conservation, seqlock validation, and pin/reclaim races. Add the stalled-reservation case from decision 4, reader disappearance, callback failure, fallback observation, and payload/error values that overlap control outcome types.
- Bind the checker to implementation code through instrumentable lowering or a shared generated core; native assembly needs its own mapping/refinement argument. GenMC works on LLVM IR, so selecting it is not an existing Dewy integration. [GenMC documentation](https://github.com/MPI-SWS/genmc)
- A timeout means required verification is incomplete and fails the gate; it is not proof of a defect. Report exact explored bounds as CI artifacts. Finite exploration does not prove unbounded liveness, all counter sizes, fairness, or every target memory model.
- Retain the 30-minute nightly budget and at most four workers as initial operational limits. Calibrate the scenario matrix to fit; do not silently shrink bounds after a failure. Small deterministic regressions belong in per-change checks; nightly exploration complements them.
- Benchmark SPSC versus Rigtorp, MPMC versus Crossbeam, fan-out versus Disruptor, and channels/select versus Go only after matching payloads, close/cancel work, contention outcomes, capacity, and placement. Count retry/Busy rates and CPU, not just successful throughput. A queue allowing `Busy` has a different contract and must be labeled accordingly.
- Keep the proposed 0.9× throughput / 1.25× median ratios as candidate targets, not measured acceptance. Establish tail-latency criteria and fresh instruction-count compile-cost baselines before landing. Missing a target calls for redesign, never weakened safety.
- **Alternatives considered:** randomized stress only — useful long-run complement, inadequate schedule coverage.
- **Alternatives considered:** a standalone reference model “certifies” the implementation — false without a checked correspondence.
- **New spellings needing approval:** none; tool names and benchmark labels are not language surface.
- **What it unblocks:** reproducible safety evidence and honest performance acceptance.
- **Reversibility:** tooling/budgets/targets adjustable; required invariants remain.
- **Where I disagree with round 0 and why:** agree on actual-core exploration; stage numeric gates after baseline equivalence, and do not conflate bounded testing with strict proof.

## Flag A. `Mutex.lock` versus cancellation — preserve David's accepted exception

- **Recommendation:** keep `lock()` noncanceling and `lock_all(...)` canceling; correct the general rule to “designated cancellation points,” not “every operation that can wait.”
- **Dewy example:**

  ```dewy
  let payload = @(m.lock())              # accepted noncanceling acquire
  inspect(payload)
  let [a b] = @(lock_all(m n)) or_throw   # may return Canceled
  ```

- #63 explicitly accepted noncanceling `lock` on 10-26. `locks.dewy` and `__lock_wait_word` implement it; console output is another documented non-cancellation boundary. This is not an unresolved implementation accident.
- Noncanceling does not mean nonwaiting: maintain lock-order certification and its progress assumptions. It does not promise prompt group cancellation if a lock holder never finishes.
- New waiting stage-4 operations can be cancellation points without changing the older lock contract. Adding a canceling single-lock convenience would be a separate surface decision; it is not needed here.
- **Alternatives considered:** change `lock` to return `Canceled` — potentially reasonable redesign, but reverses an accepted answer and affects place signatures/callers.
- **Alternatives considered:** make seqlock/queue waits noncanceling too — no requirement follows from the lock exception.
- **New spellings needing approval:** none recommended.
- **What it unblocks:** consistent implementation without reopening an already answered question.
- **Reversibility:** changing cancellation behavior later is source- and behavior-sensitive.
- **Where I disagree with round 0 and why:** its flag predates the explicit acceptance. Preserve the decision, and distinguish blocking effects from cancellation points.

## Flag B. Failed `Channel.send` payload recovery — decide before move-only select

- **Recommendation:** extend Channel to the same lossless failed-send contract as expert queues, subject to David's explicit approval; implement the migration coherently rather than maintaining two permanent transfer models.
- **Dewy example:**

  ```dewy
  match outbox.send(message) {
      failed:Unsent<Message> => save_for_later(failed.value)
      _ => {}
  }
  ```

- Current `channels.dewy` takes `value:T`, waits, and returns plain `Closed`/`Canceled` without returning `value`. Ordinary values may leave a caller copy if later used; that does not solve a unique/move-only message or eliminate copying costs.
- Changing to `void | Unsent<T>` changes annotations and `??<Closed>`/`??<Canceled>` handlers. State that migration explicitly. Preserve `reason` and causal cancellation reporting; never treat a canceled failed transfer as success.
- Reject a select implementation that drops a selected-but-unsent move-only message while preserving losing ones. Until the Channel decision is made, conservatively reject such selections, or use currently copyable payloads with visible copies; do not imply the issue is solved by arm binding.
- Returning a failed payload does not undo preparation effects or make the receiver able to recover a successfully committed value.
- **Alternatives considered:** preserve Channel forever and add a differently named lossless send — duplicates the main verb and fragments generic transfer code.
- **Alternatives considered:** consuming-place send that preserves the variable on failure — possible, but requires a new conditional initialization contract at every call; an explicit envelope is more compositional.
- **New spellings needing approval:** no additional name beyond decision 1; the changed Channel `.send` result is a separate semantic approval. No second send verb recommended.
- **What it unblocks:** coherent move-only messaging, including selected failed sends.
- **Reversibility:** substantial before release but manageable; costly after error handlers proliferate.
- **Where I disagree with round 0 and why:** don't silently change Channel, but don't defer the decision past the stage-4 ownership design either. This round should ask David to approve the migration direction.

## #118. Gathering task results — retain `concurrent` in the comprehension

- **Recommendation:** adopt `[concurrent x in xs work(x)]`; reuse the existing `concurrent` keyword because its task-scope semantics are the desired contract.
- **Dewy examples:**

  ```dewy
  let squares = [parallel x in xs x*x]
  let pages = [concurrent url in urls fetch(url)] or_throw
  let parsed = [parallel page in pages parse(page)]
  # Existing compute and waiting forms compose without async/await functions.
  ```

- **Concrete difference: scheduling.** `parallel` may run an entire iteration inline and finish it before starting the next. Native code uses the persistent fork-join pool; web runs serially. Waiting tasks must allow an admitted runnable sibling to progress while another waits. This is logical concurrency, not a promise of simultaneous CPUs or a particular launch order.
- **Concrete difference: effects.** Today's compiler rejects sleeps, channel waits, blocking I/O, waiting joins, and opaque calls in parallel bodies. The adopted design fundamentally forbids sibling-dependent waiting; implementation is conservative and also has reviewed primitive exceptions, notably mutex machinery. It is inaccurate to describe the current implementation as either unrestricted parallel threads or a fully uniform ban on every possible wait.
- **Concrete difference: data.** Parallel inputs/results use transfer checks, immutable captures, and proven disjoint mutable elements. Waiting spawns also check captures/results but do not automatically inherit the special mutable-partition form. Neither lane permits arbitrary shared mutable globals.
- **Concrete difference: failures.** Parallel collection preserves input order and ordinary result values; it does not introduce a fail-fast task group just because an element is an exception. Concurrent scopes cancel siblings on the first child failure, join cleanup, and may fail admission with `OutOfMemory`. Parent cancellation returns `Canceled`; a child's causal error must survive resulting sibling cancellation (#80).
- **Concrete difference: current implementation.** `lib/std/thread.jo` lowers collectors to indexed fork-join work; `compiler/dewy_nodes.jo` expands task scopes into create/enter/spawn/join/result retrieval. `lib/std/tasks.jo` starts Linux native threads, not M:N tasks. The comprehension is absent; nested/loop spawn results currently need channels or synchronized storage. `$task_backend='threads'|'auto'` is accepted provisionally in #110, but the M:N plan remains a plan.
- **Why effect-based dispatch is insufficient:** `blocks` is a conservative may-effect. It does not say whether two iterations depend on each other, what child errors mean, or whether task admission may fail. Adding a log/FFI call to a helper could silently change scheduling, cancellation, result shape, and supported targets. An unresolved callable cannot safely default to inline execution.
- **Could one construct cover both?** Yes, if its *public semantics were uniform*: every invocation would promise structured task concurrency and fail-fast/error/admission behavior; the compiler could fuse or run work inline only when that preserves observable behavior and progress. Calling that construct `parallel` would change today's accepted meaning, including portable sequential fallback. Uniform semantics are feasible; two meanings inferred from effects are the problem.
- **Could a setting choose?** An explicit setting could choose either contract, but would hide a consequential choice from the comprehension and complicate generic libraries. Keep backend/placement settings about implementation; they must not change a function's failure or progress contract. No additional setting is needed when `concurrent` already exists.
- **Proposed collection contract:** finite array/range, source evaluated once, one result per iteration initially, result order matches input order, structured join before return. If `work` yields `T | E`, give `array<T> | E | Canceled | OutOfMemory`, not merely the last two failures. First child exception cancels siblings; return it after cleanup. Side effects already performed are not rolled back. Several simultaneous failures need not have deterministic priority beyond the group's existing first-observed rule.
- **Collecting errors deliberately:** `[concurrent x in xs [value=work(x)]]` makes each child return a non-exception record holding its result, so ordinary domain errors can be retained per item; outer cancellation/admission can still fail the group. No new “all settled” keyword is necessary.
- **Resource/progress condition:** do not create only N iterations and wait for them before admitting the rest if those first N may depend on later ones. Maintain independently schedulable logical tasks or return admission failure and cancel/join existing children. A throttled independent-work mapper is a separate contract. Under strict resource settings, acquire/prove task and result capacity, including cleanup; a guard page is not that proof.
- **Alternatives considered:** automatically reinterpret `[parallel …]` from body effects — unstable public semantics and insufficient dependency information.
- **Alternatives considered:** redefine all `parallel` as guaranteed concurrent gather — coherent, but reverses an accepted optimization/progress contract and portable behavior.
- **Alternatives considered:** a lane setting — possible, but less local and adds spelling where an existing keyword is clearer.
- **New spellings needing approval:** **no new keyword**; the new grammar `[concurrent x in xs body]` and its gather/failure contract need approval. Reuse existing errors. No new lane-setting name proposed.
- **What it unblocks:** ordered many-task results without a result Channel/Mutex scaffold.
- **Reversibility:** grammar easy; failure policy and sequential-execution permission hard.
- **Where I disagree with round 0 and why:** agree with the comprehension direction, but include body errors and specify admission, failure, ordering, and cleanup. “Like asyncio.gather” is too imprecise to define Dewy's already structured semantics.

## #114. Passing callback parameters into parallel calls — prefer inference

- **Recommendation:** infer per-parameter parallel-use obligations and check them at call sites; if an explicit function tag is wanted, prefer `$parallel_safe` as a checked contract, before `let`/`const`, with same-line and preceding-line forms equivalent.
- **Dewy examples — preferred inferred use:**

  ```dewy
  apply = (xs f) => [parallel x in xs f(x)]
  square = (x:int) => x*x
  let ys = apply(xs @square)
  # Infer: f is invoked on parallel elements; verify its actual captures/effects.
  ```

- **Dewy examples — spelling if David chooses the optional tag:**

  ```dewy
  $parallel_safe myfn = () => 42
  $parallel_safe const apply = (xs f) => [parallel x in xs f(x)]
  $parallel_safe let local_apply = (xs f) => [parallel x in xs f(x)]

  $parallel_safe
  const apply_again = (xs f) => [parallel x in xs f(x)]
  ```

- If the tag is retained for this task, define it narrowly: it explicitly requests verification/export of the declaration's **per-parameter parallel-use obligations**. It does not mean the wrapper itself runs in parallel, does not bless unsafe arguments, and does not constrain serial-only callbacks. With inference enabled it is redundant documentation; `myfn` above has no callback obligations and the tag is harmlessly redundant. A distinct marker for a function value's own invocation safety is not proposed.
- Full order: **metatag(s), binding introducer (`let`/`const`, if present), name, optional type, `=`, initializer**. Newline is not semantic. The tag applies to that declaration and does not leak into following declarations. A mutable function binding must recheck later assignments against its contract.
- **What the existing attribute actually does:** `parallel_api` in the checker marks a function that runs its function arguments concurrently; `race_arg` permits forwarding a parameter only from a marked function, checks callback arguments at direct callers, and `parallel_direct` forbids taking/partially applying that marked API as a value. It is not simply “this function is thread-safe.” `concurrency_callback` separately checks captures/results and waiting behavior.
- A direct Dewy spelling for that boolean would mark **every function parameter**, including a callback used only serially. Instead summarize exactly which parameter is invoked where, whether invocations overlap, what captures/places are transferred or shared, and which ordinary effect exclusions apply. Forward those obligations through wrappers and recursion to a fixed point.
- **How inference works:** discovering `f` in a parallel body adds a checked invocation/transfer obligation to `apply`'s signature summary; a call such as `apply(xs @square)` discharges it. A serial error formatter parameter acquires no parallel obligation unless actually used there. Capture writes, unknown mutable aliases, disjointness, hidden hooks, and transfer legality remain separate checks.
- Callable values, partial application, returned functions, containers, and reassignment must retain these constraints. An indirect call checks the constraint carried by its callable type; an opaque callable with no sufficient contract is rejected. Do not merely remove `parallel_direct` while losing its call-site check.
- **Effect-row connection:** reuse the demand-driven contract-bearing callable machinery in `effects.md`, including symbolic callback applications and substitutions. `& no blocks` only excludes waiting; `& no panics` only excludes panics; `allocates` measures allocation permission, not race safety. Safe parallel code can allocate. A positive row is a closed upper bound; a negative-only row is open except for its exclusions. `blocks` is inferred and only negatively spelled.
- **Annotated/exported signature example, deliberately conservative:**

  ```dewy
  PureStep:type = <(x:int):>int & no_effects>
  apply_pure = (xs:array<int> f:PureStep) => [parallel x in xs f(x)]
  ```

- `no_effects` can express a strict invocation contract, but still does **not** certify that a closure's environment can cross tasks. A function capturing a nontransferable handle may have an innocuous body and still fail that obligation. The actual value/type conversion must also verify the environment; exported metadata must retain that requirement. The example illustrates the recommended contract route, not a claim today's race checker accepts parameter forwarding with this row.
- For richer public APIs, infer and display the per-parameter requirement in the exported signature metadata; permit explicit ordinary rows now, and design a public value constraint only when a real exported API needs an uninferrable/opaque form. Keep published contracts stable: losing a proof diagnoses the implementation instead of silently changing a caller's obligations.
- **`$send`/`$sync` connection:** these are structural facts about values and shared identity, not invocation effects. The callback environment and argument/result paths consult them. `$send` alone does not authorize simultaneous use; `$sync` alone does not prohibit waits or mutation races through other reachable state. Unsupported claims require the existing unsafe boundary; a safe `$parallel_safe` annotation must demand verification, never assert “trust me.” Strict configuration cannot treat the marker itself as proof.
- **Naming judgment:** `$parallel_safe` is the best of David's candidate names for a checked parallel-invocation contract. `$thread_safe` is too broad and suggests guarantees for arbitrary shared calls, reentrancy, waiting, and task/thread affinity. `$parallel` sounds like a scheduling request. None precisely means “all callbacks supplied to this wrapper are checked,” which is another reason to infer per-parameter obligations instead of exposing the old flag verbatim.
- **Alternatives considered:** mandatory function-wide `$parallel` — preserves the current direct-call restriction and overconstrains serial callbacks.
- **Alternatives considered:** mandatory `$parallel_safe` — clearer name, but still redundant boilerplate where use determines the requirement.
- **Alternatives considered:** add `parallel_safe` or `thread_safe` as a may-effect — mixes value/ownership compatibility with effects and obscures what is actually proved.
- **Alternatives considered:** rely solely on `& no blocks` — admits nonblocking data races; relying solely on `no_effects` still misses unsafe capture transfer.
- **New spellings needing approval:** none for inference with existing rows; optional `$parallel_safe` and its precise scope/meaning if selected. `$parallel`, `$thread_safe`, and hypothetical row atoms `parallel_safe`/`thread_safe` are evaluated alternatives, not recommended additions. `PureStep`, `apply`, and `myfn` are local example names.
- **What it unblocks:** ordinary higher-order parallel helpers, including safe first-class wrapper functions, without Sloppy syntax or a blanket trust flag.
- **Reversibility:** inferred internal summaries easy to evolve; exported callable constraints and tag meaning require compatibility care.
- **Where I disagree with round 0 and why:** the coordinator's marker proposal exposes an implementation workaround. Solve the underlying per-parameter contract; use a marker only as optional explicit documentation/verification, not as the gate that turns on safety checking.

## Evidence and handoff notes

- Primary local sources: `docs/design/{safety_and_concurrency,effects,decisions,resource_exhaustion,multi_expressions}.md`; concurrency sections of `docs/LANGUAGE.md`; requested pending questions; the round-0 stage-4 proposal (`primitives-proposal.md`) and M:N plan; the earlier concurrency research report. Older research claims are background, not fresh verification of external runtimes.
- Implementation anchors: `compiler/concurrency.jo:139` (wait summaries), `:209` (callback checks), `:250` (task/parallel finalization); `compiler/lower.jo:1831` (race checks and forwarding restriction); `compiler/dewy_nodes.jo:542` (task-scope expansion); `lib/std/thread.jo:43` (parallel library), `:221` (noncanceling mutex acquire), `:314` (channel send); `lib/std/tasks.jo:148` (spawn/join); `lib/prelude/{channels,locks}.dewy` (public wrappers). Stage-4 primitives were not found in `lib/` or `compiler/` during this inspection.
- Cross-cutting implementation acceptance: control outcomes must stay distinguishable when payload types overlap `Empty`, `Busy`, `Closed`, or `Canceled`; decision 1 recommends an explicit first-slice restriction, with ordinary record wrapping available. No implicit sentinel ambiguity, guessed capacity, hidden allocation, or “counter cannot wrap in practice” may become an unlisted strict-mode assumption.
- Round-2 reconciliation priorities: MPMC nonwaiting progress; sequencer commit/drop invariants; ordinary `void` outcome binding in select; Channel error migration; inferred callback constraints versus an optional tag. Each has a recommendation above, not an open-ended request for another design brainstorm.
- Out-of-scope discoveries, not acted on: wait classification still includes library-path/name trust and special mutex treatment; the general effects framework and old race checker are not yet one mechanism; some design/status text predates accepted #72/#80 answers. These are follow-up consistency work, not edits authorized by this read-only round.
- No repository files edited, tests run, benchmarks claimed, or commits made.
