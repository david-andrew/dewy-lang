# Compile-throughput strategy, 2026-10-21

Master `bd59cea2`, own fixed point, 1 emission worker unless stated. Synthetic = `generate_dewy(1000)`, 22,005 root lines: **1,185.0 M** uninstrumented.
Machine: i7-6700 (4C/8T), shared, load 1.5–2.7. Phases come from perf_event_open brackets (+0.2% overhead), exclusive and nested-aware.
A function counts as library when its declaration lies under `lib/`, including generic instances of library code.

## 1. Root versus library (M instructions)

| Phase | Synthetic root | Synthetic library | Hello (all library) | Self-build library (release, 9.37 G) |
|---|---:|---:|---:|---:|
| Load: lex/parse root; prelude load | 138.6 | 37.9 | 37.9 | 69.8 |
| Check: bodies + top level + glue | 268.5 + 22.8 + 13.6 | 52.0 + 8.0 | 48.3 + 8.0 | 112.4 |
| Lower | 165.8 | 19.5 | 17.5 | 85.3 (+6.0 helpers) |
| Optimize (inline, local pass, vectorize) | 198.8 | 17.0 | 16.3 | 18.2 (+ serial release optimizer in glue) |
| x64 | 193.7 | 16.6 | 16.1 | 144.4 |
| Image / other | ~19 | ~2 + 4 | 2.7 | — |
| **Total** | **~1,021 (86%)** | **~153 (13%)** | **146.8** | **~430 (4.6%)** |

Counts on the synthetic program: 1,000 root functions plus the top level. 210 library functions are checked (one generic instance), 161 lowered plus 10 helpers, and 160 emitted. Library code is 14.4k of 175k IR instructions.
Hello checks 201 library functions (no generic instances), lowers 154 plus 9 helpers and emits 153. That is the near-root-independent library closure.
Generic re-instantiation is not a cost here: the self-build checks 280 library instance bodies, all inside the 112 M.

**Per-unit root cost.** Check: 13.9k/line, ~1.7k per AST node (177k nodes). Lex/parse: 6.3k/line. Lower: 7.5k/line (1.03k per IR instruction produced). Optimize: 9.0k/line (1.24k/IR). x64: 8.8k/line (1.48k/IR).
**Root total: 46.4k/line.** The north star allows 18.2k/line *including* the library.

## 2. Persistent library caching: bounded

- **Ceiling (warm library, fresh root).** The cache can remove at most the library column, **−153 M (−13%) → ~1.03 G**, which is about −24 ms wall. Hello would drop from 147 M (31 ms) to roughly 10–15 M. The self-build would drop by only 4.6%.
- **What caching cannot do.** It cannot reach 0.40 G. The root alone is 2.6× over budget.
- **What should be cached.** Two of the candidate layers are root-independent and safe:
  - the post-load prelude state (38 M);
  - checked non-generic library bodies with their bottom-up summaries (52 M).
- **Machine code (~50 M) carries the hazards:**
  - `fast_inline_into` inlines library leaves into root code, so the cache needs optimized IR, not only bytes;
  - `find_unique_globals(closed)` is closed-world, and the prelude-globals init is a root-dependent fixed point;
  - global data offsets are absolute; `par_join` already remaps rodata and calls, but not globals;
  - `lx_vec_on`/`want_cpu_flag`, target, release/debug mode and `checked_flags` must enter the key;
  - instances over root types can't be cached;
  - emit pruning is reachability-based.
- **Whole-program analysis does not block a cut.** Effect rows are per-function summaries with callee edges, solved by SCC. Facts and refinements flow callee→caller. The only caller-dependent pieces are:
  - callable or effect-variable parameters (treat them as generic);
  - closed-world global uniqueness;
  - prelude init.
- **Clean cut.** Cache through check and summaries for the root-independent library closure. Lower, optimize and emit fresh anything that touches closed-world facts or callables.
- **Policy.** GOALS says "a persistent cache is not the way the language stays fast". A user-side cache is out. A **toolchain-baked library image** is different: it is built with the compiler, keyed by the compiler+lib hash, and falls back to fresh on a mismatch. That makes it a distribution artifact (like a shipped libstd), not a cache. **This needs David's decision.**

## 3. Parallelism (wall, median of 10 fresh runs)

| Workers | Synthetic wall | CPU | Emit phase | Self-build | Hello |
|---|---:|---:|---|---:|---:|
| 1 | 187.8 ms | 190 ms | 58.2 ms serial | 1,476 ms | 30.9 ms |
| 2 | 180.9 | 215 | 39 wait + 5.0 join | — | 30.3 (below fork threshold) |
| 4 | 174.6 | 250 | 34 wait + 4.8 join; workers 17–28 ms | 1,371 | — |
| 8 (default) | 166.5 | 260 | — | — | — |

- **Today's parallel slice is small.** Only optimize+x64 runs in parallel: 426 M, **36%** of synthetic. **64% is serial** (lex/parse, prelude, check, lower, image), so the Amdahl ceiling is 1.56×. Measured gains are 1.04–1.13×.
- **Emission losses.** There are three:
  - IR-count cuts are imbalanced: the 1,000-call top-level function alone costs 35 M;
  - workers 1–2 block 16 ms on pipe writes, because the parent reads the pipes in order;
  - fork/CoW costs 2–3.5k minor faults per child.
