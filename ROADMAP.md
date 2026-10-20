# Roadmap

The single work queue. Owned by the coordinator; agents propose changes in
their reports instead of editing it. [docs/GOALS.md](docs/GOALS.md) says what
Dewy must become; this file says what we do next and how we know we are closer.

## North star

| Measure | Now (2026-10-19) | Goal |
|---|---|---|
| Acceptance ladder, design surface | 62/63 programs (0/31 on 10-19) | all milestones |
| Acceptance ladder, current dialect | 63/63 | stays green |
| Fresh compile, 22k-line synthetic Dewy (+37k library lines) | 1.36 G instructions (10-20; was 1.30 G at the 10-19 checkpoint) | 250k root lines/s (~88 ms) |
| Compiler self-build | 7.5 G instructions, ~1.6 s | seconds-scale edit loop |
| Game-tick kernel vs C -O2 | ~2× instructions (was 3.6×; 8.85× wall) | ~1× |
| Managed helper calls / generic closures vs C | 1.65× / 2.5× | ~1× |
| Quick suite / full suite (+bootstrap) | ~30 s / ~2 min | stay under 30 s / 5 min |

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

Tier 2 (programs 32–63, added 10-20), harder programs:
11. Interpreter and checker kernels: bytecode VM, type checker, regex.
12. Robust text and records: query, base64, Markdown, quoted CSV, Unicode wrap.
13. Mutable indexed data structures: B-tree with deletes, O(1) LRU.
14. Durable data and module failures: WAL crash recovery (needs `Path`),
    errors across modules.
15. Scientific and ML kernels: broadcasting, dual-number autodiff, k-means,
    backprop, FFT, units.
16. Bounded systems kernels: slab allocator, ring, binary protocol, CRC32,
    SHA-256.
17. Generic callback libraries: deque, combinators (`<(args):>R>` contracts).
18. Deterministic owned parallelism: reduce, pipeline.
19. Large game state: ECS with 4k entities, A*, rollback.
20. Compile-time library generation: `fields`/`$field` reflection, compile-time
    tables.

## Now

- **Surface convergence, round 2:**
  - function handles (`@fn`, bare names call);
  - `pop(index)`, dictionary `pop(key)`, `insert` order, `starts_with`;
  - function type expressions.
- **Dewy-program differential tester:** a generator plus an independent Python
  interpreter oracle, metamorphic variants, shrinking, and nightly CI.
- **Compile throughput, budgeted** (10-20). The target is about 400 M instructions
  for the 22k-line synthetic program, from 1,322 M today: roughly 18k instructions
  per root line, with library work included.

  | Phase | Now (M) | Target (M) | Kind of work |
  |---|---:|---:|---|
  | Lex | 60 | 20 | Tune: scalar scanner, ASCII fast paths |
  | Parse | 197 | 40 | Redesign: build the compact AST directly, no projection |
  | Check and lowering | 567 | 135 | Redesign: checked-function results finalized once, shared proof summaries |
  | Default optimization | 244 | 100 | Redesign: shared operand/control facts, region updates |
  | Register allocation and emission | 211 | 80 | Redesign: shared interval facts, batched encoding |
  | Image writing | 21 | 5 | Tune |
  | Prelude | 68 | 20 | Demand loading (landed) |

  - Plus the compiler's own code quality: SRA of aggregates passed to helpers,
    condition forwarding, fewer spills. That helps compile speed and runtime
    alike.
  - Every slice must keep bench kernels within +3% instructions.
- **`$explicit_copies`:** the strict-lane first slice; ladder programs 17 and 18.

Landed 10-19 and 10-20:
- golden tests, ladder and speed gate;
- isolation summaries (the pathname miscompile fixed);
- record SRA and copy forwarding (game −44% instructions);
- directives, zero-argument members, Dewy diagnostics;
- the error family with `or_throw`;
- checked mathematical `int`;
- erased physical units.

## Next

- `int` step 2: bigint promotion. The plan: semantic TypeId vs RepId, and a
  two-word tag/payload boundary ABI. Then exact decimal literals.
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
- The rest of the Jo-shaped hint catalog in diagnostics.
- Dewy-grammar differential fuzzer with independent oracles (nightly). The
  current fuzzer only generates Jo.
- Publication migration:
  - point the site and installer at the new compiler;
  - merge this branch into master;
  - prune the old `native-*`/`udewy-*` release tags.

- **Next capability gaps from tier 2:**
  - the `Path` filesystem API with error-valued I/O (36);
  - reflection, `fields(T)`/`$field` (62);
  - compile-time evaluation for `$assert` and tables (63);
  - the B-tree type mismatch (35), probably the collection API.

- **VS Code extension as a first-class product.** The goal is everything users
  expect, backed by the compiler's LSP:
  - diagnostics, completion, hover, go-to-definition/references, rename;
  - signature help, semantic tokens, inlay hints, formatting;
  - test explorer, run/debug;
  - an easy way to get the compiler (bundled or downloaded) without a checkout.

  Publishing is automated (`.github/workflows/extension.yml`). Patch bumps only,
  at most one release a day; see docs/DEVELOPMENT.md.

- Small surface follow-ups:
  - drop `((x):>y)` type grouping, since the design's `<...>` works (one
    spelling);
  - drop set `add` (`push` only);
  - `f(@a @a)` overlap must be rejected (it compiles);
  - `let g = @sum` collides with the prelude `sum`;
  - partial application for overloaded/generic functions;
  - cyclic imports, which the design rejects and the core accepts;
  - `$target` (bench harness, self-hosting).

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
- **Self-hosting** (audit 10-20). Start module-level dogfooding now; hold the
  full port.
  - Pilot: translate `compiler/zip.jo` to Dewy. Its CRC kernel already matches.
  - Prerequisites:
    - a resolved-type translator emitting explicit `int64`/`uint64`, `//`
      semantics fixed for truncation, and byte views (not graphemes) for
      scanners;
    - `$target`;
    - a pointer/host ABI subset;
    - import aggregation, flattened or with a cycle policy.
  - Triggers for the full port: the zip pilot works without private syntax;
    host/callable subset stable; a lexer and IR kernel match Jo in results
    and speed.
  - Bootstrap after the port: C → stage0 → frozen Jo compiler → Dewy compiler.
  - Estimate: 5–10 engineer-weeks.

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

Open (batched for David, not blocking):

- Units: display-unit selection, Celsius point/delta semantics, calendar
  durations.
- Errors: what happens when an exception reaches `main` (today `main` keeps its
  void/int contract and must handle errors explicitly).

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
- Fork-based parallel lowering (10-20). Deterministic, byte-identical across
  1/2/4 workers, but 0.88–1.00× latency, +1–2% instructions, up to 2.8× RSS.
  Lowering plus initial optimization is only about 13% of a default synthetic
  build and 31% of a self-build, so there is too little to parallelize.
- Selective default passes keyed on memory writes: −10% compile, but text
  kernels regressed 16% and shifted arrays 92%.
- Medium-record scalar replacement was rejected on whole-compiler instruction
  counts (+1.3–4.5%) alone. **Reopened:** a game kernel stands to gain roughly
  4×; judge it on application workloads plus the speed gate's explicit-accept
  path.
