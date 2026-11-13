# Independent review: cleanup round 4

Verdict: the direct-owner approach is viable, but this packet is not ready to describe as safe by default. **Two must-fix findings:** cancellation can disappear inside CleanupError, and the transaction policy treats ordinary absence/early success as permission to commit. The next most important issue is that the proposed lock workaround cannot preserve enclosing-function/loop control flow for a general protected region.

This is a paper review, not a compiler or runtime validation. Scope: round4.md, summary.md, all seventeen programs-r4 programs, and their consistency with decisions batches 3–8, D4, the ownership design, LANGUAGE.md and the original brief. Only review-round4.md and regrade-round4.md were written; no checkout edits, builds, tests, commits, delegates or benchmarks. The independent program scores were fixed before reading dogfood-round4.md. Peer-language references inform comparisons, not empirical usability claims.

## Findings

### M1 — must-fix: pairing cancellation defeats decided default propagation

**Rule:** round4.md:233–250, especially 244; cancellation policy at 268–272. Authority: docs/design/decisions.md:514–517 and 549–555; docs/LANGUAGE.md:4693–4702. Program 07:15 deliberately handles only bare Canceled, so it does not expose this broader problem.

**Concrete scenario:** save opens a buffered writer, observes Ctrl-C at a checkpoint and forwards Canceled. Its final flush then fails. The driver correctly returns CleanupError[primary=Canceled cleanup=FileError]. The caller uses `save() ?? void`, then prints a completion message and performs no further cancellation point. Ordinary `??` defaults an error-family CleanupError; its operand no longer has a top-level Canceled alternative. The same issue affects collectors and `?? return/break/continue`. The caller can continue, and potentially finish successfully, despite the decided rule that cancellation must not turn into a default or silent success. `$explicit_cancellation` also has no specified diagnostic for the wrapped case. Preserving Canceled in a cause cell preserves evidence, but does not preserve its control-flow policy.

**Suggested fix:** preserve cancellation propagation on the compiler-created cleanup envelope, including cancellation in either cause and nested pairs. Specify how an explicit handler consumes that envelope while retaining/reporting its cleanup failure, and how `$explicit_cancellation` diagnoses the operation. This can be envelope metadata; it does not require scanning arbitrary user records for errors. Alternatively, propose the relaxation of the existing cancellation rule explicitly to David. Do not claim both the current default-propagation policy and ordinary unrestricted CleanupError defaulting remain unchanged. Add the exact `save() ?? void`, collector and selective-handler cases to the acceptance matrix.

### M2 — must-fix: ordinary absence and early exits are unsafe commit authority

**Rule:** round4.md:190–205, 221, 259, 261 and 274; program 10:7–15 and 17–22. Existing `none` is an exception alternative handled by `or_throw`/`??` (LANGUAGE.md:4176–4190 and 4690–4707).

**Concrete scenario:** refactor program 10 into `transfer(...):>Receipt | none | E`. After the debit, no matching recipient is an ordinary absence, so the line corresponding to 14 returns `none`, or uses `lookup(...) ?? return none`. The transaction receives true and commits the debit without the credit. The printed program correctly returns MissingAccount instead; its safety depends on maintaining that particular error representation. Returning `[failure=MissingAccount]` as ordinary result data also commits, as does a successful early `return` abandoning the rest of an operation. A transaction acquired inside a loop body commits on a normal break/continue. `exit(0)` is another commit path under 274. A boolean makes these cases deterministic; it cannot establish that publishing the work was intended.

This is a safety objection to the default transaction policy, not a claim that program 10's existing two error branches commit. A file must release on an abandoned operation; a transaction need not publish on one. Those are different duties.

**Suggested fix:** separate guaranteed cleanup from permission to publish. At minimum, resolve absence forwarded through `or_throw`/`??` before calling it successful for transactions; the natural conservative policy is rollback on absence. Provide an ordinary transaction/whole-operation API whose default cannot commit an unfinished transfer merely because the caller returned early. A manual completion obligation, if chosen for publication, must be checked rather than silently assumed; automatic whole-value operations can cover the common path without a forgotten cleanup registration. If commit-on-every-nonfailing-exit is retained, present that as a distinct safety trade requiring David's decision, with the optional-return and early-exit examples, rather than awarding safe-by-default 5. New syntax is unnecessary to demonstrate or resolve the problem; final library spellings need their own approval if introduced.

