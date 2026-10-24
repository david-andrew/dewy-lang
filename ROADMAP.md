# Roadmap

The single work queue, owned by the coordinator. [docs/GOALS.md](docs/GOALS.md)
says what Dewy must become; this file says what we do next. Git history is the
record of what landed: no "landed" lines here. At most one ROADMAP-only commit a
day; keep it under 150 lines. Accepted designs live in [docs/design](docs/design/).

## North star

| Measure | Now (2026-10-24) | Goal |
|---|---|---|
| Acceptance ladder, design surface | 101/101 (no open rungs; new rungs needed) | all |
| Tier-4 flagship programs (1–5k lines each) | 7/7 pass | all pass |
| No traps by default (`require-static`, no opt-ins) | ~272/372 programs; flip commit on `wt/flip4` | flip the default |
| Compile throughput, single thread, default build, every processed line | flagships 139k lines/s (min 99_dewy_frontend 93k) | 200–250k on every flagship |
| Hello-world compile | 7.9 ms (instruction-derived) | ≤20 ms |
| Kernels vs C -O2 (time, default) | broadcast 3.8×, arena 4.4× | ≤1.2× |
| Quick / full suite | ~20–33 s / ~4 min (loaded machine) | ≤30 s / ≤5 min |

Ladder: `python3 -m tools.core ladder` (`tests/ladder/ladder.json`). Compile:
`speed` (single-thread instructions; the gate) and `speed --cycles` for layout
changes. Wall clock only on a quiet pinned machine or a CI runner. Kernels:
`bench`.

## Next

1. **No traps by default** (top capability). Blockers before the flip lands:
   facts/effects compile cost with facts everywhere (facts +111%, effects
   +231%), codegen regressions under the flip (bench `arrays`, lost stencil
   vectorization), remaining unproven library ops.
2. **Compile speed** (200–250k lines/s single-thread on every flagship; every
   processed line counts). Next: obligation-heavy facts cost (99_dewy_frontend's
   contracts), then the native code-quality gap vs GCC (frame/allocation,
   instruction selection). Layout changes need cycle measurements.
3. **Exact fixed-width integers** (decided): overflow policies landed; store
   obligations and exact intermediates at gate-neutral cost (Astra).
4. **Decided surface still to build:** deadlock freedom (`lock_all`,
   `try_lock`, `$no_deadlocks`, inferred lock order); place-returning methods;
   `$bulletproof`/`$no_assumed_bounds`; the time system (redesign pending).
5. **Runtime speed vs C:** loop and `push` codegen (broadcast, arena), register
   allocation, vectorization under checks.
6. **Self-hosting** ([readiness](docs/design/self_hosting.md)): next leaves
   `targets.jo`, the intern table (after the flip removes proven-read checks).
7. **Hygiene at quiet points:** the internal Sloppy comment sweep and
   `SLOPPY_*` names; moving implemented rounds out of decisions.md into their
   design docs.

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
