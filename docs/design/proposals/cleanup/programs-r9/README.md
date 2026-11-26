# Round-9 paper programs: written cleanup

The twelve round-8 programs rewritten under round 9's design, plus program 13, David's case of
three resources whose cleanup can each fail. **Paper programs, not compiled fixtures.** Library
names not in LANGUAGE.md (`FileReader`, `FileWriter`, `finish_sending`, `SocketReader`,
`temp_beside`, `persist`, `discard`, `temp_dir`, `drop`) are illustrative and have not been
cold-read. The write-up is [../round9.md](../round9.md).

| File | Subject | What round 9 adds |
|---|---|---|
| [01_buffered_write.md](01_buffered_write.md) | buffered file writes, one and two success exits | the writer idiom: one `defer` |
| [02_temp_rename.md](02_temp_rename.md) | temporary file renamed into place; forgotten `persist` | a leftover is a warning, unfinished work an error |
| [03_partial_read.md](03_partial_read.md) | socket-backed cursor read partially | still nothing written: a cursor owes nothing |
| [04_transaction.md](04_transaction.md) | transaction; early success exit; forgotten `commit` | `defer tx.rollback()` is errdefer by type |
| [05_acquire_sequence.md](05_acquire_sequence.md) | reader, connection, writer acquired in sequence | the written-socket fix: three ways compared |
| [06_moved_owner.md](06_moved_owner.md) | owners moved into an array, a record, a caller's array | a `defer` that a move cancels |
| [07_loop_exits.md](07_loop_exits.md) | one file per iteration, `break` and `continue` | a `defer` in a loop body (D40 Q6) |
| [08_generator.md](08_generator.md) | generators owning a socket and a writer | a generator's frame and its consumer |
| [09_own_or_borrow.md](09_own_or_borrow.md) | a helper that takes ownership versus one that borrows | unchanged rule, new idiom |
| [10_parallel.md](10_parallel.md) | parallel work owning files; a canceled sibling; a race | race losers |
| [11_wrapper_type.md](11_wrapper_type.md) | a type whose hook writes a footer and closes two files | a hook owns its fields |
| [12_process_scratch.md](12_process_scratch.md) | a child process and a temporary directory | a leftover and an abandon |
| [13_three_writers.md](13_three_writers.md) | three writers, an early `return expensive()` | David's case: five ways to fold, and timing |

## The design, (g) written cleanup

In one sentence: **implicit cleanup can't fail; cleanup that can fail is written, and the
compiler checks that every exit accounts for it.**

1. **Releases never appear.** Closing a reader, aborting a connection, unlocking, releasing a
   cursor: these can't fail, run silently, and never show up in a result, a `defer` or an error.
   A `defer` or `drop` on such a value is flagged as unneeded.
2. **What a value owes is part of its type.** The open mode picks the type:
   `files.open(path 'r')` gives a `FileReader`, which owes nothing; `'w'` and `'a'` give a
   `FileWriter`; `'rw'` gives a `File`, which owes what a writer owes. A connection is duplex and
   owes the finish of its sending side; `conn.finish_sending()` consumes it and gives back a
   `SocketReader`, which owes nothing. A record, array, closure or generator owes what it holds.
3. **Two strengths.** *Unfinished work* (a writer's flush, a transaction, a child process, an
   unpersisted temporary file, a connection's sending side): leaving it unaccounted for is a
   compile error. *Leftovers* (removing a temporary file or directory): a warning with a squiggle
   in the editor; at run time the failure is discarded. Under `$no_discarded_failures` (D44 Q7)
   a leftover is an error too.
4. **Every exit accounts for every owing value**, success and failure exits alike: it is
   finished or moved on that path, or a `defer` written above covers it.
5. **Unpublished work is decided at each success exit.** A value with `$__abandon__`
   (transaction, temporary file, child, connection) must be committed, persisted, waited for,
   finished, or explicitly abandoned at every success exit. So a `defer` on it only ever fires on
   failure exits: Zig's `errdefer`, with no second keyword. In a `defer`, such a value may only
   be abandoned (`defer tx.commit()` is an error).
6. **`defer` runs when its scope is left, after the exit's value is computed**, in reverse order,
   skipping values consumed or moved on that path. Every defer runs even if an earlier one failed.
   A defer can add a failure (`or_throw`), handle one (`??`) or discard one (`;`), but can't
   `return`, `break` or change a success value.
7. **Folding.** One failure comes back alone. Several, from the body and its defers, come back as
   an `ErrorStack` in the order they happened. `Canceled` stays outside the stack (D44).
8. **Parameters, generics, generators, tasks** follow the same rule as locals: round 9's
   "Compile-time rule".

`drop(x)` ends `x` now as leaving would (a writer flushes and closes, a transaction rolls back)
and gives back its failures. It is needed only where no named finishing method exists: arrays,
records, generators, user types.

## Automatic folding, for comparison: (g-auto)

The same type split and rules 1–5, except that on a **failure exit**, an owing value nobody
accounted for is cleaned up by its hook, and the hook's failure joins the leaving failure (D42's
current rule). Success exits are the same as in (g). Each program shows (g-auto) only where its
text differs.

## Library model

| Owner | Finish (success) | Abandon (failure exit) | Owes | Strength |
|---|---|---|---|---|
| `files.open(p 'r')`: `FileReader` | — | release | nothing | — |
| `files.open(p 'w')`, `'a'`: `FileWriter` | `close()`: flush, close; `void \| FileWriteFailed \| FileCloseFailed` | the same | flush and close | unfinished work |
| `files.open(p 'rw')`: `File` | as `FileWriter` | as `FileWriter` | as `FileWriter` | unfinished work |
| `net.tcp_connect(host port)`: `Socket` | `close()`: flush, TLS `close_notify`, FIN; `void \| SocketSendFailed \| SocketCloseFailed`. `finish_sending()`: the same, then gives a `SocketReader` | abort: reset, no `close_notify`, so the peer sees a truncation; a release | its sending side | unfinished work |
| `SocketReader`; a `db.scan` cursor | — | release | nothing | — |
| `files.temp_beside(p)`: `TempFile` | `persist(p)`: `void \| FileWriteFailed \| FileSyncFailed`; `discard()`: `void \| FileRemoveFailed` | `discard()` | publishing; removal | unfinished work; removal a leftover |
| `files.temp_dir()`: `TempDir` | `remove()`: `void \| FileRemoveFailed` | the same | removal | leftover |
| `db.begin()`: `Transaction` | `commit()`; `rollback()`: `void \| RollbackFailed` | `rollback()` | publishing; undo | unfinished work |
| `spawn(...)`: `Child` | `wait()`: `Status \| ProcessWaitFailed`; `stop()`: `void \| ProcessStopFailed` | `stop()` | waiting; undo | unfinished work |

A library type owes only for output its peer hasn't confirmed. `db.scan` sends its query and
reads the server's reply before handing out the cursor, so the cursor holds only the receiving
side. Telling the server to stop early is best effort, and a release.

## How each program is scored

Each program ends with the text added over round 8's (a) (nothing written), whether any success
exit can produce a failure with no written source (**hidden**), what forgetting the form gives,
and grades 1–5 on obvious, discoverable, concise, safe by default and complete, against Python,
Go, Rust, TypeScript and Swift.