### S1 — should-fix: the lock helper only covers factorizable operations

**Rule:** round4.md:82–106 and 256; program 04:3–11, 14–17. Existing last-use loan rule: LANGUAGE.md:1110–1161 and 3571–3587.

**Concrete scenario:** an enclosing loop takes the lock, changes the state, writes its journal, and must `break` that loop or return a result from its surrounding function while still protected. A plain brace unlocks after the last state access, before the independent journal write. Moving the region into `update_ledger` fixes the printed example, but `return` now returns from that helper and `break` cannot reach the caller's loop. Restoring the original control flow needs a returned control token or more factoring. That is precisely the friction the direct-scope constraint was intended to remove, even though a helper is not an acquisition callback.

**Suggested fix:** reconsider block-bound lifetime for mutex lending guards, using existing braces to shorten the region. Do not extend every infallible allocation automatically: distinguish protocol guards from storage owners. An existing-signature library scope guard could be explored, but making a dummy outcome parameter the only way to request a lifetime would obscure the policy. Any changed mutex lifetime is a change to the established loan rule and must be identified as such. A longer guard costs lock hold time, contention, and possibly deadlocks; expand the existing lock-order/wait checks to that interval and warn on material I/O/waits. It need not require heap registration or a runtime counter. Keep a short last-use operation where useful, but show a protected ordinary region with enclosing `return` and `break` before calling the requirement solved.

### S2 — should-fix: make mixed lifetime and generic-instance visibility a contract

**Rule:** round4.md:165–182, 205, 229, 248, 323 and 329. Examples: program 02:5–7, program 05:4, program 13:19–20.

**Concrete scenario:** a generic function takes an owning `T`, makes its final read, then performs tail work. With an infallible owner the release happens before that work; with a fallible or outcome-aware owner it happens after it and may return an error. A structural wrapper can extend its infallible siblings too. An infallible hook gaining a bool parameter also changes lifetime. The same source does not reveal which behavior applies without the concrete lifecycle contract. The prohibition on erasing summaries is correct, but there is no generic program in this packet demonstrating the resulting timing, callable conversion or diagnostics. “Active-owner summaries” also needs to say whether a union's classification is a conservative type summary or changes with narrowing.

**Suggested fix:** specify stable classification from the concrete instantiated type's conservative lifecycle summary, including union alternatives, or explicitly explain any path-dependent classification. Require generated signatures/docs/hover to show lifetime category, exact owning boundary and error union for each relevant instance. Show a generic template and two instances, a mixed aggregate, a callable conversion, and a never-read owner. Show the diagnostic on a declared result that cannot admit cleanup errors. The inferred result type tells a caller that a call can fail; it does not by itself tell a reader when an internal lock or descriptor is released. Do not rely on an optional performance warning for this semantic information. No new effect-row spelling is needed.

### S3 — should-fix: specify ownership boundaries for lifted parallel bindings

**Rule:** round4.md:167, 170–173, 223 and 323. Authority: D4 at docs/design/open_decisions.md:139; concurrency/unified/proposal-v4.md:76–89, particularly publication after item cleanup.

**Concrete scenario:** a top-level `let out = files.open(...) or_throw` inside `parallel { ... }` is visible afterward under D4. Later items and code after the parallel block use out. The initializer item cannot complete out when that item finishes. The proposal calls the owner boundary the innermost ordinary sequential block, but does not explicitly map this unusual declaration scope, item temporaries and cancellation of partially activated items onto that rule. Choosing item exit, parallel join, or the enclosing function's brace gives materially different file-completion timing. A destructor's ordinary-state writes also participate in the dependency footprints; moving them to a later boundary changes where they are ordered.

**Suggested fix:** state the boundary explicitly for lifted top-level declarations, grouped sequential items, parallel-loop/comprehension locals, and owning results/captures. A natural rule is that a lifted binding belongs to its surrounding binding scope, while an item's nonescaping locals and temporaries complete in that item. Include a program that uses the exported File after the join, plus an item failure before/after its acquisition. Generated cleanup edges and footprints must reflect the selected boundary before dependency analysis. The existing `or_throw` target in an item is already decided; do not change it to solve this lifetime question.

