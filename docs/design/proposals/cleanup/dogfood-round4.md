# Dogfood round 4 — direct completion

**Recommendation:** (a) automatic block-exit completion plus (c) whole-value operations; keep narrow non-failing defer. No acquisition callbacks or new block syntax. Candidate (b), compiler-enforced finish, was reconsidered as a valid alternative and loses on normal-path ceremony, not on omission detection.

**Whole-packet floor: 3/5.** Program 14 still needs manual shared-channel close coordination, program 09 has an isolated unsupported C-packaging dependency, and program 17 has a surprising valid-state replacement-on-error policy. Those are not converted into 5s by using spsc elsewhere. Ordinary streaming cleanup no longer pays a helper/callback/context parameter; its remaining scores are 4s for implicit exit/error behavior.

These are seventeen paper programs, not compiled tests, measured usability results, runtime demonstrations or independent grades. All new stream/terminal/temp/db/game module signatures are library-contract illustrations for the language rule, not a naming ballot or claims of current module availability. Actual spawned task code and the C handle’s owning callable are genuine functions, not acquisition scopes.

Vectors are **O/D/C/S/F**: obvious, discoverable, concise, safe by default, complete. Score 5 is local to the scenario, conditional on the stated semantic/driver contract; it does not assert the current compiler implements R4. Every sub-5 Dewy grade has a program-line reason below. Every sub-5 peer grade links to its own baseline source line with dimension-specific reasons. Baselines use strong ordinary idioms or explicitly identify the required checked adapter. They are outlines, not executed foreign-language ports.

## Scorecard

