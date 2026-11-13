# Dogfood: combining failures, David's design

**Author grades on paper programs, not an independent review. Nothing was compiled.** Fourteen
programs in `programs/`. Grades are O/D/C/S/K: obvious, discoverable, concise, safe by default,
complete. 5 = direct for the stated workload; 4 = a local cost or something to learn; 3 = real
protocol knowledge or an unresolved subcase; 2 = a main-path weakness; 1 = the scenario fails.

Round 1 is the design in `round1.md`; round 2 (`round2.md`) dropped one rule and changed three
programs. Line citations are to the programs as they now stand; where round 2 changed a line, the
round-1 text is quoted.

**Peers.** For the eight scenarios the round-3 errors study also covered, peer grades are adopted
unchanged from its independent regrade (`docs/design/proposals/errors/regrade-round3.md`, with
line-cited peer programs in `proposals/errors/peers/`); the workloads are close but not identical,
and the mapping is given per program. For the six new scenarios (01, 02, 06, 11, 13, 14) peer
grades are mine, from each language's standard idiom, named in the row; no peer code was written
for them, so those rows cite the idiom, not lines.

## Summary

| Program | Dewy R1 | Dewy R2 | Python | Go | Rust | TypeScript | Swift |
|---|---|---|---|---|---|---|---|
| 01 Combine and match | 5/4/4/5/5 | 5/4/4/5/5 | 4/4/4/3/4 | 5/4/5/3/4 | 4/4/3/5/5 | 4/4/4/2/3 | 4/3/3/4/4 |
| 02 Handler doesn't swallow | 4/4/5/5/5 | 4/4/5/5/5 | 4/4/4/4/4 | 4/4/4/2/3 | 4/4/4/3/3 | 4/3/4/3/3 | 4/4/4/3/3 |
| 03 Form validation | 4/4/5/5/5 | 5/4/5/5/5 | 5/4/4/4/4 | 5/4/5/4/4 | 5/4/4/5/4 | 5/4/5/4/4 | 5/4/4/4/4 |
| 04 Batch files | 4/4/5/5/5 | 5/4/5/5/5 | 4/4/4/4/5 | 4/4/4/4/5 | 4/4/3/4/5 | 4/4/4/4/5 | 4/4/4/4/5 |
| 05 Cleanup of a written file | 4/4/4/5/5 | 4/4/4/5/5 | 4/4/3/4/4 | 5/4/5/4/4 | 4/4/3/4/4 | 4/4/5/4/4 | 4/4/3/4/4 |
| 06 Two files fail to close | 4/4/4/5/5 | 4/4/4/5/5 | 4/4/4/3/3 | 4/3/3/3/4 | 3/3/3/3/3 | 4/3/4/4/4 | 3/3/3/2/2 |
| 07 Parallel failures | 4/4/5/5/4 | 5/4/5/5/4 | 4/4/3/4/5 | 4/4/3/4/5 | 4/4/3/5/5 | 5/5/5/4/5 | 4/4/3/5/5 |
| 08 Library context | 5/4/5/5/5 | 5/4/5/5/5 | 5/4/5/3/4 | 4/4/5/4/4 | 4/4/3/5/4 | 4/4/5/4/4 | 4/4/4/4/4 |
| 09 CLI locations | 4/4/5/5/5 | 4/4/5/5/5 | 5/5/5/4/4 | 4/3/2/4/3 | 4/3/2/4/3 | 4/3/2/4/3 | 4/3/2/4/3 |
| 10 Retry | 4/5/5/5/5 | 4/5/5/5/5 | 4/4/4/4/4 | 4/4/4/4/4 | 4/4/3/4/4 | 4/4/4/4/4 | 4/4/4/4/4 |
| 11 Combined records | 4/5/5/5/5 | 4/5/5/5/5 | 5/5/4/4/4 | 5/4/4/5/5 | 5/5/4/5/4 | 5/5/5/2/3 | 4/4/4/5/4 |
| 12 Cancel during cleanup | 4/4/4/5/5 | 4/4/5/5/5 | 4/4/4/4/4 | 4/4/4/3/4 | 4/3/3/4/4 | 4/3/3/3/4 | 4/3/3/3/4 |
| 13 Generic T & U | 4/4/4/5/5 | 4/4/4/5/5 | 4/4/4/3/4 | 4/4/5/3/4 | 4/4/3/5/5 | 4/4/4/2/3 | 4/4/3/4/4 |
| 14 Transaction rollback | 4/4/5/5/5 | 4/4/5/5/5 | 4/4/5/4/3 | 5/4/4/3/3 | 4/4/5/3/3 | 4/4/3/3/3 | 3/3/3/3/3 |

