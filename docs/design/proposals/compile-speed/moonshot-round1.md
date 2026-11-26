# Compile-speed moonshot, round 1: architecture and budget for 1M lines/s

## Verdict

**1,000,000 processed lines/s single-thread in default builds is reachable on every tier-4 flagship under the fixed metric**, with no library image, no persistent cache, no incremental reuse, identical diagnostics and outputs, and no regression on `bench --baseline`.

At base `475b1ded51` (2026-11-26), the flagship panel runs at **259,508 processed lines/s** (**24.27k retired instructions/line**, 986.22M total across 40,631 processed lines); the slowest flagships are **99 (`218.5k l/s`, 28.83 k/L)** and **96 (`221.2k l/s`, 28.47 k/L)**. Reaching ≥ 1,000,000 lines/s on every flagship requires **≤ 6.30k instructions/line** on every flagship: a **3.85× overall cut** and a **4.58× cut on 99** (4.52× on 96).

Two facts discovered in this study determine the architecture:

1. **Host codegen alone is a ~15% ceiling on the current IR, not a 4× lever.** Compiling the current compiler's scalar `--host-ir` with GCC `-O3 -flto -march=native` cuts the panel by **−14.85%** (986.2M → 839.8M, 259.6k → 304.8k l/s) and self-build by **−18.41%** (11.01G → 8.98G), with −19.6% to −24.3% across `check`, `facts`, `effects`, `ownership` and `lower`. Closing most of this gap compounds across every phase (~0.82× multiplier) and speeds up user programs too, but ~80% of the 4× cut must come from structural compiler redesign.
2. **Hardware floor prototypes prove 4×–6× algorithmic and data-structure headroom in both frontend and backend.** Standalone compiled prototypes measured with the gate's `count-instructions` tool on flagship 96's actual inputs hit **3.11M (0.88 k/L)** for file read + AVX2 scan + newline index + direct lex/intern + 28k compact 32B nodes (vs **20.27M = 5.74 k/L** today) and **3.98M (1.13 k/L)** for fused optimize + linear-scan regalloc + direct x86-64 emission + ELF write across 312 functions / 21k IR ops (vs **22.02M = 6.23 k/L** today).

## Measurement method

- **Host**: Desktop Intel Core i7-6700 (`redfox`), Linux x86-64, hardware `perf` retired user instructions via `tools/compiler/count_instructions.c`, `DEWY_EMIT_WORKERS=1`, default (debug) builds, fixed reference rate `IPS = 6.3e9`.
- **Whole-panel baseline**: `python3 -m tools.core speed --base HEAD` (`475b1ded51`).
- **Phase split**: `dewy-core build <src> -o <out> --time` (hardware phase counters; adds ~1.4% counter overhead, so panel sum is 1,000.3M vs 986.2M uninstrumented).
- **Instruction-level attribution**: Callgrind (`--dump-instr=yes`) over all 7 flagships against full `objdump -d` disassembly (8,168 functions). Folding `rep movs/stos` iterations to 1 instruction per execution matches hardware `perf` to **−0.03%** (985.98M folded vs 986.30M perf; 151M `rep` iterations separately tracked as memory copy/zero volume).
- **GCC host oracle**: `dewy-core build compiler/main.jo --host-ir --target x86_64-linux` (71 MB, 8,166 functions) translated to C with null/overflow UB flags disabled (`-fno-delete-null-pointer-checks -fno-isolate-erroneous-paths-dereference -fno-strict-overflow`), compiled with GCC `-O3 -flto=2 -march=native`. Output binaries verified byte-identical to native on all 7 flagships and self-build.

## Baseline attribution (`475b1ded51`)

### Per-flagship baseline and 1M budget