- **Lower+opt+x64 per function is embarrassingly parallel** once whole-program finalization has run. Everything before `find_unique_globals` is finished, and the post-check analyses cost 1.2 M. The rejected forked-lowering attempt (`dc4db306`) shipped IR back and kept a separate emission fork. Fusing lowering into the *emission* worker ships only machine code, and it parallelizes **611 M (51%)**, not 13%.
- **Probe: is checking parallelizable per function?** Partitioned checking measured in a throwaway fork probe (results discarded, synthetic has explicit signatures):
  - 1 child: 70 ms serial check loop → 86 ms (fork tax);
  - 4 children: **45.8–48.8 ms wall**;
  - each child checked 67 M of root work plus **~34 M of duplicated library checking**;
  - run one at a time, a child takes 29 ms. Running concurrently costs ×1.6 on this shared 4C/8T box.

  Checking is therefore partitionable after signatures settle, provided the library and signatures are checked in the parent before forking.

## 4. Check cost per line

- **Comparison (rough recollection, not measured).** go/types runs at roughly 3–6k instructions/line. tsc (JS) is 30–60k. tsgo is about 10–15k single-threaded.
- **Dewy at 13.9k/line** sits at tsgo level while doing more (facts, effects, ownership). A 2× gain is plausible; 5× is not.
- **Sampled self costs, synthetic − hello, check phase:**
  1. **Second AST walk.** `zonk_tree` re-walks every body after checking: 30 M ≈ 10% of root check. Finalize at node exit when the type is concrete, and zonk only nodes that recorded type variables.
  2. **Name resolution by strings and hashes.** `__str_eq` 11, `find` 8.4, `get` 6.9, `name_of` 5.5, `hash` 3.3, `collect_in` 2.6, and the checker's share of `intern_sub` ~10: **~45 M ≈ 15%**. There are 105 `intern("…")` call sites in check/expr and 34 `name_of(x) == "…"` compares. Use precomputed name ids and per-scope id tables.
  3. **Per-node allocation and refcount churn.** `__alloc_z` 8.9, `__free` 5.9, `__arr_grow` 3.9, `__rc_dec`: ~20 M, from temporary arg/candidate arrays per call. This is host-code-quality territory (budget project 6).

  Overload-plan caching and local traversal tweaks are already rejected; none of the three wastes above exceeds ~4% alone.

## 5. Is 0.40 G single-threaded fresh reachable?

No, not on any credible plan:
- the landed and proposed local projects reach ~1.05 G;
- a baked library brings that to ~0.90 G;
- a 20% host-code gain brings it to ~0.72 G.

0.40 G needs 2.6× on *every* root phase at once.

The 0.40 G figure came from assuming 1.4 IPC at 3.4 GHz. This machine sustains **6.3 G instr/s** on the compiler, so 250k lines/s (88 ms) equals ~0.56 G single-threaded.

**Proposed north star.** GOALS asks for a seconds-scale edit loop, fresh compilation, and small-program latency reported separately:
- **Primary:** synthetic-22k fresh wall-clock with **4 workers ≤ 88 ms** (250k lines/s), pinned and 7-run median, alongside a representative program;
- **Secondary:** **hello ≤ 10 ms**;
- **Guardrail:** 1-worker instructions must not regress (speed gate stays), with an efficiency target of ~0.75 G.

## 6. Ranked projects

**1. Fused partition workers: lower→optimize→x64 in the emission fork.**
- **Saving.** Fresh instructions: +1–2% overhead. Wall at 4 workers: −30–50 ms; modelled at 120–136 ms against 175 today. Warm: same.
- **Cut.** Fork after `find_unique_globals`/`facts_finalize`. Pre-assign lf ids for every checked instance and global offsets before forking. Helpers, strings, constants and globals become symbolic requests: reuse the `dc4db306` request protocol and the `par.jo` join. The parent lowers late discoveries and the prelude init after the join.
- **Risks.** Byte-identical determinism across 1/2/4 workers, diagnostics order, cross-partition `fast_inline` (pre-lower the tiny leaves in the parent), RSS, and refcount-driven CoW.
- **Pilot.** Default build, cost-balanced cuts, concurrent pipe reads. **Gate:** synthetic 4-worker wall ≥3% better than master's 4-worker run, identical binaries.

**2. Partitioned checking with long-lived partition workers (check→code).**
- **Saving.** Parallelizes another 305 M of root check. Wall: ~90–110 ms at 4 workers. Combined with #3: ~75–90 ms, which meets 250k lines/s.
- **Cut.** The parent does parse, registration, signatures (SCC order for inferred returns), the library closure and open globals. Workers check their partition, then exchange summaries at one barrier (effect edges, global writes, instance requests by canonical key), then lower and emit.
- **Risks.** Type and instance identity diverges per worker (needs canonical keys), inference-dependent callers, diagnostics deduplication. High risk.
- **Pilot.** Extend the probe for explicit-signature programs only. **Gate:** ≥3% wall on top of #1, with no duplicated library check.

**3. Toolchain-baked library image (needs David's decision).**
- **Saving.** Fresh synthetic −38 M (stage a) to −153 M (−13%). Hello 147 → ~15 M (31 → ~5 ms). Self-build −4.6%. It removes serial work, which multiplies with #1 and #2.
- **Cut.** As in §2: (a) post-prelude state, (b) checked non-generic bodies and summaries, (c) relocatable code for the closed-world-free closure.
- **Risks.** Key completeness (target, mode, CPU flags, lib hash, `DEWY_CORE_LIB` override) and a stale image (mitigated by a hash check with fresh fallback).
- **Pilot.** Stage (a), a flat-array dump of names/nodes/files/modules after `load_prelude`. **Gate:** ≥3% synthetic (38 M = 3.2%) and ≥20% hello.

**4. Checker name resolution by id plus a fused zonk.**
- **Bound.** ≤75 M (6%) single-thread. Realistically 2–4% given the history of sub-1% local pilots.
- **Pilot.** Replace the top `intern("…")`/`name_of ==` sites on the call-resolution path. **Gate:** ≥3% synthetic; stop after one failed pilot.
