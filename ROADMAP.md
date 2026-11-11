# Roadmap

The single work queue, owned by the coordinator. [docs/GOALS.md](docs/GOALS.md)
says what Dewy must become; this file says what we do next. Git history is the
record of what landed: no "landed" lines here. At most one ROADMAP-only commit a
day; keep it under 150 lines. Accepted designs live in [docs/design](docs/design/).

## North star

| Measure | Now (2026-11-07) | Goal |
|---|---|---|
| Acceptance ladder, design surface | 135/135 | all |
| Tier-4 flagship programs (1–5k lines each) | 7/7 pass | all pass |
| No traps by default | census 2,557 sites in 1,032 of 2,252 programs, down from 3,600 on 10-26 | ordinary code proves without opt-ins |
| Compile throughput, single thread, default build, every processed line | flagships 145.0k lines/s (11-11; 161.5k on 11-09 before the flagships began proving statically, +14% source cost) | 200–250k on every flagship |
| Hello-world compile | 7.5 ms (instruction-derived) | ≤20 ms |
| Kernels vs C -O2 (time, default, `bench` on redfox) | 18 of 28 at ≤1.2×; worst byte_find 2.85×, callbacks_literal 2.34× (fair C about 1.47×), name_table 1.67×, graph 1.54×, dict_words 1.51×, arena 1.43× | ≤1.2× |
| Quick / full suite | about 25 s / about 9.5 min at 4 workers | ≤30 s / ≤5 min |

Ladder: `python3 -m tools.core ladder` (`tests/ladder/ladder.json`). Compile:
`speed` (single-thread instructions; the gate) and `speed --cycles` for layout
changes. Wall clock only on a quiet pinned machine or a CI runner. Kernels:
`bench`.

## Next

1. **No traps: ordinary code proves** (top capability). Most remaining census
   sites truly lack program evidence, so diagnostics must name what to write.
   Dogfood rounds alternate discovery and fix. Coverage rounds on value layouts,
   refinements and concurrency found 23 bug causes, all fixed; run more on
   untested areas (FFI, GPU/packed/SOA layouts, other native architectures).
2. **Compile speed** (200–250k lines/s on every flagship). 99 and 100 need
   33–35% fewer instructions. GCC O3+LTO on the compiler would give about 23%;
   they would still need about 8–11% less compiler work. Allocator, isel, dense
   storage, frames, optimizer structure, normalization and non-leaf inlining all
   bounded under 1%, and profile-driven work cuts have nothing left bounded at
   0.5%. The next round needs a new structural idea to test, not another profile.
3. **Self-hosting** ([readiness](docs/design/self_hosting.md)): the front end,
   checker state, statement and expression layers, call group, ownership and
   loans, the optimizer, the emitters and nearly all of lower.jo run in Dewy.
   Next: lower.jo's last functions and ir.jo, then the rest of expr.jo, check.jo
   and facts/effects; close milestone 1 (Dewy owns all subsystem execution), then
   milestone 3 (a pinned C-reproducible seed that retires the frozen twins).
4. **Runtime speed vs C:** full landings now gate kernel instructions
   (`bench --baseline`; waive with `bench: accept <reason>`). The push family is
   reopened: arena reached 1.42×; the last large saving needs an arena-residency
   proof. Next: callback inlining on default, then dictionary helpers.
5. **Decided surface still to build** ([decisions.md](docs/design/decisions.md)):
   the rest of the time system; self-length refinements (D17); R-value units;
   examples needing `$runtime_checks`, 21 of 29 as of 11-06, toward zero.
6. **In David's design rounds, build nothing:** D4 parallel (`select`, cancel
   scopes, metatag placement, `tasks`), D10 safety tags, D11 game APIs, D21
   packages. Remaining user-facing environment variables wait for their metatag
   names (inventory: 31 knobs, mostly `$window.*` under D11).

## Decided (David; full text in [docs/design/decisions.md](docs/design/decisions.md))

- `int` is arbitrary precision; `intN`/`uintN` wrap. Decimal literals are exact
  unless the context is float64. Zero-argument calls may omit parentheses. A
  bare function name calls; `@fn` is the handle.
- No traps by default; `$runtime_checks` is the production opt-in; `$prototype`
  is for development. Boolean metatags accept `$tag`, `=true`, `=false`.
- The strict lane is `$no_hidden_costs` (library bundle); `$realtime` is reserved.
- Compile target: 250k lines/s single-threaded, default build; every flagship
  at least 200k (#126c, 11-01).
  Fresh compiles only, no library image; hello-world ~50 ms guardrail.
- Concurrency: the adopted direction; `parallel`; `concurrent {…}`/`spawn`;
  `& no blocks`; `Canceled`; `Atomic<T>` with optional orders (provisional).
  Stage 4 (11-01): `Unsent<T>` sends, `spsc<T N>`, `mpmc<T>(n)`, inferred
  parallel-safe callbacks; `select` and `[concurrent …]` on hold for one
  cohesive proposal.
- Import cycles behave as one big file (11-01). No legacy: design changes
  keep no shims or old-form diagnostics.
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