| Target | Lines (user + lib + inst) | Baseline (M) | Baseline l/s | k/line | 1M Budget (M) | Cut needed |
|---|---:|---:|---:|---:|---:|---:|
| `95_kv_store` | 6,192 (1,356 + 4,353 + 483) | 170.05 | 229,363 | 27.46 | 39.01 | 4.36× (−77.1%) |
| `96_ct_crypto` | 3,536 (1,022 + 2,510 + 4) | 100.68 | 221,217 | 28.47 | 22.28 | 4.52× (−77.9%) |
| `97_notes_service` | 6,581 (1,233 + 4,379 + 969) | 173.12 | 239,455 | 26.31 | 41.46 | 4.18× (−76.1%) |
| `98_notes_listen` | 12,060 (908 + 9,386 + 1,766) | 230.10 | 330,137 | 19.08 | 75.98 | 3.03× (−67.0%) |
| `99_dewy_frontend` | 5,031 (982 + 3,517 + 532) | 145.02 | 218,536 | 28.83 | 31.70 | 4.58× (−78.1%) |
| `100_rtos_kernel` | 3,371 (853 + 2,513 + 5) | 86.69 | 244,926 | 25.72 | 21.24 | 4.08× (−75.5%) |
| `101_ml_training` | 3,860 (315 + 3,501 + 44) | 80.56 | 301,792 | 20.87 | 24.32 | 3.31× (−69.8%) |
| **Panel sum** | **40,631** | **986.22** | **259,508** | **24.27** | **255.98** | **3.85× (−74.0%)** |
| `self-build` (release) | 194,232 | 11,006.88 | — | 56.67 | — | target ≤ 4.5G |
| `synthetic-22k` | 24,254 | 586.7 | 260,241 | 24.19 | — | — |
| `hello_min` (1 root L) | 1,640 (1 + 1,639 + 0) | 25.51 | 404,965 | 15.55 | — | — |

### Per-phase breakdown (`build --time`, k instructions / processed line)

| Flag | Lines | Total | `load` | `check` | `facts` | `effects` | `owner` | `lower` | `opt` | `codegen` | `other` |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `95` | 6,192 | 27.82 | 4.54 | 7.33 | 3.79 | 0.30 | 0.00 | 5.11 | 2.49 | 3.74 | 0.52 |
| `96` | 3,536 | 28.84 | **5.74** | 6.45 | 2.73 | **1.64** | **0.84** | **5.22** | 2.34 | 3.33 | 0.56 |
| `97` | 6,581 | 26.71 | 4.22 | 6.97 | 2.88 | 0.47 | 0.04 | 5.11 | **2.59** | **3.89** | 0.53 |
| `98` | 12,060 | 19.38 | 3.74 | 6.30 | 1.37 | 0.56 | 0.10 | 3.12 | 1.53 | 2.31 | 0.35 |
| `99` | 5,031 | **29.15** | 4.53 | 6.34 | **6.26** | 0.46 | 0.06 | 4.90 | 2.58 | 3.46 | **0.57** |
| `100` | 3,371 | 26.09 | 5.28 | 5.94 | 3.25 | **1.84** | **0.57** | 4.23 | 1.60 | 2.83 | 0.54 |
| `101` | 3,860 | 21.24 | 4.95 | 5.26 | 1.32 | 0.26 | 0.02 | 4.14 | 1.98 | 2.80 | 0.52 |
| **Panel** | **40,631** | **24.62** | **4.46** | **6.45** | **2.86** | **0.66** | **0.17** | **4.34** | **2.09** | **3.10** | **0.48** |

Root Dewy vs library asymmetry across the panel:
- **Root Dewy** (6,669 lines): **340.5M = 51.06 k/root-line** (`facts` 14.83, `check` 9.91, `lower` 8.59, `load` 6.03, `codegen` 5.92, `opt` 4.45). On 99, root Dewy is **70.9 k/root-line** (`facts` alone = 30.2 k/root-line = 29.6M).
- **Library + instances** (33,962 lines): **555.0M = 16.34 k/lib-line** (`check` 5.04, `load` 4.14, `lower` 3.29, `codegen` 2.18, `opt` 1.56).
- **Shared** (startup, prelude registration, module-level passes, ELF/DWARF): **104.5M = 2.57 k/all-line** (up to **4.51 k/L on 96** and **3.76 k/L on 100** due to `shared effects` = 5.4–5.9M).
- **Self-build (`compiler/main.jo --release`, 194,232 lines, 1.70M nodes, 10,704 fns, 13.7 MB code)**: 11.05G (`optimize` 3.83G / 34.7%, `check` 2.48G / 22.4%, `codegen` 1.66G / 15.0%, `lower` 1.59G / 14.3%, `load` 1.09G / 9.8%, `facts+effects+owner` 0.32G / 2.9%, `other` 0.10G).