| Program | Dewy | Python | Go | Rust | TypeScript | Swift |
|---|---|---|---|---|---|---|
| [01 Streaming copy / late flush](/var/home/david/dev/tmp/par9/cleanup/programs-r4/01_file_copy.dewy:1) | 4/4/5/5/4 | [5/5/5/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:7) | [4/4/3/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:8) | [4/4/3/4/4](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:9) | [4/4/4/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:10) | [4/4/3/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:11) |
| [02 TCP early return](/var/home/david/dev/tmp/par9/cleanup/programs-r4/02_tcp_early_return.dewy:1) | 5/4/5/5/5 | [5/5/5/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:12) | [5/5/5/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:13) | [5/5/5/5/5](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:14) | [4/4/4/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:15) | [4/4/4/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:16) |
| [03 Existing spsc closure](/var/home/david/dev/tmp/par9/cleanup/programs-r4/03_spsc_producer_consumer.dewy:1) | 4/4/5/5/4 | [4/4/3/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:17) | [5/5/4/3/5](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:18) | [5/5/5/5/5](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:19) | [4/4/3/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:20) | [4/4/4/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:21) |
| [04 Whole-region mutex](/var/home/david/dev/tmp/par9/cleanup/programs-r4/04_mutex_region.dewy:1) | 4/4/4/5/5 | [5/5/5/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:22) | [5/5/5/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:23) | [5/5/5/5/5](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:24) | [4/4/4/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:25) | [5/5/5/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:26) |
| [05 Raw terminal / Ctrl-C](/var/home/david/dev/tmp/par9/cleanup/programs-r4/05_terminal_ctrl_c.dewy:1) | 4/4/5/5/4 | [4/4/3/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:27) | [4/4/3/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:28) | [4/4/3/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:29) | [4/4/3/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:30) | [4/4/3/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:31) |
| [06 Temporary directory](/var/home/david/dev/tmp/par9/cleanup/programs-r4/06_temp_directory.dewy:1) | 4/4/5/5/5 | [5/5/5/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:32) | [4/4/3/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:33) | [4/4/4/4/4](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:34) | [4/4/4/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:35) | [4/4/3/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:36) |
| [07 Canceled socket task](/var/home/david/dev/tmp/par9/cleanup/programs-r4/07_canceled_socket_task.dewy:1) | 4/4/4/5/5 | [4/4/4/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:37) | [4/4/3/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:38) | [4/4/4/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:39) | [4/4/3/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:40) | [4/4/4/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:41) |
| [08 GPU/audio state](/var/home/david/dev/tmp/par9/cleanup/programs-r4/08_game_assets.dewy:1) | 4/4/5/5/4 | [4/4/3/4/4](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:42) | [4/4/3/4/4](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:43) | [5/5/4/5/4](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:44) | [4/4/3/4/4](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:45) | [4/4/4/4/4](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:46) |
| [09 C binding packaging](/var/home/david/dev/tmp/par9/cleanup/programs-r4/09_c_library_wrapper.dewy:1) | 4/4/4/4/3 | [4/4/3/4/4](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:47) | [4/4/3/4/4](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:48) | [4/4/4/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:49) | [4/4/3/4/4](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:50) | [4/4/4/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:51) |
| [10 Transaction exit outcome](/var/home/david/dev/tmp/par9/cleanup/programs-r4/10_transaction.dewy:1) | 4/4/5/5/4 | [5/5/4/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:52) | [4/4/3/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:53) | [4/4/4/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:54) | [5/5/4/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:55) | [4/4/4/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:56) |
| [11 One-off done](/var/home/david/dev/tmp/par9/cleanup/programs-r4/11_done_on_every_exit.dewy:1) | 5/5/5/4/5 | [5/5/4/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:57) | [5/5/5/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:58) | [4/4/4/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:59) | [5/5/4/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:60) | [5/5/5/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:61) |
| [12 Fallible owner aggregate](/var/home/david/dev/tmp/par9/cleanup/programs-r4/12_resource_collection.dewy:1) | 4/4/5/5/4 | [4/4/4/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:62) | [4/4/3/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:63) | [4/4/3/4/4](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:64) | [4/4/4/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:65) | [4/4/3/4/4](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:66) |
| [13 Fallible hook / both errors](/var/home/david/dev/tmp/par9/cleanup/programs-r4/13_fallible_hook.dewy:1) | 4/4/5/5/5 | [4/4/4/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:67) | [4/4/3/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:68) | [4/4/4/4/4](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:69) | [4/4/4/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:70) | [4/4/3/4/4](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:71) |
| [14 Shared-channel coordinator](/var/home/david/dev/tmp/par9/cleanup/programs-r4/14_shared_channel_coordinator.dewy:1) | 4/4/3/3/3 | [4/4/3/3/4](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:72) | [4/4/3/3/4](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:73) | [4/4/4/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:74) | [4/4/3/3/4](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:75) | [4/4/3/3/4](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:76) |
| [15 Break and continue](/var/home/david/dev/tmp/par9/cleanup/programs-r4/15_break_continue.dewy:1) | 4/4/5/5/4 | [5/5/5/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:77) | [4/4/3/4/4](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:78) | [4/4/4/4/4](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:79) | [5/5/4/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:80) | [4/4/3/4/4](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:81) |
| [16 Failed return handoff](/var/home/david/dev/tmp/par9/cleanup/programs-r4/16_return_candidate.dewy:1) | 4/4/5/5/4 | [4/4/3/4/4](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:82) | [4/4/3/4/4](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:83) | [4/4/3/4/4](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:84) | [4/4/4/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:85) | [4/4/3/4/4](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:86) |
| [17 Replacement through a place](/var/home/david/dev/tmp/par9/cleanup/programs-r4/17_replacement.dewy:1) | 3/4/5/5/4 | [4/3/3/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:87) | [4/3/3/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:88) | [4/4/3/4/4](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:89) | [4/3/3/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:90) | [4/3/3/4/4](/var/home/david/dev/tmp/par9/cleanup/comparisons-round4.md:91) |

## Every sub-5 Dewy grade

### 01 Streaming copy / late flush

- [O4, line 10](/var/home/david/dev/tmp/par9/cleanup/programs-r4/01_file_copy.dewy:10): EOF requests success, but the writer completes afterward and may replace it with failure; return is not the final observable outcome.
- [D4, line 7](/var/home/david/dev/tmp/par9/cleanup/programs-r4/01_file_copy.dewy:7): A reader must learn from the owner contract that File is scope-bound and its cleanup failures enter copy’s inferred result. Nothing spells flush at the source return.
- [F4, line 29](/var/home/david/dev/tmp/par9/cleanup/programs-r4/01_file_copy.dewy:29): Two simultaneous failures produce CleanupError rather than the original bare file-error kind. Local recovery at automatic block exit requires handling copy’s result or choosing optional explicit close first.

