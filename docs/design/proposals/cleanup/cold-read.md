# Cold reads for the cleanup names

Three context-free readers per set, answering from the lines alone. Readers are labeled A, B and C.

## Set 20

```
match save() { both:CleanupError => printl"{both.primary} / {both.cleanup}"  done => printl"saved" }
let first = failure.primary
let later = failure.cleanup
Transaction:type = [handle:DbHandle  $__drop__  finish = (successful:bool):>void | DbError => if successful commit(handle) else rollback(handle)]
save = () => { let out = open(p"data.bin" 'w') or_throw; out.write_bytes(bytes) or_throw; }
```

### Reader A

match save() { both:CleanupError => printl"{both.primary} / {both.cleanup}"  done => printl"saved" } | Calls save and pattern-matches its result: if the outcome is a CleanupError, print two labeled parts of that compound failure; otherwise (success) print that the save worked. | 4
let first = failure.primary | Binds the “primary” field from a failure value—likely the main error from the operation itself, as opposed to a secondary one. | 3
let later = failure.cleanup | Binds the “cleanup” field from a failure value—likely an error that happened while cleaning up or finishing after the main step. | 4
Transaction:type = [handle:DbHandle  $__drop__  finish = (successful:bool):>void | DbError => if successful commit(handle) else rollback(handle)] | Defines a transaction wrapper around a DB handle whose destructor runs finish, which commits on success and rolls back otherwise, and finish can fail with DbError. | 4
save = () => { let out = open(p"data.bin" 'w') or_throw; out.write_bytes(bytes) or_throw; } | Opens a binary file for writing and writes bytes, propagating open/write failures immediately via or_throw; when the local file handle is dropped at block end, flush/close runs implicitly and a failure there would not use those or_throw sites—save would return a CleanupError (not the done success path) with cleanup naming the close/flush failure and primary reflecting that the explicit write path succeeded or carrying the dominant earlier failure; save returns that failure as a value rather than throwing unless the caller uses or_throw on save(). | 3

### Reader B

match save() { both:CleanupError => printl"{both.primary} / {both.cleanup}"  done => printl"saved" } | Matches the result of `save()`. `CleanupError` named `both` is a compound failure: `both.primary` is the original operation failure (the save/write itself) and `both.cleanup` is a second failure that happened afterward while tearing down (flush/close). The `done` arm is success, when save finished with no failure. | confidence 4
let first = failure.primary | Reads the original/first failure off a compound error value: the failure from the main operation, not from later teardown. | confidence 4
let later = failure.cleanup | Reads the teardown failure off the same compound error: the failure that happened during cleanup (drop/flush/close), after the primary one. | confidence 4
Transaction:type = [handle:DbHandle  $__drop__  finish = (successful:bool):>void | DbError => if successful commit(handle) else rollback(handle)] | A transaction wraps a `DbHandle`. When the value is destroyed, `$__drop__` runs `finish`: commit if the body succeeded, otherwise rollback. `finish` returns void on success or a `DbError` if commit/rollback fails. | confidence 4
save = () => { let out = open(p"data.bin" 'w') or_throw; out.write_bytes(bytes) or_throw; } | Opens a file and writes bytes, passing open/write failures to the caller with `or_throw`. There is no explicit close: the file is destroyed at the end of the function, so `$__drop__` flushes and closes. If that final flush or close fails after a successful write, `save` returns that IO/close failure (not a successful empty result). If write already failed and then flush/close also fails during drop, `save` returns a `CleanupError` whose `primary` is the write failure and whose `cleanup` is the flush/close failure. | confidence 3

### Reader C

match save() { both:CleanupError => printl"{both.primary} / {both.cleanup}"  done => printl"saved" } | Calls save and branches on its result: if it failed with a CleanupError, it prints the primary failure and the cleanup failure together; if it succeeded (done), it prints "saved". The primary is the original failure, the cleanup is a failure from tidying up afterwards. | confidence 4
let first = failure.primary | Reads the primary field of a failure value, the original error that caused the failure, before any cleanup error. It is the first thing that went wrong, which happened in the operation itself rather than in cleanup. | confidence 4
let later = failure.cleanup | Reads the cleanup field of a failure value, the error that occurred while cleaning up after the primary failure, so it happened later than the primary one. It is the second error that was recorded alongside the first. | confidence 4
Transaction:type = [handle:DbHandle  $__drop__  finish = (successful:bool):>void | DbError => if successful commit(handle) else rollback(handle)] | Defines a Transaction type holding a database handle that is cleaned up automatically when destroyed by its drop method. finish takes a success flag: it commits the handle if true, otherwise rolls it back, and it can fail with a DbError. | confidence 4
save = () => { let out = open(p"data.bin" 'w') or_throw; out.write_bytes(bytes) or_throw; } | Opens data.bin for writing and writes the bytes, passing any open or write failure up to the caller via or_throw, so the failure is returned from save instead of handled locally. If the open fails, nothing is written and save fails with that open error. If the final flush or close fails, the close happens when out is destroyed at scope end, and its drop cannot pass a failure back, so the failure is most likely recorded as a CleanupError; with no earlier failure, save probably returns that close failure as its plain error. | confidence 2

## Set 21

