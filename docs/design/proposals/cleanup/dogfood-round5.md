# Dogfood round 5

**Floor: 2/5. The cause is program 09's completeness, which is blocked on the separate encapsulation question.** Leaving that aside, the design's own floor is **3/5**, from four kinds of program:

- the shared-channel close coordination (program 14), kept as a carve-out;
- loop jumps whose cleanup failure becomes a function return (program 15);
- the surprises of failed hand-off and replacement (programs 16 and 17);
- one generic source with two release timings (program 18).

The four review must-fix and should-fix areas now grade 5 for safety: cancellation pairs (22), transactions (10, 20, 24), lock regions (04) and temp files (06).

These are paper programs: nothing was compiled or run. The grades assume the round5.md rules work as written. Library calls such as `db.begin`, `files.open` and `stage.temp_file` are sketches of library contracts. A program that depends on an unsettled language prerequisite loses completeness (09).

The dimensions are **O** obvious, **D** discoverable, **C** concise, **S** safe by default and **K** complete. The scale:

- 5: the program meets its scenario with no material unresolved issue.
- 4: a bounded surprise or qualification.
- 3: it needs protocol knowledge, restructuring, or leaves a case open.
- 2: an important gap or a missing prerequisite.
- 1: it fails its purpose.

"Safe by default" includes ordinary edits a programmer is likely to make, not only the printed path.

## Scorecard

