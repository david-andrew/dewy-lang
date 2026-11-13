# Cleanup: amendments after the round-5 regrade

Round 5 and its programs are unchanged. These notes settle the regrade's must-fix and record the open choice brought to David.

## Must-fix: a child process's drop needs its own bound

Program 23:14 had a child's drop request a stop, wait, then kill, while rule 8 gives normal-exit cleanup no deadline. A child that ignores the stop request would hang a normal exit.

**Fix:** stopping a child is a bounded protocol of its own, independent of cancellation: the drop requests a stop, waits at most the library's stop bound (a documented default), then kills and reaps. The bound is part of the `Child` library contract, not the cleanup rules, so rule 8 stands: hooks have no general normal-exit deadline, and a hook that waits on something outside the program must bound that wait itself. No new name.

## Open choice for David: which owners are held to the end of their block

Round 5 holds owners whose cleanup can fail, and lock guards, to the end of their block; owners whose release can't fail (sockets, tickers, spsc ends, textures) still release at their last use. The regrade gave program 18 a 2 for obviousness: one generic function releases at two different times depending on its type argument.

The alternative: **every value with a cleanup hook runs it at the end of its block** (or when moved away); only plain memory is freed at its last use, which no program can observe. Braces shorten a hold. This is what Python's `with`, Rust and Swift do. Cost: a socket or ticker stays open until its block ends rather than after its last use. It was not dogfooded as a separate round; it removes program 18's split and leaves the other programs' behavior unchanged except for later socket and ticker releases.

## Should-fix items carried to implementation

From regrade-round5.md: how `is? error` and `error` arms narrow a `CleanupError` that only sometimes carries `Canceled` (22:31); a discarded owner expression such as `terminal.raw(...) or_throw;` (held to the end of the statement's block, like a binding); the cancellation bit on a hand-built `CleanupError` (13:12); rule 10's wording versus shared-channel close (14:6), which stays an explicit close; a read-only file's failed close leaving a loop on `continue` (15:7).