### 02 TCP early return

- [D4, line 5](/var/home/david/dev/tmp/par9/cleanup/programs-r4/02_tcp_early_return.dewy:5): The ordinary connect call returns a self-cleaning owner. That release property must be discovered from the type/API; there is deliberately no matching close line.

### 03 Existing spsc closure

- [O4, line 4](/var/home/david/dev/tmp/par9/cleanup/programs-r4/03_spsc_producer_consumer.dewy:4): Returning ends the sending endpoint without a written close; this is already decided spsc behavior.
- [D4, line 18](/var/home/david/dev/tmp/par9/cleanup/programs-r4/03_spsc_producer_consumer.dewy:18): The reader must select the existing single-owner queue and understand split/moves; it is not interchangeable with a shared Channel handle.
- [F4, line 25](/var/home/david/dev/tmp/par9/cleanup/programs-r4/03_spsc_producer_consumer.dewy:25): Fail-fast failure may cancel the consumer before processing every accepted value. Automatic close provides termination, not processing completion on failed work.

### 04 Whole-region mutex

- [O4, line 11](/var/home/david/dev/tmp/par9/cleanup/programs-r4/04_mutex_region.dewy:11): The call statement retains the lending guard through tail I/O even after update_ledger’s final field access.
- [D4, line 11](/var/home/david/dev/tmp/par9/cleanup/programs-r4/04_mutex_region.dewy:11): Using the existing lending call for a whole region is less discoverable than reading a lexical lock/with region.
- [C4, line 3](/var/home/david/dev/tmp/par9/cleanup/programs-r4/04_mutex_region.dewy:3): A named protected-operation helper is still needed for this region under last-use loans. It is ordinary program factoring, not an acquisition callback, but it is real structure.

### 05 Raw terminal / Ctrl-C

- [O4, line 4](/var/home/david/dev/tmp/par9/cleanup/programs-r4/05_terminal_ctrl_c.dewy:4): The unused mode binding intentionally remains alive to the enclosing brace because restoration can fail; a last-use intuition would be wrong.
- [D4, line 15](/var/home/david/dev/tmp/par9/cleanup/programs-r4/05_terminal_ctrl_c.dewy:15): Byte-oriented input and terminal signal generation differ. Fully raw Ctrl-C is byte 3 unless ISIG is retained.
- [F4, line 16](/var/home/david/dev/tmp/par9/cleanup/programs-r4/05_terminal_ctrl_c.dewy:16): Restoration failure turns a pending cancellation into CleanupError, changing ordinary stop handling/default exit code. That visible failure is preferable to losing restoration errors, but needs explicit policy knowledge.

### 06 Temporary directory

- [O4, line 12](/var/home/david/dev/tmp/par9/cleanup/programs-r4/06_temp_directory.dewy:12): The closing brace can fail while deleting the temporary directory even after the successful archive message.
- [D4, line 5](/var/home/david/dev/tmp/par9/cleanup/programs-r4/06_temp_directory.dewy:5): temp_dir now means an owner with an owned Path, not a bare path string. Its lifetime/error contract must be known.

### 07 Canceled socket task

- [O4, line 15](/var/home/david/dev/tmp/par9/cleanup/programs-r4/07_canceled_socket_task.dewy:15): Expected child cancellation is consumed, but the caller’s own cancellation still needs the line-16 check.
- [D4, line 5](/var/home/david/dev/tmp/par9/cleanup/programs-r4/07_canceled_socket_task.dewy:5): A once-run task capture moves the owner; an ordinary reusable closure would not have the same transfer permission.
- [C4, line 14](/var/home/david/dev/tmp/par9/cleanup/programs-r4/07_canceled_socket_task.dewy:14): stop, wait with selected cancellation handling, and caller check are still three task-policy steps. Socket release itself adds no line.

### 08 GPU/audio state

- [O4, line 12](/var/home/david/dev/tmp/par9/cleanup/programs-r4/08_game_assets.dewy:12): The engine borrows Level across its real loop; setup-local assets cannot be assumed to survive return from main.
- [D4, line 16](/var/home/david/dev/tmp/par9/cleanup/programs-r4/08_game_assets.dewy:16): Drop retires assets while GPU submissions/voices retain physical storage. It does not mean immediate free or stop.
- [F4, line 17](/var/home/david/dev/tmp/par9/cleanup/programs-r4/08_game_assets.dewy:17): The native backend must reserve retirement bookkeeping and correctly retain fence/voice references. This paper program specifies that dependency, not a completed driver implementation.

