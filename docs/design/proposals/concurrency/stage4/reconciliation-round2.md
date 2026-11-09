# Stage 4, round 2 reconciliation

- **Scope/acceptance:** reconcile all 15 round-0 decisions, flags A/B, and David's #118/#114; verify disputed current-code and accepted-rule claims; produce a self-contained digest of about 3,000 words or less with every proposed spelling inventoried.
- **Owned files:** this file and `decision-digest.md`, both under `docs/design/proposals/concurrency/stage4/`. Repository read-only. Non-goals: implementation, repository documentation, tests, benchmarks, scheduler redesign, or another agent round. Budget: one focused review session, at most 90 minutes.
- **Authority:** David's accepted answers outrank older status prose. Source inspected at `42a7ce9b1`; the working tree was clean at entry. Stage-4 signatures are proposals, not compiler acceptance claims.
- **Outcome:** accept most of round 1's tightening. Withdraw `Unpublished`, blanket MPMC lock freedom, select-only success `none`, the stale Mutex flag, and unconditional cross-task transfer of scoped pins. Decide the Channel migration now rather than leaving it beyond the ownership design. The remaining substantive disagreement is #114's delivery sequence: a checked explicit tag now versus automatic forwarding inference first.
- **Historical accuracy:** round 0 contains neither #118 nor #114. The later coordinator questions are not retroactively my round-0 positions. Round 1's references to a round-0 marker/gather recommendation concern that later context.

## Factual reconciliation against the repository

- **Mutex flag corrected:** #63 explicitly accepts noncanceling `lock()` on 10-26. [Public lock signatures](/lib/prelude/locks.dewy:29), [runtime acquisition](/lib/std/thread.jo:221), and [language guide](/docs/LANGUAGE.md:2799) agree. My round-0 request to resolve the exception was stale. `lock_all` returns `Canceled`; neither this distinction nor console output's exception abolishes the blocking effect.
- **Accepted versus implemented:** #65 accepts certificate/protocol names; #72 accepts strictly outer layered service dependencies; #80 accepts preserving a child's causal failure when it cancels the body; #110 accepts provisional `$task_backend='threads'|'auto'`, default threads. None means the whole accepted change is already implemented at this HEAD.
- **Concrete lag:** [deadlock checker](/compiler/deadlock.jo:1694) still rejects any service-asking handler, and `tests/cases/no_deadlocks/handler_asks.dewy` is still negative. Use #72 as the target rule, not that older prohibition. `__task_join` returns the recorded first exception, but [early-exit cleanup](/lib/std/tasks.jo:213) discards its join result; do not claim that alone establishes #80 on early body exits. No `$task_backend` implementation was found in `compiler/` or `lib/`; acceptance of #110 is not an M:N implementation claim. These are follow-up consistency findings, not work performed here.
- **Parallel's serial permission is real:** [LANGUAGE](/docs/LANGUAGE.md:2730) permits caller-only execution and serial web fallback. [Callback checking](/compiler/concurrency.jo:209) checks bound arguments, captures, results, and blocking. `blocks` is conservative and includes special reviewed runtime boundaries: current mutex internals are not uniformly classified as blocking. Thus neither “arbitrary waiting is allowed” nor “every operation that could wait is uniformly rejected” describes current code.
- **#114's actual flag:** [race_arg/parallel_direct](/compiler/lower.jo:1841) permits forwarding an unchanged parameter only from a `parallel_api` function; every function-valued direct argument is race-checked, and marked APIs cannot be taken as values/partially applied. [check.jo](/compiler/check.jo:1832) reads Sloppy's `parallel` attribute. There is no Dewy `$parallel_safe` or `$thread_safe` parser support. This flag means “calls supplied functions concurrently,” not “this function is generally thread-safe.” round 1 is correct.
- **Channel failure is lossy at the API boundary:** [channels.dewy](/lib/prelude/channels.dewy:29) receives `value:T`, waits, and can return bare `Closed`/`Canceled` without returning that value. A retained caller copy is possible for ordinary copyable values; a move-only recovery guarantee is absent. Current native channels use a locked ring, not the proposed expert algorithms.
- **`void` correction supported by code:** ordinary `void | E` binding already has a representation. [void_union_print.dewy](/tests/cases/errors/void_union_print.dewy:12) binds a successful result; [void_result_arm.dewy](/tests/cases/errors/void_result_arm.dewy:20) distinguishes success/error. #124 accepts printing the success member as `void`. No select-specific `none` conversion is needed. Round 1's statement that success expresses no value concerns expression sinks, not the inability to represent an outcome.
- **Effects and resources:** `effects.md`'s opening runtime-check default is superseded by the no-traps ledger and its own later decided section. Positive effect rows are closed bounds; negative-only rows are open with exclusions. [resource_exhaustion.md](/docs/design/resource_exhaustion.md:166) makes ordinary heap OOM environmental, explicit-allocation mode return `OutOfMemory`, and strict capacity use require acquired/proven storage. Current task-slot/thread admission independently returns `OutOfMemory`. Do not add OOM indiscriminately to every ordinary operation or promise recovery after arbitrary stack exhaustion.
- **Spelling authority:** `Spsc`, `Mpmc`, `Sequencer`, `SeqLock`, `Snapshot`, and operation-based `select` are already design-named. Concrete constructors, endpoint/version types, members, contextual grammar, and callback metatag remain proposals. `concurrent` is already a keyword; #118 adds grammar, not a new word. `Busy` is currently an `error`, hence also an `exception`; `Canceled` and `Closed` are exceptions without being ordinary `error` subtypes. `Unsent` must be an exception envelope, with flat typed catching unless explicitly inspected.
- **Implementation scope:** searches found no stage-4 expert implementations in `compiler/` or `lib/`. No tests or performance measurements were run. Read-only source evidence must not be presented as behavioral verification.

