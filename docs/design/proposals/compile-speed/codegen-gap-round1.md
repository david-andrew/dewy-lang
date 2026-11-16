# Codegen gap, round 1: where the compiler's own code loses to GCC

## Decision proposed

Treat the compiler's generated-code quality as a planned series of backend
projects, ranked below, instead of more single-pass pilots. Re-measured at
master `ef44d895b`, GCC O3+LTO compiling the same release host IR executes
**28.3% fewer instructions on the flagship panel and 28.9% fewer on the
self-build**, evenly across every compiler phase (25–43%). That alone lifts the
panel from 146.9k to 204.9k lines/s but leaves 99 at 147k and 95, 96 and 100
at 184–186k. GCC plus proven array bounds reaches 200k on six of seven
flagships; 99 still needs about 18% less compiler work, which only its own
facts proofs (24% of its compile) are large enough to supply. 84% of the gap
remains with GCC's extra inlining, interprocedural, value-numbering and loop
optimizations all switched off: it is the plain scalar backend (allocation,
selection, local cleanup) plus padding.

The localized items below add up to 12–20%, which does not reach 200k on
their own. The first is ready: dropping compare-branch padding outside loops
cut instructions 2.47% and cycles on every flagship on redfox. No item has
both a measured bound of at least 3% and a general fix that fits a
three-hour pilot, so this round stops at the plan.

This is a measurement and plan. It changes no language surface and no
compiler source.

## Scope and method

- Base `ef44d895b` (origin/master, 2026-11-15). Desktop i7-6700 (hostname
  `redfox`, not the quiet laptop), retired user instructions from hardware
  counters, one emission worker, default builds of the inputs. No desktop
  wall-clock numbers.
- `python3 -m tools.core speed --base origin/master` on the unchanged tree:
  flagships 146,730 lines/s; self-build 14.028G.
- **Native host**: the compiler's own fixed point (three stages, the last two
  byte-identical), built in release mode as `compiler/main.jo` declares.
- **GCC host**: the scalar `--host-ir` of that compiler, translated to C by
  the retired translator (`8dc562838^`, scratch only), with the corrected
  `findb` scan, the native bulk-copy and comparison policy, and C's null and
  overflow assumptions disabled (`-fno-delete-null-pointer-checks
  -fno-isolate-erroneous-paths-dereference -fno-strict-overflow`). The
  translator needed two updates for the current IR: intrinsic 9 (CPU
  features) and the new AVX2 `findbyte` width flag, which it had misread as
  "invert". Every GCC host produces byte-identical output to the native host
  on the seven flagships, dunes and the self-build.
- **Native oracles** (one-line scratch patches): a patched compiler builds the
  *unmodified* compiler source, so only the host's own code changes and its
  output stays byte-identical (checked on all nine inputs).
- **Attribution**: Callgrind with per-instruction counts over the seven
  flagships for the native and GCC hosts. REP iterations are folded to one
  instruction per execution; the folded totals match the hardware counts
  (1.7701G vs 1.7702G native, 1.2690G vs 1.2690G GCC). Classes are physical
  instruction kinds; their differences are signed workload shifts, not
  independent removal budgets.

## The gap

| Host | Panel G | vs native | Self-build G | 95 | 96 | 97 | 98 | 99 | 100 | 101 | Panel lines/s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| native | 1.7702 | — | 14.036 | 132k | 133k | 140k | 197k | 105k | 134k | 179k | 146.9k |
| native, no bounds checks (oracle) | 1.6815 | −5.01% | 13.389 | 139k | 140k | 147k | 207k | 112k | 141k | 186k | 154.6k |
| GCC O3+LTO | 1.2690 | −28.31% | 9.987 | 184k | 185k | 195k | 275k | 147k | 186k | 248k | 204.9k |
| GCC O3+LTO, bounds assumed (oracle) | 1.1464 | −35.24% | 9.073 | 204k | 206k | 215k | 304k | 164k | 208k | 270k | 226.8k |
| GCC, no extra inlining | 1.3270 | −25.04% | 10.388 | 176k | 176k | 187k | 263k | 141k | 178k | 237k | 195.9k |
| GCC, scalar backend only | 1.3502 | −23.73% | 10.503 | 173k | 173k | 184k | 259k | 138k | 175k | 233k | 192.6k |