### 09 C binding packaging

- [O4, line 20](/var/home/david/dev/tmp/par9/cleanup/programs-r4/09_c_library_wrapper.dewy:20): The public handle is a callable owning a private native carrier, less direct than a familiar nominal Regex object.
- [D4, line 11](/var/home/david/dev/tmp/par9/cleanup/programs-r4/09_c_library_wrapper.dewy:11): Safe hiding of the carrier depends on a local-helper/encapsulation facility outside the main cleanup design.
- [C4, line 4](/var/home/david/dev/tmp/par9/cleanup/programs-r4/09_c_library_wrapper.dewy:4): The ABI declarations, error/offset buffers and private capture are one-time binding ceremony.
- [S4, line 6](/var/home/david/dev/tmp/par9/cleanup/programs-r4/09_c_library_wrapper.dewy:6): The free row is a reviewed unsafe claim for the default allocator, not a theorem implied by C void. Strict proof mode cannot accept an unproved native claim.
- [F3, line 33](/var/home/david/dev/tmp/par9/cleanup/programs-r4/09_c_library_wrapper.dewy:33): The current reader rejects the local nominal hook. R4 deliberately does not recommend that extension as part of cleanup, so this isolated safe-package route still depends on separately settled encapsulation. This is not a passing implementation or a solved packaging example.

### 10 Transaction exit outcome

- [O4, line 15](/var/home/david/dev/tmp/par9/cleanup/programs-r4/10_transaction.dewy:15): A bare successful return commits before reaching the caller, through the type’s outcome-aware completion contract.
- [D4, line 7](/var/home/david/dev/tmp/par9/cleanup/programs-r4/10_transaction.dewy:7): The reader must discover the transaction owner’s success/rollback policy, and that an ordinary stored error is not itself pending failure.
- [F4, line 20](/var/home/david/dev/tmp/par9/cleanup/programs-r4/10_transaction.dewy:20): A driver can report unknown commit state, and a later unrelated cleanup can fail after an earlier commit. Acquire dependencies in the order noted at line 22; this is not global all-or-nothing behavior for every function resource.

### 11 One-off done

- [S4, line 4](/var/home/david/dev/tmp/par9/cleanup/programs-r4/11_done_on_every_exit.dewy:4): An arbitrary omitted done action is not inferable. The retained defer is a deliberate one-off program action, not a prerequisite for resource safety; the limitation is explicit at line 14.

### 12 Fallible owner aggregate

- [O4, line 17](/var/home/david/dev/tmp/par9/cleanup/programs-r4/12_resource_collection.dewy:17): The brace completes every file and may return from main instead of reaching the next print; the failure edge is implicit.
- [D4, line 14](/var/home/david/dev/tmp/par9/cleanup/programs-r4/12_resource_collection.dewy:14): Mutable element places borrow live owner elements; array copies and implicit owner duplication are not the model.
- [F4, line 22](/var/home/david/dev/tmp/par9/cleanup/programs-r4/12_resource_collection.dewy:22): Every completion is attempted, but automatic failure exits the whole owning function. Per-file local recovery requires an explicit consuming/draining workflow; generic/owning cause preservation is also an implementation gate, not something the current no-fail-only container checker supplies.

### 13 Fallible hook / both errors

- [O4, line 20](/var/home/david/dev/tmp/par9/cleanup/programs-r4/13_fallible_hook.dewy:20): A return with no payload becomes the hook’s FlushError/CloseError pair; the final function result is not the requested success.
- [D4, line 8](/var/home/david/dev/tmp/par9/cleanup/programs-r4/13_fallible_hook.dewy:8): An existing lifecycle tag now has a fallible result contract. Readers must know its function-level error effect, unlike today’s void hook.

### 14 Shared-channel coordinator

