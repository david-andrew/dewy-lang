# Independent regrade: cleanup round 4

**Floor: 2/5**, at program **09 (complete)** and program **10 (safe by default)**. The largest disagreement with the author is transaction safety: **2 versus 5**. The straight-line automatic resource cleanup is substantially stronger than the remaining transaction and guard policy.

## Method

The seventeen Dewy score vectors below were fixed before reading dogfood-round4.md. I then read the author's grades to calculate disagreements. All are paper judgments; no programs were compiled or executed. Grades assume the proposed cleanup machinery works as specified. Ordinary illustrative library APIs receive that assumption; an explicitly excluded, undecided language/encapsulation prerequisite still lowers completeness.

The five dimensions are **O** obvious, **D** discoverable, **C** concise, **S** safe by default, **K** complete. A 5 meets the scenario without a material unresolved cleanup issue; 4 has a bounded surprise, cost or qualification; 3 needs protocol knowledge, restructuring or an unresolved case; 2 has an important safety/prerequisite gap; 1 would fail its core purpose. Safety includes the default protocol under ordinary valid edits, as well as the printed happy path. This matters particularly for program 10: its existing error branches roll back correctly, but the policy it teaches silently commits a common optional-return variant.

The peer comparison is qualitative for each submitted program. The reference points are Python's lexical with/finally, Go's function-scoped defer, Rust's scope-based owners/guards, TypeScript's using/await using, and Swift's lexical defer. Application-specific adapters are identified as adapters; comparisons do not assume that every language ships an identical terminal/game/database API.

## Independent scorecard

| Program | O | D | C | S | K |
|---|---:|---:|---:|---:|---:|
| [01 File copy](/var/home/david/dev/tmp/par9/cleanup/programs-r4/01_file_copy.dewy) | 4 | 4 | 5 | 4 | 5 |
| [02 TCP early return](/var/home/david/dev/tmp/par9/cleanup/programs-r4/02_tcp_early_return.dewy) | 5 | 4 | 5 | 5 | 5 |
| [03 Spsc producer/consumer](/var/home/david/dev/tmp/par9/cleanup/programs-r4/03_spsc_producer_consumer.dewy) | 5 | 5 | 5 | 5 | 5 |
| [04 Mutex region](/var/home/david/dev/tmp/par9/cleanup/programs-r4/04_mutex_region.dewy) | 4 | 3 | 3 | 4 | 4 |
| [05 Terminal Ctrl-C](/var/home/david/dev/tmp/par9/cleanup/programs-r4/05_terminal_ctrl_c.dewy) | 4 | 4 | 5 | 5 | 5 |
| [06 Temp directory](/var/home/david/dev/tmp/par9/cleanup/programs-r4/06_temp_directory.dewy) | 4 | 4 | 5 | 5 | 4 |
| [07 Canceled socket task](/var/home/david/dev/tmp/par9/cleanup/programs-r4/07_canceled_socket_task.dewy) | 4 | 4 | 4 | 5 | 5 |
| [08 Game assets](/var/home/david/dev/tmp/par9/cleanup/programs-r4/08_game_assets.dewy) | 4 | 4 | 5 | 5 | 4 |
| [09 C library wrapper](/var/home/david/dev/tmp/par9/cleanup/programs-r4/09_c_library_wrapper.dewy) | 3 | 3 | 3 | 4 | 2 |
| [10 Transaction](/var/home/david/dev/tmp/par9/cleanup/programs-r4/10_transaction.dewy) | 3 | 3 | 5 | 2 | 3 |
| [11 Done on every exit](/var/home/david/dev/tmp/par9/cleanup/programs-r4/11_done_on_every_exit.dewy) | 5 | 5 | 5 | 5 | 5 |
| [12 Resource collection](/var/home/david/dev/tmp/par9/cleanup/programs-r4/12_resource_collection.dewy) | 4 | 4 | 5 | 5 | 5 |
| [13 Fallible hook](/var/home/david/dev/tmp/par9/cleanup/programs-r4/13_fallible_hook.dewy) | 4 | 4 | 5 | 5 | 5 |
| [14 Shared-channel coordinator](/var/home/david/dev/tmp/par9/cleanup/programs-r4/14_shared_channel_coordinator.dewy) | 4 | 3 | 3 | 3 | 3 |
| [15 Break/continue](/var/home/david/dev/tmp/par9/cleanup/programs-r4/15_break_continue.dewy) | 3 | 3 | 5 | 5 | 5 |
| [16 Return candidate](/var/home/david/dev/tmp/par9/cleanup/programs-r4/16_return_candidate.dewy) | 4 | 3 | 5 | 5 | 5 |
| [17 Replacement](/var/home/david/dev/tmp/par9/cleanup/programs-r4/17_replacement.dewy) | 3 | 3 | 5 | 4 | 5 |

