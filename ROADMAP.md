# Roadmap

The single work queue. Owned by the coordinator; agents propose changes in
their reports instead of editing it. [docs/GOALS.md](docs/GOALS.md) says what
Dewy must become; this file says what we do next and how we know we are closer.

## North star

| Measure | Now (2026-10-19) | Goal |
|---|---|---|
| Acceptance ladder, design surface | 19/31 programs (was 0/31 on 10-19) | all milestones |
| Acceptance ladder, current dialect | 31/31 | stays green |
| Fresh compile, 22k-line synthetic Dewy (+37k library lines) | 1.35 G instructions, ~330 ms | 250k root lines/s (~88 ms) |
| Compiler self-build | 7.5 G instructions, ~1.6 s | seconds-scale edit loop |
| Game-tick kernel vs C -O2 | 8.85× | ~1× |
| Managed helper calls / generic closures vs C | 1.65× / 2.5× | ~1× |
| Quick suite / full suite | 25 s / 3 min | stay under 30 s / 5 min |

Measured on the i7-6700 desktop (shared, so expect noise). Compile numbers are
fresh builds, one emitter. Update this table at checkpoints, not per commit.

## Capability ladder

Each milestone is a set of acceptance programs, written in the design's
surface (one language, no dialect forks), that must all pass:

1. Text tools and source parsing: CLI input, Unicode, empty input.
2. One coherent surface: design files parse through verification
   (`$assert`, `$runtime_assert`, metatags with explicit "not yet" errors), and
   method/function spellings are canonical.
3. Trustworthy arithmetic: exact default integers and decimals, correct
   width-boundary semantics (wide shifts), hashes and binary formats.
4. Errors as values: nominal error types, `or_throw`, member forwarding.
5. Science and small ML: matrices, ODEs, statistics, units of measure,
   classifiers.
6. Reusable libraries: generic containers, callbacks, iterators, snapshots.
7. Storage: append-only logs, page indexes, crash-tail recovery.
8. Services and parallelism: TCP/HTTP, deterministic data-parallel work,
   rejected races.
9. Strict lane: no hidden allocation, copy, detach or panic in opted-in
   modules; lifecycle cleanup on early exits; scoped views.
10. Games and large applications at C-class speed with a fresh-build edit loop.

## Now (at most three active streams)

- **Process foundation**:
  - golden-file tests, one case per file, replacing growth of the giant pytest
    module;
  - an instruction-count speed gate (≤1% vs the previous compiler, plus a
    fixed checkpoint) in CI;
  - the acceptance ladder runner and scoreboard.
- **Soundness pilot**:
  - remove the `/lib/core/` pathname trust in `lower.jo`; it causes a
    reproduced miscompile;
  - replace it with checked per-instance isolation summaries.
  This is slice 1 of the semantic-boundary design; later slices are pulled in
  only when a capability needs them.
- **Surface convergence (milestone 2)**: directives, zero-argument members and
  Dewy-native diagnostics landed (0→19/31). Next: the function-handle migration,
  then `pop(index)`/`insert` order/`starts_with` spellings, function-type
  expressions, and `.copy`.

## Next

- Error family + `or_throw` (milestone 4). Existing unions and return cleanup
  are the seam.
- Erased physical units (milestone 5) via dimension-qualified canonical types.
- Mathematical `int` and exact decimals (milestone 3), staged as decided below.
- Game-tick gap (8.85×), diagnosed 2026-10-19. Five 24-byte record copies per
  tick survive inlining, because `opt.jo:o_sra` only promotes slots of 16 bytes
  or less; the scalar-local control is 4.6× fewer cycles. Fix:
  - extend SRA to three 8-byte lanes, guarding the lane count;
  - coalesce dead ownership/return copy temporaries after inlining.
  Then:
  - float compare/negate selection;
  - outer-target SIMD for particles;
  - escape-proven stack closure environments with devirtualization (the
    callback kernel spends 35% in allocation and free).
- Wide-shift semantics bug; Jo text in diagnostics.
- Dewy-grammar differential fuzzer with independent oracles (nightly). The
  current fuzzer only generates Jo.
- Publication migration:
  - point the site and installer at the new compiler;
  - merge this branch into master;
  - prune the old `native-*`/`udewy-*` release tags.

## Later (pull in when a capability needs it)

- Semantic-boundary slices 2–9: places and effects, lowering storage split,
  inference cells, layouts, checked instances, strict-lane facts, parallel
  lowering, parallel checking. Each needs a named consumer before it starts.
- Strict lane: start with a closed scalar/fixed-storage subset.
- Ownership: same-block moves and non-escaping views first; general loans
  later.
- Compile-time execution: extend `ceval` to checked calls, locals and control
  flow.
- Compile speed: selective default passes (≤15–19% ceiling), better generated
  compiler code, parallel lower/optimize/emit. No single lever reaches 250k;
  the plan is a combination.
- Self-hosting: once the surface can express the compiler, a parser-driven
  Jo→Dewy translation (handle capture and integer-division semantics
  deliberately), then a fixed point in Dewy.

## Decisions

Resolved 2026-10-19 (David):

- **`int`** reaches the design, arbitrary precision with word storage where
  proven, in the fastest route. Interim: overflow-checked int64 (never silently
  wrong), then bigint promotion on overflow, then range analysis to remove
  checks. Explicit `intN`/`uintN` wrap.
- **Decimal literals** denote their exact value unless an annotation says
  otherwise (e.g. `float64`). Representation strategy is ours.
- **Zero-argument calls** may omit or include the parentheses: `xs.pop` and
  `xs.pop()` are both accepted.
- **Function handles** (2026-10-20) follow the design: a bare function name
  calls; `@fn` is the handle (`xs.map(@double)`). Migrate in stages: warn on
  bare function values, then switch, updating lib/ and examples.

Open:

- Small library spellings (`starts_with` vs `startswith`, `insert` argument
  order, `pop(key)` vs `remove(key)`): check the design docs. Where they're
  silent, the coordinator batches a proposal to David.

## Tried and rejected (don't retry without a materially new idea)

- Pooled/inline syntax children; reusable register scratch workspace.
- Direct arithmetic projection: saved about 0.1%.
- A full direct-AST frontend rewrite. The parse-side difference vs Jo is only
  11% of a Dewy build.
- Zero-cost cold-call register weighting: kernels regressed 38%.
- Entry guard before the prologue.
- Block-local liveness rescue and short register caches: recovered only 4–8%
  of spills.
- Word-at-a-time name hash; paired SSE string equality; transitive
  effect-summary reuse.
- Broad release inlining-cost adjustment.
- Medium-record scalar replacement was rejected on whole-compiler instruction
  counts (+1.3–4.5%) alone. **Reopened:** a game kernel stands to gain roughly
  4×; judge it on application workloads plus the speed gate's explicit-accept
  path.