- [O4, line 6](/var/home/david/dev/tmp/par9/cleanup/programs-r4/14_shared_channel_coordinator.dewy:6): The chosen coordinator boundary is what closes the global shared queue; the constructor does not express that role.
- [D4, line 26](/var/home/david/dev/tmp/par9/cleanup/programs-r4/14_shared_channel_coordinator.dewy:26): All copies still expose send, including the waiting receiver. Last-total-handle drop therefore cannot identify end of input.
- [C3, line 5](/var/home/david/dev/tmp/par9/cleanup/programs-r4/14_shared_channel_coordinator.dewy:5): A coordinator helper and inner join are required for the two producers before the outer consumer can finish.
- [S3, line 6](/var/home/david/dev/tmp/par9/cleanup/programs-r4/14_shared_channel_coordinator.dewy:6): This required close registration can still be forgotten; it is not an enforced finish obligation. The remaining hang is explicit at line 28.
- [F3, line 28](/var/home/david/dev/tmp/par9/cleanup/programs-r4/14_shared_channel_coordinator.dewy:28): The design does not solve automatic shared-channel closure. Existing spsc solves a narrower capability; a shared sending-lease/endpoint decision is separately optional, as requested, not silently assumed complete.

### 15 Break and continue

- [O4, line 9](/var/home/david/dev/tmp/par9/cleanup/programs-r4/15_break_continue.dewy:9): A cleanup failure prevents the apparent break and returns a failure from process instead.
- [D4, line 5](/var/home/david/dev/tmp/par9/cleanup/programs-r4/15_break_continue.dewy:5): The owner’s lifecycle contract, not a visible call at break/continue, supplies that extra exit edge.
- [F4, line 17](/var/home/david/dev/tmp/par9/cleanup/programs-r4/15_break_continue.dewy:17): There is no same-function catch of an implicit brace cleanup through an outer ?? on the block. Local recovery uses optional explicit consuming close; otherwise the caller handles process’s result.

### 16 Failed return handoff

- [O4, line 8](/var/home/david/dev/tmp/par9/cleanup/programs-r4/16_return_candidate.dewy:8): The return candidate is still pending while earlier owners complete; it is not handed off at the source return statement.
- [D4, line 4](/var/home/david/dev/tmp/par9/cleanup/programs-r4/16_return_candidate.dewy:4): An older live fallible owner can prevent transferring a later resource, even when the later resource itself is valid.
- [F4, line 16](/var/home/david/dev/tmp/par9/cleanup/programs-r4/16_return_candidate.dewy:16): The safe default destroys the withheld useful result when another completion fails. Recovering both the useful owner and a warning/error requires an explicit partial-result record/API rather than this ordinary success-or-error return.

### 17 Replacement through a place

- [O3, line 9](/var/home/david/dev/tmp/par9/cleanup/programs-r4/17_replacement.dewy:9): The call can return an old-close error while the caller already owns a different, valid file. This is substantially surprising unless the nontransactional replacement rule is known.
- [D4, line 4](/var/home/david/dev/tmp/par9/cleanup/programs-r4/17_replacement.dewy:4): Plain assignment performs fallible old cleanup and publishes a valid new owner before forwarding the old failure; that contract is not spelled at the call site.
- [F4, line 20](/var/home/david/dev/tmp/par9/cleanup/programs-r4/17_replacement.dewy:20): Error does not mean destination unchanged. Preserving the closed old handle is impossible; this policy favors valid state, while callers needing transactional publication must use a different explicit API.

## Paper path traces

