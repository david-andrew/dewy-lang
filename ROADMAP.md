# Roadmap

The single work queue, owned by the coordinator. [docs/GOALS.md](docs/GOALS.md)
says what Dewy must become; this file says what we do next. Git history is the
record of what landed: no "landed" lines here. At most one ROADMAP-only commit a
day; keep it under 150 lines. Accepted designs live in [docs/design](docs/design/).

## North star

| Measure | Now (2026-10-21) | Goal |
|---|---|---|
| Acceptance ladder, design surface | 86/99 (13 held on open questions) | all |
| Acceptance ladder, current dialect | all non-held programs pass; held ones run | stays green |
| Tier-4 flagship programs (1–5k lines each) | 5/7 written (game, KV store, crypto, notes service, Dewy frontend) | 7/7 |
| Programs passing under no-traps (`DEWY_INTERNAL_FACT_POLICY=require-static`) | 43/115 ladder+examples; cases unmeasured | all, then flip the default |
| Compile throughput, single thread, default build, per corpus (`speed --corpus`) | ~1.7k–3k est. lines/s (each program pays a ~0.16 G library floor) | 250k lines/s (200k minimum) |
| Critical-path instructions at 4 workers (secondary) | synthetic 0.60 G | no regression |
| Single-thread instructions, synthetic-22k (regression signal) | 1.17 G | ~0.09 G (250k lines/s) |
| Hello-world compile (guardrail) | 31 ms | ~50 ms |
| Kernels vs C -O2 (time, default) | literal callbacks 4.6×, callbacks 2.3×, params 1.75×, graph 1.7×, game 1.6× | ≤1.2× |
| Quick / full suite | ~17 s / ~4 min | ≤30 s / ≤5 min |

Ladder: `python3 -m tools.core ladder` (`tests/ladder/ladder.json`). Compile:
`speed --corpus` and `speed` (single-thread instructions; the gate);
`--critical` is secondary. Wall clock only on a quiet pinned machine or a CI
runner, never on the shared box. Kernels: `bench`.

## Now

- Astra: codegen for `parallel` regions (fork costs about a call; then the
  work-stealing runtime).
- Opus: no-traps solver idioms; `$runtime_checks`/`$prototype`/`$no_hidden_costs`
  and boolean metatags; flagship gaps 2 (`no_effects`, copies, durable files).
- Opus: the reference-following changes (`+`, initialization, `d.keys`,
  conversions, declared rows) and context-adaptive decimal literals.
- Opus: `$shadowable const` (prelude included) and the loop value/place split.

## Next

1. **No traps by default:** prove idioms, fix the corpus (real guards or
   `$runtime_checks`), then flip the default.
2. **Concurrency** ([design](docs/design/safety_and_concurrency.md)): fork-join
   codegen and runtime; `Send`/`Sync` and parallel obligations; `concurrent`/
   `spawn` groups, `Canceled`, deadlines and `within`/`race` over a threads
   backend; `Atomic<T>` and the `blocks` effect; device-agnostic throughout.
3. **Tier-4 flagships:** a kernel/RTOS program under `$no_hidden_costs`; an ML
   training loop (question 7).
4. **Single-thread compile throughput** on `speed --corpus`: structural wins in
   the checker, lowering and the default optimizer's budget. Every program pays
   a ~0.16 G library floor today.
5. **Self-hosting** ([readiness](docs/design/self_hosting.md)): after question 24,
   new leaf compiler modules start in Dewy.
6. **Runtime gaps** (upper bound first): callback traversal, graph layout, float
   compare/negate, outer-target SIMD, destination passing, bounds-check upgrades.
7. **Small items:** swap primitive for refined arrays; strict Map invariants
   (question 10); result-length facts for `make(n)`; runtime `type<T>` statics;
   effects slice 4 follow-ups; the `@obj.method()` source-text heuristic.

## Decided (David; full text in [docs/design/decisions.md](docs/design/decisions.md))

- `int` is arbitrary precision; `intN`/`uintN` wrap. Decimal literals are exact
  unless the context is float64. Zero-argument calls may omit parentheses. A
  bare function name calls; `@fn` is the handle.
- No traps by default; `$runtime_checks` is the production opt-in; `$prototype`
  is for development. Boolean metatags accept `$tag`, `=true`, `=false`.
- The strict lane is `$no_hidden_costs` (library bundle); `$realtime` is reserved.
- Compile target: 250k lines/s single-threaded, default build (200k minimum).
  Fresh compiles only, no library image; hello-world ~50 ms guardrail.
- Concurrency: the adopted direction; `parallel`; `concurrent {…}`/`spawn`;
  `& no blocks`; `Canceled`; `Atomic<T>` with optional orders (provisional).
- GPU: placement follows data; mixing devices is a compile error.
- Follow the reference: no `+` concatenation; initialize before reading;
  `d.keys` is a set; value-preserving conversions; declared rows are contracts.
- `$shadowable const` at module top level; the prelude uses it.
- Loops iterate the entry value; `loop x in @xs` iterates the place live.
- Inference keeps precision; `end` and `new` are reserved.
- Tensors: one `array`, shape in the type, dot broadcasting ([tensors](docs/design/tensors.md)).
- Safety bundles ladder: `$prototype` → `$runtime_checks` → default →
  `$explicit_copies` → `$no_hidden_costs` → `$explicit_allocation_failure`.
- Allocation: implicit context allocator; OOM ends the process unless
  `$explicit_allocation_failure`. Floats: strict IEEE; `$fast_math`,
  `$no_nan`, `$no_inf`, `$finite_floats`.
- FFI: `$extern`/`$export` metatags, `ptr<T>`, unsafe boundary; blocking `net`.
  `$target` with canonical names; imports splat unless `as name`.
- `index_of`/`find` → `int | Missing`; `main` returns `void | errors` with
  sequential exit codes; `console` object; `print(x file=stderr)`.
- Slices proven or `xs[$clamp a..b)`; helpers adopted, `zip` dropped;
  `T?` fields default to `none`; tuples are per-position arrays; `b'a'`.
- Floored `%`; human types round half away from zero, floats IEEE (`ties=`).
- Hooks preserve value; move hooks can't fail; no `move` syntax yet.
- Spelling: extra spellings allowed when well justified; no unjustified aliases.
- Units: automatic display, `as unit` overrides; offset points/deltas by use;
  rational exponents. Time: one timeline plus layers ([time](docs/design/time.md)).
- Invariants with trusted-validator brands; resources via practical limits.
- `wrap<uint8>(x)`; `f transmute uint64`; `mod(a b kind=…)`; iterator control
  via `let w=…` and `loop x in @w`; `loop i in 0.. and x in xs` (no `enumerate`).
- `@(m.method)` places from handles; sibling literals keep positional types;
  uniform precision (string unions, int ranges); `main` optional, runs once.
- `$build` record; `Path` file methods; inferred `Send`/`Sync` with
  `$send=false` opt-outs; escapes; short-circuit `and=`/`or=`.
- Versions: language 0.0.0; extension patch bumps, at most one release a day.

## Open questions for David

The open-question pass is complete (2026-10-21). New questions carry a
recommended answer, what it unblocks and whether it's reversible; reversible
ones are implemented provisionally and flagged. Deferred until real code needs
them: index-typed refinements.

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
