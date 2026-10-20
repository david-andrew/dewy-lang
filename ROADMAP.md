# Roadmap

The single work queue. Owned by the coordinator; agents propose changes in
their reports instead of editing it. [docs/GOALS.md](docs/GOALS.md) says what
Dewy must become; this file says what we do next. Git history is the record of
what landed. Keep this file short.

## North star

| Measure | Now (2026-10-20) | Goal |
|---|---|---|
| Acceptance ladder, design surface | 64/81 (tiers 1–2: 63/63; tier 3: 1/18), 13 held open on decisions | all milestones |
| Acceptance ladder, current dialect | 82/82 | stays green |
| Fresh compile, 22k-line synthetic Dewy (+37k library lines) | 1.27 G instructions | ~0.40 G (250k root lines/s) |
| Compiler self-build | 8.0 G instructions | seconds-scale edit loop |
| Game-tick kernel vs C -O2 | ~2× instructions | ~1× |
| Quick / full suite | 38 s / 6.6 min (load average 14–24; remeasure when quiet) | ≤30 s / ≤5 min |

Ladder milestones (1–30) and their programs are in `tests/ladder/ladder.json`;
`python3 -m tools.core ladder` prints the scoreboard. Compile numbers come from
`python3 -m tools.core speed`; kernel numbers from `bench --instructions`.

## Now

- **Bigint `int` and exact decimals** (Astra): promotion on overflow and exact
  decimal literals; completes milestone 27's arithmetic base.
- **Refinement slice 1** (Astra): scalar facts and symbolic `$assert`. The
  design is in ~/dev/tmp/coord/refinement-design.md, in 6 slices.
- **Front page** (Opus): restore the previous design, with verified examples.

## Next

- Tier-3 implementation (designed, no decisions needed):
  - refinement slices 2–6: canonical refinements, lengths and fields,
    joins/loops, checked proofs, diagnostics;
  - effect rows, 6 slices (~/dev/tmp/coord/effects-design.md). Slice 1 shares
    places with refinement slice 1;
  - ownership: lifecycle hooks and drop, `$lend` checking, arenas, 6 slices
    (~/dev/tmp/coord/ownership-design.md);
  - builtin `rational`;
  - `$test`/`$expect`, and scoring test results in the ladder (program 89);
  - `sort(key=…)`.
- Compile throughput, toward ~0.40 G. Budget in
  ~/dev/tmp/coord/throughput-budget.md. Open projects, roughly in order:
  - finish direct compact-AST construction (statements, declarations, special
    forms) and delete the projection path;
  - finalize checked-function results once, with shared proof summaries;
  - shared optimizer facts;
  - cheaper register-allocation intervals and encoding;
  - better code generation for the compiler itself (aggregate SRA into
    helpers, condition forwarding, fewer spills).
- Runtime gaps:
  - float compare/negate selection;
  - outer-target SIMD (particles);
  - stack closure environments with devirtualization (the callback kernel
    spends 35% in allocation and free).
- Self-hosting pilot: translate `compiler/zip.jo` to Dewy. This needs
  `$target`, a pointer/host ABI subset and byte views. Hold the full port
  (5–10 engineer-weeks) until the zip pilot works without private syntax and a
  lexer/IR kernel matches Jo in results and speed. Bootstrap afterwards:
  C → stage0 → frozen Jo compiler → Dewy compiler.
- Small items:
  - the remaining Jo-shaped hints in diagnostics;
  - partial application for overloaded/generic functions;
  - delete `restart/sloppy-frontend` and its publish-policy entry once the
    bigint task lands.

## Decided (David)

- `int`: arbitrary precision with word storage where proven, by the fastest
  route (checked int64 → bigint promotion → range analysis). `intN`/`uintN`
  wrap.
- Decimal literals are exact unless annotated (e.g. `float64`).
- Zero-argument calls may omit or include the parentheses.
- Function handles follow the design: a bare name calls; `@fn` is the handle.
- From GOALS: ordinary code keeps runtime checks; static rejection of unproven
  facts is a strict-lane property.
- Versions: the language stays 0.0.0; the extension gets patch bumps only, at
  most one release a day.

## Open questions for David (batched, not blocking)

1. The strict-lane opt-in surface: one profile directive, or effect rows plus a
   module default? Are panic and detach named separately?
2. Scope of `$prototype`.
3. Readonly/lifetime-bearing payload places beyond `$lend`.
4. Allocation capabilities and allocation-failure policy.
5. Explicit `move` syntax.
6. Structured concurrency: the partition/task surface, `Send`/`Sync`
   spelling, atomics/memory orders, cancellation and locks.
7. Multidimensional arrays: tensor syntax and broadcasting rules.
8. IEEE float policy.
9. Units: display (`as km`), affine units (Celsius point vs delta), calendar
   durations.
10. Invariant authority beyond scalar refinements.
11. Finite-resource and denial-of-service guarantees.
12. The portable sockets/FFI boundary.
13. Lifecycle hooks: must `$__copy__`/`$__move__` preserve the abstract value?
    Can a move hook fail?
14. Errors that reach `main`.
15. Provisional file helpers: `copy_file`, `rename_file`, `make_dirs`,
    `walk_dir`, `glob`, `file_size`, `file_time`, `chmod`, `env`. Keep, rename
    or drop?

Each tier-3 program's ladder note says which question holds it open.

## Tried and rejected (don't retry without a materially new idea)

- Pooled/inline syntax children; reusable register scratch workspace.
- Zero-cost cold-call register weighting: kernels regressed 38%.
- An entry guard before the prologue.
- Block-local liveness rescue and short register caches: recovered 4–8% of
  spills.
- Word-at-a-time name hash; paired SSE string equality.
- Broad release inlining-cost adjustment.
- Compact IR encoding: −0.3%.
- Selective default passes: −10% compile, but kernels regressed 16–92%.
- Fork-based parallel lowering: 0.88–1.00× latency. Lowering is only about 13%
  of a default build.