## 1. Outcomes and payload recovery

- **Round 0 → round 1:** I proposed `Full`, `Empty`, `Unsent<T>`, plus batch-specific `Unpublished<T>`; round 1 keeps one generic `Unsent<P>`, operation-specific reasons, and explicit sentinel-collision rules.
- **Agreement:** use `Unsent<array<T>>` for batches; a separate batch error name earns no semantic distinction.
- **Final:** success transfers the complete payload; failure returns it exactly once, with no implicit clone or partial acceptance. Try sends fail `Full`/`Closed` (also `Busy` where specified); waiting sends fail `Closed`/`Canceled`, not transient fullness. Try operations never consume cancellation.
- **Correction:** choosing names other than `none` does not solve `T` itself containing `Closed`, `Empty`, `Busy`, or `Canceled`. Initially reject overlap with the particular operation's flattened control alternatives. An ordinary record wrapper makes the payload distinguishable. This restriction is semantic and must be approved, not hidden as an implementation detail.
- **Error-handling consequence:** `Unsent<P>` is not the `Canceled` alternative merely because `.reason` contains it. `??<Canceled>` stays flat; use matching/inspection of `.reason`. Preserve secret payload redaction when reporting an unhandled envelope. Recovery availability permits deliberate dropping by the handler.

## 2. SPSC construction and split

- **Round 0 → round 1:** both choose static capacity and consuming split; round 1 notices that noncopyable endpoints alone do not stop copying the unsplit queue first.
- **Agreement:** queue and both ends are unique/noncopyable, with exclusive endpoint operations and liveness-proven moves.
- **Final:** `spsc<T N>()`, positive exact `N`, consuming `.split()`, distinct sender/receiver. Endpoint/task transfer requires payload transfer legality; `not Sync` is not by itself a uniqueness proof. Stable backing storage must outlive both endpoints. Compile-time capacity permits specialization but does not promise inline stack storage.
- **Alternative retained:** runtime role leases are implementable but add state and weaken static cardinality. Runtime-capacity construction can be additive later.

## 3. SPSC verbs and close