**Floor 4, not all-5.** No program reaches 5 on every axis. Safety is 5 throughout: no program
can lose a failure part without a compile error. The remaining 4s come from four sources, none
fixable inside this design without new surface (each is listed under "What stays below 5"):
automatic cleanup that only hover shows (D40 Q1's accepted design), names not yet cold-read,
the four-branch shape for combining two maybe-failures, and two rules a reader must learn
(arms versus `is?`, and cancellation dominance under option A).

## Evidence

### 01 Combine and match: 5/4/4/5/5

- **O5:** the match at [01:17-22](programs/01_combine_and_match.dewy) reads as David's sketch, and
  `as` at [01:25-26](programs/01_combine_and_match.dewy) says what it takes.
- **D4:** [01:19](programs/01_combine_and_match.dewy) `quota:QuotaExceeded` doesn't take the pair,
  while [01:23](programs/01_combine_and_match.dewy) `is? QuotaExceeded` is true for it. Two
  consistent rules (handling names every part, using takes one), but both must be learned.
  Totality catches a missing pair arm, which helps.
- **C4:** [01:9-11](programs/01_combine_and_match.dewy): three branches to turn two maybe-failures
  into one result. Go's `errors.Join(a, b)` does it in one call (but loses the types).
- **S5:** totality forces [01:18](programs/01_combine_and_match.dewy); the projection at
  [01:23](programs/01_combine_and_match.dewy) leaves `result` whole.
- **K5:** all four cases and both parts are reachable ([01:18-21](programs/01_combine_and_match.dewy), [01:24-27](programs/01_combine_and_match.dewy)).
- Peers (idiom, not code): Python `ExceptionGroup` plus `except*` (S3: no static check that the
  group is handled); Go `errors.Join` and `errors.As` (C5; S3: an ignored `err` compiles; K4:
  the four cases aren't in any type); Rust tuple `match (r1, r2)` but a handwritten enum with a
  `Both` variant to return it (C3, S5); TypeScript `AggregateError` with untyped `.errors` (S2,
  K3); Swift typed throws carry one type, so an enum with a `both` case (D3, C3).

### 02 Handler doesn't swallow: 4/4/5/5/5

- **O4:** [02:14](programs/02_handler_does_not_swallow.dewy) reads as "parse failures give 100";
  that `ParseError & FileCloseFailed` passes through is the rule, not the text
  ([02:15](programs/02_handler_does_not_swallow.dewy) says it in a comment).
- **D4:** the combinations exist only in the inferred type
  ([02:10-12](programs/02_handler_does_not_swallow.dewy)); hover shows them.
- **C5:** one line ([02:14](programs/02_handler_does_not_swallow.dewy)).
- **S5:** the close failure can't be dropped by a fallback that doesn't name it, and
  [02:17](programs/02_handler_does_not_swallow.dewy) forwards whatever stays.
- **K5:** every outcome of [02:4-10](programs/02_handler_does_not_swallow.dewy) reaches `main`.
- Peers: Python `except* ParseError` re-raises the rest of a group automatically (S4), but a
  `with` block's close failure replaces the body's exception, which survives only as
  `__context__` (K4); Go `defer f.Close()` drops close errors unless a named return and
  `errors.Join` are added (S2, K3); Rust `File`'s `Drop` ignores close errors (S3, K3);
  TypeScript `using` gives `SuppressedError`, matched by its own shape (D3, S3); Swift `defer`
  can't throw (S3, K3).

### 03 Form validation: R1 4/4/5/5/5, R2 5/4/5/5/5

- **O:** R1 4: line 12 was `ErrorStack[problems...] or_throw`, which relied on "an empty spread
  makes no stack". R2 5: [03:12](programs/03_form_validation.dewy) is the guard Python writes.
- **D4:** a programmer must find `ErrorStack` ([03:12](programs/03_form_validation.dewy)); an
  `array<FieldError>` returned instead would type-check as a success value. The name is not yet
  cold-read.
- **C5:** [03:6-12](programs/03_form_validation.dewy): one array, one push per check, one guard.
- **S5:** no `User` is built with problems ([03:12-13](programs/03_form_validation.dewy)); a stack
  can't be empty.
- **K5:** field order kept, typed fields shown ([03:18](programs/03_form_validation.dewy)).
- Peers: the round-3 form-validation row, unchanged ([regrade-round3.md:42](../../../dewy-lang/docs/design/proposals/errors/regrade-round3.md)).

### 04 Batch files: R1 4/4/5/5/5, R2 5/4/5/5/5

- **O:** R1 4: line 18 was `return ErrorStack[skipped...]`, void when empty. R2 5:
  [04:18](programs/04_batch_files.dewy) is an explicit guard; [04:10](programs/04_batch_files.dewy)
  reads plainly.
- **D4:** [04:10](programs/04_batch_files.dewy): `or_throw<Canceled>` before `is? error` is the
  idiom to learn. Leaving it out is a compile error at [04:15](programs/04_batch_files.dewy)
  (`n` may still be `Canceled`), whose fix-it writes it.
- **C5:** [04:7-18](programs/04_batch_files.dewy) is the Python shape.
- **S5:** Ctrl-C leaves at once ([04:10](programs/04_batch_files.dewy)); every skipped file is kept.
- **K5:** count and all failures ([04:17-18](programs/04_batch_files.dewy)).
- Peers: the round-3 batch-files row ([regrade-round3.md:51](../../../dewy-lang/docs/design/proposals/errors/regrade-round3.md)).

### 05 Cleanup of a written file: 4/4/4/5/5

- **O4:** [05:8](programs/05_cleanup_written_file.dewy): the close and its possible failure are not
  in the source; hover and highlighting show them (D40 Q1's accepted condition).
- **D4:** [05:15](programs/05_cleanup_written_file.dewy): the pair arm is optional
  ([05:20](programs/05_cleanup_written_file.dewy) takes the pair too, every part being a
  `FileError`), so the programmer learns the pair exists from hover, not from an error.
- **C4:** [05:16-17](programs/05_cleanup_written_file.dewy): `(both as FileWriteFailed).message`
  needs parentheses for each part read.
- **S5:** both failures survive ([05:18](programs/05_cleanup_written_file.dewy)); cancellation
  carriers are forwarded first ([05:12](programs/05_cleanup_written_file.dewy)).
- **K5:** write, close and both are distinguished.
- Peers: the round-3 cleanup-pair row ([regrade-round3.md:33](../../../dewy-lang/docs/design/proposals/errors/regrade-round3.md)).

### 06 Two files fail to close: 4/4/4/5/5

- **O4:** [06:11-15](programs/06_two_files_fail_to_close.dewy): that two live owners of one type
  give a stack, even when only one fails, is a rule to know.
- **D4:** `ErrorStack<FileCloseFailed>` appears only in the inferred type
  ([06:13-14](programs/06_two_files_fail_to_close.dewy)).
- **C4:** [06:19-21](programs/06_two_files_fail_to_close.dewy): a test, a projection and a loop to
  list the files; `as` binds looser than `in`, so the projection needs its own line or parentheses.
- **S5:** both closes are reported, in close order; [06:23](programs/06_two_files_fail_to_close.dewy)
  forwards everything.
- **K5:** the write failure and the stack combine
  ([06:14](programs/06_two_files_fail_to_close.dewy)).
- Peers: Python `with open(a) as f, open(b) as g` keeps the second close failure only as the
  first's `__context__` (S3, K3); Go needs two deferred closures writing a named `err` with
  `errors.Join` (D3, C3, S3); Rust `Drop` drops both (all 3); TypeScript `using` nests
  `SuppressedError`s (D3); Swift `defer` can't throw (S2, K2).

### 07 Parallel failures: R1 4/4/5/5/4, R2 5/4/5/5/4

- **O:** R1 4: line 12 was `ErrorStack[failed...] or_throw`. R2 5:
  [07:12](programs/07_parallel_failures.dewy) is a guard.
- **D4:** `partition_failures` and `ErrorStack` together must be found
  ([07:11-12](programs/07_parallel_failures.dewy)).
- **C5:** [07:10-13](programs/07_parallel_failures.dewy).
- **S5:** cancellation leaves the collector ([07:10](programs/07_parallel_failures.dewy)); all
  failures kept in upload order.
- **K4:** [07:15-23](programs/07_parallel_failures.dewy): a `parallel` *block* reporting both of two
  independent failures depends on the extension in round1.md, not on decided behavior; today it
  returns the first.
- Peers: the round-3 parallel-items row ([regrade-round3.md:60](../../../dewy-lang/docs/design/proposals/errors/regrade-round3.md)).

### 08 Library context: 5/4/5/5/5

- **O5:** [08:17-22](programs/08_library_context.dewy): wrapping in a domain error with a cause is
  ordinary record construction.
- **D4:** [08:2](programs/08_library_context.dewy): a library author must choose a cause field over
  `&`; round 2 adds the guideline, but it is a choice to be taught.
- **C5:** one line per wrap ([08:19](programs/08_library_context.dewy), [08:21](programs/08_library_context.dewy)).
- **S5:** `cause:error` holds a combination whole ([08:4](programs/08_library_context.dewy));
  carriers are forwarded ([08:18](programs/08_library_context.dewy)).
- **K5:** the message includes the cause's text, and the cause keeps its `$origin`.
- Peers: the round-3 library-context row ([regrade-round3.md:69](../../../dewy-lang/docs/design/proposals/errors/regrade-round3.md)).

### 09 CLI locations: 4/4/5/5/5

- **O4:** [09:14](programs/09_cli_locations.dewy): `$parts` and `$origin` are new and not cold-read.
- **D4:** [09:18](programs/09_cli_locations.dewy) depends on `$origin_at_caller` in the library,
  which a reader learns from docs.
- **C5:** one line ([09:14](programs/09_cli_locations.dewy)).
- **S5:** Ctrl-C is forwarded before printing ([09:12](programs/09_cli_locations.dewy)).
- **K5:** every part with its location ([09:18-20](programs/09_cli_locations.dewy)). Cost of
  origins is unmeasured (round1.md, point 6), which is a gate, not a grade.
- Peers: the round-3 CLI-diagnostics row ([regrade-round3.md:78](../../../dewy-lang/docs/design/proposals/errors/regrade-round3.md)).

### 10 Retry: 4/5/5/5/5

- **O4:** [10:5](programs/10_retry.dewy) and [10:9](programs/10_retry.dewy): `loop true` with the
  stop inside, chosen so the stack's nonemptiness is proven by the push just before it;
  `loop attempt in [1..attempts]` would read better but leaves the proof to a loop fact the
  compiler may not have.
- **D5, C5:** ordinary loop, array and stack ([10:4-11](programs/10_retry.dewy)).
- **S5:** Ctrl-C stops at the connect or the backoff ([10:6](programs/10_retry.dewy),
  [10:10](programs/10_retry.dewy)); the attempt history is deliberately not reported then.
- **K5:** count and last failure ([10:16](programs/10_retry.dewy)).
- Peers: the round-3 retry row ([regrade-round3.md:87](../../../dewy-lang/docs/design/proposals/errors/regrade-round3.md)).

### 11 Combined records: 4/5/5/5/5

- **O4:** [11:9](programs/11_combined_records.dewy): `profile.id` is an error, which a TypeScript
  reader, used to `User & Settings` merging fields, won't expect.
- **D5:** the ambiguity error names both fixes.
- **C5:** [11:7-10](programs/11_combined_records.dewy).
- **S5:** neither `id` is silently chosen.
- **K5:** both parts used ([11:7](programs/11_combined_records.dewy), [11:10](programs/11_combined_records.dewy)).
- Peers: Python, a tuple or composite class (`profile.user.id`; C4, S4, K4: no "both" type);
  Go struct embedding, where an ambiguous promoted field is a compile error (the same rule), but
  passing `p` where `User` is wanted needs `p.User` (D4, C4); Rust a struct of both (C4, K4: no
  shared view); TypeScript `{...user, ...settings}` silently keeps one `id` (S2, K3); Swift
  protocol composition covers protocols only (O4, D4, C4, K4).

### 12 Cancel during cleanup: R1 4/4/4/5/5, R2 4/4/5/5/5

- **O4:** [12:10-11](programs/12_cancel_during_cleanup.dewy): the carrier comes from cleanup that
  isn't in the source.
- **D4:** [12:17](programs/12_cancel_during_cleanup.dewy): under option A an arm must name
  `Canceled` to take `Canceled & FileCloseFailed`, and `is? FileCloseFailed` is false on it
  (dominance). Totality points to the missing arm.
- **C:** R1 4: two near-duplicate arms (`stopped:Canceled` and `both:Canceled & FileCloseFailed`).
  R2 5: one arm names both shapes ([12:17](programs/12_cancel_during_cleanup.dewy)).
- **S5:** the close failure is printed with the cancellation and exit stays 130
  ([12:18-19](programs/12_cancel_during_cleanup.dewy)).
- **K5:** write failures, cancellation and the pair are all covered ([12:15-22](programs/12_cancel_during_cleanup.dewy)).
- Peers: the round-3 cancellation-boundary row ([regrade-round3.md:96](../../../dewy-lang/docs/design/proposals/errors/regrade-round3.md)).

### 13 Generic T & U: 4/4/4/5/5

- **O4, D4:** [13:5](programs/13_generic_pair.dewy): at `T == U` the result is a stack; only the
  comment and hover say so.
- **C4:** [13:3-7](programs/13_generic_pair.dewy): the same three-branch combining as 01.
- **S5:** nothing is lost at `T == U`; an ambiguous `as T` in the body would be rejected.
- **K5:** both instances used ([13:15-19](programs/13_generic_pair.dewy)).
- Peers: Python, any `ExceptionGroup` (S3); Go generics plus `errors.Join` (C5, S3); Rust
  `enum Both<T, U>` with no special case at `T == U` (C3, S5); TypeScript `AggregateError` (S2,
  K3); Swift a generic enum (C3).

### 14 Transaction rollback: 4/4/5/5/5

- **O4:** [14:13](programs/14_transaction_rollback.dewy): the rollback runs at scope end through
  `$__abandon__`, visible by hover.
- **D4:** `db.RollbackFailed` ([14:19](programs/14_transaction_rollback.dewy)) is known from the
  inferred type.
- **C5:** [14:18-22](programs/14_transaction_rollback.dewy).
- **S5:** [14:19](programs/14_transaction_rollback.dewy) is true for any failure whose rollback
  failed, and [14:22](programs/14_transaction_rollback.dewy) forwards both parts.
- **K5:** query, shortfall and rollback failures all distinguished ([14:14-15](programs/14_transaction_rollback.dewy)).
- Peers: Python `with conn:` rolls back, and a failed rollback replaces the original (K3); Go
  `defer tx.Rollback()` ignores its error (S3, K3); Rust drop-based rollback logs or ignores
  (S3, K3); TypeScript try/finally where a rollback error replaces the original (C3, S3, K3);
  Swift has no throwing cleanup (all 3).

## What stays below 5, and why it isn't fixed here

- **Cleanup visible only by hover** (O or D in 05, 06, 12, 14): D40 Q1 accepted automatic cleanup
  with hover and highlighting. Not this round's to change.
- **New names not cold-read** (03, 07, 09): `ErrorStack`, `$parts`, `$origin`,
  `$origin_at_caller`. Fixed by the cold read, not by the design.
- **Combining two maybe-failures takes three branches** (C in 01, 13). A one-call helper would be
  new surface (a library function name); reported, not proposed. A tuple `match` doesn't help yet:
  separate arms can't pool coverage (`match.md`, totality).
- **Two rules to learn**: arms versus `is?` on combinations (D in 01, 05), and option A's
  cancellation dominance (D in 12). Inherent to the design and to option A respectively.
- **Projection reads need parentheses** (C in 05, 06): `(both as X).field`, from `as` binding
  loosely. Not specific to this design.
- **The `parallel` block extension** (K in 07) needs a concurrency decision.
- **Loop facts for nonempty arrays** (O in 10): a fact-engine question, outside this design.
