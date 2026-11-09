# Strict bundles and assumptions consistency review

Review baseline: `b7d9591fc` on `wt/assume`. Scope: assumption opt-outs, library bundles, related tests, and design-document status/pointers. Repository changes are limited to new assumption tests and doc accuracy edits. Budget: four hours.

Committed review changes as `ea4fa2974` on `wt/assume`; the worktree and branch are intentionally left in place.

## Findings in progress

- `docs/design/assumptions.md` lists 14 assumption rows: three implemented metatag opt-outs, eight pending rows, and two deadlock-certificate assumptions with no automatic opt-out. The first row also contains a parallel-range cap that the stated opt-out does not disable.
- `lib/directives.dewy` defines `$no_hidden_costs`, `$finite_floats`, and `$bulletproof`. The last includes all three implemented opt-outs. Existing tests cover each opt-out at least partly, but the requested default/strict/error/fix-it pairing needs closer examination.
- **Blocking consistency gap:** `$confine_external_paths` produces a warning and leaves `check` successful (`compiler/safe_paths.jo:1157`), exactly as `docs/design/contained_paths.md` specifies. It does not meet this brief's compile-error criterion. Changing it would change decided semantics and is outside this review's allowed files.
- **Coverage gap:** `$no_assumed_bounds` gates facts for counters and array lengths, but `lib/std/thread.jo:103` still silently caps a `parallel` range of at least 2^63 values to 2^63−1. This is listed in the first assumption row yet is unaffected by the opt-out.

## Row-by-row review

“Criterion” means a test of default compilation, opt-out compile error, and repair suggestion. “Yes” under bundle means a literal or transitive member of `$bulletproof`; “partial” identifies a narrower member than the full assumption.

| # | Default assumption / mechanism | Opt-out implemented? | LANGUAGE.md? | In `$bulletproof`? | Criterion and evidence |
|---|---|---|---|---|---|
| 1 | Bounded 64-bit counter/accumulator cannot overflow; parallel range ≥2^63 is capped | **Partial.** `$no_assumed_bounds` disables the facts axiom (`compiler/facts.jo`); the parallel cap in `lib/std/thread.jo:103` remains. | Counter yes, around line 752; parallel cap no. | `$no_assumed_bounds` yes, cap unaffected. | Counter yes: `tests/test_counter_progress_axiom.py`, new `tests/test_assumption_optouts.py`. Cap no proof/diagnostic test. |
| 2 | Array length fits in 2^56 bytes | Yes: `$no_assumed_bounds` in `compiler/facts.jo:7078`. | Yes, around line 754. | Yes. | Yes: `tests/test_array_bound_scopes.py`, new test with default, error, and repair text. |
| 3 | Library `assert`/`unreachable` trusted as invariants, not `panics` | No; effects code exempts library sites (`compiler/effects.jo:2227`). | No opt-out to document. | No. | Pending; no possible negative test. |
| 4 | OOM/oversized array shape and runtime core are environmental, not `panics` | **Partial:** `$explicit_allocation_failure` exposes allocation failure; runtime core remains trusted. | Allocation policy yes, around line 3851; no full opt-out. | Partial: `$explicit_allocation_failure`. | Allocation member tested in `tests/test_bulletproof.py`; full assumption not testable. |
| 5 | Library environmental failure (`__environment_failure`) is not `panics` | No. | No. | No. | Pending. |
| 6 | Library obligations retain implicit runtime checks under a static user policy | No (`compiler/directives.jo:278`). | The distinction is discussed, but no opt-out. | No. | Pending. |
| 7 | Library raw memory is trusted by arena escape analysis | No (`compiler/arena.jo:371`). | No. | No. | Pending. |
| 8 | Library drop hooks cannot fail | No (`compiler/ownership.jo:106`). | No. | No. | Pending. |
| 9 | Local `$runtime_assert` does not make same-module callers `panics` | Yes: `$assume_local_asserts=false` (provisional). | Yes, around line 678. | Yes. | Yes: `tests/test_local_asserts.py`, new default/error/repair test, plus `tests/test_bulletproof.py`. |
| 10 | Whole external paths need no confinement proof | Yes: `$confine_external_paths` (provisional). | Yes, around line 3235. | Yes. | **No compile error:** default passes, opt-out warns with repair text but still passes. `tests/test_contained_paths.py` and new test pin the documented warning. |
| 11 | `$no_inf` assumes entering values finite | No; `compiler/floats.jo:234,326` documents/implements the assumption. | Yes, around line 853, as a limitation; no opt-out. | `$finite_floats` includes `$no_inf`, but does not remove the entering-value assumption. | Pending. |
| 12 | Fair scheduler, terminating local computation, cooperative external peers | No machine-checkable opt-outs: these are explicit premises of the `$no_deadlocks` theorem. | Yes, Deadlock certificates around line 2879. | `$no_deadlocks` yes; premises remain. | No test can prove environmental premises. |
| 13 | `$audited_wait` asserts an adapter waits only on outside world | Intentionally no opt-out; a person asserts it at the adapter. | Yes in Deadlock certificates. | The bundle includes `$no_deadlocks`, which accepts the claim; no ban on `$audited_wait`. | `tests/cases/no_deadlocks/audited_adapter.dewy` tests acceptance, not proof of the claim. |
| 14 | `serve`/`pipeline` protocol waits match library certificates | No verification gate or opt-out. | Protocol certificates described, no opt-out. | `$no_deadlocks` accepts these protocols on trust. | Existing protocol tests exercise examples, not a model-checking proof. Pending. |

