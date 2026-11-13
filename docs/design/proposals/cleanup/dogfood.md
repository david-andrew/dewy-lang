# Dogfood — final round 3

This is a paper design review of thirteen programs, not a compiler test, a benchmark, a usability study, or independent grading. Standard proposals and illustrative db/game APIs are defined in contracts.md. I traced the ordinary, failure, cancellation and ownership paths below, corrected the candidates, and kept the remaining costs in the grades. Nothing was executed that could open a window or play audio.

Scores are 1–5, in order **O / D / C / S / F**: obvious, discoverable, concise, safe by default, complete. Five means the strongest ordinary form for this particular cleanup case. Four is a meaningful remaining cost, not a euphemism for perfect. Foreign-language columns compare usable idioms, including checked-completion adapters where stock destructors would lose errors. Every sub-5 Dewy score is justified with a program line below; every sub-5 peer score links to an idiom outline and dimension-by-dimension reason on the cited comparisons.md line. These are subjective comparisons with explicit assumptions, not measured language rankings.

## Final scorecard

| Program | Dewy | Python | Go | Rust | TypeScript | Swift |
|---|---|---|---|---|---|---|
| [01 Streaming file copy / flush failure](/var/home/david/dev/tmp/par9/cleanup/programs/01_file_copy.dewy:1) | 4/4/4/5/4 | [5/5/5/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons.md:7) | [4/4/3/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons.md:8) | [4/4/3/4/4](/var/home/david/dev/tmp/par9/cleanup/comparisons.md:9) | [4/4/4/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons.md:10) | [4/4/3/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons.md:11) |
| [02 TCP early return](/var/home/david/dev/tmp/par9/cleanup/programs/02_tcp_early_return.dewy:1) | 5/4/5/5/5 | [5/5/5/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons.md:12) | [5/5/5/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons.md:13) | [5/5/5/5/5](/var/home/david/dev/tmp/par9/cleanup/comparisons.md:14) | [4/4/4/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons.md:15) | [4/4/4/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons.md:16) |
| [03 Producer / consumer closure](/var/home/david/dev/tmp/par9/cleanup/programs/03_channel_producer_consumer.dewy:1) | 4/4/5/5/4 | [4/4/3/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons.md:17) | [5/5/4/3/5](/var/home/david/dev/tmp/par9/cleanup/comparisons.md:18) | [5/5/5/5/5](/var/home/david/dev/tmp/par9/cleanup/comparisons.md:19) | [4/4/3/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons.md:20) | [4/4/4/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons.md:21) |
| [04 Mutex across a whole operation](/var/home/david/dev/tmp/par9/cleanup/programs/04_mutex_region.dewy:1) | 4/4/4/5/5 | [5/5/5/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons.md:22) | [5/5/5/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons.md:23) | [5/5/5/5/5](/var/home/david/dev/tmp/par9/cleanup/comparisons.md:24) | [4/4/4/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons.md:25) | [5/5/5/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons.md:26) |
| [05 Raw terminal / Ctrl-C](/var/home/david/dev/tmp/par9/cleanup/programs/05_terminal_ctrl_c.dewy:1) | 4/4/5/5/4 | [4/4/3/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons.md:27) | [4/4/3/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons.md:28) | [4/4/3/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons.md:29) | [4/4/3/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons.md:30) | [4/4/3/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons.md:31) |
| [06 Temporary directory](/var/home/david/dev/tmp/par9/cleanup/programs/06_temp_directory.dewy:1) | 4/4/5/5/5 | [5/5/5/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons.md:32) | [4/4/3/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons.md:33) | [4/4/4/4/4](/var/home/david/dev/tmp/par9/cleanup/comparisons.md:34) | [4/4/4/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons.md:35) | [4/4/3/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons.md:36) |
| [07 Canceled task owns a socket](/var/home/david/dev/tmp/par9/cleanup/programs/07_canceled_socket_task.dewy:1) | 4/4/4/5/5 | [4/4/4/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons.md:37) | [4/4/3/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons.md:38) | [4/4/4/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons.md:39) | [4/4/3/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons.md:40) | [4/4/4/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons.md:41) |
| [08 GPU / audio assets](/var/home/david/dev/tmp/par9/cleanup/programs/08_game_assets.dewy:1) | 4/4/5/5/4 | [4/4/3/4/4](/var/home/david/dev/tmp/par9/cleanup/comparisons.md:42) | [4/4/3/4/4](/var/home/david/dev/tmp/par9/cleanup/comparisons.md:43) | [5/5/4/5/4](/var/home/david/dev/tmp/par9/cleanup/comparisons.md:44) | [4/4/3/4/4](/var/home/david/dev/tmp/par9/cleanup/comparisons.md:45) | [4/4/4/4/4](/var/home/david/dev/tmp/par9/cleanup/comparisons.md:46) |
| [09 C library adapter](/var/home/david/dev/tmp/par9/cleanup/programs/09_c_library_wrapper.dewy:1) | 4/4/4/4/4 | [4/4/3/4/4](/var/home/david/dev/tmp/par9/cleanup/comparisons.md:47) | [4/4/3/4/4](/var/home/david/dev/tmp/par9/cleanup/comparisons.md:48) | [4/4/4/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons.md:49) | [4/4/3/4/4](/var/home/david/dev/tmp/par9/cleanup/comparisons.md:50) | [4/4/4/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons.md:51) |
| [10 Commit / rollback transaction](/var/home/david/dev/tmp/par9/cleanup/programs/10_transaction.dewy:1) | 4/4/5/5/4 | [5/5/4/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons.md:52) | [4/4/3/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons.md:53) | [4/4/4/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons.md:54) | [5/5/4/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons.md:55) | [4/4/4/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons.md:56) |
| [11 One-off done action](/var/home/david/dev/tmp/par9/cleanup/programs/11_done_on_every_exit.dewy:1) | 5/5/5/4/5 | [5/5/4/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons.md:57) | [5/5/5/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons.md:58) | [4/4/4/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons.md:59) | [5/5/4/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons.md:60) | [5/5/5/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons.md:61) |
| [12 Array and record ownership](/var/home/david/dev/tmp/par9/cleanup/programs/12_resource_collection.dewy:1) | 5/4/5/5/5 | [4/4/4/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons.md:62) | [4/4/3/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons.md:63) | [5/5/5/5/5](/var/home/david/dev/tmp/par9/cleanup/comparisons.md:64) | [4/4/4/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons.md:65) | [5/5/4/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons.md:66) |
| [13 Library result composition](/var/home/david/dev/tmp/par9/cleanup/programs/13_library_completion.dewy:1) | 4/4/4/5/4 | [4/4/4/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons.md:67) | [4/4/3/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons.md:68) | [4/4/4/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons.md:69) | [4/4/4/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons.md:70) | [4/4/3/4/5](/var/home/david/dev/tmp/par9/cleanup/comparisons.md:71) |