### Structural volume and data-structure census (panel sum)

- **Source volume**: 3,917,404 bytes (96.4 bytes/processed line; 138 B/L on 96 because 429 KB of library files are read and scanned for 2,510 reached lines — only 21.2% of file lines reached, and 29.8% of parsed library bodies unreached).
- **AST**: 314,451 nodes (7.74 nodes/line) × **104 bytes/Node** = 32.7 MB. Node construction (`mk` 6.42M, `node_mk` 2.57M, `node_set_list` 4.21M, `node_set_list_span` 2.83M, `node_append_raw` 2.62M, `node_run_of` 1.92M, `node_clone` 3.60M) = **24.2M self**.
- **IR & code**: 3,479 functions (**1,033 with loops = 29.7%**, **2,446 straight-line = 70.3%**), **217,341 post-opt IR ops** (5.35 IR ops/line, 63.8% in loop functions), **1.93 MB x86-64 code** (47.5 bytes/line). Lower emits **~45,000 redundant `mov` ops** (~20% of pre-opt IR) that `optimize` deletes (>91% deleted). Current backend cost is **1,783 instructions/post-opt IR op** (`lower` 811, `opt` 392, `codegen` 580).
- **Runtime & allocation churn** (`lib/core/rt.jo` + `str.jo` + `map.jo` = **91.1M self**, 9.2% of panel):
  - **323,718** `__alloc_z` (9.93M self), **252,744** `__arr_new_raw` (6.07M), **182,957** `__arr_push_slot` (6.97M self / 53.3M raw incl), **117,351** `__arr_grow_more` (6.81M self + 45.4M `rep` iters), **267,860** `__free` (5.09M), **23,782** `__arr_resize` (+ 34.1M `rep` iters, largely from `exact_*`), **21,383** `__arr_clone` (+ 11.6M `rep` iters, mostly `FactState`), **31,583** `__h_drop_2388` (`FactState` drop), **81,944** `clear` (65% = 48,804 calls from `begin_fn` clearing 14 mostly-empty containers), **47,348** `__map_add`, **117,959** `has`, **77,879** `get`.
- **Host machine instruction mix** (986.0M folded): `cmp/test` 17.95%, `jcc` 17.14%, **stack load+store 14.13%** (139.3M), non-stack load+store 13.72%, ALU/cmov 7.87%, reg-reg `mov` 7.32%, `ext/narrow` 3.63%, frame `push/pop/rsp` 2.79%, **NOP padding 2.54% (25.1M)**, `call+ret` 2.62% (13.0M calls), panic guards **1.90%** (18.7M, down from 5.0% in Nov 15).

## Measured upper bounds and oracles

