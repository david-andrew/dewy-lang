# Cleanup round 8: who sees a failed cleanup, and how the text shows it

## Summary

1. Six approaches, twelve programs ([programs-r8/](programs-r8/README.md)), eighteen languages surveyed.
2. Under the 11-12 rule, 26 success exits across the programs produce a failure that no written line produces.
3. No design is free: at a success exit, a lossless, local language must write *something* for every cleanup that can fail.
4. So the levers are which cleanups may fail at all, and how many exits one piece of text covers.
5. Every deterministic-destruction language made *release* infallible (Rust, C++, Swift, Zig, C#). All of them then lost data on *completion* (flush, commit, persist), which ran implicitly with nowhere to report.
6. Recommended, (f) **finish on success, clean up on failure**: a release can't fail; cleanup that does work must be finished, moved or covered by `} or_throw` on success exits; unpublished work (`$__abandon__`) must be committed or abandoned explicitly.
7. Missing either is a compile error, affordable because releases no longer fail. Failure exits need nothing written (D42's `&`).
8. `first_row` needs nothing (its socket's release can't fail); `save` needs `out.close() or_throw` or `} or_throw`.
9. Only (f) catches the forgotten `commit`, `persist` or `wait` (programs 02, 04, 12). It adds no syntax and no tag, needs no `defer`, and works under either timing rule.
10. This changes D40 Q1's recommendation from "mark the scope, warn by default, strict tag" to (f). The marker stays as one of two fixes.

## Conclusion

**Is one design objectively best?** Most of the choice is settled by evidence. Four findings
hold because one option beats the others on these criteria and loses nothing in return:

1. **The 11-12 rule loses on nonlocality** in every program with a success exit (26 exits), and
   still misses the forgotten commit. Its one advantage, writing nothing, (f) matches on the read
   path, where most resource uses are.
2. **A warning that discards the failure at run time is the wrong default.** It is exactly the
   documented bug of Go's `defer f.Close()` and Rust's `BufWriter`. The only argument for a
   warning over an error is noise, and the noise comes from release closes.
3. **Releases should not fail.** Every deterministic-destruction language does this. POSIX
   releases the descriptor whatever `close` returns, and only the write side's errors are
   actionable. Guava's history draws the same line: it deprecated quiet close for writers and
   kept it for readers. Removing release failures cuts the required text in *every* approach (it
   deletes (d)'s worst rewrites, in program 03), not only in (f).
4. **Forgotten finishing is a work problem, not a failure problem.** Markers, `defer`s and
   clauses acknowledge failures; none of them notices a transaction that was never committed or a
   temporary file never renamed into place. Only a rule about unpublished work at success exits
   catches it. Linear-type languages (Austral, Vale, Mojo, Linear Haskell) catch it but pay on every
   failure path. Dewy can be **linear on success exits and affine on failure exits**.

One choice is a real tradeoff: **how to spell coverage when several exits need it.** A scope
marker is the fewest tokens; a value-tied `defer` puts a policy per value beside its acquisition;
a call per exit is the most local. (f) teaches the explicit call as the obvious fix and accepts
round 7's marker as the short one. It needs no `defer`, because the cases where only `defer` would
help (a fallible release with many exits) no longer exist.

**What a perfect language would do**, and how close Dewy gets, is under "The perfect language"
below. Dewy can reach nearly all of it. What remains: a library's choice of which cleanups may
fail is a documented contract, not a proof; finishing methods on user types with hooks need one
small new rule (program 11); and parameters of such types must stop inferring ownership (rule 7,
program 09).

## Recommendation

Adopt (f) for D40 Q1:

1. **Releases can't fail.** A hook that only gives something back (closing a reader or socket,
   releasing a cursor, removing a scratch directory or an unpersisted temporary file) has type
   `():>void`, as the current implementation already requires of every hook. The library swallows
   an operating-system error there and reports it in debug builds. A type may keep an explicit
   `close()` that returns the error for code that wants it.
2. **Only cleanup that does work may fail:** a buffered writer's final flush, a TLS close
   notification, a rollback, a child's stop. The standard library follows this rule and its docs
   state it. A library may offer a variant whose release does report (for example a remote cursor
   whose close is audited); that variant is simply a type with fallible cleanup.
3. **Failure exits need nothing written.** Live hooks run; their failures join the leaving
   failure (D42).
4. **Success exits, completion:** an owner whose `$__drop__` can fail may not be live at a success
   exit (fallthrough, `return v`, `break`, `continue`, an inner block's end, a reassignment, a
   generator's frame dropped mid-stream). Finish it (`out.close() or_throw`), move it, or end the
   scope with `} or_throw` / `} ??<E> v` (round 7's acknowledgement, with the function-exit exemption
   removed). Otherwise it is a **compile error** naming the owner, the exit and the failures, and
   offering both fixes.
5. **Success exits, unpublished work:** an owner with `$__abandon__` may not be live at a success
   exit: commit, persist or wait for it, or abandon it explicitly (`tx.rollback() or_throw`,
   `tmp.discard()`, `child.stop() or_throw`), or move it. The marker doesn't cover this, because
   what is missing is a decision about the work, not a failure route.
6. **Structure and generics:** a record, array, closure or generator that may hold such an owner
   owes what it holds. Generic bodies are checked at each instantiation, and a marker is allowed on
   instances that owe nothing, so generic text doesn't fork.
7. **Parameters:** for a type with fallible cleanup, `(out:File)` takes the duty and `(@out:File)`
   lends it; the parameter's mode is not inferred from callers (program 09).
8. **No new syntax and no new tag.** `$prototype` turns 4 and 5 into warnings, with the 11-12
   forwarding for 4. D44's `$no_discarded_failures` already covers written discards
   (`out.close();`, `} ??<FileWriteFailed> void`), so cleanup needs no strict tag of its own.

What it changes in D40's other questions is under "Consequences for open decisions".

## The fact everything rests on

At a **success exit** where an implicit cleanup fails, the failure can go only four places:

1. into the function's result: then the result holds a failure that nothing in the function's
   text produces, unless something is written;
2. nowhere: then it is lost, unless something written says losing it is fine;
3. a crash: neither quiet nor recoverable, so not a default for I/O;
4. a side channel (a log, a hook): lost as far as the program is concerned.

So no language can be all three of: **local** (every failure in a result has a written source),
**lossless** (no failure that changes the outcome is dropped without text saying so) and
**unwritten** (cleanup needs no text). The 11-12 rule is lossless and unwritten. Rust, C++, Swift,
Zig and Go's `defer f.Close()` are local and unwritten. Every other approach is local and
lossless, and pays in text. On a **failure exit** the trilemma doesn't bite: the line already says
a failure leaves, and a cleanup failure joins it (D42's `&`) without hiding anything.

Two levers remain:

- **Which cleanups may fail at all.** Every failure removed from this set needs no text.
- **Where the text goes, and how many exits one piece of text covers.** One token per scope (a
  marker), one line per value (a `defer` or a clause), or one call per exit (an explicit close).

The approaches differ only in how they pull these.

## Approaches compared

All six keep D42 on failure exits. They differ on success exits.

| | Approach | On a success exit with a fallible cleanup |
|---|---|---|
| (a) | The 11-12 rule | the failure becomes the function's result; nothing written |
| (b) | Mark the owning scope (D40 Q1's current recommendation) | `} or_throw` / `} ??<E> v` covers every exit of the scope; unmarked: warning, failure discarded; strict tag: error |
| (c) | `defer` tied to the value | `defer out.close() or_throw` / `defer drop(x) or_throw` runs on every exit where `x` is still owned; a move cancels it |
| (d) | Explicit close, warning, strict tag | `out.close() or_throw` before each success exit; unwritten: warning, failure discarded; strict: error |
| (e) | Disposition on the binding | `let out drop or_throw = …`, `(rows:T drop or_throw)`: a clause per owner and parameter; missing: error |
| (f) | Finish on success, clean up on failure | above |

(a)–(e) are written under the assumption of today's drafts, that every close can fail. (f) drops
that assumption; "The classification axis" shows what dropping it does for (b)–(e).

### Text each approach adds, per program

`t` is a marker token, `ln` a line, `cl` a binding clause.

| Program | (b) | (c) | (d) | (e) | (f) as written | (f), markers where allowed |
|---|---|---|---|---|---|---|
| [01](programs-r8/01_buffered_write.md) buffered writes | 2 t | 2 ln | 3 ln | 2 cl | 1 ln, 1 t | 2 t |
| [02](programs-r8/02_temp_rename.md) temp file renamed in | 1 t | 2 ln | 1 ln | 1 cl | 1 ln | 1 ln |
| [03](programs-r8/03_partial_read.md) partial read | 2 t | 2 ln | 6 ln, 2 loops rewritten | 2 cl | 0 | 0 |
| [04](programs-r8/04_transaction.md) transaction | 1 t | 1 ln | 1 ln | 1 cl | 1 ln | 1 ln |
| [05](programs-r8/05_acquire_sequence.md) acquisitions in sequence | 1 t | 3 ln | 3 ln | 3 cl | 1 ln | 1 t |
| [06](programs-r8/06_moved_owner.md) moved owners | 2 t | 2 ln | 2 ln | 2 cl | 1 t, 1 ln | 2 t |
| [07](programs-r8/07_loop_exits.md) loop exits | 1 grouping | 1 ln | 2 ln | 1 cl | 2 ln | 1 grouping |
| [08](programs-r8/08_generator.md) generators | 3 t, 1 grouping | 3 ln | 5 ln, 1 loop rewritten | 3 cl | 1 ln, 1 t | 1 t, 1 grouping |
| [09](programs-r8/09_own_or_borrow.md) own or borrow | 1 t | 1 ln | 1 ln | 1 cl | 1 ln | 1 t |
| [10](programs-r8/10_parallel.md) parallel | 2 t, 1 grouping | 3 ln | 3 ln | 2 cl | 3 ln | 2 t, 1 ln |
| [11](programs-r8/11_wrapper_type.md) wrapper type | 1 t | 1 ln | 1 ln | 1 cl | 1 t | 1 t |
| [12](programs-r8/12_process_scratch.md) process, scratch dir | 2 t | 2 ln | 2 ln | 2 cl | 1 ln | 1 ln |
| **Total** | **19 t, 3 groupings** | **23 ln** | **30 ln** | **21 cl** | **13 ln, 4 t** | **10 t, 2 groupings, 4 ln** |

With markers wherever allowed, (f) writes no more than (b) in any program, and less in 03, 08
and `build` (12). The exceptions are the three unpublished-work exits (02, 04, `first_line` in 12),
where it asks for one explicit call instead of a token; those calls are the point of the rule.

### What each approach lets through

| | (a) | (b) | (c) | (d) | (e) | (f) |
|---|---|---|---|---|---|---|
| Success exits whose failure has no written source | 26 | 0 | 0 | 0 | 2 (a lazy body's end, a task's end) | 0 |
| Exits that lose a failure when the form is forgotten | 0 | 26, with a warning | 26, with a warning | 26, with a warning | 0 (error) | 0 (error) |
| Forgotten `persist`, `commit`, `stop` (02, 04, 12) | silent | warns about the rollback or removal; its fix-it keeps the bug | silent; `defer commit` publishes on failure | warns by accident | silent | error that names the work |
| Shapes per failure kind in 05 | up to 8 | up to 8 | up to 8 | up to 8 | up to 8 | at most 2 |
| New syntax or names | none | none | fallible `defer`, `drop(x)` | `drop(x)` | clause grammar | none |
| Needs block-end timing (D40 Q2) | no | yes | no | no | no | only for the marker |

### Scores

1 is worst, 5 best. Each score rests on the programs cited.

| Criterion | (a) | (b) | (c) | (d) | (e) | (f) |
|---|---|---|---|---|---|---|
| **Nonlocality:** every path visible from the text | 1: 26 exits | 3: covered, but at `}` far from `return row`; one suffix selects the value and covers cleanup (03) | 4: beside the acquisition; a move silently cancels it (06) | 5: written at each exit | 3: at the binding; lazy and task bodies escape (08, 10) | 4: explicit at exits where used; the marker reads as (b) does; releases have nothing to show |
| **Common-path cost** | 5 | 4: a token on every scope that touches a resource, readers included | 3: a line per value, readers included | 2: a line per exit; early returns rewritten (03, 08) | 3: a clause per owner and parameter | 5: nothing on the read path; a line or token per writer |
| **Safe by default** | 3: lossless, but forgotten work is silent | 2: a warning, then the failure is discarded | 2: as (b), plus `defer commit` (02, 04) | 2: as (b) | 3: errors, but forgotten work is silent | 5: errors; forgotten work caught |
| **Completeness:** exits, moves, generics, generators, parallel | 4: mechanical everywhere, but parameter inference moves failures between functions (09) | 3: handling with `??` replaces the value (03); task bodies unsettled (10); needs block-end | 3: move versus pin unsettled (06); `defer` in lazy bodies reverses batch 11 | 2: multi-exit code is rewritten; needs `drop` | 2: gaps after moves into generators and tasks | 4: everything, given rule 7; finishing methods on hooked user types need a new rule (11) |
| **Compile-time checkable** | 4: nothing to check; hover shows it | 4: round 7's analysis; selector coverage interacts with value selection | 4: plus registration and pinning | 5: per-exit liveness | 4: transfer rules for captures | 5: per-exit liveness, the same check for both rules; the library classification is a documented contract |
| **Fit with Dewy's rules** | 2: breaks "every failure in a result has a written source" | 4: reuses round 7 and D40 Q6; warning default is soft for "safe by default" | 2: reverses D40 Q5, batch 11 Q5 and round 7 | 3: needs `drop`; warning default | 1: new grammar on bindings and parameters | 4: reuses `$__abandon__`, round 7's marker, D42, D44 Q6; asks for error severity where David suggested a warning |

### The classification axis

Rule 1 of (f) (releases can't fail) is independent of the rest and helps every approach:

| | Without rule 1 | With rule 1 |
|---|---|---|
| (b) | 19 markers | 15: none in 03, `top3` (08) or `build` (12) |
| (c) | 23 lines | 17: also one `defer` instead of three in 05 |
| (d) | 30 lines | 20: 03's two rewritten loops disappear |
| (e) | 21 clauses | 15 |

With rule 1, (b) and (d) differ from (f) only in severity (warning versus error) and in missing
rule 5. That is the honest description of (f): **(b)'s marker and (d)'s explicit finish, with
release failures removed, unpublished work checked, and missing coverage an error.** It also fits
the brief's suggested combination: (e) at the type level (the type says whether its cleanup can
fail) with (b) or (d) for scopes.

### David's instinct about `defer`

He is right that the form must reach every exit: a line at the bottom doesn't, because `return`
never gets there. Under block-end timing, a scope's exits are exactly the places its owners can be
cleaned up, so a scope marker covers the same exits as a `defer` with less text and no new `defer`
semantics. Under (f), most values need nothing, and the rest are finished by a call where the work
ends. A fallible `defer` would also invite `defer tx.commit()` and `defer tmp.persist()` (programs
02 and 04), which publish on failure exits. Zig and Swift forbid failing defers for this reason,
and Go's named-result pattern is its most common cleanup bug. And it would reverse D40 Q5's
provisional rule, batch 11's lazy-body rule and round 7's recommendation. `defer` would earn a
place only under last-use timing with a different policy per value, and even there an explicit
finish works.

## The perfect language

A language that left nobody wanting would:

1. never put a failure in a result without a written source, and never drop one that changes the
   outcome without a written discard;
2. make releasing infallible and silent, since a failed release changes nothing the program can
   act on, while recording it for diagnostics;
3. treat completing work as work: the flush, commit, persist or wait is an ordinary call with an
   ordinary failure, written where the work ends;
4. prove at compile time that every success path completes or explicitly abandons the work it
   started, naming the value and the line when it doesn't (linear on success paths);
5. on failure paths, abandon automatically and attach any cleanup failure to the failure already
   leaving, keeping both (affine on failure paths);
6. offer one token for "complete everything this scope owns, at each of its exits" for code with
   many exits and for generic code;
7. show in signatures who holds the duty: owning or lending;
8. show in the editor, at every exit, which cleanups run there and what they can add.

**How close Dewy gets with (f):** all of 1 and 3–8, using machinery it already has: round 7's drop
flags and marker, `$__abandon__`, D42's `&`, `@` lending and hover. Point 2 holds in debug builds;
release builds swallow release errors, and a type can opt into a fallible release. Three gaps
remain. A library's choice of which cleanups can fail is a contract, not a proof. Finishing
methods on hooked user types need a way to consume a value without running its hook (program 11).
And parameter ownership for fallible-cleanup types has to stop being inferred (program 09). None
of them needs new syntax.

## Survey: how other languages handle failing cleanup

The question each answers: can implicit cleanup fail, and if it does, who hears about it?

| Language | Implicit cleanup | Can it fail? | Where a failure goes | What goes wrong in practice |
|---|---|---|---|---|
| Rust | `Drop` | no: `drop(&mut self)` returns `()` | ignored: `File` "Errors detected on closing are ignored by the implementation of Drop" [1]; `BufWriter`: "any errors that happen in the process of dropping will be ignored" [2] | silent data loss when `flush` is forgotten; `tempfile::TempDir` and `NamedTempFile` add a consuming `close()`/`persist()` that return the error [3]; `sqlx::Transaction` rolls back silently on drop, so a forgotten `commit` loses work [4]. Real linear types were rejected mostly because of unwinding [5] |
| C++ | destructors | `noexcept` by default since C++11; a throw during unwinding calls `std::terminate` [6] | `std::basic_filebuf`'s destructor closes and swallows failures [7] | the same silent loss; "call `close()` and check" is folklore |
| Swift | `deinit`, `defer` | no: `deinit` can't throw; a `defer` body can't throw or leave [8] | `try?` or a `do`/`catch` inside the `defer` | noncopyable types (SE-0390) add `consuming func close() throws` with `discard self` [9], but nothing makes callers call it |
| Zig | `defer`, `errdefer` | a `defer` can't `try` or `return`; `close` returns `void` [10] | `defer w.flush() catch {}` | the explicit-sync rule (`try file.sync()`) is folklore; `errdefer` handles failure-only cleanup well |
| Go | `defer f.Close()` | yes, but a bare `defer` discards the result | dropped, unless a named result and a closure assign it, now with `errors.Join` [11] | "Don't defer Close() on writable files" [12]; linters exempt read-side `Close` because its error is not actionable [13] |
| Java | try-with-resources | yes: `close() throws` | propagates; when the body already threw, the close failure is attached as *suppressed* (JLS 14.20.3) [14] | `IOException` on closing readers forced `closeQuietly`; Guava deprecated the general `closeQuietly(Closeable)` because people used it on writers and lost data, then re-added it only for `InputStream` and `Reader` [15] |
| Kotlin | `use {}` | yes | as Java: propagates, else suppressed [16] | — |
| C# | `using`, `await using` | possible, but discouraged: "AVOID throwing an exception from within Dispose" [17] | a `Dispose` failure *replaces* the body's exception (try/finally) | the design guidelines tell libraries to offer a separate `Flush`/`CloseAsync` that may throw |
| Python | `with` (`__exit__`), `__del__` | yes in `__exit__`; `__del__` failures print "Exception ignored in" via `sys.unraisablehook` [18] | `with`: propagates, chaining the body's exception as `__context__`; `ExceptionGroup` (PEP 654) for several [19] | `with` is the scope marker, written every time; without it, CPython's refcount closes the file and a failure is printed, not raised |
| TypeScript, JavaScript | `using`, `await using` (TypeScript 5.2, TC39 explicit resource management) | yes | propagates; when the body also threw, both travel as a `SuppressedError` [26] | without `using`, Node closes a forgotten handle at collection with a warning, and a failure is lost |
| Haskell | `bracket` | yes | in `base`, a failing release replaces the body's exception [20]; GHC 9.10 keeps the first as context (`WhileHandling`) | releases are expected to be total |
| Koka | handler `finally` | yes | deep finalization runs on return and on unresumed operations [21] | resource-and-handler design, not a failure-reporting design |
| Odin, Jai | `defer` only; no destructors | the deferred call's result is dropped unless handled in place | explicit | forgetting the `defer` leaks; nothing checks |
| Austral, Linear Haskell | linear values | close must be called; it may return a result, which is itself linear | must be handled [22][23] | every path must consume, including failure paths, which is verbose and is exactly what Rust balked at under unwinding |
| Vale, Mojo | "higher RAII", explicitly destroyed types | the compiler forbids implicit destruction; destroyers may take arguments and return values [24] | handled at the destroyer call | same cost on failure paths |
| POSIX | `close(2)` | yes; the descriptor is released anyway and must not be retried after `EINTR`; "failing to check the return value when closing a file may lead to silent loss of data ... especially ... with NFS and with disk quota" [25] | — | the read side's errors aren't actionable; the write side's are |

### What the survey shows

1. **Every deterministic-destruction language made release infallible** (Rust, C++, Swift, Zig,
   C#'s guidelines, Haskell's convention). None regrets it for readers, sockets or locks.
2. **Every one of them then lost data on the write side**, the same way: the work-completing step
   (flush, sync, commit, persist) ran implicitly, failed, and had nowhere to go. Their fix is
   always an explicit consuming call (`flush`, `sync_all`, `persist`, `commit`, `close() throws`)
   that the compiler *doesn't require*. The bugs are the forgotten calls.
3. **The languages that propagate close failures** (Java, Kotlin, Python's `with`, TypeScript's `using`) are lossless
   but write a marker every time and drown readers in unactionable close errors; Guava's
   history is the cleanest evidence that the useful line runs between writers and readers,
   not between "cleanup" and "not cleanup".
4. **When body and cleanup both fail**, replacing the first failure (C#, old `bracket`, Java
   before 7) is universally regretted; keeping the first and attaching the second (Java's
   suppressed, Python's context, TypeScript's `SuppressedError`, Go's `errors.Join`, GHC 9.10) is where everyone converged. D42's
   `&` already does this.
5. **Linear types** solve the forgotten call completely, and every language that adopted them
   pays on failure paths, where each early exit must consume each value by hand. Rust's
   objection [5] is entirely about failure paths (unwinding).
6. **`defer` that can fail** exists only in Go, by assigning to a named result, and it is the
   pattern Go programmers most often get wrong. Zig and Swift forbid it on purpose: a deferred
   failure has to merge with whatever the exit was already doing.

Dewy has what none of these has at once: failures as values that combine (`&`), compile-time
exits for every owner (round 7's drop flags), and `$__abandon__` for unpublished work. That is
enough to be linear exactly where linearity pays (success exits, where forgetting loses work)
and affine where it costs (failure exits, where the hook runs and its failure joins). That is
(f).


### Sources

1. Rust `std::fs::File`: https://doc.rust-lang.org/std/fs/struct.File.html
2. Rust `std::io::BufWriter`: https://doc.rust-lang.org/std/io/struct.BufWriter.html
3. `tempfile` `TempDir::close`, `NamedTempFile::persist`: https://docs.rs/tempfile/latest/tempfile/
4. `sqlx::Transaction`: https://docs.rs/sqlx/latest/sqlx/struct.Transaction.html
5. A. Beingessner, "The Pain Of Real Linear Types in Rust": https://faultlore.com/blah/linear-rust/
6. cppreference, destructors and `noexcept`: https://en.cppreference.com/w/cpp/language/destructor
7. cppreference, `std::basic_filebuf::~basic_filebuf`: https://en.cppreference.com/w/cpp/io/basic_filebuf/~basic_filebuf
8. The Swift Programming Language, Statements, "Defer Statement": https://docs.swift.org/swift-book/documentation/the-swift-programming-language/statements/
9. SE-0390, noncopyable structs and enums: https://github.com/swiftlang/swift-evolution/blob/main/proposals/0390-noncopyable-structs-and-enums.md
10. Zig language reference, `defer` and `errdefer`: https://ziglang.org/documentation/master/
11. Go `errors.Join`: https://pkg.go.dev/errors#Join; deferred functions and named results: https://go.dev/blog/defer-panic-and-recover
12. J. Shaw, "Don't defer Close() on writable files": https://www.joeshaw.org/dont-defer-close-on-writable-files/
13. `errcheck` default exclusions: https://github.com/kisielk/errcheck
14. JLS 14.20.3, try-with-resources: https://docs.oracle.com/javase/specs/jls/se21/html/jls-14.html#jls-14.20.3
15. Guava `Closeables`: https://guava.dev/releases/snapshot-jre/api/docs/com/google/common/io/Closeables.html
16. Kotlin `use`: https://kotlinlang.org/api/core/kotlin-stdlib/kotlin.io/use.html
17. .NET Dispose pattern guidelines: https://learn.microsoft.com/en-us/dotnet/standard/design-guidelines/dispose-pattern
18. Python data model, `object.__del__`: https://docs.python.org/3/reference/datamodel.html#object.__del__
19. PEP 654, exception groups: https://peps.python.org/pep-0654/
20. `Control.Exception.bracket`: https://hackage.haskell.org/package/base/docs/Control-Exception.html
21. D. Leijen, "Algebraic Effect Handlers with Resources and Deep Finalization", MSR-TR-2018-10: https://www.microsoft.com/en-us/research/publication/algebraic-effect-handlers-resources-deep-finalization/
22. Austral specification, linearity: https://austral-lang.org/spec/spec.html
23. Bernardy et al., "Linear Haskell", POPL 2018: https://arxiv.org/abs/1710.09756
24. E. Ovadia, "Higher RAII": https://verdagon.dev/blog/higher-raii-7drl
25. Linux `close(2)`: https://man7.org/linux/man-pages/man2/close.2.html
26. TC39 explicit resource management: https://github.com/tc39/proposal-explicit-resource-management; TypeScript 5.2 release notes: https://www.typescriptlang.org/docs/handbook/release-notes/typescript-5-2.html

## The programs

Twelve programs, each under all six approaches, with a score table at the end of each:
[programs-r8/](programs-r8/README.md). The library model (which hooks can fail under (a)–(e)
and under (f)) is in that README. They are paper programs: nothing was compiled or run.

## Dogfood of (f)

(f) graded on every program, 1–5, against how Python, Go, Rust, TypeScript and Swift write the
same program.

| Program | Obvious | Discoverable | Concise | Safe by default | Complete | Why not 5 |
|---|---|---|---|---|---|---|
| 01 buffered writes | 5 | 5 | 5 | 5 | 5 | |
| 02 temp file renamed in | 5 | 5 | 5 | 5 | 5 | |
| 03 partial read | 5 | 5 | 5 | 5 | 4 → 5 | no way to get a close status at several exits; iteration 1 |
| 04 transaction | 5 | 5 | 4 | 5 | 5 | the replay exit needs an explicit rollback; Python's `with conn:` and callback APIs commit implicitly; see iteration 5 |
| 05 acquisitions in sequence | 5 | 5 | 5 | 5 | 5 | |
| 06 moved owners | 4 | 5 | 5 | 5 | 5 | the marker on `write_rows` finishes four files on every exit; a newcomer may read it as running only at the bottom |
| 07 loop exits | 5 | 5 | 4 | 5 | 5 | one more line than Python's `with` inside the loop; the grouping fix is shorter but less obvious |
| 08 generators | 4 | 5 | 5 | 5 | 5 | that dropping a generator mid-stream flushes its log is learned from the error |
| 09 own or borrow | 5 | 5 | 5 | 5 | 4 → 5 | inferred parameter mode moved the duty; iteration 3 |
| 10 parallel | 5 | 5 | 5 | 5 | 5 | |
| 11 wrapper type | 4 | 5 | 5 | 5 | 4 → 5 | marker as in 06; no finishing method can be written; iteration 2 |
| 12 process, scratch dir | 5 | 5 | 5 | 5 | 5 | |

### Against the five languages, on the decisive cases

| Case | Python | Go | Rust | TypeScript | Swift | Dewy (f) |
|---|---|---|---|---|---|---|
| A writer's final flush fails (01) | `with`: raised; without `with`: printed "Exception ignored", lost | bare `defer f.Close()`: lost | `BufWriter` drop: lost | `await using`: raised, `SuppressedError` beside a body failure [26]; without it: closed by the collector, lost | `defer { try? close() }`: lost | compile error until finished or covered |
| Forgotten rename into place (02) | silent | silent | `NamedTempFile` deleted on drop, silent | silent | silent | compile error naming `tmp` |
| Forgotten commit (04) | plain cursor: silent; `with conn:` commits on any normal exit | `defer tx.Rollback()`: silent | `sqlx`: silent rollback | callback APIs commit on return; handle APIs: silent | handle APIs: silent | compile error naming `tx` |
| A reader's or socket's close fails (03) | `with closing(…)`: raised | lost | lost | raised with `using`, else lost | lost | can't fail, by contract; opt-in variant reports it |
| Child left running (12) | `Popen` left running, `ResourceWarning` | left running | `Child` drop doesn't kill: left running | left running | left running | compile error naming `tail` |
| Multiple exits (01, 03, 07) | `with` covers them | `defer` covers them, losing failures | drop covers them, losing failures | `using` covers them | `defer` covers them, losing failures | explicit finish per exit, or one marker |

### Iterations

1. **03, complete.** A program that must know whether a remote cursor closed cleanly has no
   multi-exit form, because releases can't fail. Fix, with no language change: a library may
   offer a variant whose release reports its failure (say, an audited cursor). That variant is an
   ordinary type with fallible cleanup, so the marker and every other rule apply to it. → 5.
2. **11, complete.** A `$__consume__` method that writes `Archive`'s footer and closes its fields
   still has the outer hook run at its end, so the footer is written twice; fields under a hook
   can't be taken apart either. A finishing method needs to consume its value without running the
   hook, as Swift's `discard self` does. That is a new rule (not proposed here, spelling open), so
   it goes to David. Meanwhile callers use the marker, which needs no finishing method. → 5 once
   decided.
3. **09, complete.** Rule 7 (a plain parameter of a type with fallible cleanup takes the duty;
   `@` lends) was added to (f). The added line in program 09 becomes a use-after-move error where
   it is written, instead of moving the flush to another function. → 5.
4. **06, 08, 11, obvious.** Tried requiring an explicit finish everywhere and dropping the
   marker: concise falls to 3, because an array of writers or a hooked type has no finishing call
   without a generic `drop` (06, 11). Tried highlighting every covered exit and listing the covered
   owners on hover: that helps but doesn't change the text. The residual 4 belongs to any
   scope-level form. Python's `with` has the same property, but its indentation shows the scope.
   Kept at 4.
5. **04, concise.** Tried letting the marker abandon unpublished work on early success exits:
   that brings back the forgotten commit at an early `return`, the bug `sqlx` and callback APIs
   ship. Tried allowing an abandon when no write happened on that path: that needs flow-sensitive
   typestate whose verdict changes when a line is added. The explicit rollback is the intended
   cost. Kept at 4.
6. **07, concise against obvious.** The explicit closes are obvious, and round 7's grouping is
   short. The fix-it offers both, explicit first. Kept at 4 for the program as written.

The remaining 4s come from the rule's purpose (04) or from scope-level forms in general (06, 07,
08, 11). No version of the design reached all 5s without giving up safety or adding syntax.

## Consequences for open decisions

- **D40 Q1:** replace the recommendation with (f). The scope marker survives as one of two fixes,
  without the function-exit exemption. The placeholder strict tag `$explicit_cleanup` isn't
  needed.
- **D40 Q2 (timing):** (f)'s checks hold under either rule. Under last use, a mid-block drop of a
  fallible owner is a success point that needs an explicit finish, and the marker doesn't reach
  it. Block-end keeps the marker useful, so (f) favors block-end mildly and lowers the stakes.
- **D40 Q5 (`defer`):** not needed for cleanup failures. The restoration question stays as round
  7 left it; if `defer` stays, it stays infallible.
- **D40 Q6:** applies only to owners whose cleanup can fail; option A (explicit close) is (f)'s
  first fix, B and C its marker. An uncovered exit is an error, as Q6 already recommends for
  continuing exits, and now for function exits too.
- **D42:** fewer combined shapes. Reader and socket closes never join, so a handler for a failed
  connect always consumes it (program 05). Q6's stack is still needed (two writers). Under (f),
  `FileCloseFailed` comes only from writable files and explicit closes.
- **D44 Q6, Q7:** consistent. A race loser has no release failures to discard; its completion
  failures go with its discarded result; `UndoFailed` still can't be discarded.
  `$no_discarded_failures` also covers written discards of cleanup failures.
- **Generators Q6 (batch 12, folded into D40 Q1):** the owner that drops a generator owes what
  the generator's frame holds. A socket-backed generator owes nothing. A generator holding a
  writer is read to its end or its owner's scope is marked, and the lazy body's own end is a
  success exit for what the body owns (program 08).
- **Batch 9 (`$__abandon__`), D43:** unchanged, plus rule 5: an uncommitted transaction at a
  success exit is an error.

## For David

**Q1 (replaces D40 Q1's recommendation).** Turn this on, and a writer, transaction, unrenamed
temporary file or running child left unfinished on a success path is a compile error that names
it and offers the fix. Closing a reader or socket can never fail, so code that only reads writes
nothing. Failure paths clean up by themselves, and cleanup failures join the failure already
leaving.

- **Rec:** yes. It is lossless and local, and it alone catches forgotten commits, renames and
  waits. It adds no syntax and no tag, and it keeps hooks infallible for releases, as the
  implementation already does.
- **Unblocks:** hook signatures in the standard library, the cleanup checker (it is round 7's
  per-exit analysis), D40 Q6 and generators Q6.
- **Reversible:** before release. Turning the errors into warnings later breaks nothing; making a
  release fallible later breaks callers, so rule 1 should be decided before the standard library
  ships its hooks.
- **You give up:** release errors in release builds (debug builds report them); (b)'s
  one-token-only style at the three unpublished-work exits; Python-style commit on any normal
  exit.

**Q1a.** Error by default rather than warning? **Rec:** error. A warning that discards the failure
at run time is the bug Go and Rust document. `$prototype` downgrades it.

**Q2 (natural extension, rule 7).** For a type whose cleanup can fail, a plain parameter takes the
duty and `@` lends it; the mode isn't inferred from callers. **Rec:** yes. **Reversible.**

**Q3 (new semantics, not blocking).** Let a `$__consume__` method finish a value that has a hook
without the hook running again (Swift's `discard self`), so library and user types can offer
`close()` and `commit()` methods. No spelling is proposed; one would need cold reads. Until then
callers use the marker.

No new names are proposed. The library names in the programs (`temp_beside`, `persist`,
`discard`, `temp_dir`) are illustrative and haven't been cold-read; LANGUAGE.md lists the durable
write API as unsettled.

## Outside this round's scope

- Inferring parameter ownership moves cleanup duty between functions when a caller adds a line
  (programs 03, 09).
- A type with a hook can't have a finishing method today (program 11).
- Under D42's narrow rule, releases joining failures make handlers miss combinations (program
  05); (f) removes most of them, but other approaches keep them.
- (b) has no settled place for a marker on a `spawn` body (program 10).
- A fallible `defer` invites `defer commit` and `defer persist` (programs 02, 04).

## Limits

Paper programs, not compiled. The grades are this round's own; there is no independent review or
cold read of the error messages yet. Recommended before deciding: an independent review, a cold
read of the three error messages, and a cost check of rule 5 on the flagship panel. Rule 5 reuses
round 7's per-exit analysis on `$__abandon__` owners, so its cost should be small, but nothing has
measured it.