**Final Dewy floor: 4.** No 5 is awarded for current implementation status: these are proposed semantics. Program 09 and program 13 explicitly retain completeness 4 for required frontend/library capabilities, and program 08 for a specified but unimplemented driver contract. The remaining 4s include callback scope/control flow, hidden release timing, explicit aggregate errors, terminal mode details and the irreducible remembered one-off action.

## Each sub-5 Dewy score

### 01 Streaming file copy / flush failure

- [O4, line 16](/var/home/david/dev/tmp/par9/cleanup/programs/01_file_copy.dewy:16): The nested open returns only after an inner completion, and the outer open at line 28 still has to finish; the last visible write is not the end of the save.
- [D4, line 4](/var/home/david/dev/tmp/par9/cleanup/programs/01_file_copy.dewy:4): The safe streaming route is a library callback overload; readers must discover it rather than expect a File value plus destructor.
- [C4, line 7](/var/home/david/dev/tmp/par9/cleanup/programs/01_file_copy.dewy:7): copy_chunks plus copy_into (line 15) and an explicit borrowed context (line 16) are more structure than two Python with managers. Existing Path.copy_to is shorter only for an unmodified copy.
- [F4, line 30](/var/home/david/dev/tmp/par9/cleanup/programs/01_file_copy.dewy:30): A joint failure changes the top-level kind to CleanupError. A bare FileError arm at line 34 does not handle the pair, and a callback cannot directly return from main or break its outside loop.

### 02 TCP early return

- [D4, line 6](/var/home/david/dev/tmp/par9/cleanup/programs/02_tcp_early_return.dewy:6): A reader must learn that TcpStream owns local release; the release is not named in this program. It is a documented owner property, not evident from tcp_connect spelling alone.

### 03 Producer / consumer closure

