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
| Tier-4 flagship programs (1–5k lines each) | 1/7 (the game) | 7/7 |
| Compile throughput, lines/s per corpus | corpus not yet built | 250k lines/s |
| Critical-path instructions, synthetic-22k at 4 workers (regression signal only) | 0.60 G | no regression |
| Single-thread instructions, synthetic-22k (guardrail) | 1.17 G | ~0.75 G (pending David) |
| Hello-world compile | 31 ms | ≤10 ms |
| Kernels vs C -O2 (time, default) | literal callbacks 4.6×, callbacks 2.3×, params 1.75×, graph 1.7×, game 1.6× | ≤1.2× |
| Quick / full suite | ~17 s / ~4 min | ≤30 s / ≤5 min |

Ladder: `python3 -m tools.core ladder` (`tests/ladder/ladder.json`). Compile:
`speed --critical` (load-independent; the gate). Wall clock only on a quiet,
pinned machine or a CI runner, never on the shared box. Kernels: `bench`.

## Now

- Opus: `end` and `new` (reserve both; `new` axis insertion on nested arrays).

## Next

1. **Tier-4 flagships** (Opus writes them, design surface plus a core-dialect
   twin where possible, added to the ladder). They drive the blocked pillars:
   - a freestanding kernel/RTOS-style program in the strict lane;
   - an ML training loop over tensors;
   - a persistent KV or small SQL store;
   - constant-time crypto (SHA-256 plus ChaCha20 or Poly1305);
   - an HTTP server with a wasm UI;
   - a compiler or lexer module;
   - the game (existing flagship).
2. **Compile-speed corpus.** Report lines/s per corpus: the compiler's own
   sources (as they move to Dewy), the ladder and examples concatenated, the
   game, and later the flagships. synthetic-22k stays as a regression signal.
3. **Hard pillars, for Astra** (one stream): strict lane, concurrency, codegen
   architecture, as David's answers arrive. Designs:
   [refinement](docs/design/refinement.md), [effects](docs/design/effects.md)
   (slices 3, 5–6), [ownership](docs/design/ownership.md) (slices 4–6).
4. **Compile throughput** ([strategy](docs/design/compile_throughput.md)):
   instance reconciliation so partitioned checking reaches real programs (game,
   2–10k-line programs); a shipped library image (question 22); checker name
   lookup by id.
5. **Self-hosting** ([readiness](docs/design/self_hosting.md)): after question 24,
   new leaf compiler modules start in Dewy, not Jo.
6. **Runtime gaps** (measure the upper bound before any pilot): callback
   traversal, graph memory layout (contiguous adjacency), float compare/negate
   selection, outer-target SIMD, destination passing, bounds-check upgrades
   (call-site entry facts, a 2^48 length axiom, hoisting through `@`).
7. **Small items:** swap primitive for refined arrays; strict Map invariants
   (question 10); result-length facts for `make(n)` (strict 67/70); static calls
   through runtime `type<T>` values; effects slice 4 follow-ups; replace the
   `@obj.method()` source-text heuristic with a node flag.

## Decided (David)

- `int`: arbitrary precision with word storage where proven. `intN`/`uintN` wrap.
- Decimal literals are exact unless annotated (e.g. `float64`).
- Zero-argument calls may omit or include the parentheses.
- A bare function name calls; `@fn` is the handle.
- Ordinary code keeps runtime checks; static rejection of unproven facts is a
  strict-lane property.
- Inference keeps the most precise type it knows; only an explicit wider
  annotation widens (literal unions; integers keep range facts).
- `end` and `new` are reserved: `end` is the last index inside an index; `new`
  inserts a singleton axis (NumPy `newaxis`): `xs[new ..]`, `xs[.. new]`.
- Versions: the language stays 0.0.0; the extension gets patch bumps only, at
  most one release a day.

## Open questions for David

New questions carry a recommended answer, what it unblocks and whether it's
reversible; reversible ones are implemented provisionally and flagged.

1. Strict-lane opt-in surface; are panic and detach named separately? (64, 67, 70)
2. Scope of `$prototype`. (72)
3. Readonly/lifetime-bearing payload places beyond `$lend`.
4. Allocation capabilities and allocation-failure policy. (76)
5. Explicit `move` syntax.
6. Structured concurrency: tasks/partitions, `Send`/`Sync`, atomics,
   cancellation, locks. (81–83)
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
22. Ship a prebuilt library image with the toolchain (hello 31 → ~5 ms)?
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
27. Compile north star: relax single-thread to ~0.75 G and gate on 4-worker
    critical path / wall clock.

Each held ladder program's note names the question that holds it.

## Tried and rejected (an idea family ends after one failed pilot)

- Pooled/inline syntax children; reusable register scratch workspace.
- Zero-cost cold-call register weighting (kernels −38%); an entry guard before
  the prologue; block-local liveness rescue and short register caches.
- Word-at-a-time name hash; paired SSE string equality; word-at-a-time emission.
- Broad release inlining-cost adjustment; selective default passes (kernels
  regressed 16–92%); compact IR encoding (−0.3%).
- Readonly aggregate argument forwarding from loop snapshots (−1.25%).
- Local check-traversal fixes (four pilots under 1%); overload-dispatch plan
  cache (2.79% ceiling); x64 live-interval stream (1.9% ceiling).
- Fork-based parallel lowering alone (0.88–1.00×); worker instance
  reconciliation as piloted (game +0%, lost determinism on fallback).
- Effects slice 3 consolidation as piloted (+28% self-build).
- Null-trap lowering for params; dictionary micro-pilots (8-byte slots,
  single-probe updates, borrowed fetches, triangular probing). Graph is
  memory-bound; only a layout change (contiguous adjacency) is left.
- Inferred scope regions (1.18× upper bound); lambda-lifting (environments are
  already on the stack).