| Program | Ordinary path | Hard exits / failure trace |
|---|---|---|
| 01 | Open two streams; EOF returns from copy; output then input complete; caller receives success only afterward. | Linux --flush-error prepares three buffered bytes for /dev/full; assuming setup/open succeeds, final flush returns FileError. Read failure plus output flush failure pairs; close is still attempted after flush failure. No helper/context callback remains. |
| 02 | Read header and return bytes; release the local socket after last use. | EOF/empty reply/NetError/Canceled all release the owner. No claim that local close acknowledges a protocol. |
| 03 | Producer returns at 400; receiver drains 0..399 and prints 79,800. | Existing endpoint drop closes; once-run task transfer avoids a retained sending root. Failure may stop processing early; that remains group policy. |
| 04 | Whole lending call holds the mutex through tail I/O; reset defer then unlock. | Error/Canceled returns from the protected operation, runs the reset, and releases the call-statement loan. Plain last field use would not protect the later I/O. |
| 05 | q/EOF returns from main; mode owner restores before that success is delivered. | SIGINT works because ISIG is retained; restore runs shielded and failed restore pairs with Canceled. Mode has no later read but cannot be optimized to early discard. |
| 06 | Capture tar status, return, then delete the owned temp directory/manifest. | File/child error/Canceled still attempts deletion; deletion refusal or timeout returns/joins a failure with leftover identity. No callback or cleanup timeout parameter. |
| 07 | Stop child if still running; wait joins cleanup; check the parent stop separately. | Canceled-before-entry still drops the captured stream. Bare child Canceled is expected; CleanupError is not swallowed by that selected handler. |
| 08 | Move complete Level from loader and borrow it through the engine loop. | Failed third load releases the initialized prefix; native GPU/voice references retain storage after public release. Backend contract is stated, not executed. |
| 09 | Compile default-allocator PCRE, capture its owner, query two groups, release with callable lifetime. | Native failure leaves no owner; closure construction failure cleans the initialized owner. Trusted ABI claims and the unsupported local packaging route are explicit, isolated dependencies. |
| 10 | Successful return commits via successful=true; caller receives success only after completion. | Insufficient funds/missing recipient/Canceled => rollback. Failed commit attempts rollback if active; failures pair; unknown commit state is not described as safe retry. Later independent cleanup cannot undo a completed commit. |
| 11 | One done registration prints once at scope exit. | Early return/InvalidRow/Canceled still run it. Arbitrary missing intent is not inferable. The sample has no resource whose cleanup it falsely certifies. |
| 12 | Move array/record to main; write through mutable places; the inner brace completes all files before the success print. | Failed acquisition closes initialized prefix; later completion attempts all files in reverse order; any failure exits main instead of printing success. |
| 13 | work requests void success; hook records that close was attempted. | Flush+close failures become a pair; work returns it and main can verify closed. A declared void work result would be rejected. This is an ordinary-value protocol model, not an OS adapter. |
| 14 | Inner producers join; coordinator defer closes the shared queue; consumer drains and outer join ends. | Producer failure stops/joins siblings and closes at coordinator exit. Omit the close and receiver can wait forever. Last total drop cannot help because receive holds q. |
| 15 | An empty file continues and marker byte 0 breaks after input completion. | A failing close prevents either jump and returns from process; the post-loop print is skipped. There is no callback return or resumption at the wrong statement. |
| 16 | If earlier completes, transfer result without closing it in open_result. | The specified /dev/full flush instead fails: cancel handoff, complete result once with that failure pending, retain any extra completion failure. Result may have written bytes; raw stream output is not atomic. |
| 17 | Evaluate replacement; complete old output; install new live owner. | If old completion fails, replace returns error only after publication. Caller can use the new output and forward the old error; main later completes the new owner and pairs any further failure. If RHS acquisition fails, old ownership is retained until normal unwind. |

## Adversarial rule checks (paper)

1. **Candidate (b) omission:** a successful early return before close is an error under (b), not a warning. Under recommended (a), automatic completion handles it. This distinction is shown in round4.md; omission detection was not dismissed.
2. **Cleanup cannot resume a failed return:** any failure while unwinding a return or break goes to the same enclosing function result; no later statement outside an acquisition call is resumed. Program 15 gives the direct loop case.
3. **No local block-handler illusion:** `let r = { let out = open(...) or_throw; value } ?? fallback` does not catch an implicit cleanup forward from inside the block. Explicit close gives a local recovery point; otherwise handle the function call. This is explicitly graded, not hidden.
4. **Pending return owns its result:** move the result out of its old slot before other cleanup, but keep it registered pending successful handoff. On failed handoff complete it once. Programs 12/16 exercise aggregate transfer and aborted transfer.
5. **A failed replacement must not publish an uninitialized place:** program 17 leaves a live replacement before its error is forwarded. Clear/remove leave valid structural state and attempt every removed owner. No hidden retired-resource queue.
6. **Outcome is local to this cleanup plan:** a transaction sees the pending result of its own boundary, not a global current-exception getter. An ordinary helper called during cleanup has its own function result; directly traversed owner fields and abandoned return candidates share the driver’s pending failure. Hooks receive only an ordinary bool, not a borrow/copy of that error, and preceding failures change the bit for later cleanup.
7. **Cancel once, preserve real errors:** observing the same pending Canceled does not create a spurious double-Canceled pair. Recorded native failures survive deadline expiry; immediate release still runs, no reset of the shared grace per array element, and uncooperative C is still joined.
8. **Generic/owning causes remain owned:** a file-close error after `send(job) or_throw` must retain the exact Unsent.value, not erase/drop its job to fit fixed exception storage. R4 explicitly requires lossless cause cells, concrete lifecycle descriptors and preserved qualifiers; the current fixed-storage limitation is not papered over.
9. **Shared-channel smaller rules really fail:** receive retains a bidirectional Channel; last-total-drop cannot end it. All copies expose send, so last-can-send is not a smaller library rule unless a new capability analysis is introduced. A producer function return is too early if other producers remain. Program 14 remains manual and receives 3s.
10. **Unused scope owners are intentional:** removing mode in program 05 or output in program 13 would change completion timing. No unused-local fix may silently turn them into immediately discarded temporaries.