- [O4, line 4](/var/home/david/dev/tmp/par9/cleanup/programs/03_channel_producer_consumer.dewy:4): A normal early return closes a sending right; the close is implicit in owner destruction rather than at a written close line.
- [D4, line 18](/var/home/david/dev/tmp/par9/cleanup/programs/03_channel_producer_consumer.dewy:18): The constructor returns two ownership capabilities, and duplicating one requires discovering consuming split instead of copying a shared Channel.
- [F4, line 26](/var/home/david/dev/tmp/par9/cleanup/programs/03_channel_producer_consumer.dewy:26): On failure, fail-fast sibling cancellation may prevent draining all accepted items. Closure is automatic, but processing completion still requires an application policy.

### 04 Mutex across a whole operation

- [O4, line 13](/var/home/david/dev/tmp/par9/cleanup/programs/04_mutex_region.dewy:13): The full-region guarantee comes from the call statement, not the last field read inside update_ledger; the reader needs the existing lending rule.
- [D4, line 13](/var/home/david/dev/tmp/par9/cleanup/programs/04_mutex_region.dewy:13): Using a named helper to pin a lending call is less discoverable than a lexical with/lock statement.
- [C4, line 4](/var/home/david/dev/tmp/par9/cleanup/programs/04_mutex_region.dewy:4): A helper function is needed to define this precise region under last-use destruction; an unused RAII guard is not a substitute.

### 05 Raw terminal / Ctrl-C

- [O4, line 13](/var/home/david/dev/tmp/par9/cleanup/programs/05_terminal_ctrl_c.dewy:13): Raw byte input and OS signal generation are independent, hence the explicit signals option.
- [D4, line 14](/var/home/david/dev/tmp/par9/cleanup/programs/05_terminal_ctrl_c.dewy:14): Without knowing that fully raw POSIX mode turns Ctrl-C into byte 3, the expected cancellation path is easy to misread.
- [F4, line 18](/var/home/david/dev/tmp/par9/cleanup/programs/05_terminal_ctrl_c.dewy:18): A failed restoration paired with Canceled is CleanupError, changing bare-cancellation matching and default exit code. Forced termination still cannot guarantee restoration.

### 06 Temporary directory

- [O4, line 11](/var/home/david/dev/tmp/par9/cleanup/programs/06_temp_directory.dewy:11): Directory deletion and cancellation-cleanup grace happen after the named callback, outside its last visible operation.
- [D4, line 15](/var/home/david/dev/tmp/par9/cleanup/programs/06_temp_directory.dewy:15): timeout here bounds cancellation-finalization grace, while within bounds the whole operation; the reused spelling has to be learned from the signature.

### 07 Canceled task owns a socket

- [O4, line 18](/var/home/david/dev/tmp/par9/cleanup/programs/07_canceled_socket_task.dewy:18): The expected child cancellation is consumed locally, but line 19 still checks a concurrent cancellation of the parent.
- [D4, line 15](/var/home/david/dev/tmp/par9/cleanup/programs/07_canceled_socket_task.dewy:15): Only the scheduler once-run body can move this captured owner onward. An ordinary reusable callable is not interchangeable.
- [C4, line 17](/var/home/david/dev/tmp/par9/cleanup/programs/07_canceled_socket_task.dewy:17): stop, wait with selected cancellation handling, and caller check are three lines of necessary task policy, even though socket release itself needs no line.

### 08 GPU / audio assets

- [O4, line 14](/var/home/david/dev/tmp/par9/cleanup/programs/08_game_assets.dewy:14): The game engine borrows the Level across its whole loop; a setup-local that main never used again would not do this.
- [D4, line 18](/var/home/david/dev/tmp/par9/cleanup/programs/08_game_assets.dewy:18): Drop retires a GPU asset, and line 19 describes playback-owned audio memory. Neither is just an immediate free or stop operation.
- [F4, line 18](/var/home/david/dev/tmp/par9/cleanup/programs/08_game_assets.dewy:18): Correct native release still depends on the backend retaining in-flight submission/voice references and reserving retirement bookkeeping. This is specified, not demonstrated by executable driver code here.

### 09 C library adapter

