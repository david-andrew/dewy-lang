# Safety metatag names — cold read, then score

## Phase 1 — names only

`?` = another reading fits.

- `$panic_on_unproven` — less safe; less proof; run panic. Unproven checks crash, not a compile error. `?` which obligations.
- `$no_nan_or_inf` — safer; more proof; ensure. Ban NaN and Inf. `?` proof or trap; inputs or results.
- `$no_deadlocks` — safer; more proof; ensure; compile. Reject unproven locks. `?` overclaims.
- `$no_hidden_costs` — ensure; compile. Ban hidden allocs and copies. Not a crash tag. `?` which costs.
- `$no_unconfined_paths` — safer; more proof; ensure. Paths stay under a root. `?` files or memory.
- `$no_assumed_waits` — safer; more proof; no assumption. Bound or handle every wait.
- `$prove_size_bounds` — safer; more proof; ensure; compile. Prove indexes and sizes. `?` which.
- `$prove_library_asserts` — safer; more proof; ensure. Callers discharge asserts. `?` or the library's own.
- `$prove_library_obligations` — safer; more proof; ensure. Prove declared library duties. `?` which.
- `$prove_library_arena_safety` — safer; more proof; ensure. No use after an arena reset.
- `$prove_library_cleanup` — safer; more proof; ensure. Release every library resource.
- `$prove_finite_float_args` — safer; more proof; ensure. Prove float args finite.
- `$explicit_copies` — more writing; compile. Implicit copy is an error. `?` all or only large.
- `$explicit_allocation_failure` — safer; more handling. Alloc is a value, not an abort.
- `$explicit_graphics_failure` — safer; more handling. Graphics failure is a value.
- `$explicit_local_panics` — unsure. Written panics stay local. `?` contained, or not inserted.
- `$assume_external_wait` — less safe; less proof; assume. A foreign wait returns.
- `$prototype` — less safe; less proof; assume. A sketch drops checks. `?` which.
- `$bulletproof` — safer; more proof; ensure. Strictest bundle, no panics. `?` marketing.
- `$unsafe` — less safe; assume. Waive proofs in a region. `?` which proofs.
- `$time.explicit_clock_accuracy` — ensure; compile. Declare clock accuracy. `?` or only report a bound.

## Phase 2 — scored

Matched: `$panic_on_unproven` (also allows panicking callees), `$explicit_copies` (costly only), `$explicit_allocation_failure`, `$prove_finite_float_args` (body may rely on it).

- `$no_nan_or_inf` — proof, not a trap, values in included. Name is fine.
- `$no_deadlocks` — tasks, not locks; assumed waits still pass. Better: `$no_task_deadlock`.
- `$no_hidden_costs` — also bans detaches and panics. A panic is not a cost.
- `$no_unconfined_paths` — any non-`SafePath`, even `args[0]`. Better: `$prove_confined_paths`.
- `$no_assumed_waits` — rejects that tag and `& no_effects`; does not bound waits. Better: `$no_assumed_externs`.
- `$prove_size_bounds` — not indexes. Trusted counters and ranges. Better: `$prove_counter_overflow`.
- `$prove_library_asserts` — internals; the caller cannot discharge them.
- `$prove_library_obligations` — hidden index, division, narrowing, refinement. Better: `$prove_library_runtime_checks`.
- `$prove_library_arena_safety` — library must not keep storage. Better: `$prove_library_drops_arena`.
- `$prove_library_cleanup` — drop cannot fail, not "cleanup happens." Better: `$prove_library_drop_cannot_fail`.
- `$explicit_graphics_failure` — unions `texture`; draws still abort. Better: `$explicit_graphics_creation_failure`.
- `$explicit_local_panics` — same-module callers opt in. Better: `$explicit_module_panic_calls`.
- `$assume_external_wait` — "outside world only," not "it returns." Better: `$assume_waits_outside`.
- `$prototype` — `$panic_on_unproven` plus warnings. Drop it.
- `$bulletproof` — `$unsafe` stays; `printl(1)` fails. Alias of a written block only.
- `$unsafe` — next expression, not a region. Waiver unstated.
- `$time.explicit_clock_accuracy` — sample is `today.year` → `AmbiguousToday`. Sixteen siblings undefined.

## Problems

Opt-in unsafety, a strong reason to reverse it, an easy 80% path, a one-step fix.

- **Draws abort, and the tag misses them.** `circle` on driver failure is fatal (B3); the tag only unions `texture`. Mid-frame limits justify `void`, not exit 1. `window(...) or_throw; loop { circle(...) }` dies uncaught, and `texture` aborts off-frame. Change: sticky error on the window, reported at frame end, no tag; `texture` like `load_wav`.
- **The OOM opt-in does not hold.** A union on every `push` fails the 80% test, so the crash is fair. Ran: `let r = grow(3); printl(r.length)` under the tag in `():>void` still compiles. Change: `T | OutOfMemory` used as `T` is an error.
- **`$no_deadlocks` is not the "Yes" in section 5.** It accepts unchecked `$assume_external_wait`. A literal cycle is an error; a runtime capacity only warns (B6). `channel<int>(input_int("cap? ") or_throw)` with `send` opposite `receive` hangs at 0. Change: an unproven wait errors unless that call opts in; this tag rejects the assume. Withdraw `serve` / `pipeline` certificates until the gate exists.
- **`$bulletproof` is the theatre C6 forbids.** `printl(1)` fails it, and `graphemes("hi")` has no caller-side fix. `$time.strict` is 17 undefined renames. Change: drop `$prove_library` and `$time.strict` until hello-world compiles and each time tag has one line.
- **Section 1 is not section 2.** A crash supposedly takes a written word, and nothing you can meet may lie. `printl(1.0 / 0.0)` is `inf`, exit 0. Change: keep IEEE; `$no_nan_or_inf` and an `is_finite` guard are the step. Name IEEE, OOM, and stack as exceptions, and do not excuse graphics that way.