## What changed during this round

- Removed all acquisition callbacks and the borrowed-context/file-copy helper chain. Program 01 now opens input/output in one ordinary function.
- Compared automatic (a) with compiler-enforced success-path consumption (b) and whole-value (c). Chose a+c; kept explicit close only as an optional recovery/release point.
- Chose block-exit completion rather than early completion plus a carried error. Specified return/break/continue, partial construction, aggregate cleanup, mutation, withheld return results and annotations.
- Added the optional ordinary bool hook parameter only after showing a zero-argument hook cannot select commit/rollback without remembered state. Reduced the draft’s full error argument to the single success bit actually needed; no pending-error borrow/escape machinery. Existing tag/parameter syntax, but a new semantic contract requiring approval.
- Kept current Channel/Mpmc semantics, used existing spsc for the single-owner case, and separately exposed the shared-channel question. No Sender/Receiver constructor redesign in the proposal or name packet.
- Kept C-local declaration/encapsulation work out of the main recommendation, with an explicit low completeness grade in its isolated example.
- Added semantic checks for error-payload retention, replacement validity, and temporary/return-candidate cleanup; no claim that today’s no-fail-only implementation supplies them.

## Remaining 3s and why they are not erased

Program 14’s automatic shared-channel gap requires a separate capability/protocol decision; adding that large change back into this cleanup pass would violate the requested scope reduction. Program 09’s safe packaging depends on separate encapsulation/local-type capability, which is not part of this semantic proposal. Program 17’s replacement-on-error behavior is a deliberate valid-state policy: old close is irreversible, so a failure cannot safely resurrect the old handle; requiring explicit close at every replacement would instead impose part of candidate (b). This round retains and explains those costs. The straight-line file/brace/control-flow rules themselves no longer have the callback 3s.

## Sources and limits

Local authority: decisions batches 6–8, scope-blocks/brief.md:13–17, LANGUAGE records/places/errors/channels and discussion_points.md:1193–1208. Current no-fail/local-type limits were inspected, not executed. No checkout writes, commits, GUI/audio launches, compiler tests or benchmarks.

Primary comparison references: [Python with/finally](https://docs.python.org/3/reference/compound_stmts.html#the-with-statement), [Go defer](https://go.dev/ref/spec#Defer_statements), [Rust Drop](https://doc.rust-lang.org/std/ops/trait.Drop.html) and [File close errors](https://doc.rust-lang.org/std/fs/struct.File.html), [Swift defer](https://docs.swift.org/swift-book/documentation/the-swift-programming-language/statements/), [TypeScript disposal/SuppressedError](https://www.typescriptlang.org/docs/handbook/release-notes/typescript-5-2.html). The late ENOSPC scenario uses [Linux full(4)](https://man7.org/linux/man-pages/man4/full.4.html); the native wrapper uses [PCRE2 compile](https://www.pcre.org/current/doc/html/pcre2_compile.html), [free](https://www.pcre.org/current/doc/html/pcre2_code_free.html) and [pattern info](https://www.pcre.org/current/doc/html/pcre2_pattern_info.html). These sources support the language/API facts, not the subjective numerical grades.