| Candidate | Scope | Baseline | Measured oracle / floor | Implied ceiling | Notes |
|---|---|---:|---:|---:|---|
| 1. Native host codegen + inlining | All phases + self-build | 986.2M panel / 11.01G self | GCC `-O3 -flto -march=native`: **839.8M (−14.85%)** panel; **8.98G (−18.41%)** self (`check` −23.1%, `lower` −23.9%, `effects` −24.3%, `facts` −19.6%, `codegen` −15.0%) | **~0.80×–0.85× multiplier** (incl. non-loop NOP pad −2.54% + drop helpers + direct Dewy globals) | GCC `load` regressed +4.1% on `.jo` due to loop unroll/SIMD peel, but won −13.0% on Dewy self-build `load`. |
| 2. Non-loop compare-branch padding removal | Compiler host + `x64_encode` | 25.1M host NOPs + 2.3M `nop_pad` + per-insn `x_pad_track` | `cmp_branch_pad` currently falls through to `nop_pad` when `x_loop_depth == 0`! | **−3.0% to −3.5%** immediately (`codegen-gap-round1` verified −2.47% + cycle win on `redfox`) | Keep alignment inside loops (`x_loop_depth > 0`) for Skylake JCC erratum; verify on `redfox`. |
| 3. Frontend (`load`): lazy std prelude + AVX2 scan/lines + streaming lex/intern + compact 32B AST | `load` (`181.0M`, `96` = 20.3M / 5.74 k/L) | `96` load = **20.27M** (5.74 k/L) | `proto_load` hardware floor on `96`'s 38 files (486 KB, 13.1k lines, 34k toks, 1.2k interns, 28k 32B nodes): **3.11M (0.88 k/L)** excl. parse | **~4.3–5.0M on `96` (1.20–1.40 k/L)**; **~42–46M panel (1.05–1.15 k/L)** — **4.0× cut** | Extending `std_optional_file` to `files.jo`/`json.jo`/`text.jo` & fixing `story.jo` false triggers drops ~100–130 KB of wasted library scanning on `96`/`100`/`hello`. |
| 4. Compact 32B/SoA AST + `TypeFlags` + non-COW `RawVec`/arena pools | Cross-cutting (`rt.jo` 91M + AST 24M + `vc` 4.8M + `is_managed` 1.9M + `begin_fn` 1.7M) | ~125M across phases | Eliminates 323k allocs/253k arr_new/183k push_slot/117k grow/49k clears/216k `vc`/83k `is_managed`; 3.25× smaller AST | **−70M to −90M** across `load`/`check`/`facts`/`lower` | Replaces `ast.jo`, `types.jo`, `ir.jo` with pure-Dewy storage; removes double-pointer indirections (`xe_nodes[0].ptr`). |
| 5. Fast-path checker (mono direct-call, zero-alloc args, `.jo` fast path, demand zonk) | `check` (`262.3M` = 6.45 k/L; `95` = 7.33 k/L) | 262.3M (`resolve_fn_call`+call stack ~65M incl; `xz_walk` 4.6M; lib `.jo` 171M) | GCC alone: −23.1% (201.8M); mono direct-call kills 18.4k `node_run_of` + 8.1k `node_set_list` + 19k `__free`; skip `xz_walk` when 0 tvars | **~65M panel (1.60 k/L)**, **≤ 1.75 k/L on `95`** — **4.0× cut** | `.jo` library functions (65% of `check`) need none of Dewy's rational/juxt/unit/narrowing/refinement/exact hooks. |
| 6. Two-tier `facts` (Tier-1 local prover + Trailed mutable arena `FactState` + cursor summaries) | `facts` (`116.1M` = 2.86 k/L; **`99` = 31.5M / 6.26 k/L**) | `99` facts = **31.5M** (`fact_join` 1k calls, `fact_slice_prepare_fast` 30 calls @ 52k/c, `__h_drop_2388` 9.4k, `__arr_clone` 5.2k, `fact_distance_slow` 1.9k) | Local dominance/range prover discharges simple loops/guards/fixed arrays without `FactState`; trailed mutable workspace kills 21.4k `__arr_clone` + 31.6k `__h_drop_2388` and turns O(bindings) joins into O(mutations) | **~18–20M panel (0.45–0.50 k/L)**, **≤ 4.0M on `99` (0.80 k/L)** — **6×–7.5× cut** | Preserves 100% of static proofs and `check --obligations` output. |
| 7. Compact bitset `effects` + single-walk `ownership`/`copies` | `effects + ownership` (`33.8M`; **`96` = 8.8M / 2.48 k/L**, **`100` = 8.1M / 2.41 k/L**) | 8.8M (`96`), 8.1M (`100`) | Replace event dicts/arrays & 5 copy AST walks with `uint64` effect bitmasks + 1 reverse liveness/escape walk | **~8M panel (0.20 k/L)**, **≤ 1.7M on `96`/`100` (0.48 k/L)** — **4.5×–5× cut** | Demanded only on contracted / `$explicit_copies` / `$no_hidden_costs` / owned functions. |
| 8. Fused default backend (direct-target lower + fused opt/liveness + fast regalloc + direct-ptr x64 + fast DWARF) | `lower + opt + codegen + other` (`407.1M` = 10.02 k/L; `96` = 40.5M / 11.45 k/L) | `96` `opt+codegen+other` = **22.02M** (6.23 k/L); `lower` = 18.5M (5.22 k/L) | `proto_backend` hardware floor on `96` (`opt+liveness+regalloc+x64+ELF`): **3.98M (1.13 k/L)**! Direct-target lower kills 91% of 45k dead `mov`s (~25% smaller pre-opt IR). | **~95M panel (2.35 k/L total)**: `lower` 1.00 + `opt` 0.45 + `codegen` 0.78 + `other` 0.15 — **4.3× cut** | Loop functions keep SRA, CSE, LICM, fast_inline, and vectorization so all 32 `bench --baseline` kernels stay within ≤ 3% (target ≤ 0%). |