"No extra inlining" marks every translated function `noinline`, keeping only
the inlining the native release optimizer already did. "Scalar backend only"
also disables GCC's IPA, value numbering/PRE/dominator and loop
optimizations (`flags.json` of the Nov 4 attribution).

**84% of the gap is the plain scalar backend.** With no extra inlining, no
IPA, no value numbering, PRE or dominator optimizations and no loop
optimizations, GCC still executes 23.7% fewer instructions (25.2% on the
self-build). Inlining is worth 3.3 points and the rest of GCC's mid-level
optimizer together about 1.3. What remains is register allocation,
instruction selection, local scalar cleanup (dead stores, combining,
known-bits propagation) and the 3.5 points of padding GCC never emits.

By phase (panel, million instructions, `build --time`):

| Phase | Native | GCC | Change |
|---|---:|---:|---:|
| load | 314.7 | 233.9 | −25.7% |
| check | 389.8 | 279.7 | −28.2% |
| facts | 240.7 | 176.7 | −26.6% |
| effects | 53.5 | 37.2 | −30.4% |
| ownership | 26.0 | 14.9 | −42.5% |
| lower | 275.4 | 178.9 | −35.0% |
| optimize | 241.5 | 175.3 | −27.4% |
| codegen | 213.3 | 158.7 | −25.6% |

The gap is a property of the generated code, not of one phase.

### By code-generation category

Points are percent of the native panel (1,770M). "Oracle" is a native
deletion bound measured by removing exactly that work from the host.

| Category | Native share | Native − GCC | Native oracle | What the native code does |
|---|---:|---:|---:|---|
| Scalar stack traffic (spills, reloads, stack-resident locals; callee saves excluded) | 9.7% | **+6.46** | — | One location per vreg for the whole function: a value spilled anywhere lives in memory everywhere. 172M scalar stack loads/stores vs GCC's 58M; only 26M of them sit next to a call (GCC 17M), so this is pressure in large functions, not call clobbers |
| Entry zeroing of managed locals | 2.6% | +2.43 | (deletion breaks the host: some zeroing is needed) | `lower_functions.dewy` zeroes every managed local at function entry (`e_zero` for aggregates, `mov v,0` for scalars) so exit cleanup can drop it. In a large function every call zeroes every arm's locals (`fact_capture_value`: 30 KB frame, 0.6% of the panel), and the entry definition stretches each local's live range to the whole function. 1.66% zero stores (1.00% at function-entry frequency) plus 0.9% setup; the GCC host, given the same IR, executes 0.14% |
| Compare and branch | 32.9% | +6.34 | bounds 5.01 | Zero tests after loads and `setcc` (+1.92), memory-operand compares (+1.38), branch-on-boolean (+0.53); bounds checks are below |
| Bounds checks | 5.0% | (inside the rows above) | **5.01** (null half 1.70) | Release: `test arr; je fail; cmp idx,[arr+8]; jae fail`. GCC keeps 92% of the dynamic check branches (28.6M → 26.4M): generic redundancy elimination removes little. Assuming them in-bounds is worth a further **6.93 pts** under GCC |
| Executed padding NOPs | 3.8% | +3.50 | **3.54** (outside loops 2.36, loop entries 0.78) | JCC-boundary padding (`cmp_branch_pad`), mostly in straight-line code; loop-alignment pads sit on the entry path and run once per loop entry |
| Extension / normalization | 4.7% | +3.31 | — | `movzbl` after `setcc` (1.03), `movslq`/`movzbq` of registers (1.01): narrow values re-normalized at each use |
| Register moves | 8.0% | +3.05 | — | Copies around calls and two-operand forms; overlaps the stack row |
| Constant materialization | 3.4% | +2.53 | — | `mov $0,r` before a compare or store (1.9), where GCC uses an immediate or `xor` |
| Other loads and stores | 12.3% | +1.77 | — | Field and global reloads that GCC's value numbering keeps in registers (its value-numbering ablation was 1.25 pts on Nov 4); aggregate copies through stack temporaries are in the stack row (+0.28) |
| Frames | 3.3% | +1.05 (`rsp` adjust); callee saves −0.58 | — | Nearly every function builds a frame; GCC saves *more* callee registers (push/pop), so saves are not the gap |
| Calls and returns (inlining) | 2.9% | +1.03 | GCC ablation **3.27** | 25.6M native calls vs 16.7M GCC. GCC inlines whole hot runtime helpers and accessors the native release inliner keeps out of line (`__arr_new_raw` 0.72%, `__map_add` 0.53%, `has` 0.52%, `__tid` 0.51%, `ow_push` 0.38%) |
| Runtime thread-state lookup | ~1.2% | (inlined by GCC, still computed) | **1.22** | `__ts()` derives the thread state from the stack pointer on every allocation, free and refcount: a `__tid` call (8 instructions) plus a callee-saved register around it |
| Allocator policy | 4.1% alloc/free | +0.75 | **−0.30** (bump, never free) | Free lists already beat a bump allocator; not a lever |
| LEA, push/pop, ALU | | −3.1 | | GCC spends these to save moves and saves elsewhere |