## Every score below 5

### 01 File copy — 4/4/5/4/5

- **O4:** [line 10](/var/home/david/dev/tmp/par9/cleanup/programs-r4/01_file_copy.dewy:10), EOF's apparent successful return can become failure during unwinding.
- **D4:** [line 7](/var/home/david/dev/tmp/par9/cleanup/programs-r4/01_file_copy.dewy:7), the inferred File contract supplies both block retention and failure alternatives; neither is written at the return.
- **S4:** [lines 7 and 11](/var/home/david/dev/tmp/par9/cleanup/programs-r4/01_file_copy.dewy:7), direct streaming output can leave a replaced/partial target when a later write or flush fails (round4.md:254). Cleanup errors are preserved, but this is a weaker data-preservation default than the documented atomic Path write. This is not a memory-safety or lost-error allegation.

**K5:** late flush, earlier read failure plus flush failure, and close-after-flush failure are all specified. Recovering locally rather than at the function call is an ergonomic choice with an optional explicit close route, not a missing cleanup mechanism.

### 02 TCP early return — 5/4/5/5/5

- **D4:** [line 5](/var/home/david/dev/tmp/par9/cleanup/programs-r4/02_tcp_early_return.dewy:5), automatic local socket release is a library owner contract the reader must discover. Its distinction from fallible File completion is not lexical.

No second close, callback control target or graceful-peer-acknowledgment claim is needed for this scenario.

### 03 Spsc producer/consumer — 5/5/5/5/5

The parameter types identify one owning endpoint per side; split consumes the queue; ordinary return ends the producer; and the receiver drains before Closed on normal completion. The stated fail-fast cancellation caveat does not make successful end-of-input incomplete. This is an already specified ownership protocol with a direct use, so I do not deduct merely because it must be learned or because shared Channel has a different purpose.

### 04 Mutex region — 4/3/3/4/4

- **O4:** [line 11](/var/home/david/dev/tmp/par9/cleanup/programs-r4/04_mutex_region.dewy:11), the loan's full-call lifetime must cover the helper's independent tail I/O after its final state use.
- **D3:** [line 16](/var/home/david/dev/tmp/par9/cleanup/programs-r4/04_mutex_region.dewy:16), the plausible plain-block/let-place version unlocks early. Finding the helper workaround requires understanding the last-use loan rule.
- **C3:** [line 3](/var/home/david/dev/tmp/par9/cleanup/programs-r4/04_mutex_region.dewy:3), a named function is required just to express this protected extent.
- **S4:** [lines 7 and 11](/var/home/david/dev/tmp/par9/cleanup/programs-r4/04_mutex_region.dewy:7), the written helper holds the lock correctly, but routinely inlining it into an ordinary block changes protection before the journal write without a resource leak or type error.
- **K4:** [line 3](/var/home/david/dev/tmp/par9/cleanup/programs-r4/04_mutex_region.dewy:3), moving a region into this helper cannot preserve an enclosing caller return or loop break. It completes the printed operation, but not the general direct-control-flow region requirement. See review S1.

### 05 Terminal Ctrl-C — 4/4/5/5/5