| Program | Dewy O/D/C/S/K | Python | Go | Rust | TypeScript | Swift |
|---|---|---|---|---|---|---|
| [01 File copy](programs-r5/01_file_copy.dewy) | 4/4/5/4/5 | 5/5/5/4/5 ¹ | 4/4/3/4/5 ¹ | 4/4/3/4/4 ¹ | 4/4/4/4/5 ¹ | 4/4/3/4/5 ¹ |
| [02 TCP early return](programs-r5/02_tcp_early_return.dewy) | 5/4/5/5/5 | 5/5/5/4/5 ¹ | 5/5/5/4/5 ¹ | 5/5/5/5/5 ¹ | 4/4/4/4/5 ¹ | 4/4/4/4/5 ¹ |
| [03 Spsc producer/consumer](programs-r5/03_spsc_producer_consumer.dewy) | 5/4/5/5/5 | 4/4/3/4/5 ¹ | 5/5/4/3/5 ¹ | 5/5/5/5/5 ¹ | 4/4/3/4/5 ¹ | 4/4/4/4/5 ¹ |
| [04 Mutex region, return and break](programs-r5/04_mutex_region.dewy) | 4/5/5/5/5 | 5/5/5/4/5 | 4/4/3/3/5 | 5/5/5/5/5 | 4/4/4/4/5 | 4/5/4/4/5 |
| [05 Terminal and Ctrl-C](programs-r5/05_terminal_ctrl_c.dewy) | 4/4/5/5/5 | 4/4/3/4/5 ¹ | 4/4/3/4/5 ¹ | 4/4/3/4/5 ¹ | 4/4/3/4/5 ¹ | 4/4/3/4/5 ¹ |
| [06 Temp dir and temp file](programs-r5/06_temp_directory.dewy) | 4/4/5/5/5 | 5/5/5/4/5 | 4/4/3/3/4 | 4/4/4/4/4 | 4/4/3/4/5 | 4/4/3/3/4 |
| [07 Canceled socket task](programs-r5/07_canceled_socket_task.dewy) | 4/4/4/5/5 | 4/4/4/4/5 ¹ | 4/4/3/4/5 ¹ | 4/4/4/4/5 ¹ | 4/4/3/4/5 ¹ | 4/4/4/4/5 ¹ |
| [08 Game assets](programs-r5/08_game_assets.dewy) | 4/4/5/5/4 | 4/4/3/4/4 ¹ | 4/4/3/4/4 ¹ | 5/5/4/5/4 ¹ | 4/4/3/4/4 ¹ | 4/4/4/4/4 ¹ |
| [09 C wrapper (blocked)](programs-r5/09_c_library_wrapper.dewy) | 3/3/3/4/**2** | 4/4/3/4/4 ¹ | 4/4/3/4/4 ¹ | 4/4/4/4/5 ¹ | 4/4/3/4/4 ¹ | 4/4/4/4/5 ¹ |
| [10 Transaction](programs-r5/10_transaction.dewy) | 5/5/5/5/5 | 4/5/5/3/5 | 5/5/4/4/5 | 5/5/5/4/5 | 4/4/4/3/5 | 4/4/4/5/5 |
| [11 Done on every exit](programs-r5/11_done_on_every_exit.dewy) | 5/5/5/5/5 | 5/5/4/4/5 ¹ | 5/5/5/4/5 ¹ | 4/4/4/4/5 ¹ | 5/5/4/4/5 ¹ | 5/5/5/4/5 ¹ |
| [12 Resource collection](programs-r5/12_resource_collection.dewy) | 4/4/5/5/5 | 4/4/4/4/5 ¹ | 4/4/3/4/5 ¹ | 4/4/3/4/4 ¹ | 4/4/4/4/5 ¹ | 4/4/3/4/4 ¹ |
| [13 Fallible hook](programs-r5/13_fallible_hook.dewy) | 4/4/5/5/5 | 4/4/4/4/5 ¹ | 4/4/3/4/5 ¹ | 4/4/4/4/4 ¹ | 4/4/4/4/5 ¹ | 4/4/3/4/4 ¹ |
| [14 Shared channel](programs-r5/14_shared_channel_coordinator.dewy) | 4/3/3/3/3 | 4/4/3/3/4 ¹ | 4/4/3/3/4 ¹ | 4/4/4/4/5 ¹ | 4/4/3/3/4 ¹ | 4/4/3/3/4 ¹ |
| [15 Break and continue](programs-r5/15_break_continue.dewy) | 3/3/5/5/5 | 5/5/5/4/5 ¹ | 4/4/3/4/4 ¹ | 4/4/4/4/4 ¹ | 5/5/4/4/5 ¹ | 4/4/3/4/4 ¹ |
| [16 Return hand-off](programs-r5/16_return_candidate.dewy) | 4/3/5/5/5 | 4/4/3/4/4 ¹ | 4/4/3/4/4 ¹ | 4/4/3/4/4 ¹ | 4/4/4/4/5 ¹ | 4/4/3/4/4 ¹ |
| [17 Replacement](programs-r5/17_replacement.dewy) | 3/3/5/4/5 | 4/3/3/4/5 ¹ | 4/3/3/4/5 ¹ | 4/4/3/4/4 ¹ | 4/3/3/4/5 ¹ | 4/3/3/4/4 ¹ |
| [18 Generic owner](programs-r5/18_generic_owner.dewy) | 3/4/5/5/5 | 4/4/4/4/5 | 4/4/4/4/4 | 5/5/5/4/4 | 4/4/4/4/5 | 4/4/4/4/4 |
| [19 Lifted parallel binding](programs-r5/19_parallel_lifted.dewy) | 4/4/5/5/5 | 4/4/3/4/5 | 4/4/3/4/4 | 4/4/4/4/4 | 4/4/4/4/5 | 4/4/4/4/4 |
| [20 Transaction exits](programs-r5/20_transaction_exits.dewy) | 4/4/4/5/5 | 4/4/5/2/4 | 4/4/4/4/5 | 5/4/5/4/5 | 4/4/4/3/4 | 4/4/4/4/4 |
| [21 D4 capture](programs-r5/21_d4_capture.dewy) | 4/4/5/5/5 | 4/4/3/3/5 | 5/5/4/4/5 | 5/5/5/5/5 | 4/4/3/4/4 | 4/4/4/4/5 |
| [22 Cancellation pair](programs-r5/22_cancellation_pair.dewy) | 4/4/5/5/5 | 4/4/5/3/4 | 4/4/3/4/5 | 3/3/3/4/3 | 4/4/4/3/4 | 4/4/4/3/4 |
| [23 Child process](programs-r5/23_child_process.dewy) | 4/4/5/5/5 | 4/4/4/4/5 | 4/4/3/3/5 | 4/4/3/2/4 | 4/4/3/3/4 | 4/4/3/3/4 |
| [24 Dependent fields](programs-r5/24_dependent_fields.dewy) | 4/3/4/5/5 | 4/4/4/3/5 | 4/4/3/4/5 | 5/4/4/4/4 | 4/4/3/4/4 | 4/4/3/4/4 |

¹ The program is unchanged from round 4, so its peer vectors are carried over from [comparisons-round4.md](comparisons-round4.md), which gives the idiom behind each one. New and revised programs are compared below.

## Every Dewy score below 5

### 01 File copy: 4/4/5/4/5

- **O4, [line 10](programs-r5/01_file_copy.dewy):** the EOF `return` asks for success, but `output`'s flush can still replace it with a failure.
- **D4, [line 7](programs-r5/01_file_copy.dewy):** that `output` is held and that its completion enters `copy`'s result comes from the File contract. The hover and inlay on lines 33–39 show it in an editor; a plain-text review does not.
- **S4, [line 11](programs-r5/01_file_copy.dewy):** a streaming write can leave a partial target on a later failure. The atomic route is whole-value `write_bytes`. No error is lost.

### 02 TCP early return: 5/4/5/5/5

- **D4, [line 5](programs-r5/02_tcp_early_return.dewy):** that the socket releases itself, with no close line, is a library contract a reader has to learn.

### 03 Spsc: 5/4/5/5/5

- **D4, [line 18](programs-r5/03_spsc_producer_consumer.dewy):** automatic close comes only with the spsc ends. A programmer who reaches for `channel` gets explicit close instead (program 14).

### 04 Mutex region: 4/5/5/5/5

- **O4, [lines 6 and 10](programs-r5/04_mutex_region.dewy):** a reader who knows release owners drop at their last use may expect the guard to drop at line 10 as well. Guards hold to line 13. The hover on line 25 says so, and the rule matches Rust and Python, but the two categories still differ in Dewy.

Why the rest are 5:

- **D5:** the plain block works.
- **C5:** no helper function is needed.
- **S5:** the default is the protected, longer hold. The deadlock checks cover the whole interval, and waits past the last use warn.
- **K5:** enclosing `break` (line 7), `return` (line 12), per-iteration unlock (line 13) and shortening with braces (lines 19–22) are all shown.

### 05 Terminal and Ctrl-C: 4/4/5/5/5

- **O4, [line 4](programs-r5/05_terminal_ctrl_c.dewy):** `mode` is never read and still lives to the brace, because its restoration can fail.
- **D4, [line 15](programs-r5/05_terminal_ctrl_c.dewy):** whether Ctrl-C arrives as a cancellation or as byte 3 depends on the `signals` mode.

### 06 Temp directory and temp file: 4/4/5/5/5

- **O4, [line 12](programs-r5/06_temp_directory.dewy):** the closing brace can fail twice (two removals). The print on line 15 now runs only after both succeed, which fixes round 4's early "archive complete".
- **D4, [line 7](programs-r5/06_temp_directory.dewy):** `stage.temp_file` returns deletion authority, while the `Path` on line 6 is plain text. The reader must know which values own deletion.

Why K is now 5: there are two independent owners, the order of their completion is traced, all four failure combinations and Ctrl-C are covered (lines 17–25), and the program publishes atomically (line 11).

### 07 Canceled socket task: 4/4/4/5/5

- **O4, [lines 15–16](programs-r5/07_canceled_socket_task.dewy):** consuming the child's `Canceled` still needs a separate check for the caller's own cancellation.
- **D4, [line 5](programs-r5/07_canceled_socket_task.dewy):** ownership moves through a once-run task capture, not through an ordinary closure.
- **C4, [lines 14–16](programs-r5/07_canceled_socket_task.dewy):** stop, a selective wait and a checkpoint are three explicit task actions.

With M1 fixed, `??<Canceled>` on line 15 provably cannot swallow a failed socket cleanup.

### 08 Game assets: 4/4/5/5/4

- **O4, [line 12](programs-r5/08_game_assets.dewy):** the state lasts through the game loop only because the borrow covers it.
- **D4, [lines 16–18](programs-r5/08_game_assets.dewy):** asset owners release at their last use, but fences and voices keep the physical storage longer.
- **K4, [line 17](programs-r5/08_game_assets.dewy):** the retirement bookkeeping is stated as a backend duty and is not exercised here.

### 09 C wrapper: 3/3/3/4/2 (blocked)

- **O3, [lines 20–30](programs-r5/09_c_library_wrapper.dewy):** a callable that privately owns the regex is less direct than an opaque type.
- **D3, [lines 11–14](programs-r5/09_c_library_wrapper.dewy):** hiding the carrier needs an encapsulation facility that is not settled.
- **C3, [lines 3–26](programs-r5/09_c_library_wrapper.dewy):** there is substantial one-time wrapper structure.
- **S4, [line 6](programs-r5/09_c_library_wrapper.dewy):** the no-fail free is a reviewed unsafe claim about the ABI.
- **K2, [lines 33–35](programs-r5/09_c_library_wrapper.dewy):** **blocked.** The local nominal hook is rejected today, and fixing that is outside this design. The header (line 1) marks the program blocked, so it is not counted as a solved case.

### 10 Transaction: 5/5/5/5/5

None of the five dimensions is below 5:

- **O5:** `tx.commit()` (line 13) is the visible publication, and every other exit rolls back.
- **D5:** begin and commit is the universal transaction shape. Forgetting it gets warnings, both "never committed" and the per-exit one.
- **C5:** there is no defer and no flag.
- **S5:** the review's `return none` case (line 11) rolls back, as do wrapped errors returned as data, early returns, jumps and `exit(0)`. Nothing is published without the explicit step.
- **K5:** COMMIT failure, rollback failure and the unknown COMMIT outcome are each specified (lines 22–28).

### 11 Done on every exit: 5/5/5/5/5

One registration, checked as non-failing. No resource depends on it.

### 12 Resource collection: 4/4/5/5/5

- **O4, [line 17](programs-r5/12_resource_collection.dewy):** the inner brace can forward a failure and skip line 18.
- **D4, [line 14](programs-r5/12_resource_collection.dewy):** the reader needs the rules for element places and aggregate ownership.

### 13 Fallible hook: 4/4/5/5/5

- **O4, [line 20](programs-r5/13_fallible_hook.dewy):** the `void` return is replaced by the hook's pair.
- **D4, [line 8](programs-r5/13_fallible_hook.dewy):** a hook whose result affects the function's result is an extension of the existing hook that has to be learned.

### 14 Shared channel: 4/3/3/3/3

- **O4, [line 6](programs-r5/14_shared_channel_coordinator.dewy):** the coordinator's exit is what signals end of input.
- **D3, [lines 26–29](programs-r5/14_shared_channel_coordinator.dewy):** every handle can send, so a last-drop rule cannot work.
- **C3, [lines 5–10](programs-r5/14_shared_channel_coordinator.dewy):** a helper, a nested join and a remembered `defer` are all needed.
- **S3, [line 6](programs-r5/14_shared_channel_coordinator.dewy):** deleting the close can hang the consumer, and nothing proves the omission.
- **K3, [lines 28–29](programs-r5/14_shared_channel_coordinator.dewy):** automatic shared close is out of scope. This is the carve-out the review accepted.

### 15 Break and continue: 3/3/5/5/5

- **O3, [lines 7 and 9](programs-r5/15_break_continue.dewy):** a loop jump becomes a function return when the close fails, which skips line 12.
- **D3, [line 5](programs-r5/15_break_continue.dewy):** that exit edge comes from the File contract, not from anything at the jump.

### 16 Return hand-off: 4/3/5/5/5

- **O4, [line 8](programs-r5/16_return_candidate.dewy):** `return result` has not transferred `result` yet.
- **D3, [lines 4–8](programs-r5/16_return_candidate.dewy):** a failure of `earlier` cancels the hand-off and completes a valid result.

### 17 Replacement: 3/3/5/4/5

- **O3, [lines 9–12](programs-r5/17_replacement.dewy):** a failed `replace` has already changed which file the caller owns.
- **D3, [line 4](programs-r5/17_replacement.dewy):** plain assignment hides a completion, a publication and a failure edge.
- **S4, [lines 11–12](programs-r5/17_replacement.dewy):** recovering needs knowledge that the mutation was not transactional.

### 18 Generic owner: 3/4/5/5/5

- **O3, [line 6](programs-r5/18_generic_owner.dewy):** the same source releases `source` before the append (socket) or after it (file), and only the instance tells which. The behaviour is fixed and shown, but it cannot be read from the generic's text.
- **D4, [line 5](programs-r5/18_generic_owner.dewy):** the hover lists one line per instance (lines 24–31). A reader without an editor sees nothing.

Why S and K are 5: the declared-result diagnostic (lines 11–12 and 33–36), the callable's type (line 16) and the never-read owner (line 18) are specified, and a union takes its most conservative alternative.

### 19 Lifted parallel binding: 4/4/5/5/5

- **O4, [lines 11 and 15](programs-r5/19_parallel_lifted.dewy):** `out` completes at the end of the block around the `parallel`, not at the end of its item. This follows D4's unusual binding scope.
- **D4, [line 11](programs-r5/19_parallel_lifted.dewy):** the boundary cannot be seen at the declaration; the hover shows it.

### 20 Transaction exits: 4/4/4/5/5

- **O4, [line 15](programs-r5/20_transaction_exits.dewy):** `return none` after a change rolls back silently, while a value return after a change warns (line 8). The difference has to be learned.
- **D4, [line 7](programs-r5/20_transaction_exits.dewy):** the warning's fix-it teaches that `tx.rollback()` marks an intended abandon.
- **C4, [lines 7 and 23](programs-r5/20_transaction_exits.dewy):** intended rollbacks on success-shaped exits need an explicit call to silence the warning. That call is optional for safety but is real ceremony.

### 21 D4 capture: 4/4/5/5/5

- **O4, [line 38](programs-r5/21_d4_capture.dewy):** the queue closes when `completed` is dropped at its last use, and no line says so. The same holds for Rust's sender.
- **D4, [line 34](programs-r5/21_d4_capture.dewy):** a once-run lambda is needed because `@progress(reports)` would partially apply an owner.

### 22 Cancellation pair: 4/4/5/5/5

- **O4, [line 18](programs-r5/22_cancellation_pair.dewy):** `?? void` forwards a `CleanupError` when it carries `Canceled`. This extends the existing "`??` never eats Ctrl-C" rule, but the value's type is `CleanupError`.
- **D4, [line 14](programs-r5/22_cancellation_pair.dewy):** consuming a carrying pair means naming both `Canceled` and `CleanupError`.

### 23 Child process: 4/4/5/5/5

- **O4, [line 11](programs-r5/23_child_process.dewy):** this `return` stops the server. That is the intent here, but the drop's stop policy has to be known.
- **D4, [line 12](programs-r5/23_child_process.dewy):** knowing to call `server.stop()` explicitly in order to see a stop failure is learned from the warning.

### 24 Dependent fields: 4/3/4/5/5

- **O4, [lines 7–8](programs-r5/24_dependent_fields.dewy):** audit-then-commit is the program's chosen order, not something enforced.
- **D3, [line 5](programs-r5/24_dependent_fields.dewy):** a consuming method on a record is a tool for library authors; an application author has to find it.
- **C4, [lines 4–10](programs-r5/24_dependent_fields.dewy):** the record plus its method is extra structure. Two plain bindings with `audit.close() or_throw; tx.commit() or_throw` would do the same inline.

## Peer comparisons for new and revised programs

Each entry is a short idiom with the reasons for any score below 5. These are outlines, not executed ports.

**04 mutex region.**

- **Python:** `with lock:` holds the lock to the block end, and `break` and `return` work. S4: `lock.acquire()` without `with` is possible.
- **Go:** `defer mu.Unlock()` holds to the end of the function, so a loop needs a closure or a manual `Unlock` before each `break` or `return` (C3, S3).
- **Rust:** a `MutexGuard` lasts to the end of its scope, and `drop(guard)` shortens it.
- **TypeScript:** a single-threaded mutex adapter with `using` (O/D/C/S 4).
- **Swift:** `lock.lock(); defer { lock.unlock() }` in the loop body works, but the `defer` must be remembered (S4). `withLock` cannot `break` the caller's loop (C4).

**06 temp directory and file.**

- **Python:** `TemporaryDirectory` with `NamedTemporaryFile(dir=...)` raises cleanup failures. S4: the programmer has to opt in with `with`.
- **Go:** `MkdirTemp` with `defer os.RemoveAll` ignores the error unless the result is joined (C3, S3, K4).
- **Rust:** dropping a `tempfile` value ignores the error, and only `.close()` reports it (S4, K4).
- **TypeScript:** `mkdtemp` plus `finally` or an `await using` adapter (C3).
- **Swift:** `defer { try? removeItem }` discards failures (C3, S3, K4).

**10 transaction.**

- **Python:** sqlite3's `with conn:` commits on any exit without an exception, early return included. That is the review's M2 problem (S3).
- **Go:** `defer tx.Rollback()` plus an explicit `Commit` is safe but must be remembered (C4, S4).
- **Rust:** a rusqlite or sqlx `Transaction` rolls back on drop and commits explicitly. A forgotten commit gets no warning (S4).
- **TypeScript:** knex's callback commits when the callback resolves (S3).
- **Swift:** GRDB's explicit `.commit` and `.rollback` results inside a closure (O/D/C 4).

**18 generic owner.**

- **Rust:** consistent scope-end drop for any `T`, but close errors are lost (S4, K4).
- **Python:** duck typing plus `with`, which requires context-manager support (4s).
- **Go:** an `io.ReadCloser` with `defer Close()` whose error is ignored (K4).
- **TypeScript:** a `Disposable` bound (4s).
- **Swift:** a protocol with `deinit`, which cannot report errors (K4).

**19 lifted parallel binding.** In all five, the file is opened before or after the concurrent part and closed by `with` or `defer`; Dewy's lifted binding is unusual but needs no restructuring.

- **Python:** `asyncio.gather` with the `with` around it (C3).
- **Go:** an `errgroup` plus a `defer` close (C3, K4).
- **Rust:** `thread::scope` (K4, close errors).
- **TypeScript:** `Promise.all` plus `await using`.
- **Swift:** `async let` plus `defer` (K4).

**20 transaction exits.**

- **Python:** `with conn:` commits on `break` and `return` (S2).
- **Go:** an explicit `Commit` with a deferred `Rollback`; there is no warning for a forgotten commit (S4).
- **Rust:** rollback on drop, with no warning per exit (D4, S4).
- **TypeScript:** commit when the callback resolves (S3).
- **Swift:** explicit per-closure results (4s).

**21 D4 capture.**

- **Python:** a queue sentinel plus `join`, where a forgotten sentinel hangs (C3, S3).
- **Go:** `close(ch)` plus a `WaitGroup` (C4, S4: the close must be remembered).
- **Rust:** dropping the mpsc sender closes the channel, then a join.
- **TypeScript:** an async queue adapter (C3).
- **Swift:** `AsyncStream`'s `continuation.finish()` must be remembered (S4).

**22 cancellation pair.**

- **Python:** a close error raised while `KeyboardInterrupt` unwinds becomes the primary exception, so `except Exception` swallows the interrupt (S3).
- **Go:** `errors.Is(err, context.Canceled)` sees through `errors.Join`, but the result policy is explicit (C3).
- **Rust:** std has no cancellation model, and an async runtime drops futures (O/D/C/K 3).
- **TypeScript:** `catch` swallows an `AbortError` inside a `SuppressedError` (S3).
- **Swift:** `try?` swallows a `CancellationError` (S3).

**23 child process.**

- **Python:** `with Popen(...)` waits rather than stops on exit (4s).
- **Go:** a forgotten `cmd.Wait` leaks the process, and a context is needed to kill it (C3, S3).
- **Rust:** dropping a `Child` neither kills nor waits, which leaves a zombie (S2).
- **TypeScript:** `child_process` needs explicit `kill` and `wait` (S3).
- **Swift:** `Process` needs explicit `terminate` and `waitUntilExit` (S3).

**24 dependent fields.**

- **Python:** nested `with conn, open(audit)` commits when the inner block exits, which is the wrong order unless the code is restructured (S3).
- **Go:** explicit ordering (C3).
- **Rust:** a struct with a consuming `publish(self)`, but drop paths lose close errors (S4, K4).
- **TypeScript:** an explicit sequence (C3).
- **Swift:** an explicit sequence (C3).

## What still keeps the floor down

- **Program 09** is blocked on encapsulation, a decision outside this design.
- **Program 14** is the shared-channel close carve-out; an endpoint or lease design would be a separate question.
- **Programs 15–17** show implicit failure edges at jumps, hand-offs and replacement. This is the price of not requiring a close at every exit; candidate (b), a compiler-enforced finish, would trade them for ceremony on every success path.
- **Program 18** has a generic whose release timing depends on the instance. Making every owner held would remove it, at the cost of holding sockets and memory longer.
