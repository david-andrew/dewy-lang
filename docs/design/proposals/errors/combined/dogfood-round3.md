# Dogfood, round 3

**Author regrade of `programs-r3/`, starting from the independent regrade
(`regrade-round2.md`), not from my round-2 grades.** Each Dewy grade below is the independent
grade, changed only where round 3 changed the design or the program, and each change says why.
Peer grades for 01–14 are the independent ones, unchanged (they credit an explicit, preserving
peer implementation and charge its ceremony). Program 15 is new; its peer grades are mine, made
the same way. Nothing was compiled. O/D/C/S/K = obvious, discoverable, concise, safe by default,
complete.

## Summary

| Program | Independent R2 | Dewy R3 | Python | Go | Rust | TypeScript | Swift |
|---|---|---|---|---|---|---|---|
| 01 combine and match | 4/3/5/5/5 | 5/4/5/5/5 | 4/4/4/5/5 | 4/4/3/5/5 | 4/4/3/5/5 | 4/4/3/4/5 | 4/4/3/5/5 |
| 02 handler does not swallow | 4/3/5/5/5 | 4/3/5/5/5 | 4/4/4/5/5 | 4/3/3/4/5 | 4/4/3/5/5 | 4/4/3/4/5 | 4/4/3/4/5 |
| 03 form validation | 5/4/5/5/4 | 5/4/5/5/5 | 5/5/5/5/5 | 5/5/4/5/5 | 5/5/4/5/5 | 5/5/5/5/5 | 5/5/4/5/5 |
| 04 batch files | 4/3/5/4/3 | 5/4/5/5/5 | 5/4/4/5/5 | 5/4/4/4/5 | 5/4/4/5/5 | 5/4/4/4/5 | 5/4/4/4/5 |
| 05 cleanup written file | 4/3/5/4/5 | 4/3/5/5/5 | 4/4/4/4/5 | 4/4/4/4/5 | 4/4/3/4/5 | 4/4/3/4/5 | 4/4/3/4/5 |
| 06 two files fail to close | 4/3/4/4/4 | 4/3/4/5/5 | 4/4/3/4/5 | 4/4/3/4/5 | 4/4/3/4/5 | 4/4/3/4/5 | 4/4/3/4/5 |
| 07 parallel failures | 4/3/4/4/3 | 4/3/4/5/4 | 4/4/4/4/5 | 4/4/3/4/5 | 4/4/3/4/5 | 4/4/4/4/5 | 4/4/3/4/5 |
| 08 library context | 4/4/5/5/4 | 4/4/5/5/5 | 5/5/5/5/5 | 5/5/4/5/5 | 4/4/4/5/5 | 4/4/4/4/5 | 4/4/4/5/5 |
| 09 CLI locations | 4/3/5/4/4 | 4/3/5/5/5 | 5/4/4/5/5 | 4/3/3/4/5 | 4/3/3/5/5 | 4/3/3/4/5 | 4/3/3/4/5 |
| 10 retry | 5/4/5/5/4 | 5/4/5/5/5 | 5/4/4/5/5 | 5/4/4/4/5 | 5/4/4/5/5 | 5/4/4/4/5 | 5/4/4/4/5 |
| 11 combined records | 3/2/5/4/2 | 4/4/5/5/5 | 5/5/4/5/5 | 5/5/4/5/5 | 5/5/4/5/5 | 5/5/4/5/5 | 5/5/4/5/5 |
| 12 cancel during cleanup | 4/3/4/5/4 | 4/4/5/5/5 | 4/4/3/4/5 | 4/4/3/4/5 | 4/4/3/4/5 | 4/4/3/4/5 | 4/4/3/4/5 |
| 13 generic pair | 3/2/5/4/2 | 4/4/5/5/5 | 4/4/4/4/5 | 4/4/3/4/5 | 4/4/3/5/5 | 4/4/3/4/5 | 4/4/3/5/5 |
| 14 transaction rollback | 4/3/5/4/3 | 4/4/5/5/5 | 4/4/4/4/5 | 4/4/4/4/5 | 4/4/3/4/5 | 4/4/3/4/5 | 4/4/3/4/5 |
| 15 upload boundary (new) | — | 4/3/4/5/5 | 4/4/3/4/5 | 4/4/3/4/5 | 4/4/3/5/5 | 4/4/3/4/5 | 4/4/3/4/5 |