- **O4:** [line 4](/var/home/david/dev/tmp/par9/cleanup/programs-r4/05_terminal_ctrl_c.dewy:4), a never-read local remains active through the brace because its restoration hook can fail, unlike an ordinary infallible owner.
- **D4:** [line 15](/var/home/david/dev/tmp/par9/cleanup/programs-r4/05_terminal_ctrl_c.dewy:15), the signals-preserving mode matters to whether Ctrl-C is cancellation or an input byte.

The exact saved-mode/partial-acquisition contract is stated, and a restoration error reaches main as a failure. This program has no default operator swallowing its resulting pair; the wider cancellation-envelope defect is review M1.

### 06 Temp directory — 4/4/5/5/4

- **O4:** [lines 11–12](/var/home/david/dev/tmp/par9/cleanup/programs-r4/06_temp_directory.dewy:11), the successful archive message precedes a closing brace that may still fail deleting temporary state.
- **D4:** [line 5](/var/home/david/dev/tmp/par9/cleanup/programs-r4/06_temp_directory.dewy:5), the factory returns deletion authority, while the manifest Path is ordinary non-owning identity text.
- **K4:** [lines 6–7 and 13](/var/home/david/dev/tmp/par9/cleanup/programs-r4/06_temp_directory.dewy:6), this covers directory-tree removal, not a separate temporary-file owner's fallible deletion. The claim at round4.md:258 that it exercises both duties is too strong. The directory-only example itself is coherent.

### 07 Canceled socket task — 4/4/4/5/5

- **O4:** [lines 15–16](/var/home/david/dev/tmp/par9/cleanup/programs-r4/07_canceled_socket_task.dewy:15), consuming expected child Canceled still requires a separate check for the caller's cancellation.
- **D4:** [line 5](/var/home/david/dev/tmp/par9/cleanup/programs-r4/07_canceled_socket_task.dewy:5), ownership relies on once-run task capture rather than an ordinary reusable closure's transfer permissions.
- **C4:** [lines 14–16](/var/home/david/dev/tmp/par9/cleanup/programs-r4/07_canceled_socket_task.dewy:14), stop, selective wait handling and caller checkpoint remain three explicit task-policy actions.

The socket itself adds no cleanup ceremony, and cancellation before task entry has an explicit capture-cleanup owner. That merits S5/K5 under the stated task contract.

### 08 Game assets — 4/4/5/5/4

- **O4:** [line 12](/var/home/david/dev/tmp/par9/cleanup/programs-r4/08_game_assets.dewy:12), keeping the state alive through the real game loop relies on this borrow covering that loop.
- **D4:** [lines 16–18](/var/home/david/dev/tmp/par9/cleanup/programs-r4/08_game_assets.dewy:16), dropping the public owner retires storage, with fences/voices extending physical lifetime; observer drop has another policy.
- **K4:** [line 17](/var/home/david/dev/tmp/par9/cleanup/programs-r4/08_game_assets.dewy:17), reserved bookkeeping and in-flight GPU/voice retention are stated backend obligations, without a concrete submission/playback path exercising their interaction in this sample.

### 09 C library wrapper — 3/3/3/4/2

- **O3:** [lines 20–30](/var/home/david/dev/tmp/par9/cleanup/programs-r4/09_c_library_wrapper.dewy:20), a callable secretly owning a native regex is less direct than an opaque resource with a named query.
- **D3:** [lines 11–14](/var/home/david/dev/tmp/par9/cleanup/programs-r4/09_c_library_wrapper.dewy:11), safely hiding the carrier needs a packaging facility that has not been settled.
- **C3:** [lines 3–26](/var/home/david/dev/tmp/par9/cleanup/programs-r4/09_c_library_wrapper.dewy:3), ABI declarations, output buffers, private carrier and returned closure are substantial one-time wrapper structure.
- **S4:** [line 6](/var/home/david/dev/tmp/par9/cleanup/programs-r4/09_c_library_wrapper.dewy:6), the trusted no-fail/no-allocation/no-blocking free contract needs a reviewed unsafe ABI claim under the stated allocator assumptions.
- **K2:** [lines 33–35](/var/home/david/dev/tmp/par9/cleanup/programs-r4/09_c_library_wrapper.dewy:33), the current local nominal hook is rejected, and the fix is explicitly outside the proposed cleanup surface. There is no demonstrated approved opaque packaging replacement. A disclosed blocking prerequisite still blocks this case.

