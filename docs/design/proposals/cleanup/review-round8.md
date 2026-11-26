# Review: cleanup round 8, option (f)

**Verdict.** (f) is the right recommendation for D40 Q1 if the finish/release split is a type property. Error, not warn-and-discard; finish real work on a success exit; on a failure exit, join the cleanup failure to the failure already leaving; a marker must not stand in for commit, persist, or wait. It does not hold up as written. A socket, pipe, or read-write file that has accepted bytes is not a release, and one `File` type cannot carry the check. Program 05 is the counterexample the study scores as a win.

## 1. Cross-language claims

These check out against the cited sources:

- Rust `File` Drop ignores close errors; `BufWriter` Drop ignores flush errors (`std::fs::File`, `std::io::BufWriter`). `sqlx::Transaction` rolls back on drop when neither `commit` nor `rollback` ran.
- Guava's general quiet close is gone. `closeQuietly` remains for `InputStream` and `Reader` only, and the javadoc draws the reader/writer line (guava.dev `Closeables`).
- Go: a bare `defer f.Close()` drops the error. Joe Shaw's article is real. Zig: `return` inside `defer` is a compile error; `errdefer` runs only on the error path (language reference). Swift: a `defer` body cannot transfer control, so it cannot `throw`. SE-0390 does add `consuming func close() throws` and `discard self`.
- Java try-with-resources attaches a close failure as suppressed when the body already threw (JLS 14.20.3). C# `using` is try/finally, so a throwing `Dispose` replaces the body exception. The cited guideline says to avoid throwing from `Dispose`.
- Linux `close(2)`: the descriptor is released before a later error is reported; earlier `write` errors surface at `close`, "especially … with NFS and with disk quota"; do not retry.

Wrong or overstated:

- "POSIX releases the descriptor whatever `close` returns, and must not be retried after `EINTR`." That is Linux. The same man page says POSIX.1-2024 standardized the HP-UX rule (`EINTR` may leave the fd open), and that Linux is non-conforming. The row is labeled POSIX and sourced to the Linux page.
- "Only the write side's errors are actionable" is the study's gloss. The man page says a close error means an earlier write may have failed, and that a successful close still does not put data on disk (`fsync`).
- "Every deterministic-destruction language made release infallible," including C#'s guidelines and Haskell's convention. C# is advice: `Dispose` may throw, and `using` is explicit, unlike Rust `Drop`. `bracket` can fail. Those languages did not split release from completion. They made the destructor unable to report, then ran flush inside it.
- "GHC 9.10 keeps the first as context (`WhileHandling`)." `WhileHandling` was added to `catch` in GHC 9.12, not 9.10 (Well-Typed, "Exception Annotations," 2026). In 9.10, if `bracket`'s release throws, that exception replaces the body. Under `WhileHandling` the release exception is still primary and the body is context, the opposite primary from Java's suppressed.
- Python is grouped with that convergence. A raising `__exit__` becomes the exception that propagates; the body is `__context__`. `with` does not build an `ExceptionGroup` (PEP 654 is `except*` / `TaskGroup`). The cited data-model section says a `__del__` exception is ignored and a warning goes to `sys.stderr`. "Exception ignored in" via `sys.unraisablehook` is CPython's hook, not that section.
- Source [13], kisielk/errcheck: `DefaultExcludedSymbols` does not include `Close`. The maintainer argued that `Close` on a written file must be checked (errcheck issue 101). golangci-lint's EXC0001 suppresses `.*Close` and `.*Flush` together, not the read side only.
- Mojo's default is implicit `__deinit__` (`Deinitable`). `not Deinitable` is opt-in, and the manual recommends it when cleanup can fail. The survey row ("the compiler forbids implicit destruction") describes the opt-in, then charges Mojo with linear cost on every path. Vale's "higher RAII" is a design article, not a rule verified here.
- Linear Haskell is opt-in (the POPL 2018 file example). Austral matches the row. "Rust rejected linear types entirely because of unwinding" overstates Beingessner: unwinding is the main argument; `mem::forget` and leaks are separate.
- "None regrets it for readers, sockets or locks" is not evidence. Rust's own `BufWriter` example is a `TcpStream`.

## 2. Is "a reader or socket close can't fail" sound?

Sound for a file opened only for reading, and for a socket that was only read. Not sound as stated.