**Floor 3**, all on discoverability, in 02, 05, 06, 07, 09 and 15. Round 2's independent floor
of 2 (programs 11 and 13) came from contradictions between rules, which round 3 removes (M1,
M3). The 3s that remain are rules a programmer must learn before the source explains itself; no
program depends on two rules that disagree. No program is all 5.

## Changes from the independent grades, with evidence

### 01: 4/3/5/5/5 → 5/4/5/5/5

- **O 4→5:** the independent O4 was that `QuotaExceeded` selected the pair in `is?` but not in
  `match`. Arms now select what `is?` selects ([01:17-22](programs-r3/01_combine_and_match.dewy),
  [01:23](programs-r3/01_combine_and_match.dewy)), and the more specific arm goes first, as for
  any overlapping patterns.
- **D 3→4:** one selection rule remains; what is left to learn is that an arm binds the whole
  value and must deal with what its type doesn't name (round3.md Q1).
- C5, S5, K5 unchanged ([01:9-11](programs-r3/01_combine_and_match.dewy) is the three-branch
  combine the independent grade accepted as short).

### 02: 4/3/5/5/5, unchanged

- **O4** ([02:14-15](programs-r3/02_handler_does_not_swallow.dewy)) and **D3**
  ([02:10-15](programs-r3/02_handler_does_not_swallow.dewy)): a fallback that names `ParseError`
  leaves `ParseError & FileCloseFailed` a failure; the consume-all rule and the cleanup
  combinations both have to be learned. Round 3 states the rule as a dual (select any, consume
  all) but doesn't make it visible in the source. The program now writes to a log
  ([02:5](programs-r3/02_handler_does_not_swallow.dewy)), since reads no longer combine (M4).

### 03: 5/4/5/5/4 → 5/4/5/5/5

- **K 4→5:** the stack's nonemptiness is a storage refinement now (round3.md M6), so the invariant
  behind [03:12](programs-r3/03_form_validation.dewy) and [03:18](programs-r3/03_form_validation.dewy)
  holds for the stack's whole life.
- **D4** unchanged: `ErrorStack` must be found and is matched as itself.

### 04: 4/3/5/4/3 → 5/4/5/5/5

- **O 4→5, S 4→5, K 3→5:** the independent deductions rested on the claim that a one-shot read
  can't combine. It is now a stated library contract (round3.md M4: a read-only close can't fail,
  under the existing assumptions row; `read_text` closes before decoding), so
  `array<FileError | InvalidUtf8>` ([04:8](programs-r3/04_batch_files.dewy)) holds every failure
  `count_lines` can give ([04:5-6](programs-r3/04_batch_files.dewy)), and M6 covers the stack
  at [04:19](programs-r3/04_batch_files.dewy).
- **D 3→4:** what is left to learn is forwarding cancellation before testing for ordinary errors
  ([04:11](programs-r3/04_batch_files.dewy)); leaving it out is a type error at
  [04:16](programs-r3/04_batch_files.dewy).

### 05: 4/3/5/4/5 → 4/3/5/5/5

- **S 4→5:** the success message moved to the `<void>` arm, after the close succeeded
  ([05:13](programs-r3/05_cleanup_written_file.dewy)).
- **O4** ([05:7](programs-r3/05_cleanup_written_file.dewy): the cleanup exit is shown only by
  hover) and **D3** ([05:14-19](programs-r3/05_cleanup_written_file.dewy): `problem:FileError`
  is a selector that can bind a pair, while a `FileError` parameter can't hold one, and arm order
  matters) unchanged.

### 06: 4/3/4/4/4 → 4/3/4/5/5