### 10 Transaction — 3/3/5/2/3

- **O3:** [line 15](/var/home/david/dev/tmp/par9/cleanup/programs-r4/10_transaction.dewy:15), bare return publishes database changes through an invisible finalizer rather than a visible commit operation.
- **D3:** [line 7](/var/home/david/dev/tmp/par9/cleanup/programs-r4/10_transaction.dewy:7), the inferred owner type must teach commit/rollback, success classification and late failure. None of those policies is visible in the acquisition spelling.
- **S2:** [line 14](/var/home/david/dev/tmp/par9/cleanup/programs-r4/10_transaction.dewy:14), the printed MissingAccount branch rolls back, but the ordinary optional-return variant `return none` after the debit commits under round4.md:201. A wrapped error returned as data does too. The default protocol makes error representation/early control flow a publication decision. Review M2 gives the concrete transfer scenario.
- **K3:** [line 22](/var/home/david/dev/tmp/par9/cleanup/programs-r4/10_transaction.dewy:22), acquisition-order advice leaves dependent-field/outer-hook completion ordering unexercised, and the optional/early-exit publication problem remains unresolved. Unknown native commit state is honestly reported; that unavoidable driver uncertainty is not the reason for S2.

### 11 Done on every exit — 5/5/5/5/5

One explicit, infallible one-off action is appropriate here. The sample owns no resource that would become unsafe if an unrelated human intention were absent. I do not deduct a safety point solely because arbitrary desired logging cannot be inferred. The specified action runs on all controlled exits and does not certify successful completion of unrelated owners.

### 12 Resource collection — 4/4/5/5/5

- **O4:** [line 17](/var/home/david/dev/tmp/par9/cleanup/programs-r4/12_resource_collection.dewy:17), the plain inner brace can forward failure out of main and suppress the following success message.
- **D4:** [line 14](/var/home/david/dev/tmp/par9/cleanup/programs-r4/12_resource_collection.dewy:14), readers need the mutable element-place/borrow and aggregate ownership rules.

The prefix/whole aggregate move, reverse completion, all-elements-attempted rule and paired failures cover this program. A different per-file recovery interface is optional, not required for its batch-success contract.

### 13 Fallible hook — 4/4/5/5/5

- **O4:** [line 20](/var/home/david/dev/tmp/par9/cleanup/programs-r4/13_fallible_hook.dewy:20), successful void return is replaced by the finalizer's failure pair.
- **D4:** [line 8](/var/home/david/dev/tmp/par9/cleanup/programs-r4/13_fallible_hook.dewy:8), this extends an existing hook to a function-result-affecting failure contract.

As an explicit two-phase unit-error protocol model, it covers its claimed scenario. It does not claim to validate a real native adapter.

### 14 Shared-channel coordinator — 4/3/3/3/3

- **O4:** [line 6](/var/home/david/dev/tmp/par9/cleanup/programs-r4/14_shared_channel_coordinator.dewy:6), the coordinator's chosen exit is the end-of-input signal.
- **D3:** [lines 26–29](/var/home/david/dev/tmp/par9/cleanup/programs-r4/14_shared_channel_coordinator.dewy:26), send-capable receiving handles defeat the simple last-drop intuition, and the constructor expresses no close coordinator.
- **C3:** [lines 5–10](/var/home/david/dev/tmp/par9/cleanup/programs-r4/14_shared_channel_coordinator.dewy:5), a helper, nested join and remembered defer remain necessary for this pattern.
- **S3:** [line 6](/var/home/david/dev/tmp/par9/cleanup/programs-r4/14_shared_channel_coordinator.dewy:6), deleting the close registration can hang the consumer; there is no complete omission proof.
- **K3:** [lines 28–29](/var/home/david/dev/tmp/par9/cleanup/programs-r4/14_shared_channel_coordinator.dewy:28), automatic shared-channel protocol closure remains explicitly unresolved. Keeping that larger redesign separate is a reasonable scope choice, not a solution to this case.

