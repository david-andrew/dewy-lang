# Round-8 paper programs: failures during cleanup

Twelve realistic programs, each written under six approaches. **Paper programs, not compiled
fixtures.** Library calls follow the model below; where a name isn't in LANGUAGE.md it is
illustrative, not a proposed public name. The write-up and scores are in [../round8.md](../round8.md).

| File | Subject |
|---|---|
| [01_buffered_write.md](01_buffered_write.md) | buffered file writes, one and two success exits |
| [02_temp_rename.md](02_temp_rename.md) | a temporary file renamed into place; forgotten `persist` |
| [03_partial_read.md](03_partial_read.md) | a socket-backed cursor read partially (`first_row`, `find`) |
| [04_transaction.md](04_transaction.md) | a transaction; early success exit; forgotten `commit` |
| [05_acquire_sequence.md](05_acquire_sequence.md) | several resources acquired in sequence; a later open fails |
| [06_moved_owner.md](06_moved_owner.md) | owners moved into an array, a record and (conditionally) a caller's array |
| [07_loop_exits.md](07_loop_exits.md) | one file per iteration, with `break` and `continue` |
| [08_generator.md](08_generator.md) | a generator owning a socket; a generator owning a writer |
| [09_own_or_borrow.md](09_own_or_borrow.md) | a helper that takes ownership versus one that borrows with `@` |
| [10_parallel.md](10_parallel.md) | parallel work owning files; a sibling canceled mid-write |
| [11_wrapper_type.md](11_wrapper_type.md) | a library type whose `$__drop__` writes a footer and closes two files |
| [12_process_scratch.md](12_process_scratch.md) | a child process and a temporary directory |

## Approaches

Every approach keeps D42 on **failure exits** (an `or_throw` that leaves, a `return` of a
failure, cancellation): a live owner's cleanup runs and its failure joins the leaving failure
with `&`, or a stack for repeats. They differ on **success exits**: fallthrough, `return v`,
`break`, `continue`, an inner block's end, reassignment.

- **(a) Implicit (11-12).** Nothing written; a failed cleanup becomes the function's result.
- **(b) Marked scope.** `} or_throw` (or `} ??<E> v`) on the owning scope covers its exits,
  function bodies included; loop bodies use round 7's `loop x in xs ({ … } or_throw)`. Unmarked:
  warning, and the failure is discarded at run time; under the strict tag (placeholder
  `$explicit_cleanup`) an error.
- **(c) Value-tied `defer`.** `defer out.close() or_throw` or `defer drop(x) or_throw` runs on
  every exit where the value is still owned; a consuming call or a move cancels it on that path.
  Missing: same warning and strict tag as (b).
- **(d) Explicit close.** `out.close() or_throw` or `drop(x) or_throw` before each success exit.
  Missing: same warning and strict tag.
- **(e) Disposition on the binding.** `let out drop or_throw = …`, parameters
  `(rows:T drop or_throw)`, or `drop ??<E> v`. Applies at every exit and reassignment of that
  binding; a move clears it. A fallible owner without a clause is an error. New grammar.
- **(f) Finish on success, clean up on failure.** Releases can't fail (library rule). An owner
  whose `$__drop__` can fail must be finished, moved or covered by a scope marker on every
  success exit; an owner with `$__abandon__` must be finished or explicitly abandoned. Both are
  compile errors. No new syntax or tag.

`drop(x)` (consume `x`, run its hook, give the hook's result) is the generic verb from the
round-8 brainstorm; (c) and (d) need it for owners without a close method. It is not in
LANGUAGE.md. (f) never needs it: a marker covers generic and collection owners.

## Library model

| Owner | Explicit finish | Implicit hook, (a)–(e) | Implicit hook, (f) |
|---|---|---|---|
| `files.open(path 'w')`: buffered `File` | `close()`: `void \| FileWriteFailed \| FileCloseFailed` | flush and close: same failures | same: this cleanup does work |
| `files.open(path 'r')`: `File` | `close()`: `void \| FileCloseFailed` | `void \| FileCloseFailed` | `void`: a release |
| `files.temp_beside(path)`: `TempFile` | `persist()`: flush, sync, rename over `path`, `void \| FileWriteFailed \| FileSyncFailed`; `discard()` | `$__abandon__`: remove the temporary, `void \| FileRemoveFailed` | `$__abandon__`: `void` (a stray temporary is a release failure, as in D44 Q6) |
| `files.temp_dir()`: `TempDir` | `remove()`: `void \| FileRemoveFailed` | remove recursively: `void \| FileRemoveFailed` | `void` |
| `net.tcp_connect(host port)`: `Socket`; a generator owning one | `close()`: `void \| SocketCloseFailed` | `void \| SocketCloseFailed` | `void` |
| `db.begin()`: `Transaction` | `commit()`: `void \| CommitFailed \| CommitFailed & RollbackFailed`; `rollback()`: `void \| RollbackFailed` | `$__abandon__`: roll back, `void \| RollbackFailed` | same |
| `spawn(program args)`: `Child` | `wait()`: `Status \| ProcessWaitFailed`; `stop()`: `void \| ProcessStopFailed` | `$__abandon__`: stop and reap, `void \| ProcessStopFailed` | same |

Failure names are D42 Q3's vocabulary. `RollbackFailed` and `ProcessStopFailed` are
`UndoFailed` (D44 Q6).

## How each program is scored

Each program ends with a table: the text each approach adds over (a); how many success exits
can produce a failure with no written source (**hidden**); how many can lose a failure with
nothing written (**lossy**); and what happens when the writer forgets the form (**forgotten**).
Aggregate scores are in round8.md.