- **S 4→5, K 4→5:** the independent deductions were M5 (cleanup storage) and M6
  (nonemptiness). Round 3 specifies both: failures live in their owners' slots and the stack links
  them ([06:11-13](programs-r3/06_two_files_fail_to_close.dewy)). This is a paper contract with
  its construction gate still open; the grade assumes it is built as specified, as for every other
  program.
- **O4, D3** ([06:11-16](programs-r3/06_two_files_fail_to_close.dewy): stack or single depends
  on the live owners) and **C4** ([06:20-24](programs-r3/06_two_files_fail_to_close.dewy):
  test, project, loop, forward) unchanged. The program no longer forwards cancellation first
  ([06:19](programs-r3/06_two_files_fail_to_close.dewy)): the close report also runs when
  canceled, which is what a user wants.

### 07: 4/3/4/4/3 → 4/3/4/5/4

- **S 4→5, K 3→4:** the one-shot read contract (M4) covers [07:4](programs-r3/07_parallel_failures.dewy).
  K stays 4: the `parallel` block half ([07:16-24](programs-r3/07_parallel_failures.dewy)) still
  needs the undecided extension.
- **C4, D3** unchanged, and the collector now holds `Canceled` like any failure, so a per-element
  forward is one more line ([07:11](programs-r3/07_parallel_failures.dewy)).

### 08: 4/4/5/5/4 → 4/4/5/5/5

- **K 4→5:** the independent K4 was that `Canceled & FileCloseFailed` escaped the one-error
  abstraction. A read-only close can't fail (M4), so `load`'s result is `Config | ConfigError |
  Canceled` ([08:9](programs-r3/08_library_context.dewy), [08:23](programs-r3/08_library_context.dewy)).
  Where cleanup can fail at a boundary, program 15 shows the wrapping policy.
- **O4, D4** unchanged: cause wrapping is learned separately from combining
  ([08:2](programs-r3/08_library_context.dewy), [08:18-21](programs-r3/08_library_context.dewy)).

### 09: 4/3/5/4/4 → 4/3/5/5/5

- **S 4→5, K 4→5:** the independent deductions were the storage contract (M5) and the metadata
  boundary (S4). Both are specified now: origins within the whole-program source build, the demand
  closure listed, traces bounded with the empty-trace limit disclosed (round3.md S4). Only the
  write handle's close can fail ([09:8-9](programs-r3/09_cli_locations.dewy)).
- **O4, D3** unchanged: [09:14](programs-r3/09_cli_locations.dewy) hides flattening by `$parts`,
  demand-driven storage and the library's caller attribution. The cold read confirmed the names
  (`$parts` 4, `$origin` 4/4/4, `$origin_at_caller` 4/4/3), which doesn't reveal the mechanisms.

### 10: 5/4/5/5/4 → 5/4/5/5/5

- **K 4→5:** M6 makes the stack nonempty for life, and `.last` needs no index proof
  ([10:16](programs-r3/10_retry.dewy)).
- **D4** unchanged.

### 11: 3/2/5/4/2 → 4/4/5/5/5

- **O 3→4, D 2→4, S 4→5, K 2→5:** M1. `User & Settings` now means one thing everywhere: minted
  types are facets, plain records merge, and an alias means what its expression means. The program
  mints both types ([11:4-5](programs-r3/11_combined_records.dewy)) and shows plain records
  merging ([11:14-16](programs-r3/11_combined_records.dewy), [11:19](programs-r3/11_combined_records.dewy)).
- O and D stay 4: a reader must know that minting is what keeps two `id`s
  ([11:2-3](programs-r3/11_combined_records.dewy)); the error for plain records that share a field
  names the fix ([11:21-23](programs-r3/11_combined_records.dewy)).

### 12: 4/3/4/5/4 → 4/4/5/5/5

- **D 3→4:** the dominance rule is gone, and `Canceled` is ordinary. What is left to learn is that
  `stopped:Canceled` takes `Canceled & FileCloseFailed` whole ([12:16](programs-r3/12_cancel_during_cleanup.dewy)).
- **C 4→5:** the arm no longer repeats the cleanup shape; one test reports the close failure
  ([12:17](programs-r3/12_cancel_during_cleanup.dewy)).