- **Round 0 → round 1:** both use channel-like verbs and drain-on-close; round 1 adds receiver-loss cleanup and qualifies whole-call progress.
- **Agreement:** keep `try_send`, `send`, `try_receive`, `receive`, `close` and explicit try outcomes.
- **Final:** sender close/drop closes publication; accepted values drain FIFO. Receiver disappearance wakes senders, makes sends fail losslessly, and destroys unread values once. Close is idempotent. Waiting operations check established cancellation even if ready. Full/empty are observations, not facts stable across interference.
- **Correction:** bounded/wait-free ring bookkeeping does not make arbitrary payload copy/drop hooks or final teardown bounded. Strict rows must account for those effects separately.

## 4. MPMC ordering and progress

- **Round 0 → round 1:** I called per-slot CAS tries lock-free and promised only per-producer FIFO; round 1 requires FIFO linearization and allows `Busy` on obstruction.
- **Agreement:** withdraw the unsupported lock-free claim; nonwaiting obstruction returns `Busy` without consuming a send payload.
- **Why:** reserve A, stop A before publication, finish B's later send, then receive. Waiting for A violates the nonwaiting promise; returning `Empty` after B's completed send violates that result's meaning; skipping A conflicts with reservation-ordered FIFO. `Busy` honestly declines to complete a transfer. CAS use alone proves none of the required progress properties.
- **Final:** linearizable successful FIFO transfers, including real-time order for nonoverlapping sends; simultaneous sends may linearize either way. Bound try retries; reserve/publication/close must share a coherent protocol. Waiting wrappers retry/park cancellably. Explicit close is needed with roleless copied handles; final owner reclaims storage.
- **External check:** [Crossbeam source](https://docs.rs/crossbeam-queue/latest/src/crossbeam_queue/array_queue.rs.html) separates position reservation, payload initialization, and stamp publication and contains backoff paths. Round 1's warning against treating a direct port as a proof of the stronger no-wait contract is justified. Dewy's proposed `Busy` contract must be labeled when benchmarking against it.
- **Strong alternative:** a helping algorithm can earn stronger progress later; a nonwaiting try-locked implementation can satisfy `Busy` semantics but cannot be called lock-free. Do not weaken source guarantees silently by target.

## 5. Sequencer publication and lifecycle

- **Round 0 → round 1:** both favor atomic whole batches over exposed claims. Round 1 rejects ambiguous tombstone repair and fills subscription/drop/close gaps.
- **Agreement:** publication success is irrevocable delivery to every live subscriber; no internal recovery may silently erase accepted data.
- **Final:** serialize admission initially, return `Busy` from tries before reservation, and prepare all potentially failing/copying work before reservation. Reserved installation must finish without user callbacks, allocation, or recoverable failure. Tombstones may repair a never-visible reservation only when the whole payload is returned; they are not successful publication. “Contiguous” describes sequence positions, not addresses at physical wrap.
- **Final lifecycle:** prove setup subscription precedes publication through exclusive setup/alias analysis; unknown ordering diagnoses. Require initial subscribers. Dropping one removes its gate and abandons its unread subscription; losing the last closes publication. Publisher ownership counts exclude reader references. Close arbitrates against acceptance; no final `Closed` before committed items drain.
- **Alternative:** public claims/views/acknowledgments can avoid copies, but add incomplete-claim cancellation and reuse lifetimes; defer them.

## 6. Sequencer readers

- **Round 0 → round 1:** both choose copied values/implicit cursor advance. My `Send` plus copyability and “independent value” language was insufficient.
- **Agreement:** require proven safe simultaneous source copying, and preserve ordinary identity-handle semantics.
- **Final:** each exclusively operated, movable reader advances only after a successful copy. Initially reject unsupported fallible copy hooks; record all other hook costs. Every live subscriber observes each committed value in order; slowest live cursor gates reuse. `Sync` or an equivalent source-read proof is required in addition to transfer/copy eligibility; no new public trait is proposed.
- **Correction:** copying a record of ordinary values preserves their independent meanings; copying a mutex handle preserves shared identity. Broadcast does not recursively clone shared objects.

## 7. SeqLock

- **Round 0 → round 1:** both require atomic-word payload access and value snapshots; round 1 adds counter reuse, representation validity, and a narrower callback phase.
- **Agreement:** retain eligible fixed-size layouts; prove coherent validation and wrap safety, not just absence of ordinary data races.
- **Final:** `try_read` makes one attempt and returns `Busy` on interference. Never interpret tentative torn bits as a `T` before validation. Retrying reads and writer serialization wait cancellably. Update computes privately with the old complete version readable; only the prepared atomic installation uses the odd/write phase. Error/cancellation before installation preserves the stored value, but cannot undo callback side effects.
- **Conservative first slice:** require nonblocking callbacks and reject writer reentrancy. This excludes useful cases compared with round 0, but avoids expanding a new primitive's critical-section protocols; broadening later is additive. Callbacks, hidden hooks, and serialization still enter effect/deadlock summaries.
- **Proof obligation:** a suspended reader can span counter wrap. A verified reuse protocol or established bound is needed; “64 bits is enough in practice” is not the strict proof. Verified fallback must expose its actual effects.

## 8. Snapshot registration and reclamation

- **Round 0 → round 1:** both use explicit registration/collection. I permitted publication to reclaim; round 1 concentrates payload destruction in collection/owner teardown.
- **Agreement:** keep publication's initial contract to preparation, swap, and retirement; do not run arbitrary retired-payload destruction there.
- **Final:** acquire version and retirement bookkeeping before the swap; preparation failure leaves the published version unchanged. Under explicit resource failure, preserve candidate ownership until preparation succeeds; implementation must show this with the existing storage/move machinery, not assume an error result reconstructs an already moved value. No additional public preparation API is approved here.
- **Final lifetime:** owner outlives registrations, reader outlives pin. Final owner teardown owns remaining retirement destruction; no orphan lists or hidden reclaimer. Per-reader hazards are a useful initial representation because a held pin need not retain unrelated later versions. `collect` does not wait for pins but its scans/destructors have visible cost/effects. Registration/task migration cannot use an untracked worker-local pin.
- **Bound caveat:** explicit collection is not bounded memory. State reachable-reader and retired-version bounds; resource acquisition/proofs apply in strict settings. Storage bookkeeping and cleanup capacity count too.

## 9. Reader/load/version

- **Round 0 → round 1:** both use one scoped live version per reader. I marked versions `Send` without specifying the necessary reader-bound transfer proof; round 1 defers that transfer.
- **Agreement:** initially move readers between logical tasks only while unpinned; do not transfer live versions independently across tasks.
- **Final:** `.value` allows read-only, nonescaping access or ordinary copying out; no mutable published place. A saved copy remains valid after unpinning and pays its own effects. Another simultaneous pin requires another registered reader. Scheduler migration of the same task remains valid if the runtime preserves the pin identity; that is distinct from language-level cross-task transfer.
- **Progress:** hazard validation may retry under continuous publication; nonwaiting is not wait-free latency. A stopped publisher must not leave a reservation readers need completed. Later owning/scoped cross-task pin designs can broaden eligibility with a checked lifetime.

## 10. Deep immutability / `Freeze`

- **Round 0 → round 1:** both defer a public property while requiring immutable reachable published state.
- **Agreement:** internal derivation is enough now; `Sync` and binding `const` do not freeze shared identity.
- **Final:** include aliases, hooks, and reachable handles in eligibility. Ordinary value/COW semantics may prove isolation; a reachable mutex or atomic can violate it. Produce a specific eligibility diagnostic. Do not allow a safe annotation to assert away this proof. `Freeze` is neither approved nor reserved here.

## 11. Selection surface and preparation

- **Round 0 → round 1:** both prefer contextual operation arms with optional `_`; round 1 makes pending ownership and fallback observation explicit.
- **Agreement:** implement recognized Channel operations first, without general futures or arbitrary half-run calls.
- **Final:** evaluate receivers/payload expressions once, in source order, after checking established cancellation. Preparation effects are not transactional. Existing move-only sources are conditionally transferred at commit; losers retain them. Fresh losing temporaries are destroyed normally. Reject interfering aliases/operand mutations, and initially reject one source offered to multiple arms unless exclusive transfer is proved. Bodies run after resolution, outside internal locks.
- **Correction:** a stable temporary does not by itself prove conditional source ownership. A fallback also needs validated no-readiness across all eligible arms, not unrelated stale probes. Register/validate without lost wakeups, and remove losing registrations before referenced storage dies.
- **Alternative:** first-class event values would enable composition but add public types and abort/ownership contracts. They are not needed to decide this first syntax.

## 12. Binding selected outcomes

- **Round 0 → round 1:** I mapped send success to `none` locally; round 1 keeps ordinary `void | E`.
- **Agreement:** retract the conversion; normal outcomes already have the needed representation.
- **Final:** binder gets the same operation outcome as ordinary binding/matching. Success does not itself contribute an expressed payload; the arm body can still yield a label or multiple values. Use ordinary sink/arity rules, no forced wrapper record. With B approved, failed sends bind `Unsent<T>` and can recover locally. Pure send failure must not be forced to escape before recovery.
- **Strongest case for my old alternative:** `none` is a familiar inspectable singleton. It loses to substitution consistency and adds a gratuitous semantic rule, so it is no longer recommended.

## 13. Selection cancellation, close, fallback

- **Round 0 → round 1:** both place cancellation outside the chosen operation arm; round 1 distinguishes arm resolution from data transfer and defines fallback arbitration.
- **Agreement:** one resolution wins; at most one data transfer occurs, and closed/fallback outcomes may transfer nothing.
- **Final:** already-canceled entry runs no operand or body; cancellation arising during preparation has ordinary visible effects, then participates in final arbitration. Recheck/resolve cancellation, commit, close, and fallback coherently. Whichever resolves first stands. Close readies sends as failures; receives drain committed values first. Rotate/randomize readiness without a starvation guarantee.
- **Not proposed:** a normal cancellation arm that can lose to data after cancellation was already established, or rollback of preparation/body side effects.

## 14. Effects and wait certificates

- **Round 0 → round 1:** both classify peer-dependent spins as waits and demand protocol proofs. Round 1 corrects my blanket syscall ban and overly easy nonblocking assumptions.
- **Agreement:** `no blocks` is a semantic nonwaiting claim, not bounded latency, purity, no allocation, no panic, or deadlock certification.
- **Final:** classify reviewed operations and hidden hooks, not names. Nonwaiting clock/process queries need not block; a syscall that may wait does. MPMC reservation waits and internal Channel locks cannot disappear because the surface says `try` or has `_`. A fallback selection can exclude `blocks` only when its preparation/probe/registration/cleanup implementation earns it. Cancellation can remain a result without blocking.
- **Analysis:** reuse demanded function/identity summaries and add O(k) arm records for k arms. That does not make the OR-dependency solver O(k). A closed deadlocked set requires every alternative to depend on that set, possibly on different tasks. Budget solver work separately; ordinary unknowns warn, required strict certificates reject. Retain the accepted ranked-service rule, fairness/terminating-local-work/external-peer assumptions, and explicit trusted boundaries.
- **Compile cost:** no new whole-program primitive pass. Measure dormant/active instruction counts, including flagship programs, before landing. `$bulletproof` proof requirements and `$no_deadlocks`' narrower theorem must not be conflated. Bounded exploration is not a replacement for either.

## 15. Verification and performance gates

- **Round 0 → round 1:** both require implementation-linked exploration; round 1 stages numerical ratios and distinguishes evidence from proof.
- **Agreement:** retain the initial 30-minute nightly budget and maximum four workers; calibrate matched performance gates before treating candidate ratios as release thresholds.
- **Final:** explore small capacities, reduced counters/wrap, reservation stalls, batch/reader disappearance, payload-control collisions, update failures, selection fallback/duplicate-arm/close/cancel races, and snapshot pin/reclaim races. Required bounds/timeouts are recorded as CI artifacts; timeout means incomplete verification, not a discovered bug or a pass. Keep deterministic regressions per change and longer stress separately.
- **Tool feasibility:** [GenMC documentation](https://github.com/MPI-SWS/genmc) describes an LLVM-based checker. There is no Dewy integration established here. Instrument the actual core or share generated code with a justified correspondence; a handwritten model alone cannot certify native lowering. Finite exploration does not prove unbounded liveness or every target memory model.
- **Performance:** preserve matched capacities/payloads/ordering/contention/cancel/close semantics. Count retries/Busy, CPU and tails. Initial 0.9× throughput and 1.25× median ratios are candidates; do not waive correctness or tail regressions to hit a median. Failure of a decided capability calls for diagnosed redesign, not abandoning its semantics.

## Flag A. Mutex cancellation

- **Round 0 → round 1:** I treated the exception as unresolved; round 1 cites accepted #63.
- **Agreement:** preserve noncanceling `lock`, canceling `lock_all`; retire the flag.
- **Final:** describe level-triggered cancellation in terms of designated cancellation points. New expert waits may cancel without changing the older lock signature. A noncanceling acquisition still waits and can delay group cleanup under its existing progress assumptions. No new convenience API is needed.

## Flag B. Channel failed-send recovery

- **Round 0 → round 1:** I deferred Channel review while adopting lossless expert sends; round 1 asks for an explicit migration decision before move-only selection.
- **Agreement:** ask David to approve the migration direction now, without claiming that approval has already happened.
- **Final:** `Channel.send(value)` should return `void | Unsent<T>` and obey the same commit/recovery rule. Change annotations, typed catches, diagnostics, certified protocol wrappers, and group-error handling coherently. `??<Closed>`/`??<Canceled>` will no longer directly catch these send failures; inspect `.reason`. Preserve #80 causal error reporting when the envelope's reason is scope cancellation; that is explicit group-boundary interpretation, not general recursive typed matching.
- **Strongest case for deferral:** Channel already works, and changing error shape expands the implementation slice. **Strongest case for migration:** a selected closed/canceled move-only send otherwise loses the winner's payload while preserving losers, and generic transfer code gets two incompatible ownership models. Recovery wins before release.
- **If declined:** preserve today's Channel API and reject move-only selected sends; do not quietly claim recovery or silently copy. A separately named permanent send verb is not recommended.

## #118. David: “Can we not just reuse `parallel`?”

- **Round-0 status:** absent; the later coordinator proposed waiting gather. Round 1 endorses the existing `concurrent` keyword in a new comprehension.
- **Agreement/final answer:** **No, not while retaining `parallel`'s accepted serial-execution permission. Approve `[concurrent x in xs work(x)]`.** This reuses a construct already carrying the required task-group semantics and adds no keyword.
- **Concrete reuse and failure:**

  ```dewy
  let ch = channel<int>(1)
  step = (i:int) => if i =? 0 (ch.receive() or_throw) else {
      ch.send(42) or_throw
      0
  }
  let proposed_reuse = [parallel i in [0..2) step(i)]
  # Today: rejected because the body waits.
  # If admitted: caller-only execution may enter 0 and never reach sender 1.
  let results = [concurrent i in [0..2) step(i)] or_throw
  ```

- **The strongest one-keyword argument:** a uniform structured-concurrency contract could legitimately be named `parallel`, with compiler optimizations fusing/serializing only when progress and observable semantics are preserved. This is coherent, not impossible.
- **Exactly what it costs:** revoke unrestricted serial fallback; alter failure/cancellation/task-admission contracts; provide a suitable implementation or diagnose targets that currently run `parallel` serially. Waiting for an external independent operation may merely serialize or starve rather than deadlock, but sibling-dependent waiting gives the definite counterexample above. A physical thread-per-item implementation is not required; independently schedulable logical tasks are.
- **Why effects alone do not choose a contract:** a may-block summary does not encode sibling dependence, first-failure versus per-item errors, capacity admission, or platform support. Letting a helper acquire a blocking effect silently change all those behaviors makes public semantics unstable. Backend settings should choose implementations under a contract, not redefine it.
- **Gather contract:** finite array/range, source evaluated once, one result per iteration initially, input-order result array, first child exception cancels siblings, join before returning. `work: T | E` yields `array<T> | E | Canceled | OutOfMemory`. Preserve causal failure after cleanup; no rollback. Error records permit collecting outcomes intentionally: `[concurrent x in xs [value=work(x)]]`.
- **Admission:** never admit a bounded prefix and wait for it before admitting tasks it may depend on. Maintain schedulable logical tasks or fail admission, cancel and join. Strict settings must also account for result storage, stacks and cleanup capacity. This is not an implicit independent-work throttling mapper.
- **Unblocks/reversibility:** ordered many-task results; grammar renamable before release, progress/failure guarantees expensive to reverse. No remaining round-0/round-1 disagreement.

## #114. David: marker, same-line form, and binding order

- **Round-0 status:** absent; the later coordinator suggested `$parallel` above the declaration. Round 1 recommends automatic per-parameter inference and only an optional tag.
- **Final spelling answer:** prefer **`$parallel_safe`**, and support both placements. It precedes any binding introducer:

  ```dewy
  $parallel_safe myfn = () => 42
  $parallel_safe const apply = (xs f) => [parallel x in xs f(x)]
  $parallel_safe let local_apply = (xs f) => [parallel x in xs f(x)]
  $parallel_safe
  const apply_again = (xs f) => [parallel x in xs f(x)]
  square = (x:int) => x*x
  let ys = apply([1 2 3] @square)
  ```

- **Meaning:** request checked forwarding of callback parameters into parallel calls; derive obligations for the actual parameters used that way, not every function-valued parameter. Check race freedom, environment/argument/result transfer, disjointness, effects and hooks at the supplied callback. It is not an unchecked safety assertion or a request to schedule `myfn` in parallel. A declaration with no such obligations is harmless; tagging it must not gratuitously prevent use as a value.
- **Order/scope:** tags, optional `let`/`const`, name, optional type, `=`, initializer. Same-line and preceding-line forms are equivalent and apply to one declaration. This is a new annotation grammar here, not a claim all existing metatags already support both forms. Reassignment of a mutable callable binding must retain or revalidate its contract.
- **Where round 1 and I agree:** `$thread_safe` promises too much about arbitrary shared calls; `$parallel` sounds like scheduling. `Send`/`Sync` are value facts, `no blocks` is an invocation exclusion, and `no_effects` alone still cannot prove an environment transferable. Reuse accepted callable-contract/substitution machinery; don't invent another effect atom or blanket trust bit.
- **Remaining disagreement — strongest round-1 argument:** use of a parameter already reveals the obligation; automatic inference avoids redundant annotations, does not blanket-restrict serial callbacks, and supports ordinary higher-order composition. Carry the requirements in callable identity through wrappers, recursion, partials, values and reassignment. A mandatory tag exposes today's checker workaround.
- **Remaining disagreement — strongest explicit-first argument:** David asked for a concrete marker and its placement. Current direct-call checks already provide a conservative, comprehensible migration boundary. Requiring complete automatic forwarding and first-class callable propagation before unblocking a direct helper expands the deliverable unnecessarily. Even inference needs an explicit/exported contract story at opaque boundaries.
- **Final recommendation:** implement the checked `$parallel_safe` bridge now with per-parameter summaries; initially keep direct-call-only use for APIs with forwarding obligations until callable metadata can retain those checks. Do not silently remove `parallel_direct`. Automatic admission of untagged helpers and broader first-class support can follow; the tag can then remain optional checked documentation. This is a sequencing recommendation, not approval to weaken safety or permanently restrict all annotated functions.
- **Analysis constraint:** demand summaries only for relevant helper/callback paths, propagate parameter requirements with indexed graph state, and measure compile cost under AGENTS rule 4. Existing effect rows are reused for effects; they do not replace the separate transfer/race requirements.
- **Unblocks/reversibility:** immediate checked higher-order parallel helpers without Sloppy syntax; spelling reversible, published callable obligations need compatibility care.

## Handoff

- `decision-digest.md` is the clean decision document; all 19 items have a recommendation, example, alternative, disagreement line and unblocker, followed by a complete surface inventory. Helper names in examples are local placeholders.
- No repository files, branches, commits, implementation tests or benchmark artifacts were created. Accepted-rule/current-code gaps above are findings for the coordinator, not additional changes made in this review.