```
Transaction:type = [handle:DbHandle  $__rollback__  undo = ():>void | DbError => rollback(handle)]
Child:type = [pid:int  $__abandon__  kill_and_reap = ():>void | ProcessError => stop(pid)]
Transaction:type = [handle:DbHandle  $__discard__  undo = ():>void | DbError => rollback(handle)]
Transaction:type = [handle:DbHandle  $__abandon__  undo = ():>void | DbError => rollback(handle)]
File:type = [fd:int  $__drop__  close = ():>void | FileError => flush_and_close(fd)]
```

### Reader A

Transaction:type = [handle:DbHandle  $__rollback__  undo = ():>void | DbError => rollback(handle)] | On destroy, automatically runs rollback on the handle (undoes uncommitted work). (a) Thrown away—not kept or published. (b) Yes—I'd expect a warning if you never explicitly commit or finish the transaction. | 4
Child:type = [pid:int  $__abandon__  kill_and_reap = ():>void | ProcessError => stop(pid)] | On destroy, automatically kills and reaps the child process without a graceful shutdown path. (a) Any in-flight work from the child is thrown away; the process is terminated. (b) Maybe—less clear than a commit metaphor; might warn if you never explicitly joined or waited, but "abandon" reads as intentional neglect on drop. | 3
Transaction:type = [handle:DbHandle  $__discard__  undo = ():>void | DbError => rollback(handle)] | On destroy, automatically discards the transaction by rolling back (same as undo). (a) Thrown away. (b) Yes—similar to rollback; expect warning without an explicit commit/finish. | 4
Transaction:type = [handle:DbHandle  $__abandon__  undo = ():>void | DbError => rollback(handle)] | On destroy, abandons the transaction and rolls back. (a) Thrown away. (b) Yes—warn if no explicit commit or completion. | 4
File:type = [fd:int  $__drop__  close = ():>void | FileError => flush_and_close(fd)] | On destroy, flushes buffered data then closes the file descriptor. (a) Kept/published—flush implies pending writes take effect before close. (b) Possibly mild warning if you never call explicit close, but auto flush-on-drop suggests the important finish happens anyway; warning less expected than for transactions. | 3

### Reader B

Transaction:type = [handle:DbHandle  $__rollback__  undo = ():>void | DbError => rollback(handle)] | On destroy, `undo` runs and rolls the transaction back. (a) Thrown away — uncommitted work is undone, not published. (b) Yes, warn if nothing like `commit` was ever called. | 4
Child:type = [pid:int  $__abandon__  kill_and_reap = ():>void | ProcessError => stop(pid)] | On destroy, `kill_and_reap` runs and stops the child. (a) Thrown away — the child is killed, its work is not kept. (b) Yes, warn if nothing like `wait` was ever called. | 4
Transaction:type = [handle:DbHandle  $__discard__  undo = ():>void | DbError => rollback(handle)] | On destroy, `undo` runs and rolls the transaction back as a discard. (a) Thrown away — uncommitted work is dropped, not published. (b) Yes, warn if nothing like `commit` was ever called. | 4
Transaction:type = [handle:DbHandle  $__abandon__  undo = ():>void | DbError => rollback(handle)] | On destroy, `undo` runs and rolls the transaction back as an abandon. (a) Thrown away — uncommitted work is not published. (b) Yes, warn if nothing like `commit` was ever called. | 4
File:type = [fd:int  $__drop__  close = ():>void | FileError => flush_and_close(fd)] | On destroy, `close` runs and flushes then closes the fd. (a) Kept — flush publishes pending writes, then the handle is released. (b) No, drop/close is the normal finish; I would not expect a warning for never calling another explicit closer. | 4

### Reader C

Transaction:type = [handle:DbHandle  $__rollback__  undo = ():>void | DbError => rollback(handle)] | (a) Thrown away: the destroyed value rolls back the transaction, so the work done through it does not take effect. (b) No warning expected; dropping it is a deliberate rollback. | confidence 3
Child:type = [pid:int  $__abandon__  kill_and_reap = ():>void | ProcessError => stop(pid)] | (a) Takes effect: destroying the value stops the child process (stop(pid)), so the child is not left running. (b) Probably yes: a program that never calls kill_and_reap leaves the child to be handled implicitly, so a warning is plausible. | confidence 2
Transaction:type = [handle:DbHandle  $__discard__  undo = ():>void | DbError => rollback(handle)] | (a) Thrown away: discard runs rollback(handle), so the work done through the value does not take effect. (b) No warning expected; discarding by destruction is the intended path. | confidence 3
Transaction:type = [handle:DbHandle  $__abandon__  undo = ():>void | DbError => rollback(handle)] | (a) Thrown away: abandon runs rollback(handle), so the work done through the value does not take effect. (b) No warning expected; abandoning is treated as an intentional give-up. | confidence 3
File:type = [fd:int  $__drop__  close = ():>void | FileError => flush_and_close(fd)] | (a) Kept: destroying the value flushes and closes the file, so the work done through it is published. (b) No warning expected; drop runs its cleanup silently. | confidence 4

## Result

- `CleanupError`, `.primary`, `.cleanup`: read correctly by all three (confidence 3–4).
- `$__abandon__`: read as "dropping discards the work" by all three; `$__discard__` read the same; `$__rollback__` read well on a transaction but does not fit a child process.
- Semantic lesson: only one of three readers was sure a lone flush failure is returned as itself, not as a `CleanupError`; round 5 makes hover say so.