## Bundle review

| Bundle in `lib/directives.dewy` | Implemented and documented? | In `$bulletproof`? | Evidence / limit |
|---|---|---|---|
| `$no_hidden_costs` | Yes; `docs/LANGUAGE.md` Directives around line 4328. | Yes. | `tests/test_bulletproof.py` covers static index, default row and costly copy errors, and scope opt-out. It cannot force the library's own runtime obligations into static proof. |
| `$finite_floats` | Yes; `docs/LANGUAGE.md` Floats around line 842 and Directives. | Yes. | `tests/test_bulletproof.py` covers `$no_inf` and `$no_nan` operation failures. The entering-value assumption of `$no_inf` remains. |
| `$bulletproof` | Yes as a composed bundle; `docs/LANGUAGE.md` Directives around line 4338. | Self. | `tests/test_bulletproof.py` has a proven program and negative members. It is **not yet certifiably strictest** because rows 3–8, 11 and 14 remain pending, row 10 warns, and row 1's parallel cap persists. |

Its other direct members are `$explicit_allocation_failure`, `$no_deadlocks`, `$no_assumed_bounds`, `$assume_local_asserts=false`, and `$confine_external_paths`; all are implemented and documented, with the limits above. `$bulletproof=false` is scoped, but the allocation-failure module policy remains set, as documented.

## Pending spellings for David

These are **recommendations, not accepted names**. Each is reversible before published use; semantics need David's approval. The mechanism also needs an implementation plan that can demand a real proof rather than just reject all library use.

1. **`$no_trusted_library_asserts`** (row 3): make library `assert`/`unreachable` visible as proof obligations or `panics`; unblocks checking transitive library calls under `$bulletproof`.
2. **`$explicit_runtime_failure`** (row 4): account for runtime-core and oversized-shape failures as returned failures, alongside existing `$explicit_allocation_failure`; unblocks an explicit failure boundary for the core. Name and failure value are provisional.
3. **`$explicit_environment_failure`** (row 5): expose `__environment_failure` to the effect/result contract; unblocks explicit handling of input, driver, and test-runner failures.
4. **`$no_implicit_library_checks`** (row 6): require library obligations to meet static policy or explicit failure handling; unblocks real end-to-end no-trap proof.
5. **`$no_trusted_library_memory`** (row 7): subject library raw-memory paths to the arena escape proof; unblocks a checked arena boundary.
6. **`$check_library_drop_hooks`** (row 8): demand the same no-failure summary for library drops as user drops; unblocks proof that cleanup cannot introduce hidden failure.
7. **`$no_assumed_finite_inputs`** (row 11): require `$no_inf` callers and external values to prove finiteness on entry, as `$no_nan` does for NaN; unblocks a complete finite-float contract.
8. **`$verify_certified_protocols`** (row 14): require a model-checking certificate for `serve` and `pipeline` before trusting their waits; unblocks a checked protocol premise under `$no_deadlocks`.

Two additional decisions are needed for the stated goal: whether `$bulletproof` should reject whole external paths (currently a documented warning), and whether it should prohibit `$audited_wait`/the parallel-range cap or provide a stronger proof mechanism. The scheduler and external-peer premises of `$no_deadlocks` cannot be discharged by a source metatag alone; the guarantee must state that boundary.

## Documentation changes and gates

- `docs/design/user_managed_storage.md`: corrected stale “lifecycle implementation pending” status; the nominal hook protocol exists in `compiler/ownership.jo`, while the user-managed allocation substrate is pending.
- `docs/design/contained_paths.md`: replaced obsolete pre-4aeca23b2 decision titles with the current ledger pointer. A script checked all `decisions.md` Markdown targets and heading anchors; no broken link was found.
- `docs/design/assumptions.md`: clarified that the strictest bundle is intended to cover all rows but is not yet fully enforceable.
- `docs/design/tensors.md` already says “Largely built” and names broadcasting; the example stale line in the brief is absent on this baseline. The sampled `Built`/`Not built` status lines in `safety_and_concurrency.md` fit the implementation inventory. The decided GPU rule's historical “nothing to build yet” line was left untouched as required.
- The ledger still repeats the full bulletproof principle under “Ledger” despite the owning `assumptions.md` rule. The links themselves resolve; shortening or relocating David's decided wording was outside this review.
- Focused new tests: **4 passed** (`python3 -m tools.core test -k test_assumption_optouts`). Quick suite: **371 golden cases passed; 618 pytest passed, 23 xfailed** (`python3 -m tools.core test --quick`). `git diff --check` passed.
