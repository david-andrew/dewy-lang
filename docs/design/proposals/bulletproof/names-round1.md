# Safety and parallel tag names: cold-read test, round 1

**Method.** Each candidate name went, alone, to three readers with no context. Each reader guessed what the name does, whether it makes a program safer or less safe, and how confident it was (1–5). Names were shuffled, and alternatives for one meaning sat in the same list. Misread groups were retested in round 2 with new candidates and fresh readers. Raw guesses are kept outside the repo; this is the scored result.

| Meaning | Picked | Readers got it | Rejected, and how it was misread |
|---|---|---|---|
| Unproven index/division/narrowing compiles and ends the program if it fails | `$allow_unproven` (and `$allow_unproven_indexing`, `$allow_unproven_division`) | 3/3, less safe | `$runtime_checks`: 2/3 read it as *safer*. `$crash_if_unproven` named the mechanism better but has no `allow`. `$allow_crash_if_unproven_fails`: confusing |
| Implicit costly copy is an error | `$no_hidden_copies` | 3/3 | `$explicit_copies`: tied; picked to match `$no_hidden_costs` |
| Allocation returns `T \| OutOfMemory` | `$explicit_allocation_failure` | 3/3 | `$allocation_can_fail`: 1/3 read it as less safe |
| Same-module calls to a function with a run-time assert count as "may panic" | `$count_local_asserts_as_panics` | 2/3, roughly | `$explicit_local_panics`, `$track_local_panics`, `$no_hidden_local_panics`, `$local_panics_propagate`, `$panics_spread_within_module`: all read as something else |
| 64-bit counters need a real overflow proof | `$prove_no_counter_overflow` | 3/3 | `$no_assumed_bounds`: read as index bounds |
| Prove the library's internal asserts | `$prove_library_asserts` | 3/3 | `$library_asserts_may_panic`: read as less safe |
| Prove the library's hidden run-time checks | `$prove_library_runtime_checks` | 3/3, low confidence | `$no_library_runtime_checks`: read as "turn the checks off" |
| Prove the library doesn't keep arena memory | `$prove_library_arena_safety` | 3/3, vague | `$no_trusted_library_memory`: similar |
| Prove the library's cleanup can't fail | `$prove_library_drop_cannot_fail` | 3/3 | `$no_trusted_library_cleanup`: weaker |
| All four library tags | `$no_trusted_library` | 3/3 | `$distrust_libraries`: one weak read |
| Every path proven inside a base folder | `$prove_confined_paths` | 2/3 (one read pointers) | `$confine_paths`, `$no_unchecked_paths`: vaguer |
| Opt out of path confinement | `$allow_unconfined_paths` | 3/3 | |
| A person's claim that a C call never waits on the program's own tasks | `$assume_extern_never_waits_on_tasks` | 3/3 | `$assume_waits_outside`, `$foreign_wait_is_external`, `$trust_extern_wait`: vague |
| Reject such claims | `$no_unverified_extern_waits` | 3/3 | `$no_assumed_externs`, `$reject_wait_claims`: vague |
| Callers must prove float arguments finite | `$args.prove_finite_floats` | 3/3 in round 2 | One round-1 reader took `$args.` as command-line arguments; `$params.` read the same |
| `today` must handle an unsure clock | `$time.handle_uncertain_today` | 3/3, low confidence | `$time.explicit_clock_accuracy`: read as "state the accuracy" |
| Most items in flight at once | `$parallel.max_concurrent` | 3/3 | `$parallel.window`: unsure |
| Items per chunk | `$parallel.chunk_size` | 3/3 | `$parallel.grain`: read as minimum work |
| Threads for parallel work here | `$parallel.threads` | 3/3 | `$parallel.cores`: "sets or reads" |
| Program-wide thread limit | `$program.max_threads` | 3/3 | `$resources.cores`: vague |
| Run parallel code sequentially | `$parallel.off` | 3/3 | `$sequential`: also fine |
| CPU or GPU | `$parallel.device` | 3/3 | |
| Struct-of-arrays layout | `$memory.layout` | 3/3 | `$layout`: vaguer |
| Most negative finite float | `float64.most_negative` | 3/3 | `float64.min`: ambiguous, as in C |
| Smallest normal float | `float64.smallest_normal` | 3/3 | `float64.min_positive`: read as the subnormal |
| Smallest float above zero | `float64.smallest_above_zero` | 3/3 | `float64.min_subnormal`: right but jargon; `float64.tiniest`: vague |
| Gap after 1.0 | `float64.epsilon` | 3/3 | |
| Largest integer with all below it exact | `float64.max_exact_int` | 3/3 | `max_safe_int`: read as 2^53−1 |
| Next float above x; gap above x | `x.next_up`, `x.spacing` | 3/3 | `ulp(x)`: right but jargon |
| Random bytes, never fails, not for secrets | `random_bytes` | neutral; no reader would use it for a token | `fast_random_bytes`: also clear |
| Random bytes for secrets, can fail | `secure_random_bytes` | 3/3; all chose it for a password-reset token | `crypto.random_bytes`: second choice |

Kept by David without testing: `$finite_floats`, `$prototype`, `$unsafe`, `$bulletproof`, `$no_deadlocks`, `$no_hidden_costs`.