**Closed / low-ceiling ideas (do not pursue):**
- **Never-free bump allocator for `__alloc`**: measured −0.30% slower in `codegen-gap-round1` (free lists beat bump allocation). Instead, eliminate the 323k allocations via reusable arenas/pools and value/SoA layouts.
- **Generic body deduplication/sharing**: bounded at ≤ 3.39% on 99 and ≤ 0.08% on 100 in `structural-round2`.
- **Generic dominance bounds-check elimination on host IR**: GCC only removes 8% of dynamic bounds branches (~0.4% ceiling in `codegen-gap-round1`).

## The 1,000,000 lines/s budget

### Per-phase panel budget (k instructions / processed line)

| Phase | Today Panel | Today Worst | Target Panel | Target Worst | Cut |
|---|---:|---:|---:|---:|---:|
| `load` | 4.46 | 5.74 (`96`) | **1.05** | **1.25** (`96`) | 4.2× |
| `check` | 6.45 | 7.33 (`95`) | **1.55** | **1.70** (`95`) | 4.2× |
| `facts` | 2.86 | 6.26 (`99`) | **0.45** | **0.80** (`99`) | 6.4× |
| `effects + ownership` | 0.83 | 2.48 (`96`) | **0.20** | **0.48** (`96`/`100`) | 4.2× |
| `lower` | 4.34 | 5.22 (`96`) | **1.00** | **1.10** (`95`/`97`) | 4.3× |
| `optimize` | 2.09 | 2.59 (`97`) | **0.45** | **0.52** (`97`/`99`) | 4.6× |
| `codegen` | 3.10 | 3.89 (`97`) | **0.78** | **0.90** (`97`/`95`) | 4.0× |
| `other` | 0.48 | 0.57 (`99`) | **0.15** | **0.18** (`96`/`100`) | 3.2× |
| **Total (uninstrumented)** | **24.27** | **28.83 (`99`)** | **5.60** | **≤ 6.18 (all 7)** | **4.3×** |

### Per-flagship budget verification (target k/L and projected lines/s)

| Flagship | `load` | `check` | `facts` | `eff+own` | `lower` | `opt` | `codegen` | `other` | **Target k/L** | **Projected l/s** |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `95_kv_store` | 1.05 | 1.70 | 0.60 | 0.08 | 1.10 | 0.50 | 0.88 | 0.16 | **6.07** | **1,038k** |
| `96_ct_crypto` | 1.25 | 1.55 | 0.45 | 0.48 | 1.08 | 0.45 | 0.76 | 0.18 | **6.20** | **1,016k** |
| `97_notes_service` | 1.02 | 1.65 | 0.48 | 0.12 | 1.10 | 0.52 | 0.90 | 0.16 | **5.95** | **1,059k** |
| `98_notes_listen` | 0.92 | 1.50 | 0.25 | 0.15 | 0.72 | 0.32 | 0.56 | 0.12 | **4.54** | **1,388k** |
| `99_dewy_frontend` | 1.05 | 1.52 | 0.80 | 0.12 | 1.05 | 0.52 | 0.80 | 0.17 | **6.03** | **1,045k** |
| `100_rtos_kernel` | 1.22 | 1.45 | 0.52 | 0.48 | 0.96 | 0.35 | 0.66 | 0.18 | **5.82** | **1,082k** |
| `101_ml_training` | 1.18 | 1.30 | 0.25 | 0.08 | 0.92 | 0.42 | 0.66 | 0.17 | **4.98** | **1,265k** |
| **Panel average** | **1.05** | **1.54** | **0.45** | **0.19** | **0.95** | **0.43** | **0.73** | **0.15** | **5.49** | **1,148k** |

## Chosen architecture (pure-Dewy trajectory)

All new compiler code is written in Dewy. Where a slice replaces `.jo` storage (`ast.jo`, `types.jo`, `ir.jo`, `facts.jo`, `lex.jo`, `lower.jo`), the replacement lives in Dewy, removing double-pointer host-bridge indirections and advancing self-hosting.

