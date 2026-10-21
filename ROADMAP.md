# Roadmap

The single work queue. Owned by the coordinator; agents propose changes in
their reports instead of editing it. [docs/GOALS.md](docs/GOALS.md) says what
Dewy must become; this file says what we do next. Git history is the record of
what landed. Keep this file short.

## North star

| Measure | Now (2026-10-20) | Goal |
|---|---|---|
| Acceptance ladder, design surface | 82/82 (tiers 1–2: 63/63; tier 3: 19/19), 12 held open on decisions | all milestones |
| Acceptance ladder, current dialect | 82/82 | stays green |
| Fresh compile, 22k-line synthetic, wall clock, 4 workers (i7-6700) | 175 ms | ≤88 ms (250k lines/s) |
| Same, single-thread instructions (guardrail) | 1.19 G (was 1.36 G on 10-20) | ~0.75 G; never regress |
| Hello-world compile | 31 ms (147 M, all library) | ≤10 ms |
| Compiler self-build | 9.35 G instructions (the compiler grew) | seconds-scale edit loop |
| Game-tick kernel vs C -O2 (time) | 1.6× default and release (default was 6.3× before small-leaf inlining) | ~1× both |
| Worst other kernels vs C (time, default) | params 1.75×, graph 1.7×, string_equal ~1.25×, recursive_tree 1.4× | ≤1.2× |
| Quick / full suite | 38 s / 6.6 min (load average 14–24; remeasure when quiet) | ≤30 s / ≤5 min |

Ladder milestones (1–30) and their programs are in `tests/ladder/ladder.json`;
`python3 -m tools.core ladder` prints the scoreboard. Compile numbers come from
`python3 -m tools.core speed`; kernel numbers from `bench --instructions`.

## Now

GPT quota is limited: at most one Astra stream, at medium effort; Sol for reviews
only.

- Astra: ownership slice 2 part 2 (resource containers, recursive/optional owners,
  field moves, closure copyability, generic hooks); part 1 (hooks, inheritance,
  inline aggregates, cleanup) landed.
- Opus: fused partition workers pilot (compile wall clock).

## Next

- Tier-3 implementation (designed, no decisions needed):
  - effect rows slices 3, 5–6 (1–2 and 4 landed; ~/dev/tmp/coord/effects-design.md);
  - ownership slices 4–6 (1, 2 in flight, 3 `$lend`): allocator runtime,
    escape promotion, integration
    (~/dev/tmp/coord/ownership-design.md);
- Compile throughput. Strategy: ~/dev/tmp/coord/throughput-strategy-2026-10-21.md.
  The root program is 86% of the work (46k instructions/line); library 13%;
  only optimize+x64 (36%) runs in parallel today. 0.40 G single-threaded is not
  credible, so the target is now wall clock with 4 workers. Projects, in order:
  1. fused partition workers: lower→optimize→x64 in the emission fork (51%
     parallel; modelled 120–136 ms);
  2. partitioned checking with long-lived workers (modelled 90–110 ms);
  3. a toolchain-baked library image (question 22);
  4. checker name lookup by id plus a fused zonk (≤6%).
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
- Recover the game-panel compile cost of mathematical `int` (+5.7%, accepted
  10-20); the frontend work recovered the synthetic panel's share.
- Small items:
  - `xs.swap` on refined arrays is rejected (goes through `data()`); indexed
    rewrite costs +62–93% on array_swap, so it needs a swap primitive;
  - maps fail their own index proofs under the strict policy;
  - diagnostics spell `Set<…>` instead of `set<…>`; a failed overload can
    blame an unrelated candidate (GpuBuffer, Set); `.length` on a user type
    without one says "use `.length`";
  - strict 67/70 need result-length facts for functions like `make(n)`
    (stop at `saved[0]`); likely needs design;
  - static calls through runtime `type<T>` values (needs type values);
  - effects slice 4 follow-ups: conditional capacity/uniqueness proofs,
    complete late-operation verification.

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
17. Can a function nested inside a method change the object's members?
    Today it can't, and that's a clear error.
19. Should `T?` fields default to `none` implicitly? Today they need an
    explicit `= none`, which the design implies.
20. Tests: each `$test` runs in its own process, so a panic marks only that
    test as aborted and the others still run. (The design says a failed
    `$runtime_assert` stops the file.) OK? `dewy-core test --json` fields are
    provisional.
21. Rounding ties: rational `.round()` rounds ties to even, while float
    `.round()` rounds half away from zero. Which rule should both use? Also
    `as rational`, and NaN → panic vs `| none`.
18. Printing details decided provisionally: minted values print with their
    type name (`Fault[code=7]`); ranges print as `[0..2]`/`[1,3..9]`; methods
    get unused warnings only on private types. OK?
16. Partial application of an overloaded function without a type annotation:
    the version leaving the fewest parameters open wins (implemented
    provisionally). OK?
22. A library image built and shipped with the toolchain (keyed by compiler and
    library hash, fresh fallback): hello 31 → ~5 ms, synthetic −3 to −13%. GOALS
    says a persistent cache is not how Dewy stays fast; is a shipped image OK?
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
- Readonly aggregate argument forwarding from loop snapshots: self-build −1.25%,
  no runtime change (under the 3% pilot bar).
- Local check-traversal fixes beyond the two landed: four pilots each under 1%.
- Direct null-trap lowering for managed/method params: 14.97 → 15.28 ms.
- Overload-dispatch plan cache: 80% repeat rate, but repeats cost only 2.79% of
  synthetic (33.9 M) before overhead.
- x64 live-interval stream: no duplicated walk inside x64; realistic saving 1.9%
  synthetic / 0.5% self-build. Word-at-a-time emission: ~1%.
- Triangular hash probing for graph: −0.3% instructions, default 7% slower.
  Graph is memory-bound (slot reads 43%, adjacency fetch/retain 24%); the next
  idea is contiguous adjacency storage/ownership.
- Fork-based parallel lowering: 0.88–1.00× latency. Lowering is only about 13%
  of a default build.
