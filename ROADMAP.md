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
| Fresh compile, 22k-line synthetic, wall clock, 4 workers (i7-6700) | 175 ms before fused workers; remeasure when quiet | ≤88 ms (250k lines/s) |
| Same, critical-path instructions at 4 workers (`speed --critical`, load-independent) | 0.60 G (0.90 G before fused workers; game 0.81 G, not partitioned) | ~0.35 G |
| Same, single-thread instructions (guardrail) | 1.16 G (was 1.36 G on 10-20) | ~0.75 G; never regress |
| Hello-world compile | 31 ms (147 M, all library) | ≤10 ms |
| Compiler self-build | 9.35 G instructions (the compiler grew) | seconds-scale edit loop |
| Game-tick kernel vs C -O2 (time) | 1.6× default and release (default was 6.3× before small-leaf inlining) | ~1× both |
| Worst other kernels vs C (time, default) | literal callbacks 4.6×, callbacks 2.3×, params 1.75×, graph 1.7×, recursive_tree 1.4× | ≤1.2× |
| Quick / full suite | ~17 s / ~4 min at load 5–8 (quick trimmed to smoke; case runner fixed) | ≤30 s / ≤5 min |

Ladder milestones (1–30) and their programs are in `tests/ladder/ladder.json`;
`python3 -m tools.core ladder` prints the scoreboard. Compile numbers come from
`python3 -m tools.core speed`; kernel numbers from `bench --instructions`.

## Now

GPT quota is limited: at most one Astra stream, at medium effort; Sol for reviews
only.

- Astra: paused (quota). The Sol parallel review found 2 diagnostic-order bugs,
  both fixed (9109989b), with guards extended.
- Opus: design coverage, round 2. The 10-21 audit: 613 features, 401 work, 47
  broken, 134 missing; round 1 fixed ~25.
- Held: fused partition workers (wt/fused); gates pass, the wall-clock gain
  needs a quiet machine to confirm.

## Next

- Tier-3 implementation (designed, no decisions needed):
  - effect rows slices 3, 5–6 (1–2 and 4 landed; slice 3's consolidation pilot
    regressed self-build +28%, so only its tests landed; ~/dev/tmp/coord/effects-design.md);
  - ownership slices 4–6 (1–3 landed): allocator runtime, escape promotion,
    integration; arena surface waits on question 4. Slice 2 leftovers, rejected
    conservatively for now: generic closure literals capturing owners, partial
    application of owners, escaping borrowed-owner closures, transfers through
    outer hooks or boxed fields
    (~/dev/tmp/coord/ownership-design.md);
- Compile throughput. Strategy: ~/dev/tmp/coord/throughput-strategy-2026-10-21.md.
  The root program is 86% of the work (46k instructions/line); library 13%;
  only optimize+x64 (36%) runs in parallel today. 0.40 G single-threaded is not
  credible, so the target is now wall clock with 4 workers. Projects, in order:
  1. fused partition workers landed (critical path −11% at 4 workers);
  2. partitioned checking: stages 1–2 landed (synthetic critical path
     0.77 → 0.64 G). Game eligibility was piloted and rejected (+0%): game has
     few roots, and workers discover new library instances. Next needs
     canonical reconciliation of function instances;
  3. a toolchain-baked library image (question 22);
  4. checker name lookup by id plus a fused zonk (≤6%);
  5. lazy function-body parsing landed (critical −5.1%).
  Rejected: worker instance reconciliation (game +0%, synthetic −0.03%, a
  2.2k-line program −24%, and dunes lost determinism on fallback). Game's
  serial cost looks library-bound: question 22, or parallel library checking.
- Runtime gaps:
  - float compare/negate selection;
  - outer-target SIMD (particles);
  - callbacks: stack environments plus bounded specialization landed;
    literal-lambda code is 4.6×/2.8× C (was 36×), callbacks 2.3×/1.7× (was 13.6×);
    traversal is now 57%; retry only with a materially new approach.
    Still the largest runtime gap.