- Program 05 calls `conn.send`, then (f) drops `conn` as an infallible release. That socket is a writer. A userspace buffer, a TLS `close_notify` (rule 2 lists it as fallible work; rule 1 says a socket close cannot fail), and `SO_LINGER` are the forgotten-flush bug. Kernel TCP often returns 0 from `close` while data is still unacknowledged, so an infallible close does not mean the bytes were delivered.
- NFS and quota are why writer close stays fallible even after a userspace flush. That part of (f) is right. It does not extend to "any socket."
- Missing from the library model: `O_RDWR`, a pipe's write end, a file opened append-and-read. A generic parameter cannot see the mode.
- The programs use one `File` for `'r'` and `'w'` (`array<File>`, `out:File`). `LANGUAGE.md` types every `$__drop__` as `():>void`. If both modes are the same type, the checker is unsound or every `File` is fallible, and "nothing on the read path" disappears. Open mode has to be in the type. The study calls the library label "a contract, not a proof" and scores compile-time checking 5. Both cannot be right.
- Iteration 5 rejects flow-sensitive "no write happened here" typestate because adding a line changes the verdict. The same objection forbids recovering read-vs-write from use. The constructor's mode has to be part of the type.

## 3. Do the programs show the claims?

All twelve were read. The Hidden cells sum to 26 if "1 exit, 3 hooks" counts as one exit: 3+1+4+1+1+2+3+4+1+3+1+2. That is the table sum.

- Program 01's prose gives `export_csv` three unwritten places and includes "each failing write," which is a failure exit. The three success exits are `save`'s end, `return i`, and the fallthrough. The number is defensible; the sentence is not.
- Program 02's Hidden is 1, but both `return false` and `publish_forgot`'s end can emit an unwritten `FileRemoveFailed`. Program 04 counts the replay `return` and parks `rename_account` only under Forgotten. Counting those, the figure is 28, not 26.
- (f) does catch a forgotten persist (02), commit (04), and wait/stop (12). The errors name the value. The marker is not a fix. (b)'s marker silences the removal or rollback warning and leaves the bug. (c)'s `defer persist` / `defer commit` publishes on the failure path. (e) accepts the clause and still rolls back or deletes. Those comparisons hold.
- Spot checks. (a) on 01, 03, 05, 07 matches a world where every close can fail; 05's "up to 8" is the 2³ joins of three hooks. (b) on 02, 03, 04, 08: `??` on `find` replaces the found row; the lazy-body grouping is a new spelling. (d) on 03 really rewrites both loops; 07's (d) and (f) are the same text. (e) on 08 and 10 honestly leaves the generator's end and the task's end uncovered. (f) on 03, 06, 10, and 11 matches the write-up only after the classification is granted. 05 does not.

## 4. Can the rule be checked?

Per-exit liveness of a known obligation is round 7's drop-flag CFG: several exits, a conditional move, a reassignment. That part is local and cheap. Nothing here measured it; the study says the same.

These are not that check:

- A generator frame, a closure, an array element, and a generic parameter have to carry the obligation on the type. "Checked at each instantiation" assumes monomorphization and a type that already has the bit.
- A task boundary transfers the duty only when the capture is a move. Program 10 checks each body alone. A race whose parent succeeds and drops the loser is not in the set. D44 discards a loser's ordinary close failure with the result and keeps `UndoFailed`. A writer flush in that loser is a completion failure; "goes with its discarded result" is how it is lost. That case needs a rule.
- Failure exits skip the finish check. Cancellation is one, so a canceled writer is joined, not finished. That matches (f). It is the wrong outcome if the caller then discards the joined failure.

## 5. What the study missed

No better surface rule turned up. Mojo's opt-in linear type is the closest shipped analogue and supports the split; the survey cites it backwards. (f)'s real improvement on that design is staying affine on failure exits, so a failing path does not write a close by hand.

Breaks, as specified:

- Program 05, and any buffered or TLS socket, pipe writer, or `O_RDWR` file classed as a release.
- A `$__drop__` that commits. The marker runs the drop hook, so it would publish on every covered success exit: the `defer commit` bug. Rule 5 helps only when commit is not inside the drop hook. The checker cannot see that.
- Infallible `discard()` swallows a failed unlink of unpublished bytes. D44 already treats a stray temporary as discardable. Those bytes may be the secret; the recommendation should say so.
- "Reported in debug builds" must not change the result between builds. The study does not say which.

`LANGUAGE.md` requires `$__drop__` to return `void`. The batch-9 decision already types `$__abandon__` as `():>void | DbError`. (f) keeps that, and also makes some drop hooks fallible. "The implementation already requires this of every hook" is true of `$__drop__` only.

## What must change, and the top three

1. Put finish versus release on the type. A value that has accepted bytes (write or read-write file, pipe write end, socket after send, TLS) has a fallible finish. A pure reader does not.
2. Keep the errors in programs 02, 04, and 12. `} or_throw` covers a fallible drop. It does not satisfy `$__abandon__`.
3. Correct the survey before using it as the argument: Mojo, the Haskell version, errcheck, Python versus Java, POSIX versus Linux.

Top three: the socket and read-write hole, together with one `File` type; survey claims the recommendation rests on that are false or mis-cited; generator, closure, generic, and race-loser obligations are not the round-7 liveness check.
