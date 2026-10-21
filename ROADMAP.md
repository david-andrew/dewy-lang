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
| Fresh compile, 22k-line synthetic Dewy (+37k library lines) | 1.24 G instructions (was 1.36 G on 10-20 morning) | ~0.40 G (250k root lines/s) |
| Compiler self-build | 8.0 G instructions | seconds-scale edit loop |
| Game-tick kernel vs C -O2 (time) | 1.6× default and release (default was 6.3× before small-leaf inlining) | ~1× both |
| Worst other kernels vs C (time, default) | params 1.75×, graph 1.7×, string_equal ~1.25×, recursive_tree 1.4× | ≤1.2× |
| Quick / full suite | 38 s / 6.6 min (load average 14–24; remeasure when quiet) | ≤30 s / ≤5 min |

Ladder milestones (1–30) and their programs are in `tests/ladder/ladder.json`;
`python3 -m tools.core ladder` prints the scoreboard. Compile numbers come from
`python3 -m tools.core speed`; kernel numbers from `bench --instructions`.

## Now

GPT quota is limited: at most one Astra stream, at medium effort; Sol for reviews
only.

- Astra: overload-dispatch plans pilot (compile throughput).
- Opus: refinement and container follow-ups (small items).

## Next

- Tier-3 implementation (designed, no decisions needed):
  - effect rows slices 3, 5–6 (1–2 and 4 landed; ~/dev/tmp/coord/effects-design.md);
  - ownership slices 2, 4–6 (1, drop hooks and moves, and 3, `$lend`, landed):
    custom copy/move hooks, resource containers, arenas
    (~/dev/tmp/coord/ownership-design.md);
- Compile throughput, toward ~0.40 G. Profile (10-21, 1.217 G): checking 371 M,
  optimization 248 M, x64 211 M, lowering 185 M, parse 85 M, lexer 49 M, prelude
  38 M (~/dev/tmp/coord/throughput-profile-2026-10-21.md). Structural projects,
  each estimated (not measured):
  - reusable typed overload-dispatch plans (`resolve_fn_call` is 109 M): 35–55 M;
  - shared optimizer operand/control/use facts: 40–60 M;
  - a finalized live-interval stream fed into x64 allocation: 35–50 M;
  - the lexer: 49 M against a 20 M target.
  These reach ~1.05 G; 0.40 G needs a bigger idea (per-line checking cost is
  ~17k instructions).
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
  - removing from a map/set whose refined element rejects zero (`Pos`) fails:
    the library zeroes the freed slot (`lib/core/map.jo:309`); needs a
    library-only dead-slot primitive;
  - diagnostics spell `Set<…>` instead of `set<…>`; a failed overload can
    blame an unrelated candidate (GpuBuffer, Set); `.length` on a user type
    without one says "use `.length`";
  - refinement follow-ups: a call argument (`printl(take(z))`) drops facts, so
    a refuted contract only fails at run time; `.copy()` doesn't carry length
    facts (strict 67/70 stop there); witnesses for `and`/`or` conditions; the
    hint inside `$proof` suggests `$runtime_assert`;
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
- Triangular hash probing for graph: −0.3% instructions, default 7% slower.
  Graph is memory-bound (slot reads 43%, adjacency fetch/retain 24%); the next
  idea is contiguous adjacency storage/ownership.
- Fork-based parallel lowering: 0.88–1.00× latency. Lowering is only about 13%
  of a default build.
