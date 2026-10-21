# Roadmap

The single work queue, owned by the coordinator. [docs/GOALS.md](docs/GOALS.md)
says what Dewy must become; this file says what we do next. Git history is the
record of what landed: no "landed" lines here. At most one ROADMAP-only commit a
day; keep it under 150 lines. Accepted designs live in [docs/design](docs/design/).

## North star

| Measure | Now (2026-10-21) | Goal |
|---|---|---|
| Acceptance ladder, design surface | 82/94 (12 wait on open questions) | 94/94, then tier 4 |
| Acceptance ladder, current dialect | all non-held programs pass; held ones run | stays green |
| Tier-4 flagship programs (1–5k lines each) | 5/7 written (game, KV store, crypto, notes service, Dewy frontend) | 7/7 |
| Programs passing under no-traps (`DEWY_INTERNAL_FACT_POLICY=require-static`) | 43/115 ladder+examples; cases unmeasured | all, then flip the default |
| Compile throughput, single thread, default build, per corpus (`speed --corpus`) | ~1.7k–3k est. lines/s (each program pays a ~0.16 G library floor) | 250k lines/s (200k minimum) |
| Critical-path instructions at 4 workers (secondary) | synthetic 0.60 G | no regression |
| Single-thread instructions, synthetic-22k (regression signal) | 1.17 G | ~0.09 G (250k lines/s) |
| Hello-world compile | 31 ms | ≤10 ms |
| Kernels vs C -O2 (time, default) | literal callbacks 4.6×, callbacks 2.3×, params 1.75×, graph 1.7×, game 1.6× | ≤1.2× |
| Quick / full suite | ~17 s / ~4 min | ≤30 s / ≤5 min |

Ladder: `python3 -m tools.core ladder` (`tests/ladder/ladder.json`). Compile:
`speed --corpus` and `speed` (single-thread instructions; the gate);
`--critical` is secondary. Wall clock only on a quiet pinned machine or a CI
runner, never on the shared box. Kernels: `bench`.

## Now

- Astra: concurrency stage 1, a work-stealing fork-join runtime and `parallel`.
- Opus: no-traps solver idioms; flagship gaps (COW cliff, record callees,
  optional literals); flagship gaps 2 (`no_effects`, copies, durable files).
- Opus: `$runtime_checks`, `$prototype`, `$no_hidden_costs`, boolean metatags.

## Next

1. **No traps by default** (Decided). Make the solver prove idioms (loop
   indices, guards, short-circuit `and`, `.length` checks); fix the corpus with
   real guards or `$runtime_checks`; then flip the default.
2. **Tier-4 flagships:** a kernel/RTOS program under `$no_hidden_costs`, and an
   ML training loop over tensors (question 7; device-agnostic).
3. **Concurrency** ([design](docs/design/safety_and_concurrency.md)), staged:
   fork-join runtime, then `Send`/`Sync` and parallel-loop obligations, then
   task groups once spellings are decided.
4. **Single-thread compile throughput:** re-plan around structural wins in the
   checker, lowering and the default optimizer's budget, measured on
   `speed --corpus`. Every program pays a ~0.16 G library floor; fresh compiles
   only (question 22 leans no).
5. **Self-hosting** ([readiness](docs/design/self_hosting.md)): after question 24,
   new leaf compiler modules start in Dewy.
6. **Runtime gaps** (upper bound first): callback traversal, graph layout, float
   compare/negate, outer-target SIMD, destination passing, bounds-check upgrades.
7. **Small items:** swap primitive for refined arrays; strict Map invariants
   (question 10); result-length facts for `make(n)`; runtime `type<T>` statics;
   effects slice 4 follow-ups; the `@obj.method()` source-text heuristic.

## Decided (David)

