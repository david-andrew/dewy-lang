# Independent regrade, round 5 (graded before reading dogfood-round5.md)

Scale O/D/C/S/K = obvious, discoverable, concise, safe by default, complete. Paths are programs-r5/NN_*.dewy.

| # | O/D/C/S/K | Lines cited for scores under 5 |
|---|---|---|
| 01 | 4/4/5/5/5 | O/D: the error appears at the implicit brace/return (10), explained only by editor contract (33-39) |
| 02 | 4/4/5/5/5 | O: nothing shows a release (5); comment 17 says "releases on both early returns" but release is already at line 7's last use |
| 03 | 4/4/5/5/5 | O/D: close-on-drop is only a comment (4); Go/Rust-style reader sees no close |
| 04 | 3/4/5/4/5 | O: sockets drop at last use (02) but this guard does not; comment line 10 "last use of book" is misleading while the lock is held to 13. S: I/O under lock (11) not warned by default; contention silent |
| 05 | 3/4/5/4/5 | O: unused `mode` (4) looks deletable. S: nothing in R5 says what happens to a discarded owner expression (`terminal.raw(...) or_throw;`), which restores at once |
| 06 | 4/4/4/4/5 | O/D: two removal duties on one brace (12). C: trace table 17-25 (nested pairs). S: a leftover-temp failure turns an already published archive into an error (11, 15) |
| 07 | 3/3/4/5/4 | O/D: 15-16 are `??<Canceled>`, `or_throw`, then `check_cancel`; implicit capture move of `stream` (4-5). K: no case where wait gives non-Canceled failure |
| 08 | 4/4/5/5/4 | D: correctness rests on library internals (16-17). K: retirement bookkeeping not exercised (17) |
| 09 | 3/3/3/4/2 | blocked (33-35). C: 3-26 ceremony and magic constant 17. K: nominal hook rejected today |
| 10 | 4/4/5/5/4 | O/D: rollback hook is invisible in the program (21); `$__abandon__` uncold-read. K: serialization conflict and retry not shown (25-28) |
| 11 | 5/5/5/4/5 | S: forgetting the defer is undetectable (14-15) |
| 12 | 4/4/5/4/5 | S: "all files completed" (18) is correct only because of braces (12, 17); drop them and it prints before completion. Remembered step |
| 13 | 3/3/4/4/4 | O/D: author hand-builds the pair (12) and flush/close sequencing (9-16). K: how a hand-built CleanupError gets its cancellation bit is unspecified |
| 14 | 4/3/4/3/3 | S/K: deleting line 6 hangs (28-29). D: why spsc ends differ (26-27). Also contradicts rule 10 "library resources never depend on a defer" |
| 15 | 3/3/5/5/5 | O/D: `continue`/`break` (7, 9) can return from the function (12, 16); a failed close of a read-only file aborts the whole loop |
| 16 | 4/4/5/5/5 | O: `return result` (8) not a plain transfer (14-17) |
| 17 | 3/3/5/5/4 | O/D: assignment (4) hides completion and a failure edge (11). K: no way to restore old handle (20) |
| 18 | 2/3/4/4/4 | O: same text, different timing per instance (6 vs 25-26). D: editor-only (24-31). C/S: natural signature rejected (11-13, 33-36). K: Never-read statement form not covered |
| 19 | 3/3/5/4/5 | O/D: lifted `let` (11) completes at 15, item locals at item end (21-22); 18-32 needs a page of rules. S: conditionally initialized held owner (26-27) needs init flags |
| 20 | 3/3/4/5/4 | O/D: `return none` silent but `return value` warns (8 vs 15, 33-34); "after a change" = mutable borrow (41-42). C: explicit rollback (7, 23). K: shipping program carries two warnings by design |
| 21 | 3/4/5/4/5 | O: no line says the queue closes (38); `reports` moves into a lambda capture (34, 45-46). S: `?? void` (39) then line 40 `reporter.error is? error` misses a carrying pair |
| 22 | 2/3/4/4/4 | O: three handlers (13, 14, 18) behave differently for the same call, and line 18's behavior depends on a runtime bit. D: need to name both kinds (14). C: double parentheses (13-14). S/K: static narrowing for `is? error`/`error` arm of a CleanupError that is "sometimes Canceled" is unspecified (31) |
| 23 | 4/4/5/4/4 | S/K: drop stops a child (14), a "launch and return" child dies silently, with only a warning; grace on normal exit is contradicted by rule 8 (see must-fix 1); `sleep(200ms)` readiness (9) |
| 24 | 3/3/4/4/4 | O/D: `$__consume__` and hand-written `publish` (4-9). S: no atomicity (28-32) |

**Floor: 2.** Programs at it: 09 (blocked), 18 (O2), 22 (O2). Without 09 the design floor is still 2 (18, 22).

## Differences from the author of 2 or more

Compared per dimension and per floor against dogfood-round5.md:

- 22 Cancellation pair: O2 vs author O4. Same call `save(...) ?? ...` reads three ways (13, 14, 18) and, at 18, defaults or forwards by a runtime bit. This is the only dimension gap of 2 or more. Related: author floor 3 vs my floor 2 is a gap of 1 only, since author excludes 09 and I count 18 and 22.

Everything else is within 1 (04 O/S, 05 O/S, 10 K, 12 S, 13 O/D, 18 O/K, 19 O, 20 O/D, 21 O, 24 O differ by 1). The author's self-grades are mostly honest; the all-5 rows I disagree with are 10 (K 4) and 11 (S 4), each by one point.

## Must-fix checks

M1 (program 22): fixed. `??`, `?? void`, collectors, `?? return/break/continue`, `??<E>` without Canceled forward a carrying pair (round5.md rule 7; 22:13-20); only a handler naming both kinds consumes it; `$explicit_cancellation` diagnoses it. Program 07:15 `??<Canceled>` cannot swallow a failed cleanup. Residual should-fix: static typing of `is? error` and `error` arms for one type (CleanupError) that is sometimes Canceled-like is not specified (22:31); say the else branch keeps CleanupError.

M2 (programs 10, 20, 24): fixed. A drop hook never commits. `return none` (10:11, 20:15), failure returns, `break`/`continue` (20:7-8), `exit(0)` (20:23-24) all roll back; success-shaped exits after a change only warn. Program 24: field drop order cannot publish. Residual (not must): forgetting `commit` on a success return rolls back with a warning only, never an error.

Locks (program 04): holds. `break` (7) and `return` (12) cross the held guard and release it; fallthrough releases per iteration (13); braces shorten the hold (19-22). Value-semantics and deadlock/wait checks are stated in round5.md S1.

## Must-fix: 1

1. Child drop deadline contradicts rule 8. Program 23:14 and round5.md M2 say drop requests stop, "waits within the grace", then kills; rule 8 says the grace exists only once the task is canceled and normal-exit cleanup has no deadline. Scenario: `make` returns non-zero, `main` returns BuildFailed (23:7) while a child that ignores the stop signal is alive (as with `server` at 23:11); drop waits forever on a normal exit. State a per-hook stop timeout independent of cancellation, then kill.

## Should-fix (not counted)

- A discarded owner expression (`terminal.raw(...) or_throw;`, `db.begin(...) or_throw;`) is unspecified; it should be an error or warning like the unread binding at 18:18.
- Hand-built `CleanupError[primary=Canceled ...]` (13:12): say whether the cancellation bit is derived from the causes.
- Rule 10 says library resources never rely on defer, but shared `Channel` close (14:6) does; state it as the carve-out in rule 10.
- A read-only file's failed close aborts a loop on `continue` (15:7); consider whether read-only owners can have a non-failing close.