- [O4, line 22](/var/home/david/dev/tmp/par9/cleanup/programs/09_c_library_wrapper.dewy:22): A callable is the owning public handle so the native owner stays in a private capture; this is less direct than a familiar nominal Regex object.
- [D4, line 12](/var/home/david/dev/tmp/par9/cleanup/programs/09_c_library_wrapper.dewy:12): The author needs local nominal lifecycle declarations and closure ownership to hide a forgeable raw representation without a new private/opaque spelling.
- [C4, line 4](/var/home/david/dev/tmp/par9/cleanup/programs/09_c_library_wrapper.dewy:4): The ABI declarations, offset/error buffers (lines 16–20), trusted free row (line 6) and callable factory are real binding ceremony, paid once.
- [S4, line 6](/var/home/david/dev/tmp/par9/cleanup/programs/09_c_library_wrapper.dewy:6): No-panics/no-allocation/no-blocking is an unsafe C claim for the default allocator, not a proof derived from C void. The strict no-trusted-library lane cannot accept it unproved.
- [F4, line 37](/var/home/david/dev/tmp/par9/cleanup/programs/09_c_library_wrapper.dewy:37): Reader-source inspection confirms local nominal types/methods are currently rejected (round3.md addendum). This proposal therefore adds closed local nominal lifecycle declarations using the existing declaration form. That frontend capability is unimplemented; without it the C example remains an unsafe adapter.

### 10 Commit / rollback transaction

- [O4, line 15](/var/home/david/dev/tmp/par9/cleanup/programs/10_transaction.dewy:15): The transaction call commits on body success even though transfer itself contains only execute statements and ordinary returns.
- [D4, line 10](/var/home/david/dev/tmp/par9/cleanup/programs/10_transaction.dewy:10): Returning InsufficientFunds rolls back; returning a successful record containing an error would not. The policy is the callback outcome, not a search through nested data.
- [F4, line 19](/var/home/david/dev/tmp/par9/cleanup/programs/10_transaction.dewy:19): CommitUnknown is a genuine distributed/driver uncertainty, not proof that a failed call changed nothing. Driver contracts, paired rollback errors and retry policy remain visible concerns.

### 11 One-off done action

- [S4, line 4](/var/home/david/dev/tmp/par9/cleanup/programs/11_done_on_every_exit.dewy:4): This deliberately remains an action the author can forget. There is no resource acquisition/type protocol from which the compiler can infer that printing done is required. The missing-action fact is explicit at line 15.

### 12 Array and record ownership

- [D4, line 12](/var/home/david/dev/tmp/par9/cleanup/programs/12_resource_collection.dewy:12): Stable iteration borrows an owning socket element. That must be learned from resource-array iteration rules; a copyable-array intuition would be wrong.

### 13 Library result composition

- [O4, line 13](/var/home/david/dev/tmp/par9/cleanup/programs/13_library_completion.dewy:13): The joint failure is a new top-level kind; it is not the original error with invisible extra state.
- [D4, line 12](/var/home/david/dev/tmp/par9/cleanup/programs/13_library_completion.dewy:12): none is a successful callback result even though it belongs to exception; classification requires this explicit branch.
- [C4, line 8](/var/home/david/dev/tmp/par9/cleanup/programs/13_library_completion.dewy:8): The ordinary generic helper and paired error type replace hidden unwinding semantics, at a one-time library cost.
- [F4, line 27](/var/home/david/dev/tmp/par9/cleanup/programs/13_library_completion.dewy:27): The actual acquisition overload must infer the callback result without contextual void erasure, and the real adapter must implement disarming/continuing finalization. The commented OS skeleton is not executable proof of either.

## Paths traced (paper, not execution)