1. **Reusable low-level compiler storage facilities (`compiler/arena_vec.dewy`)**: Non-COW `RawVec<T>` (raw pointer/len/cap, O(1) `clear` via `len = 0`, single-check bump push), `GenSet` (generation-stamped `int32[]` replacing `{int: bool}` dicts), and a shared `list_scratch` stack for building child lists without temporary heap arrays.
2. **Host codegen upgrades (helps compiler and all user Dewy code)**:
   - Restrict compare-branch JCC padding to loops (`x_loop_depth > 0`); fast byte-table `nop_pad`.
   - Release inliner: allow cold-call leaves (`*_slow`, `__arr_push_slot`, `__arr_grow_more`, `__arr_clone`, `ice`) and tune thresholds so 5–15 line Dewy helpers (`mk`, `vc`, `e_mov`, `e_bin`, `k_vreg`, `xl_finish`, `op_rm64`, `ld`, `st`) inline cleanly.
   - Compact RC drop helpers: single `__mt_active` branch at helper entry, `decq (%reg)` in place of `mov; cmp 1; jle; lea -1; mov`, single compare against 1.
   - Split-range / local register caching in `allocate_release` and scoped zeroing of managed locals (closing the 14.1% stack traffic gap).
3. **Compact SoA/split AST & inline `TypeFlags` (`compiler/ast_store.dewy`, `compiler/type_flags.dewy`)**:
   - Hot 32-byte `NodeHot` (or parallel SoA arrays for `kind`, `flags`, `pos`, `a`, `b`, `c`, `d`, `type`, `sym`, `aux`) + cold side-table for `ival`/`fval`/`sval`/`list2`/`aux2`/`mod`.
   - Precomputed `TypeFlags` bitmask on `TypeInfo` (`vc`, `vt`, `managed`, `shared`, `int`, `float`, `signed`, `agg`, `refined`, `has_var`, `mem_mode`), replacing `vc()` (216k calls), `is_managed()` (83k calls), `is_shared()` (60k calls), `vt_of()`, `mem_mode()`.
4. **Single-pass SIMD frontend + tighter lazy std prelude**:
   - Extend `std_optional_file` index (`tools/compiler/gen_prelude_index.py`) to `files.jo`, `json.jo`, `text.jo`, `dewy_sets.jo`, `dewy_ranges.jo`, `console.jo`, `process.jo` and avoid false-loading `story.jo` on method names (`next`, `save`, `load`).
   - AVX2 fused `scan_source` + lazy `line_starts` (32 B/iter `pcmpeqb` newline & unit boundary scan).
   - Compact 8-byte token streaming (`lex`, `dx_lex`) with inline FNV-1a open-addressed interning, pre-interned keyword IDs (`id < KW_MAX`), single-byte dispatch tables, and iterative Pratt expression parsing writing directly into compact AST storage.
5. **Fast-path checker**:
   - Monomorphic direct-call fast path in `resolve_fn_call` / `check_call` (direct `DeclInfo.mono_inst`, read args directly from `lists` without `node_run_of` or redundant `set_list`, inline exact-type check).
   - Single `fn_feature_mask` + `.jo` fast path bypassing unused Dewy hooks (rational, juxtapose, units, narrowing, refinement, exactness, concurrency, game).
   - Demand-driven zonking (skip `xz_walk` when `fn_created_tvar == false`).
6. **Two-tier `facts` + Trailed mutable `FactState` + Bitset `effects`/`ownership`**:
   - **Tier 1**: O(N) local dominance/range prover during or right before `facts_finalize` (tracks `lo`, `hi`, `lt_len`, fixed-array bounds in flat local arrays); marks `NF_INBOUNDS`/`exact_decided` directly and skips `fact_slice_prepare_fast` + `FactState` whenever all obligations in a function are discharged.
   - **Tier 2**: Single mutable global `FactState` workspace with checkpoint/undo trail (eliminates 21.4k `__arr_clone` + 31.6k `__h_drop_2388`; `fact_join` diffs only trail-mutated bindings; fast 1-hop/2-hop difference check before BFS; cursor-loop summaries and converged loop transfer reuse).
   - **Effects & ownership**: `uint64` summary bitmasks + sparse place list; fused single reverse walk for `copy_live`/`copy_escapes`/`copy_deferred`/`copy_mentions`.