- `int`: arbitrary precision with word storage where proven. `intN`/`uintN` wrap.
- Decimal literals are exact unless annotated (e.g. `float64`).
- Zero-argument calls may omit or include the parentheses.
- A bare function name calls; `@fn` is the handle.
- No traps by default (10-21; supersedes "ordinary code keeps runtime
  checks"): every partial operation is proven, handled as a value
  (`xs.get(i)` → `T | none`) or checked with `$runtime_assert`; unproven is a
  compile error with a fix-it. `$runtime_checks` (module/function/block) is the
  production opt-in: unproven obligations become reporting checks, listable via
  `check --obligations` and an LSP hint. `$prototype` keeps its archived
  semantics (runtime deferral with a `prototype:` warning per site).
- Boolean metatags accept `$tag`, `$tag=true`, `$tag=false`.
- Strict lane is `$no_hidden_costs`: a library-defined module bundle over
  function rows (`& no allocates`, …) plus `$explicit_copies` semantics; forbids
  hidden allocation, detach, implicit costly copies and `$runtime_checks`/
  `$prototype`; `$no_hidden_costs=false` opts a scope out. `$realtime` is
  reserved for a future stronger bundle (no blocks, bounded stack).
- Compile speed: 250k lines/s single-threaded in the default build (200k
  minimum), on representative code. Parallelism is a bonus.
- Concurrency direction (docs/design/safety_and_concurrency.md, "Adopted
  direction"): no coloured functions, groups-only spawn, level-triggered
  `Canceled`, first failure cancels siblings, two lanes, deterministic
  reductions, bounded channels, explicit atomic orders, no language actors.
  The parallel loop is the keyword `parallel` (`parallel i in [0..10) {…}`,
  `[parallel x in xs x*x]`).
- GPU: tensor and `parallel` designs stay device-agnostic; device is placement
  context, not a type change.
- Inference keeps the most precise type it knows; only an explicit wider
  annotation widens (literal unions; integers keep range facts).
- `end` and `new` are reserved: `end` is the last index inside an index; `new`
  inserts a singleton axis (NumPy `newaxis`): `xs[new ..]`, `xs[.. new]`.
- Versions: the language stays 0.0.0; the extension gets patch bumps only, at
  most one release a day.

## Open questions for David

New questions carry a recommended answer, what it unblocks and whether it's
reversible; reversible ones are implemented provisionally and flagged.

3. Readonly/lifetime-bearing payload places beyond `$lend`.
4. Allocation capabilities and allocation-failure policy. (76)
5. Explicit `move` syntax.
6. Concurrency spellings: the task-group form, `blocks`, `Canceled`, `Atomic`
   orders (direction decided). (81–83)
7. Multidimensional arrays: tensor syntax and broadcasting. (84)
8. IEEE float policy. (85)
9. Units: display (`as km`), affine units, calendar durations. (88)
10. Invariant authority beyond scalar refinements (strict Map invariants).
11. Finite-resource and denial-of-service guarantees.
12. Portable sockets/FFI boundary. (92)
13. Must lifecycle hooks preserve the abstract value? Can a move hook fail?
14. Errors that reach `main`.
15. Provisional file helpers (`copy_file`, `walk_dir`, `glob`, …): keep or rename?
16. Partial application of an overloaded function picks the fewest open
    parameters (provisional).
17. A function nested in a method can't change the object's members (today).
18. Printing details (minted type names, range forms, unused-method warnings).
19. Should `T?` fields default to `none` implicitly?
20. Per-process `$test` isolation; provisional `test --json` fields.
21. Rounding ties (rational to-even vs float half-away); `as rational`; NaN.
22. Ship a prebuilt library image with the toolchain? (David leaning no: fresh only.)
23. Dogfooding: decimal literals default to rational; `index_of` → `int|none`;
    sibling minted literals; `main` returning `int|error`; `loop [k @v] in d`;
    string helpers; slice clamping; a stderr print; union-member comparison;
    `sqrt` of quantities (landed provisionally); exposed Jo helpers.
24. Self-hosting surface: OS selection, build-mode flags, pointer types,
    `extern`/C bindings, tuples, byte-char literal, `import p"x"` splat vs
    namespace.
25. Behavior vs the archived reference: `+` concatenation; reading an
    uninitialized `let x:T`; bound `[1 2]` as `array<int>`; mutating a container
    in its own loop; explicit `main()`; `d.keys` array vs set; unknown escapes;
    user functions vs prelude overloads; `and=` evaluation; unproven narrowing
    (runtime vs compile error); `uint64(x)` bit casts; top-level `count = 3`;
    declared vs inferred effect rows for callers.
26. Index-typed refinements ("below `a.length`"); Euclidean `%` (recommended:
    keep floored).

Each held ladder program's note names the question that holds it.

## Tried and rejected (an idea family ends after one failed pilot)

- Compile: pooled syntax children; scratch reuse; cold-call register weighting;
  entry guards; liveness rescue; word-at-a-time hashing, SSE equality and
  emission; broad inlining-cost changes; selective default passes; compact IR;
  aggregate forwarding; local check-traversal fixes; overload-plan caching
  (2.79% ceiling); x64 interval stream (1.9%); fork-based lowering alone;
  worker instance reconciliation as piloted; effects slice 3 consolidation
  (+28% self-build).
- Runtime: null-trap param lowering; dictionary micro-pilots (graph is
  memory-bound; only contiguous adjacency is left); inferred scope regions
  (1.18× upper bound); lambda-lifting (environments already on the stack).