| Program | Normal path | Failure / early-exit / ownership check |
|---|---|---|
| 01 | Read EOF returns to inner open; close input; then flush/close output before main gets success. Linux --flush-error buffers a three-byte copy to /dev/full and gets a late ENOSPC on completion (paper trace). | Acquisition/read/write/flush/close failures are distinct; failed flush still closes; body + flush + close all survive as nested pairs. Context cannot escape; failed finalization destroys a withheld owning result. |
| 02 | Header read returns bytes; socket releases after its last use. | EOF and empty reply return early; network errors/Canceled forward with no release line. Sending does not imply peer receipt. |
| 03 | Producer returns at 400; drain 0..399, total 79,800; last-sender close is observed before successful join. | Sender is moved, not copied; cancellation before task start still drops captures. On producer failure, consumer may be canceled rather than drain. Outstanding Reserved capability delays close. |
| 04 | Lock held throughout update_ledger call, including tail filesystem I/O; flag-reset defer precedes unlock. | On or_throw/Canceled, helper defer resets flag, then call-statement loan releases. Equivalent let-place + last state access would unlock too early. |
| 05 | q/EOF ends callback; restore prior mode; then return success. | Real SIGINT requires signals=true; restore is shielded; restore failure + cancellation becomes CleanupError. Acquisition half-failure also restores saved state. |
| 06 | Build temporary manifest/archive, then remove directory tree. | Child failure, file error or cancellation still finalize; blocked deletion reports leftover path; timeout is cancellation-finalization grace only, and cooperative; uncanceled normal completion has no added deadline. Nonreturning panic uses emergency backstop, not normal callback result. |
| 07 | Child can finish before stop; stop is idempotent, wait joins. | Stop wakes socket receive; child capture retains socket through wait cleanup; expected child cancellation is handled without swallowing parent cancellation. Canceled-before-start owns the capture too. |
| 08 | Return complete Level by move; engine borrows it for the loop; retire resources after it returns. | Failure on second/third load drops only the completed prefix; GPU submissions/voices retain storage; dropping a playback observer does not stop sound. |
| 09 | Compile PCRE2 with default allocator, move Code into callable; capture-count query returns 2; callable drop frees it. | Null compile result leaves no Code; closure construction failure cleans initialized owner; raw helper is lexically inaccessible to caller; trusted ABI assumptions are explicit; local nominal hooks require the documented frontend extension. |
| 10 | Two affected rows => commit before reporting success. | Insufficient funds/missing recipient/execute failure => rollback; rollback failure pairs; failed/uncertain commit is not described as safe-to-retry rollback. A record containing an error is not automatically failure. |
| 11 | Register once and print done at scope exit. | Early return at stop, InvalidRow or Canceled all run the action. If the declaration is omitted, no type evidence can infer the missing intention. |
| 12 | Move completed array into Peers, move Peers into probe; borrow each element for send/receive. | Failed third connect cleans prior two; EOF break only crosses loop body; or_throw releases the owning aggregate; return does not release the transferred result. |
| 13 | Success + successful finish returns exact result; none remains success. | Error + success returns exact error; success + failure returns failure; two failures pair; nested finalizers attempt all resources; contextual void must not erase callback failure. |

## Rejected negative examples

```dewy
# Not a block-end guard: an otherwise unused owner dies at last use.
let done = DoneGuard
perform_work()

# Not a safe escape: wrapper still owns and must finish file.
files.open(path 'write' (@file:files.File) => file)

# Not an ordinary reusable capture: this would transfer its owner per call.
let repeat = () => consume(stream)
repeat()
repeat()

# New narrow-defer rule rejects escaping/failing cleanup.
defer close_that_can_fail() or_throw

# No copy hook: create multiple capabilities with consuming split.
let another = tx
use(tx)
use(another)
```

The first is semantically wrong for the intended region and needs the existing lending-call/helper pattern; it is not declared a compiler error merely for having an unused guard. The scoped owner escape and repeated transfer lack a last-use/nonescape proof. The failing defer violates the proposed summary restriction. The sender copy violates move-only ownership; one last-use transfer without the later tx read would be valid. No new warning claims to infer arbitrary program intention.

## Iterations and stopping rule

- Round 1 provisional floor **2**: a copyable sender or captured bidirectional root can keep a consumer waiting across the same callback's join; the first rule set also leaves paired failure/grace behavior unspecified. Repair rather than grade those holes away (round1.md, Channel closure and Review questions).
- Round 2 pilot floor **3**: move-only endpoints and explicit pairs repair the first issues. Inspection of the C pilot finds that curl void cleanup can run callbacks/protocol shutdown, public raw fields are forgeable, and an unused owner dies before the status print. Raw terminal Ctrl-C also needs an explicit signal-generation choice. These are actual candidate defects, not assumed passing tests.
- Round 3 floor **4**: replace the C pilot with default-allocator PCRE2 and private capture/local nominal helper; source inspection proves that local nominal hooks need a small frontend extension; make raw-mode signals explicit; use once-run task capture; keep callback result inference distinct from void-context coercion; clarify array break lifetime; replace the always-shielded finalizer prototype with ordinary resumable completion and grace only after Canceled, avoiding an unexpected normal-path 100 ms cap. The final programs and all remaining 4s are above.

The final 4s are not removed by a spelling tweak. Making callbacks support surrounding-function return/break would require rejected nonlocal block semantics; making void drops return file errors would change the hook/error system; inferring arbitrary missing done actions would invent intent. The confirmed-missing C lexical capability and driver/finalizer implementation gates need concrete compiler/library work outside this read-only design subtask. Three rounds are complete. Names still require fresh cold readers before any decision item; this review does not claim those readers ran.

## Reference scope

Language-level comparison claims are limited to the primary references linked in round1.md: Python with/exception context, Go defer, Rust File/Drop, Swift defer, Zig errdefer, C# using and TypeScript disposal/SuppressedError. The baseline outlines do not assert particular third-party library APIs exist unchanged on every platform. C API details and constants were checked against PCRE2 documentation and the installed pcre2.h; no native code was executed.