7. **Fused default-mode backend**:
   - Direct-target lowering (pass destination vreg + on-the-fly constant/copy fold, killing >80% of 45k dead `mov`s), flat reusable `IrBuf` with inline bump `emit`, lazy `begin_fn` clear, precomputed AST flags replacing `uq_scan`/`may_write_root` re-walks.
   - **Straight-line functions (70% of fns)**: fuse `opt_fast_straight` + `backend_analyze` into ONE pass; O(1) `fast_inline_into` skip; fast direct/linear-scan allocation without scanning empty positions.
   - **Loop functions (30% of fns)**: keep `o_sra` (gated on in-loop small slot), `fl_pass2` CSE/strength-reduction, `o_licm`, `fast_vectorize` so every `bench` kernel keeps full speed; fuse `fl_pass4_compact` + `backend_analyze` into ONE pass.
   - **Direct-pointer x86-64 encoder + fast DWARF/line-table**: reserve `nc * 16 + 128` once per function, hold raw `xp: ptr<uint8>` cursor, inline `emit_ins` dispatch, direct-buffer LEB128/ELF emission.

## Owned files and landing order

Each slice lands independently on `master` via `~/dev/tmp/coord/land.sh <branch> --full` and passes: focused tests, quick suite, full suite, `--bootstrap`, fixed point, `speed`, `bench --baseline`, and `redfox` cycle check where codegen/layout changes.

| Slice | Scope & expected gain | Owned files |
|---|---|---|
| **Slice 1** | **Host codegen, padding, inlining & drop helpers**: fix non-loop `cmp_branch_pad` + fast `nop_pad`; release cold-leaf inlining & thresholds; compact RC drop helpers (single `__mt_active`, `decq`); lazy `begin_fn` clears. **Target: ~260k → ~315k l/s (−17%), self-build −18%.** | `compiler/x64_emit.dewy`, `compiler/x64_encode.dewy`, `compiler/inline_ops.dewy`, `compiler/inline.jo`, `compiler/lower_storage.dewy`, `compiler/lower_helpers.dewy`, `compiler/lower_functions.dewy` |
| **Slice 2** | **TypeFlags, lazy std prelude, AVX2 scan/lines & checker direct-call fast path**: inline `TypeFlags` killing `vc()`/`is_managed()`/`is_shared()`; extend `std_optional_file` + fix `story.jo` trigger; AVX2 fused `scan_source`/`line_starts`; zero-alloc mono `resolve_fn_call` + demand `xz_walk` + `.jo` checker fast path. **Target: ~315k → ~440k l/s.** | `compiler/checker_types.dewy`, `compiler/type_ops.dewy`, `compiler/lower_storage.dewy`, `compiler/prelude.jo`, `compiler/prelude_ops.dewy`, `tools/compiler/gen_prelude_index.py`, `compiler/scan_index.dewy`, `compiler/line_table.dewy`, `compiler/checker_call_resolve.dewy`, `compiler/checker_expr.dewy`, `compiler/checker_literals.dewy`, `compiler/checker_blocks.dewy` |
| **Slice 3** | **Fused default backend & direct-pointer x86-64 encoder**: direct-target lowering (kill dead `mov`s); compact `IrBuf` + inline `emit`; fuse `opt_fast_straight`+`backend_analyze` and `fl_pass4_compact`+`backend_analyze`; interval-list `allocate`; direct-pointer `x64_encode` + inlined `emit_ins`; fast `dwarf_format`/`native_debug`/`x64_patch_module`. **Target: ~440k → ~640k l/s.** | `compiler/ir_types.dewy`, `compiler/ir_builders.dewy`, `compiler/lower_group.dewy`, `compiler/lower_analysis.dewy`, `compiler/opt_core.dewy`, `compiler/opt_rewrite.dewy`, `compiler/opt_sra.dewy`, `compiler/backend_analysis.dewy`, `compiler/x64_allocate.dewy`, `compiler/x64_emit.dewy`, `compiler/x64_encode.dewy`, `compiler/dwarf_format.dewy`, `compiler/native_debug.dewy` |
| **Slice 4** | **Two-tier `facts` + Trailed mutable `FactState` + Bitset `effects`/`ownership`**: Tier-1 O(N) local bounds/exact prover; trailed mutable `FactState` workspace (zero COW clone/drop, delta `fact_join`, fast 1/2-hop `fact_distance`); cursor-loop summaries & converged loop reuse; fix `exact_*` huge array resizes; `uint64` effect bitmasks + single-walk `copy_ops`. **Target: ~640k → ~780k l/s (99 > 750k, 96/100 > 750k).** | `compiler/facts_lifecycle.dewy`, `compiler/facts_slice_prep.dewy`, `compiler/facts_joins.dewy`, `compiler/facts_loops.dewy`, `compiler/facts_capture.dewy`, `compiler/facts_compare.dewy`, `compiler/facts_index_writes.dewy`, `compiler/facts_value_queries.dewy`, `compiler/exact_preparation.dewy`, `compiler/exact_count_bounds.dewy`, `compiler/exact_static_widths.dewy`, `compiler/effect_control.dewy`, `compiler/effect_scan.dewy`, `compiler/isolation_ops.dewy`, `compiler/copy_ops.dewy` |
| **Slice 5** | **Compact 32B/SoA pure-Dewy AST, `RawVec` arenas & streaming SIMD lex/parse**: `compiler/arena_vec.dewy`; replace `ast.jo` with compact 32B/SoA `compiler/ast_store.dewy`; streaming/8B-token `lexer_scan.dewy` + `dewy_lexer.dewy` with inline FNV-1a interning & keyword IDs; iterative Pratt `parser_expr.dewy` + `dewy_reader.dewy` writing directly to compact AST. **Target: ~780k → ~960k l/s.** | `compiler/arena_vec.dewy`, `compiler/ast_store.dewy`, `compiler/node_store.dewy`, `compiler/intern.dewy`, `compiler/lexer_scan.dewy`, `compiler/dewy_lexer.dewy`, `compiler/parser_expr.dewy`, `compiler/dewy_reader.dewy`, `compiler/ast.jo` (retired/thin shim) |
| **Slice 6** | **Final host codegen & worst-flagship push to ≥ 1.00M on every flagship**: split-range/local-cache `allocate_release` + scoped managed zeroing; eliminate remaining Jo-bridge double indirections (`check.jo`/`types.jo`/`ir.jo` → Dewy); profile-driven tightening on whichever flagship trails 1.00M (likely 96, 95, or 99). **Target: ≥ 1,000k l/s on all 7 flagships (panel ≥ 1,100k l/s), self-build ≤ 4.0G.** | `compiler/x64_allocate.dewy`, `compiler/lower_functions.dewy`, remaining hot `.jo` state bridges, tail profiles |