- Self-hosting. The zip pilot works: `zip.dewy` matches Jo's archives byte for
  byte and its instruction counts (~/dev/tmp/coord/selfhost-readiness.md).
  `$target` landed, and the shipped compiler now runs `compiler/zip.dewy`; the C
  bootstrap builds its frozen `zip.jo` twin (`FROZEN_TWINS` in build.py). Next
  modules must be import-cycle leaves with interfaces spellable in both
  languages; a lexer module waits on question 24.
- Recover the game-panel compile cost of mathematical `int` (+5.7%, accepted
  10-20); the frontend work recovered the synthetic panel's share.
- Small items:
  - `xs.swap` on refined arrays is rejected (goes through `data()`); indexed
    rewrite costs +62–93% on array_swap, so it needs a swap primitive;
  - strict policy: map element access indexes `m.vals` with a library call's
    result, and proving it needs Map invariants (question 10) or a trusted
    library result rule. Combined loops (`x in xs and y in ys`) lack the
    `k < length` fact for non-constant lengths (our analysis gap);
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
23. From the dogfooding sweep (12 everyday programs, friction log in
    ~/dev/tmp/dogfood/friction.md):
    - decimal literals default to rational, so float code needs annotations
      everywhere: let later float writes settle a decimal-literal local's type,
      as later pushes settle an empty container's type?
    - `index_of` returns -1; return `int|none` like `find`?
    - infer the common parent for literals of sibling minted types?
    - `main` returning `int|error` (print the error, exit 1); see also 14;
    - `loop [k @v] in dict` to update values in place;
    - strings: `is_empty`, prefix/suffix removal, `chars()` as graphemes;
      `any`/`all` without a predicate; `count(value)`;
    - slicing past the end panics (Python clamps);
    - a documented stderr print (`eprintl`, or `print` with a target);
    - comparing a union with one of its members (`back =? n`): `false`, not an
      error?
    - landed as a natural extension, revert if unwanted: `sqrt` of a quantity
      halves even dimension powers (odd powers are an error).
    - undocumented Jo helpers reach Dewy (`enumerate`, `zip`, `lines`,
      `trim_start`): adopt or hide?
24. Self-hosting surface (zip needed none; a real compiler module needs these):
    OS selection (`$target` names only backends; Jo uses `TARGET=="windows"`),
    build-mode flags (BOOTSTRAP/DEBUG/WATCH), a pointer type spelling, an
    `extern`/C-binding form, tuple types, a byte-character literal. Also: the
    design splats `import p"x"` without `as`, but the compiler and tests treat
    it as a namespace import. Which is right?
25. Current behavior vs the archived reference (design coverage audit,
    ~/dev/tmp/coord/design-coverage-2026-10-21.md). Which wins?
    - `+` joins strings/arrays (the reference: never concatenates);
    - `let x:T` with no value reads as zero (the reference: must be initialized);
    - a bound `[1 2]` is `array<int>`, rejected where `array<int64>` is expected;
    - mutating a container inside its own loop;
    - an explicit `main()` call suppresses the automatic one;
    - `d.keys` returns an array, not a set;
    - unknown escapes like `\N` are errors;
    - user functions join prelude overloads rather than shadowing them;
    - `and=` on bools always evaluates its right side.
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
- Dictionary 8-byte slots: graph default 1.56× → 1.83× C (dependent key reads).
- Borrowed dictionary value fetches: graph 1.06×/1.03×.
- Single-probe `d[k] += 1` (hand-expanded upper bound): dict_words 1.2× on long
  runs; under the bar. Borrowed adjacency fetches are untested.
- Triangular hash probing for graph: −0.3% instructions, default 7% slower.
  Graph is memory-bound (slot reads 43%, adjacency fetch/retain 24%); the next
  idea is contiguous adjacency storage/ownership.
- Fork-based parallel lowering: 0.88–1.00× latency. Lowering is only about 13%
  of a default build.