### 15 Break/continue — 3/3/5/5/5

- **O3:** [lines 7 and 9](/var/home/david/dev/tmp/par9/cleanup/programs-r4/15_break_continue.dewy:7), a source loop jump may become a function return, skipping the apparently post-break print.
- **D3:** [line 5](/var/home/david/dev/tmp/par9/cleanup/programs-r4/15_break_continue.dewy:5), the unannotated owner's close contract supplies that exit edge without a failing call at the jump.

The rule itself is exact: per-iteration completion, normal jumps after success, full-function propagation after failed cleanup. The optional explicit close supplies local recovery; this is complete within the chosen design.

### 16 Return candidate — 4/3/5/5/5

- **O4:** [line 8](/var/home/david/dev/tmp/par9/cleanup/programs-r4/16_return_candidate.dewy:8), returning the new owner does not yet transfer it to the caller.
- **D3:** [lines 4–8](/var/home/david/dev/tmp/par9/cleanup/programs-r4/16_return_candidate.dewy:4), an older owner's later failure cancels handoff and causes completion of the otherwise valid candidate.

Exactly-once candidate disposal and retention of further failures are specified. Returning useful partial results alongside an error would be a different API contract; its absence does not make this success-or-error handoff incomplete.

### 17 Replacement — 3/3/5/4/5

- **O3:** [lines 9–12](/var/home/david/dev/tmp/par9/cleanup/programs-r4/17_replacement.dewy:9), a failed replace call can already have changed which file the caller owns.
- **D3:** [line 4](/var/home/david/dev/tmp/par9/cleanup/programs-r4/17_replacement.dewy:4), plain assignment contains an implicit destructive completion, publication and function failure edge.
- **S4:** [lines 11–12 and 20](/var/home/david/dev/tmp/par9/cleanup/programs-r4/17_replacement.dewy:11), the new file is valid, but error recovery must understand the destructive nontransactional mutation. Error does not imply unchanged external state.

The three-way ownership policy is complete: RHS failure retains the old slot, old completion failure still publishes a valid replacement, and later unwind completes the replacement exactly once. The deliberate surprise is an obviousness/default-risk deduction, not an uninitialized-state hole.

## Comparisons against all five languages

These are scenario-specific judgments using the mechanisms below. A “wrapper” means library work is required; it is not assumed built in. The Dewy scores above incorporate these comparisons, rather than assigning numbers to unwritten peer ports.