## Unknowns and risks

1. **Worst-flagship margin on 96 and 99**: 96 has high fixed/library ratio (489 KB source for 3,536 processed lines) plus `$explicit_copies` + effects; 99 has 19 cursor `while` loops + 192 `if`s driving `facts`. Both sit near 6.0–6.2 k/L in the budget (~2–5% headroom). If either lands at 6.5–7.0 k/L after Slices 1–5, Slice 6 will need an extra pass (e.g., deeper host codegen or direct AST→x64 fast path for trivial library leaf functions).
2. **Skylake JCC erratum wall-clock check**: Dropping compare-branch padding outside loops saves ~2.5% retired instructions and won cycles on `redfox` in `codegen-gap-round1`, but every loop-alignment or encoding change must be cycle-checked on `redfox` via `~/dev/tmp/coord/bench.sh` and must pass `bench --baseline`.
3. **Bootstrap seed compatibility**: `tools/compiler/build.py` still builds stage1 from `bootstrap-seed/` (`--bootstrap`). Any migration of `.jo` storage (`ast.jo`, `ir.jo`, `types.jo`) to Dewy must preserve clean bootstrap staging and pass `python3 -m tools.core --bootstrap test` and the fixed-point check on every landing.
4. **Parallel master churn**: Other agents continue landing proof rules, library changes, and features. Slices 1–3 touch mostly backend/codegen/prelude/storage infrastructure with minimal overlap; Slice 4 (`facts`) and Slice 5 (`ast_store`) require frequent rebases and tight coordination on shared interfaces.
5. **No language surface changes expected**: Everything in this plan is internal representation, analysis, and code generation. Any unexpected library or surface question will be surfaced to David rather than changed silently.