Two oracles close ideas outright: never-free bump allocation is 0.30%
*slower*, and GCC's generic redundancy elimination removes only 8% of the
dynamic bounds-check branches, so a dominance-based redundant-check pass is
bounded near 0.4%.

## Is the metric creating the shortfall?

- **Lines.** The speed tool's line accounting was audited on 10-26 (zero
  duplicate or negative coverage, generic instances charged once). Nothing
  here changes the denominators; they are reused unchanged.
- **Executed padding.** 3.54% of the counted instructions are NOPs whose only
  purpose is cycles (JCC-erratum and loop alignment on Skylake-family cores,
  which includes the reference i7-6700 and redfox's i5-8350U). The
  instruction proxy charges them as full work, so a change that removes them
  must also show cycles. For the 2.36% outside loops it does: removing them
  on redfox lowered self-build cycles 2.24% and flagship cycles 0.6–3.1%
  (item 1). There the metric and the machine agree.
- **Facts on 99 are real work.** 99's own 982 lines spend 73.1M of its 305M
  instructions in facts (14,975 per processed line across the program). That
  is proof of no-trap obligations in its lexer and parser, not an accounting
  artifact.

The shortfall is therefore not a metric effect.

## Ranked plan

Ranking: measured and achievable gain first (a measured change beats an
oracle, an oracle beats a GCC reference), then how general and safe the fix
is, then cost. "User programs" uses the 28 runtime kernels (default builds,
desktop instructions) where an oracle exists.

### 1. No padding outside loops (−2.33% instructions; flagship cycles down 0.6–3.1% in the first probe)

- **Evidence.** `cmp_branch_pad` pads compare-and-branch pairs away from
  32-byte boundaries (the Skylake JCC erratum) mostly in straight-line code,
  where each pad runs once per call. Deleting only those pads (one line,
  `if x_loop_depth =? 0 {return}`, mirrored in the twin; scratch branch
  `wt/speeddesign-padprobe`) was measured with `speed --cycles --runs 15` on
  redfox (CPU 2, performance governor, load 1.1–2.5), both compilers at their
  own fixed points:

  | Item | Cycles | Instructions |
  |---|---:|---:|
  | self-build | −2.24% | −2.29% |
  | 95_kv_store | −1.82% | −2.50% |
  | 96_ct_crypto | −0.58% | −2.40% |
  | 97_notes_service | −3.14% | −2.47% |
  | 98_notes_listen | −1.04% | −2.47% |
  | 99_dewy_frontend | −1.05% | −2.48% |
  | 100_rtos_kernel | −0.85% | −2.46% |
  | 101_ml_training | −0.71% | −2.35% |
  | synthetic-22k / game / 84 / hello | +0.28 / +0.50 / +2.22 / −0.07% | −2.45 / −2.36 / −2.31 / −2.20% |

  Medians of 15 interleaved runs; the three small cycle increases sit inside
  wide run ranges (synthetic 0.546–0.868G, 84 0.068–0.109G). Outside loops the
  padding costs the compiler cycles rather than buying them.
  The same probe **regressed kernels** (redfox `bench --runs 9`, base then
  candidate; the C column moved −2.5% to +4.2% between the two runs, so
  only large changes count): string_equal +43% default / +41% release,
  byte_find +9.5% / +28%, arena +2.9% / +13.7%. The cause is in the probe,
  not the idea: the intrinsic emitters (`memeq`/`streq`, `findbyte`, `findb`,
  `scanbytes`) emit their own machine-code loops while the IR loop depth is
  0 (`emit_memeq` even resets it to 0 on purpose so its branches stay
  padded), so the probe stripped the padding from exactly the loops that
  need it. The refined probe keeps padding inside those emitters (a
  machine-loop counter around their dispatch) and still saves 2.33% of panel
  instructions (desktop oracle; 2.36% before).
  Its redfox kernel timing and panel cycles are not yet measured; they are
  the first gate of the backend stream.
- **Design.** Keep JCC-boundary padding inside loops, IR loops and the
  intrinsics' own machine-code loops alike, where repetition makes the
  uop-cache effect matter, and drop it in straight-line code. Loop-entry
  alignment stays: its pads are mostly single NOPs (0.78% of instructions);
  jumping over the longer ones would save only 0.29%. O(1) per branch.
- **Bound.** 2.36% of the native panel (oracle), 2.47% in the fixed-point
  speed run (the compiler's own output loses the pads too).
- **Risk.** Low code risk, real layout risk: the first probe's kernel
  regressions show that any padding change is accepted only on kernel
  timing as well as panel cycles.
- **User programs.** Instructions fall in straight-line code only; kernels'
  loops keep their layout.

### 2. Register allocation on split live ranges (stack traffic, +6.46 pts vs GCC)

- **Evidence.** Scalar stack loads and stores excluding callee saves: 95.3M +
  76.8M native vs 33.5M + 24.3M GCC. The rows for register moves (+3.05) and
  constants (+2.53) overlap it: a better allocator rematerializes constants
  instead of spilling them and needs fewer shuffles.
- **Design.** Keep the existing loop-weighted costs, but allocate *live
  ranges*, not whole-function vreg intervals: split each interval where its
  pressure changes (block and loop boundaries, call sites), assign each piece
  its own location, insert moves only at split edges, and place spill stores
  at the definition outside loops (linear scan with interval splitting,
  Wimmer–Franz; or second-chance binpacking). Constants and frame/global
  addresses are never spilled: they are rematerialized at the use. Work is
  O(n log n) in IR instructions per emitted function; no cross-function
  analysis.
- **Bound.** The GCC difference is an achieved reference, not a proof. The
  Oct 23 regional pilot (whole-region assignment, no splitting) recovered
  1.58% of a 6.02% spill exposure. Only 26M of the 172M native stack accesses
  sit next to a call, so the remaining traffic is pressure inside large
  functions, which splitting addresses and region assignment did not.
  Item 4 shortens many of these ranges first. Plausible 2.5–4%, counted twice
  through the self-build.
- **Risk.** High: the allocator, frame layout and unwind rows all move;
  needs a new differential test over the IR corpus and kernel cycle checks.
  Multi-day; not a pilot.
- **User programs.** Yes, everywhere; largest in call-heavy kernels
  (callbacks, helpers, records).

### 3. Bounds checks: fault for null, prove for length (oracle 5.01%; 6.93 more under GCC)

- **Null half (≤1.70% panel, ≤1.65% self).** Implicit null checks. In release
  and default builds on x64 and arm64 (Linux, macOS, Windows), lower an index
  check to `cmp idx,[arr+8]; jae fail` with no null test: a null array faults
  reading address 8, which is never mapped (Linux `mmap_min_addr`, macOS
  `__PAGEZERO`, Windows' reserved low 64 KiB). The emitter records each such
  load's address with its check location and index register in a sorted table
  beside the line table, only for functions that keep a check. The runtime's
  fault handler (alternate signal stack; a vectored handler on Windows)
  binary-searches the faulting PC; a hit calls `__panic_bounds(idx, 0, loc)`
  exactly as today, a miss keeps today's crash report. Compile cost O(1) per
  check; O(log n) only when a program faults. wasm keeps explicit tests
  (address 8 is readable there), as do debug builds (debuggers stop on the
  first-chance fault). Default builds benefit too: their check is
  `test; cmov; load; cmp; jae` today, two instructions after. Kernels: no
  change measured, since the oracle only touched the release path.
- **Length half (≤3.31%).** Not a redundancy problem (GCC removes 8% of check
  branches). The checks need proofs. Two existing mechanisms already remove
  them: the facts engine's in-bounds flag, and Dewy leaves indexing through
  `.ptr[...]` under `$unsafe`. The general fix is to make the compiler's own
  Dewy code prove its indexes the way the no-traps work asks of user code
  (lengths tied to fields, indices from `[0..n)` loops and lookups), which
  is the self-hosting and no-traps streams' work rather than a backend pass.
  Under GCC-quality codegen the proven checks are worth 6.93 pts, because
  inlining and loop optimization then see through them.
- **User programs.** Length proofs: managed_params −26.3%, method_params
  −26.3%, arrays −7.5%, name_table −5.8%, string_search −5.2%, text −3.5%,
  graph −2.3%, shifted_arrays −1.5% (oracle with every check removed).

### 4. Zero managed locals where their scope begins (exposure 2.57%; GCC removes 2.43)

- **Evidence.** `lower_functions.dewy` zeroes every managed local at
  function entry so that exit cleanup and the first drop-assignment see null.
  Cleanup itself is already scoped (`scope_locals`, `emit_scope_exit`). In
  large functions every call pays for every arm's locals:
  `fact_capture_value` (a 1,400-line Sloppy function) has a 30 KB frame and
  spends 0.58% of the panel zeroing it (278 instructions per call). Stack
  zero stores are 1.66% of the panel (1.00% at function-entry frequency)
  plus 0.9% of setup; GCC, given the same IR, executes 0.14%. Deleting the
  entry zeroing outright breaks the host, so some of it is needed and no
  deletion oracle exists.
- **Design.** Emit a local's zeroing at the entry of the scope that declares
  it (the scope whose `scope_locals` receives it), not at function entry; a
  loop-body scope re-zeroes after its exit cleanup, as now. Skip it entirely
  when the declaration initializes the local without dropping (a first
  binding) and dominates every cleanup and read in that scope, which the
  lowering already knows when it registers the local. O(locals); no dataflow
  pass. It also shortens every such local's live range from the whole
  function to its scope, relieving item 2.
- **Bound.** At most the 2.57% exposure; the scoped part of
  `fact_capture_value` alone is about 0.6%.
- **Risk.** Medium: Sloppy's function-scoped assignment-declared locals keep
  entry zeroing; every drop path must still see null or a live value
  (ownership and leak tests, `same_output`).
- **User programs.** Yes for functions with many owned locals in branches
  (match dispatch over records, parsers).

### 5. Selection and normalization (extension +3.31, constants +2.53, compares +3.3)

- **Design.** One forward pass per emitted function that records, per vreg,
  its known upper bits (zero- or sign-extended, from loads, `setcc` and
  narrowing operations), iterated to a fixed point over loop back edges:
  O(n · loop depth). The emitter then skips normalizations whose bits are
  already known, branches on the flags of the defining compare instead of a
  materialized boolean when every use is a branch or a select, and folds
  immediates and memory operands into `cmp`/`test`/stores (`cmpq $0,m`,
  `movq $imm,m`, `xor r,r`). Local peepholes over the same patterns were
  bounded at 0.67% on Nov 4; the cross-block known-bits pass is what they
  lacked (GCC's joint scalar-propagation control: 1.47 pts).
- **Bound.** 1.5–3% plausible; the class rows are exposures, not budgets.
- **Risk.** Medium: flag liveness across blocks; covered by the IR
  differential corpus.
- **User programs.** Yes (byte loops, parsers: integer_parse, case_conversion,
  text).

### 6. Thread state in the thread register (oracle 1.22% panel, 0.81% self)

- **Evidence.** An oracle runtime whose `__ts()` returns the main thread's
  state directly (valid for the single-threaded compiler; outputs identical)
  saves 1.22% of the panel. Today every call computes `__tstate + __tid() *
  89 words`, and `__tid` compares the stack pointer against the thread stack
  region (8 instructions, 1.1M calls per panel) before the caller's own
  foreign-thread test.
- **Design.** Give each thread its state pointer in the thread register: on
  x64 Linux the runtime already creates its own threads and can set the FS
  base (`arch_prctl`), on arm64 `TPIDR_EL0`; `__ts()` becomes one load. When a C
  runtime owns that register (`__c_threads`, `$extern` programs), keep today's
  stack-range lookup. O(1).
- **Risk.** Low to medium (signal handlers and foreign threads).
- **User programs.** Every allocation and refcount; allocation-heavy kernels
  (arena, dict_words, graph, name_table).

### 7. Inline the fast paths of runtime helpers (GCC inlining ablation 3.27; self 2.86)

- **Evidence.** Marking every translated function `noinline` costs GCC 3.27
  points of the native panel. The Nov 4 control that allowed only loop-free
  non-leaf bodies of 25–128 IR instructions recovered 0.51 of the then 3.53,
  so most of the gain is elsewhere: the runtime helpers and small accessors
  above, which have a short common path and a cold slow path
  (`__alloc_z` calls `__alloc_slow`, `__map_add` rehashes, `__free` handles
  large blocks).
- **Design.** Partial inlining. For a helper whose body is a short prefix
  ending in a return on the hot path, with every other path reaching a call,
  split it once into an inlinable fast path and an outlined remainder
  (`@noinline` already marks several slow paths by hand). Call sites inline
  the fast path under the existing size budget; the remainder is an ordinary
  call. Split decisions are per helper and cached (O(body) once); expansion
  is O(fast path) per call site, only at sites the release inliner already
  visits.
- **Bound.** Below the 3.27 ablation, which also includes inlining that
  plain size limits forbid. The helpers' entry overhead (call, frame, callee
  saves; 12 of `__alloc_z`'s 52 instructions per call) suggests 1–2%.
- **Risk.** Low to medium: code growth in the self-build's emit phase must be
  paid back (gate on the self-build row).
- **User programs.** Yes: allocation, dictionary and array growth in every
  kernel that allocates (dict_words, graph, name_table, arena).

### Closed by this round

- **Allocator policy:** never-free bump allocation measures +0.30% (worse).
- **Redundant bounds-check elimination:** ≤0.4% (GCC's dominator, value
  numbering and range passes remove 8% of dynamic check branches).
- **Callee saves:** GCC executes 10% *more* save/restore traffic; shrink-
  wrapping stays closed at its 1.64% ceiling.

## Reaching 200k on every flagship

Required instruction cut per flagship for 200k (lines × 31.5k):
95 −34.0%, 96 −33.7%, 97 −30.0%, 98 −1.5%, 99 −47.3%, 100 −33.1%, 101 −10.7%.

| Flagship | Native | Plan, low (−12%) | Plan, high (−20%) | GCC scalar backend | GCC parity | GCC + proven bounds |
|---|---:|---:|---:|---:|---:|---:|
| 95_kv_store | 132k | 150k | 166k | 173k | 184k | 204k |
| 96_ct_crypto | 133k | 150k | 166k | 173k | 185k | 206k |
| 97_notes_service | 140k | 159k | 176k | 184k | 195k | 215k |
| 98_notes_listen | 197k | 223k | 247k | 259k | 275k | 304k |
| 99_dewy_frontend | 105k | 120k | 132k | 138k | 147k | 164k |
| 100_rtos_kernel | 134k | 152k | 168k | 175k | 186k | 208k |
| 101_ml_training | 179k | 202k | 224k | 233k | 248k | 270k |
| panel | 146.9k | 167k | 184k | 192.6k | 204.9k | 226.8k |

"Plan, low/high" applies the items' combined estimates uniformly: low
2.4 + 2.5 + 1.7 + 1.5 + 1.5 + 1.2 + 1.0 ≈ 12%, high 2.7 + 4 + 5 + 2.4 + 3 +
1.2 + 2 ≈ 20% (items 1–7, in order; the high end assumes the compiler's
indexes prove).

Reading the table honestly:

- **The itemized plan does not reach 200k.** Even at its high end it leaves
  95, 96 and 100 at 166–168k and 99 at 132k. The items are the measured,
  localized part of the gap; GCC's scalar backend shows that roughly another
  5–10 points exist in register allocation, selection and local cleanup that
  this round could only see as class totals, not as designed passes.
- **What the goal needs, by flagship.** GCC parity plus proven bounds is
  enough for six of seven flagships. Native code therefore needs to reach
  about GCC's *scalar backend* quality (−24%) and the compiler's own indexes
  must prove (−5% now, more once inlining sees through them). That is a
  backend-generation project (items 2, 4, 5 and 7 as one allocator and
  selection redesign, not as separate pilots) plus no-traps proofs in the
  compiler's Dewy source.
- **99 needs less facts work, not better code.** At GCC parity with bounds
  proven, 99 is still at 164k. Its own facts proofs are 24% of its compile
  (73M of 305M; 14,975 instructions per processed line across the program);
  halving them plus about 6% elsewhere is what 200k requires. That belongs to
  the facts stream (proof work proportional to obligations), with 99 as its
  target workload.
- **Padding is already accounted.** Of GCC's 28.3%, 3.5 points are NOPs it
  never emits; item 1 recovers the 2.4 of them that redfox shows cost cycles,
  and the loop padding that may buy cycles stays.

## Recommendation and next stream

No pilot ran this round. The only item with a native bound of at least 3%
and a general fix is bounds checks, whose achievable codegen half (implicit
null checks) is 1.70%; the allocator (item 2) is a multi-day redesign
measured only against a GCC reference. Item 1 was measured as a scratch
probe instead (2.47% instructions, cycles down on every flagship, but
kernel regressions that the refined probe should remove); at under 3% it is
below this round's pilot bar but inside the compile-speed exception for
planned 1–3% cuts.

Recommended next stream, in order:

1. **Verify, then land item 1**: redfox kernel timing and panel cycles for
   the refined probe (`wt/speeddesign-padprobe`), then the full gate set
   (twin guard, quick, speed, bench, `same_output`, golden, ladder, fixed
   point).
2. **A backend-generation stream aimed at GCC's scalar-backend quality
   (−24%)**: scoped zeroing of managed locals (item 4, small, shortens live
   ranges) first, then register allocation on split live ranges (item 2),
   then known-bits selection (item 5), each measured against the GCC
   scalar-backend host as the reference.
3. Alongside, under the 1–3% exception: implicit null checks (item 3) and
   the thread-register state (item 6).
4. The facts stream takes 99's root facts cost (73M) as its target; the
   no-traps stream takes the compiler's own index proofs (item 3, length
   half).

## Reproduction

Scratch assets in `~/dev/tmp/speeddesign/`: `gcc/` (translator, adapters,
`variants.py`, `measure.py`, `phases.py`, per-variant JSON), `cg/` (Callgrind
outputs and the class, frame, stack and check-census scripts), `orc-*`
(oracle patches, built with `build_oracle.sh` / `buildlib.sh`), `kern/`
(kernel oracle counts). None of it is in the tree.