| Program | Python | Go | Rust | TypeScript | Swift |
|---|---|---|---|---|---|
| 01 Copy | with makes completion extent visible | Checked deferred error update costs ceremony | Drop lacks returned cleanup errors | using supports errors; union typing absent | Checked fallible completion needs structure |
| 02 TCP | Socket context is direct | Deferred close is short but remembered | Native ownership is equally direct | Disposable socket adapter needed | Owner/defer adapter is needed |
| 03 Spsc | Queue termination needs a protocol | Producer closes explicitly | Owned sender is a natural baseline | Single-producer endpoint adapter needed | Endpoint ownership adapter needed |
| 04 Mutex | Lexical context keeps caller control | defer keeps lock to function end | Lexical guard handles the region | Lock/disposable adapter needed | Lexical defer keeps caller control |
| 05 Terminal | Mode-restoring context adapter needed | Restore and signal policy are explicit | Guard adapter needs checked restoration | Async disposal adapter needed | Fallible restoration needs explicit handling |
| 06 Temp | Temporary-directory context is direct | Deferred checked deletion is longer | Owner deletion failures need explicit handling | Temporary-owner adapter needed | Checked deletion needs wrapper structure |
| 07 Task | Cancellation and finalization need coordination | Context, cancellation and joining are explicit | Task runtime controls cancellation policy | Abort and async-finalization need coordination | Task cancellation still needs deliberate joining |
| 08 Assets | Engine owns native retention policy | Native release wrappers still needed | RAII fits owned Level naturally | Disposable engine adapters needed | Resource owners still need backend policy |
| 09 C | Binding/context adapter has ceremony | cgo wrapper has ceremony | Private owner is a direct packaging baseline | Native binding plus disposable wrapper | Opaque native owner is a direct baseline |
| 10 Transaction | Normal-exit commit shares early-return risk | Explicit commit makes publication visible | Explicit commit makes publication visible | Success-shaped wrapper has same risk | Explicit commit/rollback can expose intent |
| 11 Done | finally is longer and clear | defer is comparably short | A scope guard adds structure | finally is longer and clear | defer is comparably short |
| 12 Collection | ExitStack adds registration | Dynamic checked-close loop needed | Container ownership composes; errors need finish | DisposableStack adds explicit registrations | Aggregate owner needs checked fallible completion |
| 13 Two failures | Exception context retains earlier failure | Pairing requires explicit result policy | Ordinary Result helper required | SuppressedError is the strongest close baseline | Explicit combined-error policy needed |
| 14 Shared channel | Explicit termination protocol remains | Close coordinator remains necessary | Owned sender capability avoids this gap | Shared queue needs termination protocol | Shared channel needs termination protocol |
| 15 Jumps | Lexical context exposes cleanup boundary | Per-iteration helper often needed | Guard extent clear; errors need finish | using exposes per-iteration disposal | Lexical defer exposes per-iteration extent |
| 16 Handoff | Ownership-transfer adapter must disarm cleanup | Deferred close must respect handoff | Move is direct; fallible finish explicit | Disposable handoff needs explicit ownership policy | Owner transfer needs checked completion policy |
| 17 Replace | Explicit replace/close adapter clarifies mutation | Explicit replace/close clarifies mutation | Rebinding alone cannot return Drop failure | Same failure policy needs an adapter | Same failure policy needs an adapter |

Dewy's strongest gains are automatic checked late errors, owning aggregate composition and eliminating per-resource close registrations. Python and TypeScript expose the lexical completion boundary more clearly. Rust is a strong owner/guard baseline, but plain Drop cannot report a returned flush/close error. Go and Swift have concise one-off defers; correctly surfacing fallible completion needs more structure. No comparator gets an automatic safety advantage from hiding a cleanup failure or committing a transaction on every normal exit.

The language facts used here come from primary references: [Python with/finally](https://docs.python.org/3/reference/compound_stmts.html#the-with-statement), [Go defer](https://go.dev/ref/spec#Defer_statements), [Rust Drop](https://doc.rust-lang.org/std/ops/trait.Drop.html) and [File's ignored close errors](https://doc.rust-lang.org/std/fs/struct.File.html), [TypeScript disposal and SuppressedError](https://www.typescriptlang.org/docs/handbook/release-notes/typescript-5-2.html), and the [Swift statement reference source](https://github.com/swiftlang/swift-book/blob/main/TSPL.docc/ReferenceManual/Statements.md#defer-statement). The grades and comparative judgments are this reviewer's inference from those mechanisms and the submitted programs.

## Differences from the author of two or more points

| Program/dimension | Author | Independent | Difference | Reason |
|---|---:|---:|---:|---|
| 10, safe by default | 5 | 2 | −3 | [Program 10:14](/var/home/david/dev/tmp/par9/cleanup/programs-r4/10_transaction.dewy:14) currently returns an error, but the proposed automatic-commit policy commits a partial transfer when the corresponding ordinary optional-return path returns none. See review M2. Author score: dogfood-round4.md:24. |

There are no other differences of two or more in the seventeen Dewy vectors. I agree with the author's explicit shared-channel floor. I assign the unsupported C packaging a lower completeness score, and give higher completeness to several fully specified ordinary success-or-error scenarios: a separate partial-result API or per-element recovery workflow is not necessary to meet their stated contracts. Program 11's arbitrary logging intent is also not a resource-safety defect.