### S4 — should-fix: outcome-sensitive outer hooks need a dependent-field example

**Rule:** round4.md:184, 201–205 and 261–262. Existing hook-before-remaining-fields order: docs/design/ownership.md:76–91 and LANGUAGE.md:2110–2118.

**Concrete scenario:** an outcome-aware record owns a buffered audit file in one field and commits its transaction in its outer hook. The driver passes true to that hook, commits, then the file field's later flush fails. The flag was truthful about failures known so far, but not about successful completion of the record's own dependencies. “Acquire the transaction before dependent resources” does not by itself explain hook-before-fields ordering. The warning about later independent cleanups does not cover this dependent-field case.

**Suggested fix:** document that the flag is a running, ordered status, not a promise that remaining fields will complete. Demonstrate a legal wrapper that completes required fields before publication, or uses a structural composition whose last-dropped transaction component runs after its dependent fields. If completing a field explicitly inside a hook is required, show the checked consumed/live state and interaction with the outer-hook partial-move restriction. Do not silently reverse the already decided outer-hook ordering. Add a dependent-field failure case and an array with more than one outcome-aware owner; do not promise global atomicity across already completed owners.

### S5 — should-fix: demonstrate the D4 Spsc rewrite, including task capture and join

**Rule:** round4.md:278, 298 and 339; program 03:18–26. D4's existing reporter is at open_decisions.md:240–254. LANGUAGE.md:3995–4009 specifies endpoint moves; 2191–2199 limits owner captures/partial applications.

**Concrete scenario:** mechanically replacing D4's `Channel<Path>` with SpscReceiver and `@progress(completed)` with `@progress(rx)` runs into the existing restriction on partial application of owners. Simply deleting the close defer without moving the sender also leaves a reporter waiting for end-of-input. Finally, normal `main` return stops program-owned background work, so successful draining cannot be assumed without a join.

**Suggested fix:** include the full proposed D4 rewrite: move rx into a genuine once-run spawned lambda, let tx's sending duty end before waiting, and join the reporter when all reports are required. A genuine task lambda is within the accepted model; it is not an acquisition callback. Program 03's direct parallel producer/consumer is sound for one owner of each endpoint, normal early return drains, and failure cancellation need not process every accepted item. Keep shared Channel and Mpmc close/reservation semantics unchanged.

### S6 — should-fix: the C example remains incomplete on the proposed surface

**Rule/program:** program 09:11–14 and 32–35; round4.md:325. Source confirmation: compiler/dewy_reader_seed.jo:5848–5856 and tests/cases/object/local_type.err.

**Concrete scenario:** a library author copies the proposed wrapper and cannot declare its private local Code hook. The proposal explicitly excludes the extension needed to make that packaging legal. The unsafe ABI boundary is correctly marked, and the issue is honestly disclosed, but a safe working wrapper route has not been established by this example. A score of 2 for completeness better reflects that unresolved prerequisite than “mostly complete.”

**Suggested fix:** show one wrapper using an approved encapsulation facility, or mark this deliverable explicitly blocked on the separate packaging decision. Do not expose a forgeable raw-pointer owner as a safe substitute and do not expand local nominal syntax in this cleanup pass. This blocks claiming that every original case is solved; it does not block the core file/owner rule.

### S7 — should-fix: fill the semantic-approval and documentation delta precisely

**Rule:** round4.md:264–274, 300–310 and 335–339; summary.md “Rules and approval.”

**Concrete scenario:** LANGUAGE.md:3655 currently says cleanup is shielded with a 100 ms grace deadline without distinguishing normal completion. Round 4 instead gives ordinary completion unlimited normal time and starts/shares grace when cancellation is observed. That is a useful policy, but needs an explicit reconciliation rather than “keep shielding.” The existing accepted protocol in docs/design/ownership.md and docs/design/user_managed_storage.md also requires non-failing zero-argument drop; updating only LANGUAGE.md would leave contradictory design authority. Pair-aware cancellation in M1 is an additional undecided change, not already covered by saying ordinary error pairing.