- **K 4→5:** a `Canceled` arm takes every cancellation however many cleanups failed, so adding an
  owner doesn't break it; program 15 shows the declared form at a boundary.
- **O4** unchanged ([12:10-11](programs-r3/12_cancel_during_cleanup.dewy), cleanup by hover).

### 13: 3/2/5/4/2 → 4/4/5/5/5

- **O 3→4, D 2→4, K 2→5:** M3. The duplicate rule is the same in generic and concrete code,
  checked at each use, with the same message ([13:26-27](programs-r3/13_generic_pair.dewy)).
  Repeats go through an explicit stack helper ([13:14-21](programs-r3/13_generic_pair.dewy)).
  O and D stay 4: the error appears at the call, not in `run_both`.
- **S 4→5:** `is? exception` ([13:5](programs-r3/13_generic_pair.dewy)) never combines a success;
  `T = U = Canceled` is the duplicate error; `ErrorStack<E>` requires `E` to be an error
  ([13:20](programs-r3/13_generic_pair.dewy)).

### 14: 4/3/5/4/3 → 4/4/5/5/5

- **D 3→4, S 4→5, K 3→5:** the commit's owner states are stated (round3.md M4): success consumes
  the transaction, a failed commit leaves it to roll back, so `CommitFailed & RollbackFailed` is
  listed ([14:12-16](programs-r3/14_transaction_rollback.dewy)). The program no longer forwards
  cancellation first ([14:19](programs-r3/14_transaction_rollback.dewy)), so the rollback warning
  also prints when canceled.
- **O4** unchanged ([14:13](programs-r3/14_transaction_rollback.dewy): rollback by hover).

### 15 (new): 4/3/4/5/5

- **O4:** [15:20-25](programs-r3/15_upload_boundary.dewy) is policy a reader must follow: success,
  bare cancellation, everything wrapped, cancellation kept as its own part.
- **D3:** `result as error` taking every error part ([15:23](programs-r3/15_upload_boundary.dewy))
  and `(result as Canceled) and failed` ([15:24](programs-r3/15_upload_boundary.dewy)) are the
  two pieces to learn; neither is guessable from ordinary narrowing.
- **C4:** four lines of policy for a four-alternative declared result
  ([15:19-25](programs-r3/15_upload_boundary.dewy)), against the 112 alternatives of the exact
  type.
- **S5:** nothing is lost: error parts go into `cause` whole, cancellation stays forwardable
  ([15:24](programs-r3/15_upload_boundary.dewy)).
- **K5:** four live resources, any subset of cleanup failures, with or without cancellation
  ([15:8-18](programs-r3/15_upload_boundary.dewy)).
- Peers: an explicit preserving implementation in each, as the independent regrade credits:
  Python `ExitStack` plus a collecting wrapper (C3: suppressed exit failures chain through
  `__context__` unless collected by hand); Go deferred closes joined into a named `err`, with
  `errors.Is(err, context.Canceled)` kept apart (C3); Rust explicit fallible closes and an enum
  (C3, S5); TypeScript `await using` with `SuppressedError` plus an abort check (C3); Swift
  explicit cleanup in `do/catch` and a wrapper error (C3).

## What stays below 5

- **Discoverability 3** (02, 05, 06, 07, 09, 15): the consume-all versus select-any rule; a
  selector type that can bind a pair a parameter of that type can't hold; stack shape following
  the live owners; mechanisms one metatag line hides; the boundary-wrapping policy. These are
  rules to teach, with diagnostics that name them; they don't contradict each other.
- **Cleanup shown only by hover** (O4 in 05, 06, 12, 14): D40 Q1's accepted design.
- **Concision 4** (06, 07, 15): stack inspection, the per-element cancellation forward the
  collector now needs, and boundary wrapping.
- **The `parallel` block extension** (K4 in 07): a concurrency decision.
- **Gates, not grades:** the obligation analysis's cost on the flagship panel; owner slots and
  stack linking built and tested with allocation refused; origin and trace sizes measured.