**Suggested fix:** enumerate the shielding/deadline clarification, outcome definitions (including none and exit(0)), destructive mutation failure edges and pair-aware cancellation in the approval delta; identify which are changes and which are previously unspecified details. Update the two authoritative ownership protocol documents when a design is accepted. There is no new grammar in the proposed drop result/parameter forms. CleanupError and its two fields are new public names; the packet correctly admits that fresh cold readers have not tested them, so naming approval is not yet ready under the project's rule. Illustrative library factories are not claims that those APIs are already approved or implemented.

## Notes and checks that pass

### N1 — note: the central return/break/continue rule is coherent

**Rule/program:** round4.md:211–229; programs 01:10, 12:12–18, 15:5–12 and 16:4–17.

A File acquired in the loop body completes every iteration on fallthrough and on a continue. A break crosses the body owner's boundary; if that close fails, process returns the failure and does not run its post-loop print. On success the loop jump takes place normally. Owners acquired outside the loop remain outside its ordinary break cleanup; if an inner cleanup instead fails, propagation crosses the remaining function scopes too. A branch or match arm is an owning boundary for bindings local to it. Moving an owner out transfers its duty and suppresses the old-slot completion.

An outer `??` or match on a block value cannot catch the block's implicit function return; this is consistent with an explicit `or_throw` in that block. A match on the containing function call can handle the returned failure. Local recovery needs the optional explicit consuming close before the brace. This is an ergonomic cost, but is not the rejected “failed return resumes after the scope call” bug. Inferred function results must include all reachable hook, pairing and driver outcomes; incompatible written types must be rejected at the exit with acquisition notes, as the proposal requires. Suggested follow-up: make these cases, including match arms, executable acceptance tests rather than prose only.

### N2 — note: failed handoff and destructive replacement preserve ownership

**Rule/program:** round4.md:227–250; programs 12, 13, 16 and 17.

The withheld return candidate remains owned, old slots are consumed before any duplicate cleanup can occur, cleanup continues after errors, and ambiguous native close is never retried. Those are the right invariants. In program 17 the failed replacement call leaves a valid new File in the borrowed destination; old cleanup failure does not restore an irreversibly closed old handle. Publish-before-forward is a coherent nontransactional policy. It deserves visible documentation and an assignment-site effect hint. Do not grade that surprise as a missing valid-state mechanism.

Lossless owning causes, allocation refusal while pairing, cause extraction, and summaries on erased callable/container types remain implementation gates. The emergency truncation path must still dispose every unretained owning cause exactly once, including a cause whose own cleanup fails; reserve/describe that bounded path before claiming implementation completeness. The paper's explicit environmental-failure exception is preferable to pretending arbitrary pairs always fit fixed exception storage.

### N3 — note: shared-channel scope reduction is acceptable, but remains a real gap

**Rule/program:** round4.md:276–298; program 14:5–10 and 26–29.

The last-overall-handle argument is correct: a waiting receiver still holds the bidirectional Channel. Counting “send-capable” handles does not help while every handle has sending capability. Closing on every producer-helper return is too early with multiple producers, and last-actual-send cannot be inferred by a library destructor. The coordinator/defer example is correct as written and can hang when its registration is omitted. Keeping a larger endpoint/lease design separate is reasonable; saying all protocol correctness no longer needs a second step would be false. Suggested action: retain this explicit carveout and review any shared-channel capability redesign separately. No new Channel API or proof that all such hangs are diagnosed should be inferred from this review.

### N4 — note: the temp-file coverage claim overstates program 06

**Rule/program:** round4.md:258; program 06:5–9 and 13–17.

The manifest is written with a whole-value Path operation and deleted as part of its owning directory's tree. There is no separately owned temporary-file value with an independent fallible removal duty. Directory cleanup is exercised; two distinct temporary-owner completion duties are not. Suggested fix: add a separate temp-file owner within the directory and a failure ordering trace, or narrow the claim. Do not interpret the harmless copied Path as deletion authority.

## Recommendation

Keep the direct owners, ordinary control-flow targets, checked non-failing one-off defer, exactly-once cleanup plan, optional explicit close and the scoped channel exception. Resolve M1 and M2 before a safe-default recommendation. Show the direct protected-region case and the missing generic/parallel/dependent-field traces before treating the paper program set as complete design validation. Performance remains unmeasured: the proposal correctly requires instruction-count and project gates before implementation lands, and this review makes no speed claim.
