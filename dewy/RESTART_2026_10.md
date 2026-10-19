# Restart: fast feedback and a Sloppy-derived implementation core

Assessment begun 2026-10-16 at Dewy `15e57975` and Sloppy `235e19a`.
Sloppy's checkout already had edits to `compiler/main.jo` and `CHANGELOG.md`;
it is a reference, and this work does not modify it. Measurements of its
existing binary identify that binary separately from its source revision.

## Older-laptop pilot and current optimized host (2026-10-19)

The current O3 PGO/LTO compiler passes **6,296 checks in 177.68 s**. Its
instruction work falls **0.23% default / 0.54% release / 0.96% fixed compiler
rebuild** against the previous optimized host. All 28 generated-artifact
comparisons remain equivalent with fresh checksums.

A short pilot on an otherwise idle **Dell Latitude 7490, i5-8350U, 8 GB RAM**
uses one CPU and emitter, AC power, and its unchanged power policy. The
44,005-line workload compiles in **217.06 ms wall / 214.86 ms CPU**, about
**203k / 205k root lines per second**. These are fresh builds with warm
filesystem caches; library compilation is included in the time. This remains
below the 250k target.

Six compilation comparisons pass, but the initial release-build comparison
reports a regression. A bounded follow-up with phase timings and native/host
variants does not reproduce it; hardware counters decrease in both variants.
Both results are retained, and the release timing remains unresolved. This
does **not** promote a new accepted baseline or replace the fixed-reference gate.

Four runtime workloads also expose remaining gaps: records beat the C comparison,
text costs about **1.06x default / 1.15x release**, managed parameters
**2.71x / 1.54x**, and branch dispatch **1.20x / 1.18x**. The laptop provides
useful independent evidence without running the full validation suite there.
[Raw samples, diagnostic, reproduction scripts and host validation](audits/2026-10-19/older-laptop-pilot.json).

## Returning arms and definite field assignments (2026-10-19)

A branch that changes a narrowed local or field and then returns no longer
poisons the continuing path. The checker records loop-exit targets as it checks
statements: exits to enclosing loops retain invalidations, while contained
breaks/continues and jumps inside other functions or closures do not block
return-path refinement. Match guard effects remain separate from returning body
effects. This adds no whole-function traversal.

Known-member assignments to optional and union fields now establish a refinement
consistently. Previously, the same program could pass only if an unrelated
helper's field guard had been checked first. Fresh compiler-process tests cover
both kinds with no helper call, a prior call, and a subsequent call. Explicit
optional operations retain their optional view after narrowing; this fixes a
compatibility failure caught by the pinned optional fixture. Dewy errors now
recommend `is?none` instead of unsupported Jo unwrapping syntax.

The independent C bootstrap and **6,296 checks pass in 191.71 s**. Four additional
updated value batches verify that returning branches preserve independent
private captures and explicit shared captures. Compilation instruction increases
remain **below 0.01%** for large default/release programs and compiler rebuilds.
The paired pilot gives **7 pass / 5 inconclusive**, with no established regression;
all 28 runtime artifacts match with fresh checksums. The fixed reference and
accepted baseline remain unchanged; a fresh optimized host is the next check.
[Reproductions, compatibility fixes and measured evidence](audits/2026-10-19/return-field-narrowing.json).

## Keep guard refinements valid after writes (2026-10-19)

The checker no longer re-applies an old condition after its surviving branch
has invalidated it. For example, `if x is?none {return 0} else {x=none}` now
correctly rejects a later `x.value`. Guards reuse their surviving, valid
condition aliases; locals declared inside an arm still stay inside that arm.

Field invalidation now uses the existing branch journal, so writes remain
visible across nested block boundaries while sibling arms remain independent.
Replacing a field with the same known member keeps its tag refinement, but
invalidates facts about nested fields, including paths rooted in prior aliases.
The change adds no whole-function analysis pass.

An independent C bootstrap and **6,291 checks pass in 200.12 s**, including nine
new diagnostic cases and six value cases in the native/web, default/release
batch. Compilation instruction counts increase only **0.008% default /
0.006% release / 0.003% compiler rebuild**. The paired pilot gives **7 pass /
5 inconclusive**, with no established regression. All 28 runtime artifact
comparisons match with fresh checksums. Returning-arm invalidation remains a
separate follow-up; the accepted performance baseline is unchanged.
[Before/after programs, validation and performance evidence](audits/2026-10-19/guard-narrowing.json).

## Reject a word-at-a-time name hash (2026-10-19)

A bounded prototype replaced the compiler interner's byte loop with bounded
8/4/2/1-byte loads and a final mixing step. The quick suite passed, but native
compiler instruction counts increased **0.09% default / 0.06% release /
0.04% compiler rebuild**. The prototype was reverted without a full timing
campaign. No language or runtime-library hash behavior changed.
[Prototype and rejection evidence](audits/2026-10-19/rejected-word-name-hash.json).

## Store optimizer scope metadata together (2026-10-19)

Scope openness, parent, branch count and export state now occupy one 16-byte
record array. This replaces four array growth/reset operations and keeps facts
used together in the same record. Parent IDs use the existing 32-bit scope-ID
range; optimization decisions are unchanged.

The independent C bootstrap and **6,282 checks pass in 196.08 s**. Beyond the
stable-value cache, compilation instruction counts improve **0.11% default /
0.27% release / 0.36% compiler rebuild**. Paired timing gives **8 pass /
4 inconclusive**, with no established regression. All 28 generated artifact
comparisons (twelve existing kernels plus recursive tree/list, both modes)
match, with fresh checksum executions. Optimized-host benefit remains to be
measured; the fixed reference and accepted baseline are unchanged.
[Bootstrap, runtime and compilation evidence](audits/2026-10-19/optimizer-scope-records.json).

## Cache stable-value facts in the optimizer (2026-10-19)

The existing prepass now caches whether a register has one definition preceding
all uses. Lookups read one boolean instead of repeatedly reading definition
counts and positions from three arrays. Parameters, constants, new temporaries,
and hidden zero-slot definitions maintain the same invariant. No additional
whole-function pass is needed.

A diagnostic build asserted equality with the original predicate throughout
453 quick checks, large default/release builds and compiler self-compilation.
The production implementation passes an independent C bootstrap and **6,282
checks in 168.84 s**. Native compilation instruction counts fall **0.11% default /
0.33% release / 0.70% compiler rebuild**. Paired timing gives **4 pass /
8 inconclusive**, with no established regression. All twelve existing kernels
plus recursive tree/list have equivalent generated artifacts in both modes,
verified with fresh checksums. Optimized-host benefit is still unmeasured; the
fixed reference and accepted whole-stage baseline remain unchanged.
[Invariant, bootstrap and performance evidence](audits/2026-10-19/stable-value-cache.json).

## Current optimized-host validation (2026-10-19)

The maintained O3 PGO/LTO builder now has a freshly trained host for `259e2c5c`,
including recursive values and sibling narrowing. All **6,282 tests pass in
159.81 s**. All twelve existing runtime kernels in both modes match the native
compiler's generated artifacts apart from equal-width bundle paths, with fresh
checksum checks. The host changes compilation speed, not program behavior.

Against the earlier frame-omitting optimized host, compilation instruction counts
increase **0.48% default / 0.36% release / 0.33% compiler rebuild** across the
intervening language features. All seven paired timing comparisons are
**inconclusive** under variable load. The current default 44,005-line build takes
**318.23 ms wall / 314.31 ms CPU** (about **138k / 140k lines/s**); the older
control also slowed to 314.37 / 310.37 ms. This is not a target-speed claim or a
new accepted baseline. The fixed reference remains unchanged.
[Build, validation and measured evidence](audits/2026-10-19/current-optimized-host.json).

## Independent narrowing in sibling branches (2026-10-19)

Assigning an optional or union local in one `if` or `match` arm no longer
incorrectly widens the same local while checking a sibling arm. A small log
records newly invalidated aliases; sibling checking rolls those changes back,
and the join merges them. Prior invalidations remain in force. This also covers
if expressions and the implementation language's if-let. Post-join narrowing
remains conservative; this is not a complete flow-analysis redesign.

The direct recursive-tree walk initially retained redundant `none` checks and
was slower than the snapshot workaround. A bounded optimizer rule now recognizes
a final register copy that leaves by another edge, restores its version for the
sibling path, and invalidates it at the actual join. It adds no whole-function
pass or state snapshots. Keeping each optimizer control frame's data together
also removes the initial prototype's bookkeeping overhead. The maintained tree
benchmark now uses the straightforward cursor spelling. It matches the snapshot
version's speed, although the paired comparison remains **1.27× C default /
1.16× C release**, so tree parity is still unfinished.

The independent C bootstrap and **all 6,282 checks pass in 178.73 s**. Compilation
instruction counts improve **0.086% default / 0.325% release / 0.456% compiler
rebuild** against the preceding native compiler. The compilation pilot gives
**9 pass / 3 inconclusive**, with no established regression. All twelve existing
runtime workloads in both modes retain identical generated artifacts except
equal-width bundle paths, verified with fresh checksums. The fixed reference and
accepted baseline remain unchanged.
[Diagnostics, rejected drafts, bootstrap and performance evidence](audits/2026-10-19/branch-narrowing.json).

## Omit optimized-host frame pointers (2026-10-19)

The optional GCC host now omits frame pointers, with `--frame-pointers` for
profilers that need frame chains. Training and final compilation use the same
setting. Matched O3 PGO/LTO hosts execute **2.12% fewer instructions** for large
default builds, **1.79% fewer** for release, and **1.42% fewer** for the fixed
compiler rebuild. Nine paired timing samples give **4 pass / 3 inconclusive**,
with no established regression. The default workload measures **185.39 ms wall /
182.71 ms CPU** for 44,005 root lines: roughly **238k / 241k lines/s**, still
short of the target. This comparison uses the matching pre-recursive compiler
snapshot; it is not a current-language throughput certification.

All **6,244 applicable checks pass in 180.30 s**, including the maintained build
API's explicit frame-pointer PGO/LTO option. The cross-host test now rebuilds
the selected bundle's matching compiler source and runtime rather than mixing
checkout source with an older bundle library. Fresh checksum executions confirm
that all twelve existing kernels in both modes have identical generated
artifacts apart from equal-width bundle paths. GCC rejected attempts to reuse
relocated profiles, so the measured candidate trained afresh; profile checks
were not weakened. The fixed reference and accepted baseline remain unchanged.
[Build provenance, measurements, exclusions and validation](audits/2026-10-19/host-frame-pointers.json).

## Redirect redundant native jumps (2026-10-19)

The x86-64 emitter now redirects branches whose destination contains only
structural ends followed by another unconditional branch. It resolves loop
backedges immediately and forwards other fixups to their final block. Lookahead
is bounded at eight ends, and no instructions move or new compiler pass runs.
This removes an extra taken jump at each level of the recursive search tree.

Seven paired samples show **16.4% less default runtime** and **19.4% less release
runtime** for tree lookup; list traversal stays flat. All four comparisons pass.
The independent C bootstrap emits the exact measured workload artifacts apart
from equal-width bundle paths, verified with fresh checksums. Tree lookup remains
behind C; this is a targeted improvement, not general parity.

All **6,274 checks pass in 164.17 s** with that bootstrapped compiler. After
self-compilation, instruction counts relative to the recursive-value compiler
change by **−0.021% default / +0.0027% release / +0.066% fixed compiler rebuild**.
The earlier native-seed generation and its slightly higher costs are retained in
the audit. Compilation timing gives **5 pass / 7 inconclusive**; the twelve
existing kernels in both modes give **13 pass / 11 inconclusive**, with no
established regression. CPU conditions varied substantially during this bounded
run, so compare paired samples rather than medians from separate campaigns.
The fixed reference and last accepted whole-stage baseline remain unchanged.
[Raw runtime/compile measurements, artifact proof and full validation](audits/2026-10-19/branch-redirection.json).

## Recursive values with fast traversal (2026-10-19)

Records can now contain themselves through optionals, other records, generic
instances and unions. `Node:type=[value:int64 next:Node?]` is an ordinary value:
copying it and changing a descendant leaves the original unchanged. Equality,
hashing, text/JSON conversion, debugger displays and live-reload migration follow
the value. Types with no finite value are rejected. Private callback captures
remain independent inside recursive values, and `$capture @name` remains explicit
sharing. Writes through narrowed captured fields now mark their actual owner.

This ports Sloppy `403f7de` and `f11c0a4`, with pinned source hashes and adapted
fixtures in `core/UPSTREAM.json`. The upstream read-only traversal analysis initially
rejected Dewy's synthetic parameter bindings, leaving traversal **9–10× behind C**.
Those bindings now remain analysis roots. Optional cursors use internal nullable
pointers, avoiding a tag load/default-address choice on each step. Small boxes
reuse the allocator header while live and restore it when freed; this halves the
list node's allocation from 64 to 32 bytes. Large allocations keep their headers.
A cached layout flag enables these recursive walks in default builds too, without
scanning unrelated function bodies. None of this requires new user notation.

The independent C bootstrap and **all 6,274 checks pass in 145.66 s**. Coverage
includes native/web and default/release, private/shared callbacks, 100k-node list
cleanup, the upstream million-node drop, size-class/large-allocation boundaries,
GDB and live reload. Two expressions were rewritten for the smaller bootstrap
parser; its restrictions were not relaxed.

Seven rotating pairs compare matching algorithms against C pointer nodes, with
construction/destruction outside the thread-CPU timer and independent checksums.
Tree lookup takes **84.95 ms default / 79.09 ms release**, versus **61.56 ms C**;
list traversal takes **17.11 / 16.95 ms**, versus **16.75 ms C**. Relative to the
first recursive implementation, both modes improve roughly **7× for trees** and
**10× for lists**. The remaining tree gap is real; these two kernels do not establish
universal C parity. The maintained `tools.sloppy_core.benchmark_recursive` runner
extends coverage without replacing the fixed historical gate. A conditional-move
experiment made traversal slower and was discarded; its evidence is retained.

The final native compiler executes **0.30% / 0.24%** more instructions for large
Dewy default/release builds and **0.21%** more for the fixed compiler rebuild.
Compilation timing comparisons give **8 pass / 4 inconclusive**, and the twelve
existing runtime kernels in both modes give **15 pass / 9 inconclusive**; neither
finds an established regression. These bounded comparisons do not accept a new
whole-stage baseline or resolve earlier uncertainty. They compare native hosts;
the preceding O3 PGO host's ~238k lines/s is not a fresh measurement of this source.
[Raw measurements, experiments, bootstrap provenance and validation](audits/2026-10-19/recursive-values.json).

## Fresh O3 profile-trained compiler host (2026-10-19)

The maintained optimized-host builder now uses `-O3` for PGO, with an explicit
`--optimization 2` override; non-PGO builds keep `-O2`. Training and final builds
use the same level. Reusing O2 profiles for O3 failed GCC's counter-layout checks,
so the candidate was trained afresh without weakening those checks. No fast-math
or machine-specific instruction sets are enabled.

All **6,243 checks pass in 128.79 s**, including profile-generation/use at both
levels with and without LTO. Nine rotating pairs compare otherwise identical
fresh O2/O3 PGO+LTO hosts: all seven compilation comparisons pass, with roughly
**3–4% lower CPU times**. Three hardware-count pairs show **4.9% fewer instructions**
for large default/release builds and **5.1% fewer** for the fixed compiler rebuild.
The pilot reaches **238k root lines/wall-second**, **242k/CPU-second**; the full
stage reaches **238k/CPU-second**. The rough 250k target is still ahead.

The full stage against the fixed reference and last accepted optimized host has
**40 passing comparisons, 20 inconclusive, no established regression**. All twelve
compilation comparisons pass; large default/release builds use about **31% less
CPU** than the last accepted host. Runtime checks cover twelve kernels in both
modes, with independent C results. Twenty runtime comparisons remain uncertain;
this does not accept a new whole-stage baseline or establish C parity. Examples
of remaining release/C ratios are **1.21× text**, **1.26× graph**, and **1.43–1.47×
managed-parameter helpers**. Records and shifted-array kernels are faster than C
on these workloads. No repeated timing campaign was used to force acceptance.

The O3 host build took **462 s**, about **359 MiB** peak child RSS. This remains
an optional release-toolchain step; ordinary compiler edits use the native build.
The measured artifact predates the new parameter interface and used the same
builder with its flags overridden in process; actual commands and provenance are
retained, and the integrated interface is covered by the full suite.
[Raw comparisons, instruction counts, build provenance and validation](audits/2026-10-19/host-pgo-o3.json).

## Regex matching tables and bounded DFAs (2026-10-19)

Ported Sloppy `6d46316`'s regex engine without changing Dewy's syntax or callback
semantics. It flattens Pike VM state, uses ASCII class bitmaps and prefix/start-set
skipping, and builds bounded lazy DFAs for long inputs. Captures and fallback
retain the Pike VM. The pinned library source and upstream fixtures are recorded
in `core/UPSTREAM.json`; Sloppy's working tree was not modified.

All **6,241 checks pass in 154.83 s**. The focused gate compares 121 deterministic
cases against independent expectations across native/web and default/release,
including captures, empty matches, Unicode byte offsets, threshold boundaries
and a state-limit stress input. Additional cases cover replacements, split,
search offsets, malformed bytes and invalid patterns.

Seven paired thread-CPU samples for each of seven regex workloads in both build
modes pass all **14 comparisons**. Long ASCII matching/search/capture workloads
are **26–40× faster**, line-anchor searches **21–33×**, and the Unicode search
**2.1–3.4×**. Reused short patterns are **1.9–2.1× faster**; preparing and matching
a short pattern together is about **1.24× faster**. These are named workloads,
not a universal regex speedup or a C/Rust parity claim. The maintained
`tools.sloppy_core.benchmark_regex` harness reproduces their inputs and checksums.

Compiler instruction counts increase only **0.016% / 0.012%** for large
Dewy default/release builds and **0.0067%** for self-build. Six of twelve matched
compilation comparisons pass; six remain inconclusive, with no established
regression. The twelve existing runtime kernels retain their artifacts and
pass fresh full-size checks. No new whole-stage baseline is accepted, and no
repeated timing campaign was used to resolve host noise.
[Raw measurements and validation](audits/2026-10-19/regex-engine.json).

## Named calls through function values (2026-10-19)

Named arguments now work through stored/returned callbacks, record fields and
array elements. Inferred values retain their declared labels; a callable-type
annotation supplies the labels at that boundary, including nested callback
types. Label changes require no runtime adapter. Callees evaluate first and
arguments retain written evaluation order. Closure copying, explicit shared
captures, const snapshots and mutable arguments keep their existing semantics.

Labels occupy the otherwise unused function-type `st` field and are interned
with the existing name pool; neither type-record size nor runtime closure
layout grows. Generic substitution preserves them, and editor hover shows the
actual labels. Ignored `_` parameters no longer produce a synthesized read of
an unbound `_`. Function-type annotations reject defaults that value calls do
not support; defaults remain available on directly called declarations.

The corrected source passes **71 focused checks**, independently bootstrapped
from C, and **6,231 full checks in 187.33 s**. All twelve existing runtime
kernels retain their artifacts and pass fresh full-size checks. Three hardware
pairs show **0.028% / 0.020%** more instructions for default/release throughput
and **0.0053%** for the compiler rebuild.

Nine of twelve seven-pair compilation comparisons pass. Against the immediate
predecessor, only release throughput remains inconclusive (ratio **1.0032**,
interval **0.9943–1.0245**); default throughput, Tour, Netpong, Dunes and self-build
pass. Against the last accepted native stage, default throughput and self-build
remain uncertain. No comparison establishes a regression, and the accepted
baseline is not moved. [Corrected-source validation and raw performance evidence](audits/2026-10-19/named-function-values.json).

## Partial operators restored (2026-10-19)

Parenthesized right operands now form ordinary unary functions: `(* 2)`,
`(<? limit)`, `(.x)`, `(as float64)` and `(transmute uint64)`. Normal precedence,
private captures, source evaluation and contextual callback typing apply.
Spaced inverted comparisons (`not in?`) work too. Prefix operators retain their
ordinary meanings. Parsing reuses the consumed opening token temporarily as
the implicit operand, avoiding insertion into the token array and preserving
the existing expression parser. No backend or closure representation changes.

The **44 focused checks** pass through both native and independent C-bootstrap
builds; the full suite passes **6,160 checks in 178.11 s**. Coverage includes
nested partials, interpolation, private captures, source side effects, type
queries, conversion, module generic inference, named outer arguments and
formatter round trips. Missing local type context has a user-facing diagnostic.

All twelve existing runtime kernels retain their generated artifacts and pass
fresh full-size checksum checks. The seven-pair compilation pilot is entirely
inconclusive under variable host load; it establishes neither a slowdown nor a
speedup. Three alternating hardware-count pairs show **0.050% / 0.035%** more
instructions for large default/release builds and essentially no change for
self-build. These counts do not substitute for timing acceptance. The last
accepted baseline remains fixed, and there is no repeated sampling campaign.
[Full validation and performance evidence](audits/2026-10-19/partial-operators.json).

## Numeric bit reinterpretation (2026-10-19)

`value transmute Type` now supports equal-width machine integers and floats.
`as` remains numeric value conversion. The source is checked independently of
the destination and evaluated once; signed zero and NaN payloads survive bit
round trips. Managed values, records, booleans and unions are rejected. Native
and web lowering reuse the existing bit-reinterpretation instructions.

All **38 focused checks** pass with both the normal native build and independent
C bootstrap, including generic aliases, width errors and formatter round trips.
The **429-check quick suite** passes in 10.00 s. All twelve existing runtime
kernels have unchanged generated artifacts and pass fresh full-size checks.

A seven-pair native pilot finds no definite compilation regression. Default
throughput, Tour, Netpong, Dunes and self-build comparisons against the immediate
native predecessor pass; release throughput remains inconclusive (paired ratio
1.013, interval 0.945–1.059). Three instruction-count pairs show only **0.005%**
more work for default throughput, **0.004%** for release, and **0.00003%** for
self-build. This adds no new optimization pass or runtime representation.
The fixed and last accepted stage references remain unchanged; no resampling
loop was used to force acceptance. [Validation, pilot, counters and artifact
proof](audits/2026-10-19/numeric-transmute.json).

## Profile-guided compiler toolchains (2026-10-19)

The maintained optional host builder now supports `--pgo`, including `--pgo
--lto`. It snapshots six compiler/native/web training inputs, checks that every
profile contains the expected accumulated run count, then builds without
instrumentation. Source mismatches and missing profiles are fatal. Each job is
sequential, bounded and reaped on failure; the final executable writes no profiles.

The full PGO+LTO host passes **6,078 checks in 146.11 s**. It emits the same
artifacts as the existing same-source LTO host on all **12 runtime kernels**,
apart from equal-width compiler paths, and passes fresh boundary/full-size
checksum checks. Those artifacts also match the earlier native text-case stage
under its existing path canonicalization. No runtime timings were reused.

Nine rotating matched samples measure **23.7% less CPU time for large default
builds** versus LTO alone, **13.8% less for Tour**, **14.2% less for Dunes**, and
**15.9% less for the compiler rebuild**. Release throughput, Netpong native and
Netpong web intervals versus LTO remain inconclusive despite lower paired
medians. Against the superseded streaming-PGO prototype, six of seven comparisons
pass and Netpong remains inconclusive; no comparison establishes a regression.
The large default-build median is about **185k root lines/CPU-second** on this
busy machine, below the 250k goal. These are matched workload results, not a
claim of universal throughput or generated C parity.

The maintained toolchain build took **448 s** (256 s instrumentation build,
190 s final build) and about **359 MiB** peak child RSS. This is an optional
release/toolchain build step; ordinary source edits retain the native rebuild
path. The old `cd07ea34` whole-stage reference remains fixed because earlier
text-case timing uncertainty is unresolved. [Build provenance, raw pilot,
full validation and generated-program proof](audits/2026-10-19/host-pgo-lto-pilot.json).

The initial streaming-PGO experiment passed 6,076 checks and showed a strong
compile-time gain, but review found missing GCC run summaries. It is superseded.
Explicit registration and GCC's normal dump fixed the summaries and the small
PGO+LTO crash. The old full stage had twelve passing compilation comparisons,
fourteen inconclusive runtime comparisons and no definite regression; it was
not accepted. [Preserved superseded experiment](audits/2026-10-19/host-pgo-stream-experiment.json).

## Refreshed Sloppy comparison (2026-10-19)

Ten rotating matched samples compare the current Sloppy binary with native and
optional LTO Dewy hosts. On equivalent large programs, LTO Dewy takes **13.1%
more CPU time in default mode** and **32.0% less in release mode** than Sloppy.
The same-host comparison of Dewy versus equivalent Jo source costs **20.8%
more in default mode / 17.5% more in release mode**. This points to frontend
work as a more substantial opportunity than the small backend probes below.

The record-update workload compiles **34.9% faster default / 43.4% faster
release** than Sloppy; its generated kernel takes **36.5% / 79.6%** of Sloppy's
runtime respectively. Release runtime is **87.0%** of the equivalent C kernel
on this run. These are workload-specific paired ratios, not universal claims.

Both languages call every generated function and produce matching checksums.
The equivalent sources contain 44,005 Dewy versus 50,009 Jo lines, so elapsed
CPU time per workload is the meaningful cross-language comparison. Dewy's
median default build is 432 ms (about 102k root lines/CPU-second on this busy
host), still below the 250k target. This should not be compared directly with
the earlier 163k result under different host conditions.

The tool now rotates sample positions/directions and supports explicitly
omitting a cross-library variant: current Sloppy needs `__panic_unwrap_in`,
which Dewy's library does not provide. Neither Sloppy nor its runtime was
modified. Own-library results include product/runtime differences; recorded
binary hashes identify the actual executables independently of checkout
revisions. This diagnostic does not replace the fixed-reference stage gate or
change the last accepted baseline. [Raw samples, identities, paired estimates
and logs](audits/2026-10-19/sloppy-refresh.json).

## Small compiler probes deferred (2026-10-19)

Three additional source-level probes are reverted. Operand classification by a
lookup table passed 424 quick checks but slightly increased instructions on the
generated workloads; its seven-pair timings did not establish a broad gain.
Local views over five private register-analysis arrays passed 424 quick checks
and removed **0.65–0.79%** of instructions. A built-in-type prefix fast path also
passed 424 quick checks and removed **0.43–1.16%**. Those latter two did not proceed
to latency pilots or full gates: their small measured upside did not justify
additional pointer-lifetime/type-initialization assumptions and another broad
validation campaign. No compiler changes from these probes remain.

[Operand-table patch and evidence](audits/2026-10-19/operand-table-experiment.json),
[register-array views](audits/2026-10-19/analysis-views-experiment.json), and
[built-in type resolution](audits/2026-10-19/prune-prefix-experiment.json)
retain the exact experiments for future work.

The subsequent AST field-order probe removed eight bytes of padding per node
(104 to 96 bytes), passed 424 quick checks, and kept generated results correct.
Its seven-pair pilot was mixed (0.985 default, 1.010 release, 0.967 compiler
rebuild), with less than 0.02% instruction reduction. It is also reverted;
[patch and measurements](audits/2026-10-19/node-layout-experiment.json) are retained.

## Optional cross-file compiler-host optimization (2026-10-19)

`build_optimized_host --lto` additionally lets GCC optimize across generated C
units. Compilation and linking remain sequential; timeouts/interruption kill
the owned compiler process group, including LTO descendants. The ordinary
native development build and application compiler modes remain unchanged.

A seven-pair pilot against the same-source C host without LTO measures paired
CPU ratios **0.951 default**, **0.943 release**, and **0.870 fixed compiler
rebuild**. Against the last accepted C host these are **0.935**, **0.957**, and
**0.918**. The default-build intervals remain inconclusive. A separate three-pair
hardware diagnostic finds **4.3%**, **4.1%**, and **3.6%** fewer retired
instructions, supporting a real reduction in work without replacing timing.

The experimental host passes **424 quick checks in 11.26 s** and **6,075 full
checks in 247.27 s**. Maintained build integration passes with and without LTO;
a separate timeout test confirms that a spawned compiler descendant is stopped.
All **12 runtime kernels** retain the native/non-LTO generated artifacts except
exact equal-width source/toolchain paths, and pass fresh boundary/full-size
checksum checks. This is code-equivalence evidence, not fresh runtime timing.

The optional build took **293 s**, including a **223 s** link, with about
**357 MiB** peak child RSS. The full host used the recorded experimental builder;
the maintained option emits the same compile/link flags and is exercised by the
integration tests. No redundant full-host rebuild was performed just to change
the driver. This is an optional build choice, **not a new accepted whole-stage
performance baseline**. The earlier text-case uncertainties remain recorded,
and the 250k-lines/s and all-kernel C-parity goals remain open.
[Build provenance, raw pilot, instruction counts, checks and equivalence proof](audits/2026-10-19/host-lto-pilot.json).

## Text conversion: correctness complete, performance acceptance pending (2026-10-19)

A pinned Sloppy `e5be9225` port changes `upper`/`lower` to make one private copy,
process ASCII eight bytes at a time, and update supported two-byte UTF-8 letters
in place. Source values and their aliases remain unchanged. The existing limited
simple-case repertoire remains; malformed bytes are now preserved instead of
being repaired by a character-decoding round trip. The language guide documents
this behavior. A permanent mixed ASCII/Unicode benchmark uses the same algorithm
and allocation work in C.

The independent C bootstrap passes the focused checks, the native quick suite
passes **423 checks in 10.34 s**, and the optional C host passes **6,073 checks
in 169.19 s**. Tests cover every ASCII byte, aligned/unaligned word boundaries,
UTF-8 cases, malformed sequences, retained aliases, and guard-page bounds.

The full native stage measures **47× default / 44× release** improvement on the
conversion kernel against the preceding stage. Its release/C paired ratio is
**0.977** in this run; the earlier seven-pair pilot was **1.095**, so this is not
a general claim of being faster than C on all hardware or inputs.

After retaining the initial 15 pairs and one bounded 31-pair recheck of uncertain
rows, **56 of 60 comparisons pass**. Four remain inconclusive: default throughput
and fixed compiler rebuild versus the previous native compiler, and default
records/graph versus the fixed reference. No comparison shows a definite
regression. Compiler medians are flat or slightly better; a separate diagnostic
finds less than **0.004%** change in retired instructions, which does not replace
the timing gate. **This is not an accepted performance baseline**; `cd07ea34`
remains the last accepted stage. There is no additional resampling loop.

The C-host candidate has full correctness coverage but has not had a separate
performance stage. Further compiler improvements continue against the accepted
baseline. All initial/recheck samples and validation logs are preserved in the
[pending audit](audits/2026-10-19/text-case-pending.json).

## Optional optimized compiler host (2026-10-19)

The compiler can now be built through a maintained scalar-IR-to-C path for
Linux x86-64 release/toolchain builds. The native compiler-development path
and native/web application backends remain the defaults. A versioned
`--host-ir` export disables vectorization only for the program being exported;
the resulting compiler retains ordinary application vectorization. The C
translator rejects unsupported operations, preserves `@noinline`, uses defined
modular integer arithmetic and unaligned memory helpers, and retains frame
pointers for runtime recovery. Its build is sequential and bounded.

The supported build command and separate bundle layout are in
[the core guide](../core/README.md#optional-optimized-compiler-host).
`HOST_BUILD.json` records the actual C binary, native source-build provenance,
IR, generated sources, tool hashes and GCC commands. Packaging and performance
identity checks validate that binary and its original compiler/library sources.

The maintained optimized host passes **6,059 full-suite checks in 142.15 s**.
The native compiler builds through the independent C bootstrap and passes
**419 quick checks in 9.71 s**. A compiler rebuilt by the optimized host also
builds and runs the 44,005-line workload with the expected checksum.
Both host paths pass all **56 fixed/previous performance comparisons**;
the native path uses one bounded recheck of three uncertain rows, retaining
all original samples. Its matched medians are essentially flat; Dunes is
about 0.8% slower, within the existing 2% gate resolution, and also passes the
cumulative fixed-reference check. That resolution is not a recurring budget.

The optimized host's paired CPU ratios against the preceding native compiler
are **0.776 default**, **0.757 release**, **0.832 tour**, **0.820 Netpong**,
**0.816 Dunes** and **0.826 fixed compiler rebuild**. All eleven runtime kernels
preserve the accepted generated artifacts and pass fresh boundary/full-size
checks; these certificates do not claim new C-parity timings. Measured fresh
root throughput is about **163k lines/CPU-second**, still below the 250k target.

Building the optimized host took **213 s** on this busy i7-6700, with about
**359 MiB** peak child RSS across export/build subprocesses. This cost is
outside the normal native edit/test loop. The optimized host needs the Linux
C library and lacks the native compiler's custom source-line backtrace table;
application debug output remains intact. The earlier diagnostic and the
maintained build are distinguished in the
[full audit](audits/2026-10-19/optimized-host.json).

## Small decimal literals: deferred (2026-10-19)

A source-byte decimal decoder avoided temporary strings for common literals,
but seven matched compilation pairs were flat: candidate/previous CPU ratios
1.00029 default, 0.99971 release and 0.99939 compiler self-build. Its 376 quick
tests passed; no independent C bootstrap, full suite or stage gate was run.
The compiler changes are reverted, with the patch and samples retained in
[`small-integers-experiment.json`](audits/2026-10-19/small-integers-experiment.json).
The accepted shifted-index stage also passed all platform CI checks.

## Redundant integer extensions: deferred (2026-10-19)

A prototype reused stable IR definitions to remove redundant sign/zero
extensions of narrow loads, comparisons and already-extended values. A static
scan found 832 candidates, but seven matched compilation pairs did not show a
useful gain: candidate/previous CPU ratios were **1.00645 default**, **1.00918
release** and **1.00042 self-build**. The compiler change is reverted; no full
suite or stage gate was run. The independent C bootstrap passed **402 quick
checks**, and four new native/web/default/release boundary tests pass on both
the prototype and accepted compiler. They cover signed/unsigned conversions at
8/16/32/64 bits against a Python modular-arithmetic oracle. The patch and raw
measurements are retained in
[`narrowing-experiment.json`](audits/2026-10-19/narrowing-experiment.json).

## Immediate integer stores: deferred (2026-10-19)

Direct x86 immediate stores were extended to byte/word and RIP-relative global
addresses, including relocation adjustment for trailing immediate bytes. The
independent C bootstrap passed **406 quick checks**, and native default/release/
debug checks passed on both candidate and accepted compiler. The tests verify
unaligned byte/word/dword/qword writes, signed immediates, large-constant fallback,
global neighbors and untouched sentinel bytes against an independent byte oracle.
Seven paired compilation samples were flat and inconclusive: candidate/previous
CPU ratios **1.00530 default**, **0.99565 release**, **1.00425 self-build**. The
emitter change is reverted; no full suite or stage gate was run. The patch and
samples are in
[`immediate-stores-experiment.json`](audits/2026-10-19/immediate-stores-experiment.json).
A static branch-table scan also ruled out a narrowly scoped few-destination
bitset emitter as the next experiment: the compiler's hot dispatch tables have
more destinations than that approach would handle.

## Classify expression leaves before compound syntax (2026-10-19)

The syntax projection now handles identifiers and literal nodes before calling
operator and include-file recognizers. Include recognition runs only for call
operators. This avoids repeatedly unwrapping/classifying ordinary leaf nodes;
syntax, AST representation and lowering remain unchanged.

The independent C bootstrap passes **409 quick checks**, the full suite passes
**6,048 checks in 150.17 seconds**, and all **56 performance comparisons pass**
without rechecks. The large-source default candidate/previous CPU ratio is
**0.99255**, with a 95% bootstrap interval **[0.98577, 0.99742]**: a small but
measured saving. Release and self-build stage intervals include no change.
All eleven generated runtime artifacts match the preceding accepted stage
apart from equal-width embedded compiler paths; their validated performance
certificates are retained, without claiming new C-comparison timings.

This run measured about **124k fresh root lines/CPU-second**, still below 250k.
Absolute rates vary with host load/frequency and are not compared across runs.
[Raw paired samples, identities and validation](audits/2026-10-19/leaf-dispatch.json).

## Pack common-subexpression table entries (2026-10-19)

The optimizer now stores each available-expression key and its validity metadata
in one 64-byte scalar record, replacing ten separate arrays. Insertion replaces
the complete record through one checked array access. The hash function, probing
order, epochs, scope/export rules, memory generations and operand versions are
unchanged. This reduces scattered accesses and removes repeated checks during
insertion; no optimization pass or user-facing behavior is added.

The independent C bootstrap passes **409 quick checks**, and the full suite
passes **6,048 checks in 146.88 seconds**. All **56 performance comparisons pass**
after one bounded Netpong recheck retaining the original samples. Large-source
candidate/previous CPU ratios are **0.98989 default** and **0.97982 release**.
Self-build is 0.99109 with an interval including no change; Netpong and Dunes
are essentially flat. Tour is 1.01431, within the gate's 2% timing resolution;
the cumulative fixed-reference checks also pass. Three hardware-counter pairs
show about **0.4–0.6% fewer instructions** across the compilation workloads.

All eleven runtime benchmark artifacts preserve the accepted generated code,
using the existing exact-artifact certificates and fresh checksum preflights.
The measured **126k fresh root lines/CPU-second** is still below 250k and is
not compared with absolute rates from other host-load conditions.
[Measurements, earlier field-store prototype and validation](audits/2026-10-19/cse-whole.json).

## Register snapshots and packed metadata: deferred (2026-10-19)

Two prototypes targeted native-emitter working storage. The first saved only
incoming parameters' temporarily changed register locations instead of copying
the entire location array. The second additionally packed first/last use,
allocation weight and location into a 32-byte record. Both bootstrap from C and
pass the **412-check quick suite**. New default/release/debug tests exercise
integer/floating, register/stack, sparse and zero-argument functions with values
live across calls; they also pass on the accepted compiler.

The prologue-only pilot has an inconclusive release result, while hardware
instruction counts fall only **0.07–0.09%**. All three compilation comparisons
for the combined layout are inconclusive. Neither establishes enough benefit
to retain it or justify repeated sampling. Both compiler changes are reverted;
no full suite or stage gate was run. The semantic tests are retained.
[Exact patches, samples and validation](audits/2026-10-19/register-layout-experiments.json).

## Recommendation

The user's October 18 continuation criteria are explicit: keep working until
Dewy has its key intended language features, roughly 250k source lines/second
fresh compilation, and generated code competitive with C/Rust. A serious
unresolved user-facing design question blocks that area, not independent work.
Performance must be maintained at each stage, rather than recovered after
feature accumulation. The current implementation has not met the throughput
target. Closing that gap takes priority over expanding the language surface.

Every implementation stage needs a matched compilation/runtime comparison
against both the preceding stage and a fixed reference. A noisy result calls
for an isolated recheck, not silently accepting slower code. Retain measurements
and workload identities; do not reset the reference to a regression, inflate
line counts with unused imports, or trade away generated-code speed merely to
make compilation numbers look better. A no-regression result is distinct from
meeting the absolute targets. Feature additions must demonstrate that they keep
the attained performance, including ordinary programs that do not use them.

User clarification during implementation: preserve the useful user-facing
language experience, not byte-identical executables, internal ABIs, existing
data structures, or every historical compiler behavior. Breaking internal
changes are welcome when they shorten the route to the intended language.
Use representative programs and focused language tests as development gates;
do not turn old implementation details into migration requirements. The
earlier byte comparison was a convenient check of a local memoization change,
not an acceptance criterion for the replacement architecture.

Use Sloppy as the implementation reference for Dewy's performance core and
application/tooling layer. Develop a bounded integration experiment on a new
branch, preserving this compiler as an executable semantic reference. The
destination is one production implementation, with independent tests and a
bootstrap path. Making every feature twice indefinitely should not remain
the price of developing the language.

Start with fast validation and an identical application benchmark, then take
one real Dewy program through a compact representation and backend boundary.
Promote that experiment only when it preserves the tested Dewy semantics and
meets its compilation/runtime budgets. Sloppy's successful programs provide
the application requirements from the start; floating-point execution,
closures, dense records, interop and a usable game loop must become near-term
customers of the architecture, rather than waiting for an ideal proof engine.

The existing guarantees are design references, not a requirement to recreate
every old mechanism before the new implementation becomes useful. The user
explicitly permits breaking changes that improve the route to the intended
language. Keep supported behavior clear and reject unsupported explicit proof
contracts rather than pretending that runtime checks discharge them. Additional
proof sophistication should earn its place by enabling ordinary programs within
measured compile-time budgets.

### Current source-level restart

`restart/sloppy-frontend` carries the implementation under active development in
[`core/`](../core/README.md), with its own in-process Dewy lexer/parser feeding the
Sloppy-derived checker, runtime, native/web backends and bundled libraries. It
bypasses the old semantic IR, proof pipeline and backend bridge. There is no
patch generator, dependency on the Sloppy checkout, or Python process in normal
program compilation. The complete compiler bootstraps independently from C in
about 20 seconds. No installed compiler has been replaced.

The working language includes inferred/generic functions, overloads, defaults,
closures, dense records, independent value copies, custom operators/indexing,
arrays, dictionaries, unions, optionals, grapheme-aware strings, imports,
lazy stored ranges, combined loops, labeled exits and loop fallback arms. Large integer literals, exact fractions through integer `/`,
powers and explicit exact-to-float conversions now use ordinary compact-core
libraries. See the [language guide](../core/LANGUAGE.md) for supported behavior
and remaining gaps; compatibility is defined by useful language behavior rather
than the old representations or proof machinery.

Closure state now follows the user's value-semantics decision: ordinary
captures are snapshots, copied counters advance independently, and `$capture @name`
in the regular parameter list explicitly shares an enclosing local. Captures can
appear among caller parameters, without consuming call arguments; `$capture name`
explicitly lists a private snapshot. Parameters, returns and nested containers
preserve private copies; module globals retain their identity. Immutable private
environments can be retained without copying. Function-containing arrays currently
copy eagerly, while ordinary data arrays retain copy-on-write storage.
Value-returning dictionary getters also return independent callbacks; passing
`@counters[key]` to an `@` parameter advances the stored value. Fixing a lost `@`
marker in dictionary lookup rewriting makes that explicit path work.

A ten-million-call counter pilot exposed a threefold CPU regression from
unconditional lifetime pinning. Pinning only owners that can be replaced removes
that regression: default/release CPU medians are 28.7/28.0 ms, versus 31.8/27.5 ms
for the previous compiler. Five alternating compilation samples show essentially
unchanged self-build CPU time and about 3% higher Netpong CPU time. Wall times
were noisy; these are workload measurements, not a general speedup claim. The
[validation and raw measurements](audits/2026-10-18/closure-value-validation.json)
record the semantic coverage, compiler identities and remaining copy costs.
The independent C-bootstrap CI, including the unified `$capture` parameter
syntax, passes 5,652 checks with five skips in 91.32
pytest seconds, followed by passing Windows, macOS ARM64 and Linux ARM64 smoke,
editor, watch and relocated-package checks. All four standalone downloads are
available from the [validated run](https://github.com/david-andrew/dewy-lang/actions/runs/39147250518).

Native/web paddle, physics, forest, Dunes and Netpong examples exercise the game
libraries. Netpong adds tested native/browser multiplayer and a bundled invite UI.
Dunes includes procedural cloth and custom terrain/shadow shaders written in
Dewy; generated GLSL is compiled and linked by a real offscreen GLES driver in CI.
The editor checks unsaved source, including opened named libraries. A native
interactive prompt retains Dewy values and definitions and recovers from failed
inputs. Templates, asset embedding, error recovery and native live reload support
application work.
Dewy's 57-body physics scene runs at 178.32 ms versus 178.64 ms for the matching
Sloppy source in the recorded headless comparison; this is one workload, not a
general runtime parity claim. The earlier nested-particle comparison brought the
release kernel within about 14% of C. Detailed results and limits are in the
[implementation notes](../tools/sloppy_core/README.md) and
[example guide](../examples/sloppy_core/README.md).

Explicit element updates now use `loop @item in items`, including nested record
fields, managed values and fixed arrays. The platformer, arcade and 3D starters
use it for their update loops. Copies remain independent, including snapshots
made during iteration; the full C-bootstrap gate passes 5,458 checks. A
250,000-record update pilot allocates nothing inside either indexed or mutable
loops, with overlapping native timings. The same pilot exposes a web release
slowdown in both forms, addressed below; see the
[measurements and scope](audits/2026-10-17/source-core/mutable-loop-validation.json).

The web release slowdown now has a measured fix: retain calls to loop-containing
functions so the web runtime can optimize those kernels across invocations.
In the paired Node/V8 pilot, particle updates fall from 188 to 76 ms, helpers
from 1,265 to 631 ms, and records from 86 to 34 ms. A longer text recheck is
within 1%; native inlining is unchanged. Forcing V8's optimizing compiler makes
the particle variants comparable, supporting the tiering explanation. The
1,225-check focused gate passes; [raw results and limits](audits/2026-10-17/source-core/wasm-loop-inline-validation.json)
include baseline-only execution and the other application workloads.

A fresh full-size native mode baseline puts release arrays at 282 ms versus
280 ms for C, helpers at 918/821 ms, text at 258/212 ms, and records at 176/204 ms.
Graph remains the largest gap at 988 ms default, 718 ms release and 465 ms for
its differently structured C reference. [Native samples](audits/2026-10-17/source-core/native-app-modes-current.json)
and the [Node/web baseline](audits/2026-10-17/source-core/web-app-modes-baseline.json)
record inputs, hashes, modes, three fresh-process samples and limits.
A SIMD experiment that preserved vector temporaries in web shadow-stack memory
was rejected: it regressed particle and physics workloads. Future work should
keep vector values in registers; [the rejected trial](audits/2026-10-17/source-core/wasm-vector-slots-rejected.json)
retains its patch and measurements so it need not be repeated.

The web baseline also reflects runtime tiering: identical release artifacts
under normal versus optimizing-only Node take about 1,127/466 ms for text and
887/356 ms for arrays. Normal execution closely tracks baseline-only execution
for these one-shot kernels. [The diagnostic](audits/2026-10-17/source-core/web-kernel-tiering.json)
keeps the engine flags separate from deployment defaults. The emitter now
combines immediate local-store/reload pairs with `local.tee`, reducing the text
module by 7.5% raw and 3.1% gzipped at unchanged measured compile cost. Runtime
results are mixed; [validation and raw results](audits/2026-10-17/source-core/wasm-tee-validation.json)
make no general speedup claim.

Profiling that graph exposed dependent reads from map slots to dense keys.
Slots now cache complete integer keys (and full hashes for other key types),
keeping insertion order and independent value copies. In a paired comparison,
the unchanged million-node graph improved from 1,023 to 777 ms default and
731 to 602 ms release; Node/web improved from 1,656 to 1,233 ms and
1,440 to 1,086 ms. Text timings and compiler CPU time were roughly unchanged.
The tradeoff is larger slots: whole-process graph peak memory rose from 218 to
250 MiB, while compiler peak memory stayed near 239 MiB. The
[profile, raw measurements and validation](audits/2026-10-17/source-core/map-slot-key-validation.json)
record the memory cost, noisy compiler wall times and platform limits.

The development gate now has over 5,400 checks; recent local full runs took
151–208 pytest seconds with two workers, excluding the independent C bootstrap. The quick smoke
suite selects a small cross-section of those checks. Focused
selections also typically take seconds. Value
checks are batched into small programs: a controlled 674-case comparison reduced
compiler launches from 674 to 44 and test time from 73.49 to 7.93 seconds, while
retaining individual results and test selection. The local driver caches an
immutable current toolchain and stops at the first failure by default. Hosted CI
always starts from C and exercises language behavior, native/web programs,
editor integration, live reload and shared-core regressions.

CI also cross-builds standalone compiler bundles and executes 133 language smoke
checks, all 37 project-test checks, the editor transport check and a saved-file/
test-watch selection on Windows x64, macOS ARM64 and Linux ARM64. All three
native-host gates pass. This exposed and fixed Windows source-path
escaping, diagnostic path comparisons and formatter directory detection; it is
smoke coverage rather than the full Linux suite on every platform.
Windows tests now isolate failures and mutable globals by starting a fresh
process per test; Linux and macOS retain their fork path. Windows initialization
therefore repeats for each test. Test mode is established before imported
initializers, including headless window behavior and the original user arguments.

CI now publishes relocatable standalone downloads for Linux x86-64/ARM64,
macOS ARM64 and Windows x64, with SHA-256 sidecars and recorded build provenance.
Each native host extracts its package into a path containing spaces, compiles
and runs a native and web sample, and builds a generated game for both targets
with build tools removed from `PATH`. All four jobs and artifact uploads passed
at `353fa45d` ([CI run](https://github.com/david-andrew/dewy-lang/actions/runs/39140006944)).
See the [download instructions](../README.md); these are development toolchains,
not certification of every graphics driver or debugger integration.

VS Code now exposes resolved references and occurrence highlighting, including
shadowed locals, closures, interpolation and named arguments in unsaved files.
References cover the current program and other open programs; unopened reverse
dependents are not indexed yet, so project-wide rename remains disabled.
The outline recognizes top-level Dewy functions, generics, records, aliases and
bindings without requiring a successful check, including unfinished buffers.

Project tests also support `test --watch`, including name filters and release
builds, with a matching VS Code command. Saving a source, import or embedded
asset reruns the tests from fresh state; failed assertions and compile errors
leave the watcher ready for the next edit. This uses ordinary test compilation
and the existing dependency watcher. The focused watch/native-test gate passes
47 checks plus the editor task check; the core rerun workflow is now also
executed on the three additional native CI hosts. A later regression check
found and fixed missing-import tracking in test-watch mode, so creating a
missing import or its parent directories can recover without touching the tests.
Quitting or restarting test watch now stops the active test and its descendants.
POSIX interruption/termination forwards to the test process group, and Windows
test drivers use a job object whose closure terminates remaining descendants.
Native-host regression checks exercise cancellation, including a test that
would otherwise sleep indefinitely; the signal helper also passes the
independent C-bootstrap path.

The generated arcade, platformer and 3D starters now exercise menus, saved scores,
text tilemaps, slopes and one-way platforms, character physics and ray-cast shots.
Each includes project tests, with additional native/web simulation checks in the
gate. Browser play exposed and fixed a pointer-capture camera jump in the shared
input layer. A small headless 3D yard measured roughly 0.066 ms per simulated frame
in default native code and 0.214 ms under Node/wasm, excluding rendering; see the
[baseline and its limits](audits/2026-10-17/source-core/3d-yard-physics-baseline.json).

Numeric array work now includes fused dotted expressions and updates, CPU/GPU
broadcasting, matrix slices and eager comprehensions. Straight-line indexed and
value comprehensions preallocate their result; short eligible float loops use
SIMD in ordinary builds. Named allocation-inclusive float64 workloads now run
close to their C reference in default builds. The [language guide](../core/LANGUAGE.md)
links the paired measurements and documents the supported shapes, arithmetic
and fallback behavior. Native project test blocks and the editor's test tasks
support application development without using the compiler's Python gate.

Dotted unary `.-values` and `.+values` also fuse with array expressions and
calls. Floating negation now vectorizes through a sign-bit flip, preserving
signed zero and NaN payloads in native SSE2/AVX2 code. A 262,144-element,
64-iteration allocation-inclusive kernel improved from about 35 to 17 ms in
both default and release builds, alongside a 20 ms C reference. This also
fixes unary plus in GLSL and SPIR-V shader output. The
[unary broadcast validation](audits/2026-10-17/source-core/broadcast-unary-validation.json)
records CPU/GPU tests, raw timings and compilation costs.

`norm` and `hypot` now rescale extreme coordinates, avoiding premature infinity
or zero when intermediate squares exceed the float range. Floating `abs` also
clears negative zero. The 613-check independent-bootstrap gate includes a Python
numerical reference, native/web execution and float32 GPU implementations.
Ordinary array norms retain their measured throughput; robust scalar `hypot`
adds about 1–3 ns per call in this local pilot. The
[magnitude validation](audits/2026-10-18/scaled-magnitude-validation.json)
records that cost, numerical tolerances and graphics-platform limits.

Default-build performance is now a separate measurement target, alongside
release builds. Positive constant floor arithmetic lowers directly, and ordinary
builds expand tiny leaf functions before their single local optimization pass.
The recent fresh-build comparison measured about 35 ms for the tour, 236 ms for
native Netpong, 121 ms for web Netpong and 1.15 seconds for the compiler itself
(one emission worker, warm filesystem caches, no program cache). These are local
workload measurements, not universal budgets. The `constant-floor-*` and
`fast-inline-*` audits record runtime comparisons and their limits. The dictionary
graph workload remains a substantial performance gap; its C reference also uses
a different graph/table representation.

Recent warmed measurements put the tour build near 50 ms, the physics release
build near 300 ms and compiler self-build near 1.1–1.2 seconds. Sharing flat loop
metadata reduced the latter by about 7% in two paired comparisons. Small integer
conditional expressions now use conditional moves: the helper application
improved from 1.196 to 0.995 seconds in seven paired samples, at a measured 2.4%
compiler self-build cost. Removing redundant register copies then improved it
from 0.993 to 0.924 seconds in another seven-pair comparison, without a measured
compilation regression. Small 64-bit records now also stay in registers when their addresses do not escape;
focused integer/float record-update workloads improve about 11.8×/3.1×, with a
measured 1.8% compiler self-build cost and no broad application speedup claim.
Compilation and runtime changes are measured separately;
inconclusive experiments are removed. Continue application development on this
core while filling useful language gaps and improving measured bottlenecks. It
is still experimental, with explicit unsupported-feature diagnostics rather than
full old-compiler compatibility or release certification.

The 2026-10-18 target is roughly 250,000 Dewy lines/second for fresh builds and
generated code competitive with C/Rust. A new [throughput baseline](audits/2026-10-18/compile-throughput-baseline.json)
records source volume separately from phases and end-to-end wall/CPU time.
On the i7-6700, five samples put default tour/Netpong/Dunes builds at about
59/390/301 ms CPU, and the release compiler self-build at 1.93 s CPU. Those
applications contain only 34/348/484 loaded Dewy lines alongside 36–41k library
lines, many in unused lazy bodies. The compiler is still implementation-language
source. These workloads measure latency and existing implementation throughput;
they do not yet establish large-program Dewy throughput against the target.


A shared IR operand view now reads call arguments from their existing span and
keeps at most three ordinary operands inline. Optimizer passes and native/web
liveness analysis no longer refill temporary operand arrays, and their operand
classification is defined in one place. Five alternating fresh-build samples
([raw results](audits/2026-10-18/operand-view-compile.json)) measured CPU medians
of 59.21 → 57.99 ms for the tour, 393.34 → 376.74 ms for Netpong, and
1882.77 → 1839.07 ms for the compiler self-build (about 2–4% less CPU).
Wall times were noisy under other host activity and did not consistently improve.
The compiler bootstrapped independently from C; 321 focused native/web checks
passed, including indirect closures with stack arguments and live values.


The [conformance compilation baseline](audits/2026-10-18/conformance-throughput-baseline.json)
adds larger Dewy inputs without repeated padding: 128, 512 and all 893 existing
executable language cases, each in its own module. Their programs verify every
case's return value outside the compilation timer. Five-sample default-build
CPU medians were 330/614/918 ms, with 1,862/4,925/8,006 loaded Dewy lines
(including generated drivers and imported fixtures), plus about 36k implementation
lines. The all-case bundle contains 5,367 physical case-source lines and a
1,830-line driver. This is a conformance stress workload, not a game; it exposes
substantial distance from the throughput target, and keeps runtime correctness
attached to the measured build. Reproduce with `benchmark_corpus` in the
[development guide](../core/README.md).


The Dewy lexer and syntax projection now share integer node tags instead of
managed kind-name strings. Operator spelling tables are initialized once rather
than rebuilt while scanning each token. The [five-pair comparison](audits/2026-10-18/syntax-tags-compile.json)
measured 922 → 866 ms compilation CPU for the full conformance bundle in default
mode (6% less), and 1321 → 1261 ms in release mode (4.5% less). Small-app and
self-build differences were modest/noisy; this is not a general 6% speedup claim.
Source syntax and value semantics are unchanged. Validation includes an independent
C bootstrap, 191 native/web smoke checks, 213 formatter-related checks, and all
893 conformance cases executing successfully in both native build modes.

Local Dewy closures now use stack environments when all uses are direct calls
and the binding cannot be copied, returned, captured, addressed or reassigned.
Those calls also have a fixed target, allowing the ordinary inliner to see them.
Private snapshots and explicit shared cells keep their existing semantics;
escaping closures retain heap environments. Cleanup still releases managed
captures, including on early returns and loop exits.

A two-million-iteration local-counter workload measured **99.4 → 24.9 ms CPU**
in default builds and **77.2 → 20.3 ms** in release builds (about 74–75% less).
This is a narrow allocation/call benchmark, not evidence of C/Rust parity.
[Runtime samples](audits/2026-10-18/stack-closure-runtime.json) and
[compilation samples](audits/2026-10-18/stack-closure-compile.json) preserve the
sources and compiler hashes. Compilation CPU was essentially flat for Netpong
and the compiler self-build; the fixed 893-case conformance bundle increased
from 814 to 851 ms (4.5%). Wall times were noisy under unrelated host activity.
Eight new lifetime cases cover zero allocation, temporary call pinning, escaped
child callbacks, private/shared copies, fallback paths and loop cleanup.

The same lifetime proof now removes generic reference-counted destruction and
unnecessary invocation pins. Stack-local captures are destroyed directly at
scope exit; scalar-only environments need no destructor call. A separate
[five-pair comparison](audits/2026-10-18/stack-cleanup-runtime.json) against the
first stack-allocation commit reduced local-counter CPU from 25.7 to 8.0 ms
(default) and 19.8 to 5.5 ms (release). With an `@` argument, the corresponding
figures were 65.7 to 8.1 ms and 41.0 to 6.1 ms. This remains a microbenchmark.
Validation covers copied managed return values and private callable captures,
as well as the previous lifetime and fallback cases. The
[compilation comparison](audits/2026-10-18/stack-cleanup-compile.json) measured
867 → 843 ms CPU for the fixed 893-case bundle, with compiler self-build CPU
essentially unchanged (1838 → 1843 ms). The preceding stack-allocation commit
also passed the complete CI gate and all three additional native host checks.

Loaded modules now have a path-to-module index, replacing a linear scan on
every import lookup. This removes quadratic lookup work as module counts grow.
The [five-pair comparison](audits/2026-10-18/module-index-compile.json) was near
flat on existing workloads: tour 58.1 → 57.7 ms CPU, Netpong 378.1 → 376.4 ms,
893-case conformance 858.7 → 849.9 ms, self-build 1849.5 → 1863.7 ms. This is a
scaling fix, not a demonstrated broad throughput improvement. The 291 focused
import/module/smoke checks passed.

A [refreshed native application comparison](audits/2026-10-18/apps-target-baseline.json)
checks the C-level runtime target separately from compilation throughput. Five
alternating samples with thread-CPU kernel timing measured:

| Workload | Default Dewy (ms) | Release Dewy (ms) | C `-O2` (ms) |
| --- | ---: | ---: | ---: |
| Helpers | 1064.3 | 986.9 | 878.1 |
| Arrays | 301.2 | 275.3 | 271.8 |
| Records | 180.9 | 176.5 | 198.3 |
| Text | 293.1 | 287.8 | 231.9 |
| Graph | 831.0 | 625.2 | 535.7 |

The kernels verify matching results on boundary and measured inputs. Input
construction is outside the timed kernel; the C graph uses a different table
and flat neighbor storage. Host contention can still affect CPU frequency and
caches. These five workloads do not establish general C/Rust parity. Default
graph code and text scanning remain useful optimization targets.

Short byte comparisons now use bounded overlapping head/tail words, avoiding
a byte-at-a-time tail. String equality checks object identity first and reads
lengths directly after checking for nil. Nil and allocated empty strings still
compare equally. A new [string-equality workload](audits/2026-10-18/string-equal-runtime.json)
compares separately allocated payloads of varied short lengths, with embedded
zero bytes and differences throughout the payload. Five-pair CPU medians fell
from 211.5 to 166.6 ms in default builds and 204.3 to 166.8 ms in release builds
(18–21% less). C's pointer/length strings and libc `memcmp` took 52.5 ms, so
this workload still exposes a roughly threefold gap. The 414 focused checks
include native/web boundary cases, unaligned ranges and nil/empty equality.
The [compilation comparison](audits/2026-10-18/string-equal-compile.json) measured
850.9 → 837.2 ms CPU for the fixed conformance bundle and 1839.7 → 1803.4 ms
for self-build; small-app differences were mixed and wall times remained noisy.

Built-in string equality now borrows an indexed left value when evaluating
the right operand is only a direct read. Calls, custom getters, alias expansion
and potentially effectful index expressions retain the snapshot path. This
removes per-comparison retain/release traffic without changing evaluation order.
The [five-pair comparison](audits/2026-10-18/string-borrow-runtime.json) reduced
string-equality CPU from 166.4 to 143.1 ms (default) and 165.9 to 132.3 ms
(release); C remained about 52.1 ms. The 290 focused checks include right operands
that replace or free the left operand's array before returning a value.
The initial [unpinned compilation comparison](audits/2026-10-18/string-borrow-compile.json)
had large CPU-time variation and an apparent self-build regression. A
[seven-pair same-CPU follow-up](audits/2026-10-18/string-borrow-pinned-compile.json)
was essentially flat: self-build 1821 → 1806 ms CPU and the fixed conformance
bundle 839 → 841 ms. This change is retained for runtime improvement, with no
compilation-throughput gain claimed.

Editor checks now stop while running when their request is cancelled, their
document changes or closes, or the editor disconnects/shuts down. This adapts
Sloppy's `ef76b155b2eb968b0d78bf0c63e1bda4db56fbaf` cancellation work, with
nonblocking framed input, parsed envelope matching and preserved active-request
JSON state. Interrupted results do not replace diagnostics or reference caches;
completion restores its temporary source edits. Child processes are terminated
and reaped on both POSIX and Windows. Cancellation polls at most every 50 ms
on POSIX (Windows already polls every 5 ms); these are polling intervals, not
an end-to-end latency guarantee. All 89 local editor checks passed in 53.39 s.
The portable protocol regression waits until a deliberately delayed checker
starts, then requires cancellation within 1.5 s instead of its 3 s delay. It
also covers request IDs with escapes/Unicode, numeric versus string IDs,
rename errors, changed versions, disconnects, and fragmented headers/bodies.
The native-host CI selection includes this regression on every supported host.

The existing optimizer now carries conditions past terminating branches. For a
block with one conditional exit and a terminating tail, reaching the join proves
that exit was taken; additional branches disable this inference. This removes
repeated checks after guards without adding an optimization pass. Native/web
checks cover mutations, nested exits, NaNs and actual removal of the repeated
branch: 563 focused checks passed, followed by an independent C bootstrap and
211 smoke/optimizer checks. The [runtime measurements](audits/2026-10-18/return-facts-runtime.json)
show about 9% less default-mode string-comparison CPU time using the median of
corresponding candidate/baseline pairs; release-mode comparison and text scanning
are roughly flat. Separate medians exaggerate differences when CPU speed changes
between rounds, so the paired samples are the useful comparison here. The
[other applications](audits/2026-10-18/return-facts-apps.json) were within a few
percent of baseline. [Fresh compilation](audits/2026-10-18/return-facts-compile.json)
remained essentially flat: fixed 893-case corpus 831 → 826 ms CPU and compiler
self-build 1804 → 1816 ms. These are code-quality/runtime improvements, not a
claim of progress toward 250k lines/s on this sample.

## Matched Sloppy comparison, October 18

The previous self-build/corpus update did not establish the cost of the fork:
self-builds request release optimization, while Sloppy's advertised 250k LOC/s
is a default-build measurement. The new
[`benchmark_sloppy.py`](../tools/sloppy_core/benchmark_sloppy.py) compares the
same generated Sloppy source through both compilers, then an equivalent Dewy
program. Every generated function is called. Compiler binaries and libraries
are copied into scratch before measurement; the Sloppy checkout is read-only.
Shared-library rows use the same Dewy library for both compilers, separating
library growth from compiler costs. Dewy cannot use the unmodified Sloppy
library because it requires additional runtime helpers.

Five alternating fresh builds, one warmup, one emission worker, CPU affinity 2,
i7-6700; CPU time is child user plus system, not wall time:

| 2,000-function workload | Default CPU | Release CPU |
| --- | ---: | ---: |
| Sloppy compiler, Sloppy library, Jo source | 377 ms | 683 ms |
| Sloppy compiler, Dewy library, same Jo source | 381 ms | 680 ms |
| Dewy compiler, Dewy library, same Jo source | 558 ms | 605 ms |
| Dewy compiler/library, equivalent Dewy source | 991 ms | 962 ms |

The Jo program has 50,009 physical lines; the equivalent Dewy formatting has
44,005. Thus this host measured about **133k Jo lines/s** for Sloppy default,
not 250k. This does not invalidate a result on a different machine or compiler;
it establishes the local comparison. Library contents have little effect on
this workload. The same-source release path is faster in the fork, while its
default path performs extra local optimization, tiny-leaf inlining and limited
vectorization absent from Sloppy default. The separate Dewy frontend adds a
large cost, not explained by backend regressions or required value copies alone.
A check-only profile of the generated Dewy program had 1,378 samples, no losses:
224 in string equality, 77 in lexing, and substantial allocation/free traffic.
This supports replacing string-driven syntax processing with compact token/node
representations before pursuing more isolated runtime micro-optimizations.

A matched million-particle, 50-step kernel checks outputs at 0/1/17/1,000 and
1,000,000 particles. Its five-run thread-CPU medians:

| Generated program | Default | Release |
| --- | ---: | ---: |
| Sloppy / its library / Jo | 539 ms | 218 ms |
| Sloppy / Dewy library / Jo | 505 ms | 215 ms |
| Dewy / its library / same Jo | 188 ms | 174 ms |
| Dewy / its library / equivalent Dewy | 184 ms | 180 ms |
| C, `cc -O2` | 207 ms | 204 ms |

This workload retains the inherited dense representation and surpasses the
reference runtime; it is not general C parity. Dropping all default optimization
would sacrifice useful performance. Optimize the frontend and measure a cheaper
default pipeline against both compile latency and generated-code speed.
[Raw samples, source/library/binary hashes and checkout identities](audits/2026-10-18/sloppy-matched-baseline.json).
The recorded Sloppy checkout revision is metadata, not proof of the provenance
of its existing binary; the binary hash identifies what was actually measured.

Reproduce without modifying Sloppy:

```sh
taskset -c 2 python3 -m tools.sloppy_core.benchmark_sloppy \
  --dewy /absolute/path/to/dewy-core \
  --sloppy-root /var/home/david/dev/slop-lang \
  --output /path/to/comparison.json
```

## Numeric grammar tokens

Following the matched comparison, the in-process Dewy parser now classifies
operators and contextual keywords once into numeric token tags, then uses those
for precedence, grouping, flow and statement decisions. Finite grammar tests no
longer allocate temporary membership arrays. Identifiers/literals retain their
payload text, and whitespace, juxtaposition, generic-closer splitting, dotted
operators and spaced inverted comparisons retain their existing behavior. The
formatter still reads the same token text; no grammar restrictions were added.

Five alternating single-worker CPU pairs against `2dd67e51`:

| Fresh default build | Before | After | Median paired ratio |
| --- | ---: | ---: | ---: |
| Equivalent 2,000-function Dewy program | 963 ms | 837 ms | 0.866 |
| Same generated Jo program | 557 ms | 555 ms | 0.982 |
| Fixed 893-case conformance corpus | 828 ms | 788 ms | 0.948 |
| Tour | 57 ms | 57 ms | 0.999 |
| Netpong | 310 ms | 314 ms | 1.014 |
| Compiler self-build (release in source) | 1830 ms | 1851 ms | 1.002 |

The large Dewy workload improves about **13%**, and the conformance corpus about
**5%**; library-heavy small programs and the Jo path are effectively unchanged.
This does not reach the 250k LOC/s target. Wall times were affected by other work
on the host; use the recorded alternating CPU samples for this comparison.
[Samples and source/binary hashes](audits/2026-10-18/numeric-token-compile.json).

Validation: the initial numeric-token implementation passed 207 smoke checks;
the final implementation passed an independent C bootstrap and **all 5,757
compact-core checks**, with two test workers, in 310.32 seconds on the shared
host. This covers native/web, default/release, editor, formatter, reload,
networking and compiler tooling. The next allocation target is the temporary
syntax tree's separately managed child arrays.

## Reclaim temporary syntax per declaration

After projection, the compact AST and interned names own every retained part of
a declaration. The in-process parser now truncates the temporary syntax tree to
its sentinel before parsing the next top-level declaration, reusing capacity.
Previously every temporary node and its child array stayed alive until the
whole file was projected. No syntax IDs escape this frontend boundary.

Against the numeric-token compiler, five alternating single-worker CPU pairs
showed **848 → 815 ms** for the generated Dewy program (median paired ratio
0.967), and **833 → 781 ms** for the conformance corpus (ratio 0.937).
Peak RSS on the generated program fell from **162,964 to 132,244 KiB**, about
**19%**, with the same computed result. A larger experiment replacing child
arrays with one shared index buffer plus per-declaration reclamation measured
essentially the same memory and speed; it was discarded in favor of the smaller
lifetime fix. The report retains that experiment as the `arena` variant.
[Measurements](audits/2026-10-18/syntax-lifetime-compile.json).

The final compiler passed an independent C bootstrap and **3,965 syntax/value,
rejection, string, membership and frontend-selection checks** in 54.26 seconds
with two workers, covering native/web and default/release. The preceding numeric
token commit also passed the full Linux CI and Windows/macOS ARM64/Linux ARM64
host jobs.

## Keep syntax operators and decimal literals compact

Expression nodes now carry numeric operator tags directly, eliminating the
separate operator nodes and string lookups in projection. The optional legacy
parser still translates its original tree at its boundary. Decimal literals
retain one source spelling instead of serializing base/fraction/exponent fields
and then splitting and reconstructing them. Unsigned decimal accumulation uses
a constant overflow bound, with the existing exact-integer fallback above u64.
Scientific notation, underscores, explicit decimal prefixes, based literals,
negative literal patterns and literal coefficients retain their semantics.
This follows Sloppy's direct numeric-token/literal processing without adopting
its rejection of integers larger than 64 bits.

Five alternating CPU pairs measured the operator change at roughly 2–3% on the
large Dewy program and conformance corpus; small shifts also appear on Jo/control
workloads, so treat that isolated speed result cautiously. Removing decimal
serialization on top of it gives a clearer result:

| Fresh default build | Parent operators | Source literals | Median paired ratio |
| --- | ---: | ---: | ---: |
| Generated Dewy program | 800 ms | 735 ms | 0.907 |
| Fixed conformance corpus | 725 ms | 661 ms | 0.909 |
| Same generated Jo program | 543 ms | 537 ms | 0.989 |
| Tour | 54 ms | 54 ms | 0.985 |
| Netpong | 369 ms | 372 ms | 1.025 |
| Compiler self-build (release) | 1738 ms | 1687 ms | 0.973 |

The two large Dewy inputs improve about **9%**; small/library-heavy builds do not
show a consistent gain. Use the median of paired CPU ratios, rather than dividing
separate medians, because the shared host varies during the measurements.
[Operator samples](audits/2026-10-18/parent-operators-compile.json),
[literal samples](audits/2026-10-18/source-literals-compile.json).

A separate end-to-end comparison against the compiler from before this frontend
work (`2dd67e51`) measured median paired CPU ratios of **0.835 default** and
**0.836 release** on the generated Dewy program: about **16% less CPU time**.
The corpus ratio was 0.927; same-source Jo default, Tour, Netpong and the compiler
self-build were essentially flat (Jo release was 1.037). Peak RSS fell from
162,944 to 132,232 KiB, about **19%**, with the generated program's result unchanged.
The default build's 669 ms median CPU time is roughly 66k physical Dewy lines/s,
still far from 250k. These combined samples supersede any estimate obtained by
multiplying improvements measured in separate sessions.
[Combined measurements](audits/2026-10-18/combined-frontend-compile.json).

The operator/literal changes passed an independent C bootstrap and **5,759
checks in 234.15 seconds**, with two workers. Ten targeted literal/formatter
checks also passed, adding native/web coverage of explicit decimal prefixes,
scientific notation, coefficients, and u64/exact-integer boundaries. A follow-up
fix classifies all legacy token payloads, including juxtaposition nodes whose
kind has no compact equivalent, and preserves legacy combined call labels. Eight
representative legacy-parser programs produced the same correct results as the
previous compiler. The in-process smoke suite also passed all 207 checks.

## Dispatch punctuation directly

After the preceding changes, a fresh check-only profile had 952 samples and no
losses: 89 in lexing and 52 in string equality (down from 224 of 1,378 in the
original profile). The lexer now selects punctuation by its first byte, trying
only relevant longer spellings, and retains canonical token text instead of
allocating a one-character string for each punctuation token. Dotted operators
also dispatch on the following byte; nested generic closers before `=>` retain
their existing split. The formatter still sees the same token text.

Five alternating single-worker CPU pairs against `9bb7e669` measured **756 →
702 ms** on the generated Dewy program (median paired ratio **0.939**) and
**762 → 744 ms** on the conformance corpus (ratio **0.974**). Jo, Tour, Netpong
and the compiler self-build were essentially flat by paired ratios. These are
about **6%** and **3%** improvements on the two large Dewy inputs, without a
change to the language or optimizer policy.
[Measurements](audits/2026-10-18/byte-dispatch-compile.json).

Validation: **207 smoke checks** and **4,062 syntax/value, rejection, string,
membership, frontend-selection and formatter checks** passed. The focused run
took 35.53 seconds with two workers and covered native/web and default/release.

## Scalar tokens and interned identifier IDs

Like Sloppy's lexer, the Dewy lexer now interns identifiers from source spans
without allocating duplicate strings. Tokens carry scalar tags, name IDs and
source bounds, with no managed text field. Syntax conversion reuses those IDs
for ordinary names and materializes literal text only when consumed. Formatting
uses tags and original source spans; it does not intern document-specific names
into the compiler's persistent name table.

Interning names alone measured essentially flat CPU time and was not shipped as
a standalone speed optimization. Combining it with scalar tokens measured median
paired CPU ratios of **0.953** on the large Dewy program and **0.968** on the
conformance corpus against `b01623a2`, about **5%** and **3%** less time. The Jo
control and Tour were flat, Netpong was 0.976, and compiler self-build was 1.025.
These are small timing changes on a shared host, not a claim of universal gain.
[Interning-only samples](audits/2026-10-18/interned-names-compile.json),
[scalar-token samples](audits/2026-10-18/scalar-tokens-compile.json).

The memory benefit is clearer: three alternating builds measured median peak RSS
of **126,084 KiB before**, **115,840 KiB with name interning**, and **111,668 KiB
with scalar tokens**, an overall **11% reduction** relative to `b01623a2`.
Every generated program produced the expected result.
[Memory samples](audits/2026-10-18/scalar-token-memory.json).

Validation: an independent C bootstrap and **4,151 syntax/value, rejection,
string, membership, frontend-selection, formatter and editor checks** passed
in 67.56 seconds with two workers. Eight representative legacy-parser programs
also retained their correct results. Both preceding frontend commits passed the
full Linux CI and Windows/macOS ARM64/Linux ARM64 host jobs.

## Refreshed matched comparison after the frontend work

Seven alternating samples compare the pre-work `2dd67e51` compiler, the
C-bootstrapped `c8f993a6` compiler, and a fresh snapshot of Sloppy at checkout
`447ad81f`. Sloppy continued development during this work, so its fresh results
must not be treated as measurements of the original Sloppy binary/library.
All variants in this run use identical Jo or equivalent Dewy sources; binaries
and libraries are snapshotted and identified by hashes in the report.

| Fresh build, median CPU time | Default | Release |
| --- | ---: | ---: |
| Sloppy, its own library, Jo | 295 ms | 670 ms |
| Sloppy, shared Dewy library, Jo | 337 ms | 667 ms |
| Pre-work Dewy, same Jo | 518 ms | 584 ms |
| Current Dewy, same Jo | 538 ms | 587 ms |
| Pre-work Dewy, Dewy source | 950 ms | 947 ms |
| Current Dewy, Dewy source | 693 ms | 738 ms |

The median paired ratios are **0.741 default** and **0.777 release** for Dewy
source: **26%** and **22%** less CPU time. The same-Jo controls are 0.997 and
0.998, effectively unchanged despite variation in their separate medians.
Current default throughput is about **64k physical Dewy lines/s** on this
44,005-line input, versus about **169k Jo lines/s** for Sloppy's 50,009-line
formatting. Neither is a claim that the 250k goal has been achieved locally.
The shared release core remains about 12% faster than Sloppy on identical Jo.

The matched million-particle kernel retained its speed and correct checksums:

| Generated program, median thread CPU | Default | Release |
| --- | ---: | ---: |
| Sloppy / its own library | 529 ms | 187 ms |
| Current Dewy / Dewy source | 170 ms | 165 ms |
| C, `cc -O2` | 194 ms | 185 ms |

This is evidence for this workload, not general C parity. The frontend changes
do not trade away program speed. A callchain profile of the current full default
build attributes about 20% of samples to the Dewy frontend, 22% to function-body
checking, 17% to local optimization, and 15% to machine-code generation (some
categories overlap). Further progress needs to address the shared compiler as
well as the language frontend.
[Matched samples and checksums](audits/2026-10-18/sloppy-matched-frontend.json).

## Skip argument mapping for ordinary positional calls

The next change addresses shared type-checking overhead. Exact-arity positional
calls now reuse the supplied argument list instead of allocating parameter-name,
default-presence and remapped-argument arrays for each overload candidate.
Missing, named and defaulted arguments still use the existing mapper. Dewy call
ordering also returns immediately when the written arguments already occupy
the leading parameter slots; reordered named arguments retain their metadata.
Candidate type checking, overload selection and default evaluation are unchanged.

Seven alternating single-worker samples against `c8f993a6`:

| Fresh build | Median paired CPU ratio |
| --- | ---: |
| Generated Dewy program | 0.969 |
| Same generated Jo program | 0.979 |
| Fixed conformance corpus | 0.992 |
| Tour, default | 0.995 |
| Netpong, default | 0.987 |
| Compiler self-build, release | 0.973 |

The large programs improve about **2–3%**; smaller changes are close to the
measurement noise. These ratios are against the preceding frontend work, not
new overall measurements against the original compiler.
[Samples and binary/source hashes](audits/2026-10-18/positional-calls-compile.json).

Validation: 207 smoke checks passed, followed by an independent C bootstrap and
**all 5,763 compact-core checks** in 207.32 seconds with two workers. This includes
overloads, named/default argument evaluation order, native/web values and
rejections, formatter/editor, networking, reload and compiler tooling.

## Numeric storage paths during lowering

Loop analysis previously formatted local/global variables and nested field
selectors as strings such as `L123.0.2`, then compared those strings and their
prefixes. It now interns numeric parent/field edges for each lowered function.
Root identity includes the local/global distinction, equality uses canonical
IDs, and containment walks parent IDs. The table resets between functions;
IDs remain stable throughout nested loop lowering. Alias, escape and mutation
rules are unchanged.

Seven alternating single-worker pairs against `9371fef2` measured CPU ratios
of **0.9885** for the generated Dewy program, **0.9922** for its Jo equivalent,
**0.9908** for the conformance corpus, **0.9639** for Netpong, **0.9940** for
Tour and **0.9887** for the release compiler self-build. This is a modest gain,
about 1% on the large programs and 3.6% on Netpong.
[Compile samples](audits/2026-10-18/numeric-paths-compile.json).

Validation: 207 smoke checks and five new native/web/default/release behavior
and rejection checks passed. The new cases replace a nested record during an
indexed loop, retain whole-record copies before nested array writes, and reject
replacing an ancestor through a mutable call during mutable element iteration.
An independent C bootstrap passed **3,792 value, rejection and upstream checks**
in 27.81 seconds with two workers.

Five-sample thread-CPU comparisons retained the array, record and graph kernel
checksums in default and release builds. Candidate/baseline medians were
299/297 and 270/269 ms for arrays, 175/175 and 175/173 ms for records, and
803/818 and 613/618 ms for graphs. These are effectively unchanged runtime
results, not a generated-code speedup claim.
[Runtime samples](audits/2026-10-18/numeric-paths-runtime.json).

## Performance gates between stages

`tools.sloppy_core.performance_gate` pins the compiler/library sources at
`ea1cba0e`, compares each candidate with that reference and the preceding stage,
and reports fresh compilation and runtime separately. Its default nine paired
samples use approximate bootstrap intervals around median CPU ratios; uncertain
results fail the gate alongside detected regressions. Compiler/library manifests
are checked, generated throughput programs must return the expected result, and
all runtime kernels check boundary and full-size results against C. Absolute
targets remain separate from the no-regression decision. See the
[stage-gate instructions](../core/README.md#work-on-this-checkout).

The first full run rejected a small experiment caching operator name IDs and
deferring angle-warning formatting. Compilation changes were below 1%; four
runtime comparisons remained inconclusive despite approximately flat medians.
The compiler patch was reverted rather than spending more validation time on
that marginal experiment. The run measured about **84k root Dewy lines/s**;
release C ratios were 1.12 helpers, 1.01 arrays, 0.88 records, 1.24 text,
1.22 graph and 2.50 string equality. These identify outstanding work, not a
completed performance milestone. The rejected run predates adding the gate's
explicit throughput-program checksum check.
[Samples and assessment](audits/2026-10-18/call-dispatch-rejected.json),
[discarded compiler patch](audits/2026-10-18/call-dispatch-rejected.patch).

## Unshared global array storage

A closed-program scan now identifies global arrays initialized and subsequently
rebound only to fresh writable storage, with no whole-array copies or exposure.
Their indexed writes omit copy-on-write checks across calls. Element values can
still be copied independently, including nested managed fields. Ordinary shared
arrays retain detachment. Read-only constant arrays, destructured initializers,
unknown assignments, mutable arguments, raw addresses, aliases, slices and whole
array iteration conservatively disqualify the candidate. Watch/editor/REPL paths
and prelude globals are excluded from this closed-world proof.

The compiler benefits from its own analysis: its AST nodes and other private
metadata arrays do not need repeated uniqueness checks. An independent C
bootstrap produced the measured second-generation compiler. Nine alternating
pairs against the fixed reference measured **0.9818** CPU ratio on the large
Dewy default build, **0.9812** on Netpong, **0.9814** on Dunes and **0.9595** on
the fixed compiler self-build. Tour passed a 23-pair recheck at **0.9798**.
The large release build remained noisy on CPU 2, whose sibling also had heavy
background work; a separate 23-pair comparison on CPU 1 passed at **0.9621**,
with an approximate interval of 0.925–1.009. Both compilers ran on the same CPU
within each comparison. The initial and follow-up samples are retained.

All twelve native runtime artifact pairs are byte-identical after masking only
equal-width compiler bundle paths embedded in panic locations. Raw hashes,
masked hashes, path lengths and occurrence counts are recorded. This establishes
unchanged generated code for those kernels despite noisy timings; it is neither
a runtime speedup claim nor a requirement to preserve binaries on later changes.
The stage gate now recognizes this evidence. The initial run still measured
only about **66k physical root Dewy lines/s** under that host load, well short of
the 250k goal. Absolute results are not compared across host-load conditions.
[Stage samples, artifact evidence and final assessment](audits/2026-10-18/unique-global-arrays.json).

Validation includes fresh-storage writes, callback copies, constant rebinding,
slice-bound and iteration snapshots, mutable rebinding, destructuring and nested
managed element copies. The C-bootstrapped compiler passed 3,808 selected value,
rejection and upstream tests in 22.04 seconds, followed by 224 smoke checks in
5.13 seconds. The complete suite then passed **5,817 tests in 163.44 seconds**
with two workers, including the new native/web cases in default and release modes.

## Slice snapshots inside loops and shorter performance validation

A slice retains its source before evaluating its bounds. The older loop analyses
incorrectly treated that source as an ordinary indexed read. For example,
`xs[0..({xs[0]+=1; 1}))` inside a loop could change the retained source instead
of detaching, so the slice contained the new first element. The fixed reference
and preceding compiler both reproduced this error in default and release modes.
Both loop analyses now count a slice source as an escaping value. New tests cover
locals, globals and nested record fields, on native and web backends.

A separate experiment used existing uniqueness proofs to remove checks from
push, pop, insert, remove, clear, reserve, resize and extend. Its incremental
compilation benefit was small (roughly 1%), with several inconclusive comparisons
on the busy host. That optimization was discarded; the independent correctness
fix and mutation tests remain. The patch below contains only the discarded
intrinsic changes, relative to the retained slice fix.
[Rejected measurements](audits/2026-10-18/array-growth-rejected.json),
[discarded patch](audits/2026-10-18/array-growth-rejected.patch).

Performance validation now groups identical native artifacts before timing.
Every binary still receives boundary checks and one full-size checksum check;
only repeated timing samples are shared, explicitly labeled by
`timing_reused_from`. The six-kernel live check reduced the timing representatives
from seven to three per kernel, without sharing samples across separate runs.
Three-or-more-variant comparisons also rotate sampling positions, so one
compiler does not always occupy the middle of a round. Unit checks verify both
position balancing and that a bad full-size result in an otherwise identical
binary still fails validation.

The retained slice fix passed **3,840 selected value/rejection/upstream checks**
in 40.53 seconds; an independent C bootstrap passed **232 smoke checks** in
12.66 seconds. The performance-tool tests passed **55 checks** in 1.78 seconds.
A Linux guard-page pilot for the next string-comparison work also passes with
the current scalar implementation in default and release modes.
Thirteen rotating compilation samples passed against the fixed reference and
preceding stage, with one release/previous comparison resolved by a 23-pair
recheck (median ratio 0.997, approximate interval 0.979–1.008). All twelve
candidate runtime artifacts match both references apart from bundle paths.
The small-count artifact-grouping check is not used to claim runtime speed or
absolute target attainment.
[Validation and performance evidence](audits/2026-10-18/loop-slice-snapshots.json).

## Bounded native memory equality

The x86-64 backend now represents byte-range equality as one memory-reading
operation. It uses SSE2 for complete 16-byte blocks and overlapping 8/4/2-byte
head/tail reads for short spans. Every load remains inside the requested range,
including unaligned inputs and empty ranges ending at an inaccessible page.
The existing source implementation serves the C bootstrap, ARM64, web and debug
builds. Lowering selects the private runtime instance, so similarly named user
functions retain their own behavior.

This removes an extra helper call and a large intermediate loop body. The
inliner accounts for the operation's expanded size and loop behavior; general
inlining limits are unchanged. The optimizer recognizes its canonical boolean
result, while retaining separate reads across mutations. Backend checks cover
all three operands, spilled destinations and compare/branch alignment.

The earlier 16-byte-helper experiment crossed the release inlining limit.
Adapting Sloppy's newer boolean-value lowering gave only a small incremental
benefit here and did not restore inlining, so that adaptation was not retained.
The final operation leaves the portable library source unchanged.
[Independent experiment measurements](audits/2026-10-18/bounded-equality-experiments.json)
record those alternatives; their gains are not multiplied together.

The initial native-operation implementation passed **5,855 checks in 175.58 seconds**.
Subsequent branch-padding and inlining-cost changes each passed an independent
C bootstrap and all 246 quick checks. The cost adjustment produces the same
twelve benchmark executables as the padded implementation, apart from the
recorded equal-width compiler-bundle path strings. The matched 13-sample run
measured string-equality ratios of **0.813 default and 0.647 release** against
the previous stage. Release string equality remains **1.69 times C** on this
workload. The initial fresh-build rate was roughly **85k root lines/CPU-second**
on the busy host; the 250k target remains unmet.

A Linux child-process instruction counter gives an additional diagnostic for
host contention. Three rotating samples of the final compiler use about 1%
fewer instructions for the large default build and 0.2% more for the fixed
compiler self-build than the preceding stage. These counts describe compiler
work; timing comparisons still decide stage acceptance.

The final candidate passes the compilation and runtime comparisons against both
references. The 23-pair compilation recheck resolved all but Netpong versus the
previous stage; a separate 23-pair run on the original CPU resolved that result
at a median ratio of 1.0005 (approximate interval 0.9959–1.0036). The array-release
recheck also passes. All samples and intermediate inconclusive assessments are
retained. Rebuilding in the original benchmark source directory verifies exact
artifact equivalence to the full runtime run, masking only the toolchain prefix.
The final busy-host compilation recheck measured roughly 67k root lines/CPU-second;
absolute rates across these load conditions should not be treated as speedups.
[Final validation, raw measurements and assessment](audits/2026-10-18/bounded-native-equality.json).

## Constant-valued match dispatch

Dense integer and enum matches whose result arms are scalar constants now use
a compact read-only lookup table. The subject still evaluates once, holes and
out-of-range values use the wildcard arm, and effectful or converting bodies
retain ordinary control flow. Entries use the smallest sufficient signed or
unsigned width. The portable IR supports native and web targets; debug builds
keep their original branches. Overflowing key spans fall back to comparisons.

The new application benchmark dispatches ten million varying inputs through
24 constant-valued arms, with an algorithm-matched C implementation. An initial
nine-pair run reduced default CPU time from roughly **124 to 54 ms** and release
time from **123 to 40 ms**, versus about **36 ms for C**. This is a dispatch
improvement, not a claim of general C parity. The compiler's own operator
precedence lookup also becomes small enough for its existing inliner; diagnostic
instruction counts fall by about 0.3% on the large generated build.

The independently C-bootstrapped compiler passes **5,879 checks in 140.43 seconds**.
All 40 compilation/runtime comparisons pass against both the fixed baseline and
the preceding stage. Initial noisy measurements and focused follow-ups are
pooled without dropping samples: compilation comparisons use 32 or 55 matched
pairs, and runtime comparisons use 9, 32 or 45. The six existing runtime
workloads produce identical artifacts to the preceding stage after toolchain
path normalization. The new dispatch kernel's release time is about **1.06 times
C** in the full gate. Fresh default compilation measured about **89k root
lines/CPU-second** in that run; the absolute target remains unmet, and changing
host load prevents interpreting later absolute rates as compiler improvements.
[Validation, all samples and final assessment](audits/2026-10-18/constant-match-lookup.json).

Before this change, three isolated frontend storage experiments tried a flat
child arena, batched arena growth and four inline children per syntax node.
Their measured gains were too small to justify the representation change, so
none is retained. A compiler built from the preserved Sloppy seed also did more
work on the same sources than the current compiler. Both builds already use
release optimization. The [experiment audit](audits/2026-10-18/frontend-storage-experiments.json)
preserves patches, raw timing and instruction measurements for those rejected
approaches.

## Native string equality

Bounded native comparison now covers the complete private string-equality
operation. It checks pointer identity, nil/allocated-empty
equivalence and unequal lengths before reading payload bytes. The native
operation shares the bounded SSE2 and short-tail implementation. Other targets
and debug builds retain the portable library body. Default inlining keeps its
existing policy; release inlining charges the operation for the previous
helper's expanded size.

Single-use comparisons can feed native branches directly through their flags.
A small cleanup removes redundant single-instruction blocks left by inlining,
which otherwise separate the comparison from its consumer. The branch-only
prototype showed no meaningful application improvement; including the string
operation removes the larger null/length/result joins and produces the gain.

The independent C bootstrap passes 266 quick checks. The full suite passes
**5,887 checks in 211.67 seconds**, including native/web behavior, explicit
function-name shadowing, register spills and guard pages. The added string
checks cover every mismatch position, relative alignment, nil values, allocated
empty values and unequal lengths whose payload would cross an inaccessible
page. A nine-pair pilot of the independently rebuilt compiler measures runtime
ratios of **0.820 default and 0.728 release** against the match-lookup stage.
The full stage gate and focused rechecks pass all **40** comparisons against
both the fixed reference and preceding match-lookup stage. All samples are
retained: compilation has 23 pairs, runtime has 23–77 depending on the required
rechecks. Against the preceding stage, string equality takes **0.793× default
and 0.709× release CPU time**. Release remains about **1.17× C** on this kernel.
The initial fresh-build rate is about **82k root lines/CPU-second** on this busy
host; the 250k target remains unmet. Absolute rates across different host loads
are not speedup measurements.
[Raw measurements, compiler identities and validation](audits/2026-10-18/native-string-equality.json).

## Default value-parameter and loop borrows

The next stage applies the existing release-mode borrowing proofs to default
builds. Read-only value parameters can use their incoming storage, and loops
whose bodies cannot change their source can avoid retaining a snapshot. Mutation,
address-taking, shared/captured bindings and function-containing values keep the
existing copying behavior. Private closure state remains independent.

Six recursive AST visitors now visit their fixed children directly, avoiding a
temporary heap array at every visited node. The parser marks its synthesized
value-parameter bindings, so ordinary declarations skip parameter borrowing
analysis.

The initial independently bootstrapped prototype passes 270 quick checks.
A nine-pair runtime pilot measures **192 → 68 ms CPU** for default builds of the
new `managed_params` workload, which passes records and arrays through small
read-only helpers. Release artifacts are unchanged; its roughly 23 ms release
time still exceeds the C counterpart's roughly 15 ms. Default graph traversal
improves about 1%. The initial full suite passed 5,895 checks, but the stage
was withheld: its default text scanner regressed about 10%. Removing ownership
instructions changed loop layout, exposing the backend's fallback to 8-byte
alignment and comparison padding on loop back edges.

A matched 23-pair text experiment compares consistent 16-byte and 32-byte loop
alignment. Both pass against the accepted compiler. Although 32-byte alignment
improves the text scanner, its full gate exposes a 15% regression in release
value-parameter calls, so that policy is rejected. The next candidate uses
consistent 16-byte alignment only in default builds and retains release's
existing limited-padding policy. This candidate passes all 5,917 checks in
331.02 seconds with two workers after an independent C bootstrap.

The final stage passes all **44** compile/runtime comparisons against both the
fixed reference and preceding compiler, retaining every matched follow-up
sample. Default value-parameter calls take **0.352×** the preceding stage's CPU
time, and default text scanning takes **0.971×**. All eight release artifacts
are unchanged from the preceding stage after masking equal-width bundle paths.
Default compilation is effectively unchanged (1.003× on the large workload);
release compilation takes 0.984× and the compiler self-build 0.995×. The tiny tour
comparison needed a larger isolated sample on this contended host and settles
at 1.001×.

The full gate measures about **68k fresh root lines/CPU-second**; a later focused
run of the same compiler reaches about 83k under different host load. Neither
meets the 250k goal. Release value-parameter calls remain about **1.58× C**;
several other kernels also remain slower than C. These are measured intermediate
gains, not completion of the performance goals.
[Raw measurements, rejected prototypes and validation](audits/2026-10-19/default-value-borrows.json).

## Deferred compiler experiments, October 19

Reusing register-analysis arrays and rejecting scalar parameter borrows earlier
did not show a latency improvement, so neither change is retained. The pilot
did validate the runtime artifact certificate end to end: freshly compiled
programs passed their checksums and matched the accepted artifacts, allowing
runtime timing to be skipped without importing historical timing samples.
[Measurements](audits/2026-10-19/register-workspace-pilot.json).

An x86-64 prototype moves nonreturning bounds-failure paths after the ordinary
function body. It passes an independent C bootstrap and 300 quick checks,
including panic arguments under register pressure and correct failure locations.
All six compilation workloads improve against the preceding compiler, taking
0.913–0.955 times its CPU time. Managed-parameter calls also improve. However,
a focused 15-pair experiment confirms text-scanning regressions of about 3.5%
in default builds and 5.1% in release builds. Consistent 32-byte loop alignment
increases that regression to about 7%, despite helping release parameter calls.
Both variants are deferred; neither is an accepted performance stage. The audit
preserves patches and raw measurements for reconsideration alongside general
loop improvements. The full suite was not run after the performance failure.
[Experiments](audits/2026-10-19/cold-panic-experiments.json).

Batching native instruction bytes into unaligned word stores also passed
correctness checks on x86-64 and ARM64. Replacing resize-and-clear with reserve
and length adjustment reduced instruction counts by 0.36–0.71%, but a 15-pair
pilot showed essentially flat compile times, including the compiler self-build.
Both variants are deferred. Six encoding, copy-on-write and bounds tests remain
useful regression coverage for the original emitter.
[Measurements and patches](audits/2026-10-19/word-emission-experiments.json).

## Classify Dewy words by interned ID

The Dewy lexer now follows Sloppy's keyword-ID lookup: initialize the keyword
table once, then classify identifiers with an indexed lookup. Boolean literals
and question-mark word operators also use their interned IDs. This avoids
retrieving and comparing the same keyword strings at every occurrence. The
formatter keeps its noninterning path, so formatting a document does not add its
names to the persistent compiler name pool. Language behavior is unchanged.

An independent C bootstrap passes 292 existing quick checks; seven focused
checks cover query operators beside ordinary bindings named `is`, `isnt` and
`notin`, Unicode identifiers, contextual `test`, and formatting/execution on
native and WebAssembly. The final full suite passes **5,923 checks in 194.34
seconds**, with two workers.

All **44** performance comparisons pass against the fixed reference and the
preceding accepted compiler, retaining the initial 15 pairs and focused 31-pair
follow-ups. Large default compilation takes **0.980×** the preceding stage's
CPU time; release takes **0.984×**. Other build workloads are essentially flat.
All eight runtime workloads match the accepted artifacts in both build modes,
so the certificate skips repeated runtime timing while still checking every
binary at boundary inputs and full size. No historical timing samples are
substituted. Fresh C ratios are consequently unmeasured for this stage.

The run measures about **69k fresh root lines/CPU-second** on the shared host;
the 250k target and broad C/Rust runtime goal remain unmet. A fresh instruction
profile identifies repeated parameter-ownership body scans and native emission
as further costs to investigate.
[Validation, measurements and profile](audits/2026-10-19/keyword-ids.json).

## Share parameter ownership analysis within each function

Private value-parameter views now share one collection of direct writes and raw
storage exposures per function. The old implementation scanned the entire body
and created a temporary identifier node for each eligible parameter. The new
analysis preserves those checks in per-local flags; global and mutable-parameter
call-effect analysis retains its separate, broader rules. A mixed-parameter test
checks read-only arguments alongside raw-buffer access and mutable arguments,
including a later function whose analysis must start fresh.

An independent C bootstrap passes **306 quick checks**; the full suite passes
**5,933 checks in 229.72 seconds**, using two workers. All **44** performance
comparisons pass after focused rechecks of Netpong and Dunes, with every matched
sample retained. Large default and release compilation take **0.997×** and
**0.992×** the preceding stage's CPU time. These are small gains; the structural
benefit is avoiding repeated body traversals as parameter counts increase.

All eight runtime workloads retain their accepted artifacts in both modes and
pass fresh boundary/full-size checks. Runtime timing and fresh C ratios are
unmeasured for this stage. Fresh default throughput is about **72k root
lines/CPU-second** on the contended host, still well short of 250k.
[Validation and measurements](audits/2026-10-19/parameter-effects.json).

## Preserve owned values when exposing raw array elements

Writable `.data()` access now detaches the array at its actual storage path,
including nested fields and indexed arrays. The path's indices run once. A
checker flag keeps exposed locals out of borrowed record/parameter views and
marks private closure state as mutable for closure copying. Narrowed optional
bindings and explicit mutable-loop aliases resolve to their owning storage;
`$capture @name` continues to share the binding while preserving older value
snapshots.

Previously, these paths could modify other value copies or write into literal
storage. All **36** new focused checks fail on the preceding compiler and pass
with the fix, covering native/WebAssembly and default/release builds. Private
closure tests also repeat creation, copying and calls to check cleanup. The
independent C bootstrap passes **342 quick checks**, and the full suite passes
**5,969 checks in 155.44 seconds**, with two workers.

All **44** performance comparisons pass after targeted rechecks, retaining every
matched sample. Large default/release compilation is essentially unchanged
(**1.002× / 1.000×** the previous stage); all eight runtime workloads retain
their accepted artifacts and pass fresh checks. Fresh runtime-to-C ratios remain
unmeasured for these unchanged workloads. Programs using the corrected raw
storage paths intentionally change behavior; byte compatibility is not the goal.
[Regression evidence, validation and performance](audits/2026-10-19/nested-data-ownership.json).

## Use scaled addressing for small integer multipliers

The x86-64 emitter now writes products by 3, 5 and 9 directly with scaled
addressing, preserving wrapping 64-bit arithmetic. An initial version retained
an unnecessary input move and showed no clear gain; that experiment is retained
in the audit. The accepted version reads the input register directly.

The helper-call workload uses **0.960× default / 0.966× release** CPU time versus
the preceding stage. Release remains **1.084× C** in matched samples, so this
does not establish C parity. Large default/release compilation is unchanged
(**0.998× / 1.002×**), and all **44** stage comparisons pass, including focused
rechecks with every sample retained. Three runtime workloads retain certified
artifacts and pass fresh checks; the other five receive fresh timing samples.
The final assessment also uses matched C samples rather than dividing separate
medians, which can be misleading on this variable-speed host.

The independent C bootstrap passes **344 quick checks**; the full suite passes
**5,972 checks in 207.78 seconds** with two workers. New coverage checks signed
boundaries, random words, register pressure and actual instruction selection.
Fresh throughput is about **98k root lines/CPU-second**, below 250k. Host load
fell during these measurements; the absolute improvement over the preceding
report is not a compiler speedup. [Validation and all measurements](audits/2026-10-19/scaled-multiply.json).

## Fuse integer comparisons with conditional moves

Sloppy's `f9ba5a4` x86-64 compare/select emission is now adapted to Dewy. The
optimizer also selects the original operands of copy-only arms, avoiding two
extra virtual-register moves and exposing adjacent comparisons for fusion.
Lazy branches retain the existing restriction to cheap, pure integer operations;
floating-point comparisons retain their separate NaN-aware behavior.

Against the preceding stage, matched CPU ratios are **0.968× / 0.957×** for
default/release helpers, **0.972×** for default arrays, and **0.910×** for default
text scanning. Release helpers remain **1.039× C**; this is progress, not C
parity across the workloads. Compilation is essentially unchanged: large
default/release ratios are **1.001× / 0.993×**, with fresh default throughput
around **98k root lines/CPU-second** on this host.

The independent C bootstrap passes **347 quick checks**, and the full suite
passes **5,974 checks in 181.42 seconds** using two workers. New tests cover all
six signed/unsigned comparisons at integer boundaries, wide and zero arm values,
register pressure, and actual fused instruction selection. All **44** performance
comparisons pass after focused runtime rechecks; every initial and recheck sample
is retained. Match dispatch and managed parameters retain certified artifacts
with fresh correctness checks and no new timing claims.
[Validation, provenance and measurements](audits/2026-10-19/native-select.json).

## Deferred allocator experiment

An allocator-only adaptation from Sloppy `06a297d` tried denser size classes,
cheaper main-thread state lookup, and direct carving from fresh chunks. The
compiler self-build's peak RSS fell from about **237 to 220 MiB**, but seven
matched pairs showed no clear compilation-time gain. The graph pilot's release
median was **1.047×** the preceding stage, with uncertainty spanning the 2%
resolution boundary. This does not establish an acceptable performance gain.

The allocator changes are **deferred and reverted**, with the exact patch and
raw pilots retained. The prototype passed four native/web allocation checks and
351 quick checks; it did not proceed to independent C bootstrap or the full
performance gate. Four useful alignment, reuse-zeroing, growth, chunk-boundary
and C-ABI lookup checks remain, and pass on the accepted compiler in 3.02 seconds.
[Experiment and measurements](audits/2026-10-19/allocator-experiment.json).

## Deferred short-copy emission

A selective Sloppy `06a297d` port replaces short x86-64 `rep movsb` copies
with bounded scalar loads and stores. The isolated 1–16-byte workload uses
**0.628×** the preceding emitter's CPU time; medium and bulk copies are flat.
The independent C bootstrap passes 353 quick checks and the full suite passes
**5,980 checks in 139.10 seconds** with two workers.

The implementation is **deferred and reverted**: 43 of 44 performance comparisons
pass, but default match dispatch remains inconclusive after 108 matched samples
(**1.017×**, 95% interval **1.0145–1.0203×**). Its diagnostic kernel and classifier
have unchanged instructions apart from addresses; layout sensitivity is plausible,
not established. Further resampling is not the next step. The exact patch and
all measurements are retained, along with useful copy bounds and live-register
tests. This candidate does not become the next performance reference.
[Experiment and measurements](audits/2026-10-19/short-copy-experiment.json).

## Bounded Dewy lexer scanning

The Dewy lexer now retains its immutable source while scanning a validated byte
span. Explicit end checks still bound every lookahead, including interpolation
excerpts; quoted strings and source slices keep their checked string operations.
Identifier scanning reuses the existing Sloppy-derived byte-class table without
changing Unicode name classification.

The diagnostic large default build retires **1.03% fewer instructions**. In the
complete matched gate, default/release CPU ratios are **0.994× / 0.998×** against
the preceding stage; other compile workloads are essentially flat. All **44**
comparisons pass without rechecks. All eight runtime workloads retain certified
artifacts and pass fresh correctness checks; this stage makes no new C timing
claims. The loaded host measures about **71k fresh root lines/CPU-second** here;
that absolute rate is not comparable to a less-loaded run and remains below the
250k target.

The independent C bootstrap passes **355 quick checks**, and the full suite passes
**5,982 checks in 145.21 seconds** with two workers. New direct lexer tests check
20 independent cases with excluded prefixes/suffixes, interning and formatting
modes, and both native optimization modes. They cover token kinds, payloads,
byte spans, spacing, operators, numeric boundaries, Unicode and string excerpts.
[Validation and measurements](audits/2026-10-19/bounded-lexer.json).

## Bind parameter views before allocating their storage

Read-only Dewy value parameters now bind to borrowed storage before local-frame
allocation. This removes unused record slots and resets those bindings on every
lowering, including REPL reuse. Debug builds, private writes, captures and raw
buffer exposure retain the existing owned-storage safeguards.

The bounded default inliner now accepts nonreturning failure calls. A small
array reader can therefore inline while preserving its bounds check and panic;
ordinary returning calls still disqualify default leaf helpers. The managed-value
helper workload uses **0.596×** the preceding stage's default CPU time. Release
is unchanged and remains **1.559× C**, so this is not broad C parity. Early
parameter binding alone removed storage but did not measurably speed this kernel.

Large default/release compilation ratios are **0.993× / 0.995×**; the compiler
self-build is flat. All **44** performance comparisons pass without rechecks.
Seven runtime workloads retain certified artifacts with fresh checks; the
managed-parameter workload receives new matched default/release/C timings.
Fresh throughput on the loaded host is about **71k root lines/CPU-second**.

The independent C-bootstrap candidate passes **360 quick checks** and the full
suite passes **5,987 checks in 140.48 seconds**, with two workers. Added tests
cover frame storage, debugger locals, repeated REPL submissions, private copied
state, and actual native/web failure paths after inlining.
[Validation and all measurements](audits/2026-10-19/checked-parameters.json).

## Deferred operand-descriptor experiment

A compact table replaced repeated IR operand dispatch in an isolated compiler
prototype. Its transient operand view matched independent expectations for all
97 operations across 388 cases, and 360 quick checks passed. However, seven
matched pairs put large default/release builds at **1.001× / 0.999×** the accepted
compiler and its self-build at **1.005×**. Diagnostic instruction counts were
slightly higher. The prototype is **reverted**, with its patch and measurements
retained; it did not proceed to independent C bootstrap or a full stage gate.
[Experiment evidence](audits/2026-10-19/operand-shapes-experiment.json).

## Checked loop endpoints and portable REPL paths

Loop versioning now rejects overflowing endpoint arithmetic before selecting a
copy with bounds checks removed. Its exclusive upper endpoint is compared to
the array length as unsigned; a huge unsigned limit no longer looks negative
and incorrectly passes the proof. The original checked loop remains the fallback,
including legal wrapped indexes and failures after earlier side effects. Native
and WebAssembly tests cover both build modes, signed offset overflow, unsigned
limits, empty ranges, and valid negative starts.

The preceding macOS CI failure was a separate REPL path mismatch: a trailing
slash in `TMPDIR` produced a virtual-source key different from its normalized
lookup key. Insertion now uses the same normalization. The regression reproduces
on Linux as well, and the REPL value-copy test exercises trailing separators on
every host.

The independent C-bootstrap candidate passes **364 quick checks** and the full
suite passes **5,991 checks in 139.29 seconds**. Five focused checks pass after
strengthening the offset cases to exercise the optimizer's actual add patterns.
All **44** performance comparisons pass; only the small tour compilation needed
a focused recheck, with its original samples retained. Large default/release
compile ratios versus the preceding stage are **0.999× / 1.005×**. The fresh
default throughput measurement is **122k root lines/CPU-second** on this run;
host conditions differ from the earlier 71k run, so that difference is not a
compiler speedup. The 250k target and broad C parity remain unmet.
[Complete validation and measurements](audits/2026-10-19/loop-endpoints.json).

## Deferred additional global-load hoisting

An isolated port of Sloppy `cd6ead0`'s IR global/header-load hoisting passes
364 quick checks, but three Dewy pilots produce identical before/after IR in
both build modes: read-only global arrays, array updates, and raw-buffer updates.
The first two already benefit from Dewy's existing loop analysis; the raw-buffer
case still contains an ownership call that prevents the new pass from helping.
The port is reverted rather than adding analysis without a demonstrated benefit.
It did not proceed to C bootstrap or a full stage gate. The independent affine
indexing portion of the Sloppy change remains a separate candidate.
[Prototype and pilot evidence](audits/2026-10-19/global-hoist-experiment.json).

## Shifted-index loop proofs and vectors

The affine-index portion of Sloppy `cd6ead0` now supports checks involving a
counter plus invariant terms, including row-stride arithmetic. Dewy's endpoint
proof tests the unsigned first and last indexes of a nonempty counter interval;
it preserves legal modular arithmetic and retains the checked loop when the
index sequence wraps during the interval or exceeds the array.

Simple checked `i + offset`, `i - offset`, and `offset + i` memory indexes can
also vectorize. Their bases are shifted once, overlap guards remain, and indexes
used as data retain the scalar path. Vector trip checks use remaining distance
so counters near the integer limit cannot overflow a `counter + lanes` test.
The source-level range machinery and explicit value semantics are unchanged.

The new permanent `shifted_arrays` workload takes **0.130×** the preceding
release kernel time; its default artifact is unchanged. The focused pilot is
**0.877× C compiled with `-O3 -march=native`**. The stage suite retains its
established C `-O2` reference, against which this workload is **0.443×**; these
are distinct comparisons. All eight earlier runtime workloads remain in the
gate. This result does not establish C parity for the whole language.

All **48** stage comparisons pass after one focused record-release recheck,
retaining its original samples. Large default/release compile ratios are
**1.006× / 1.004×**, and the compiler self-build is **1.002×**, versus the
preceding accepted stage. Fresh default throughput on this run is about **101k
root lines/CPU-second**; host-dependent absolute figures still fall short of
250k. The independent C bootstrap passes **376 quick checks**, the full suite
passes **6,007 checks in 141.15 seconds**, and the strengthened vector/application
selection passes 12 checks. Coverage includes native/web, float32/float64,
SSE2/detected CPU paths, vector tails, overflowing endpoints, overlap fallback,
and observable first-failure order.
[Full evidence and retained recheck](audits/2026-10-19/affine-vectors.json).

## Reuse checker facts for private parameter views

The checker now records all direct raw storage exposure when checking it:
array/string data pointers, field/index addresses, and permitted internal header
casts. Lowering uses those facts together with existing write/capture/alias flags,
removing its extra walk over eligible function bodies. An instrumented comparison
passed all 6,007 existing tests before the duplicate walk was removed.

That comparison also exposed a false positive: Dewy initially marks every method
receiver as permitting mutation, even when the selected method is read-only.
The old parameter walk treated that permission as a write. Private read-only
parameters now stay borrowed through such calls. The new `method_params`
benchmark retains the original `managed_params` data and arithmetic, with method
syntax instead of free-function calls; both remain in the suite. It uses
**0.280× default / 0.262× release** CPU time versus the preceding stage (about
**3.6× / 3.8× faster**). Release remains roughly **1.6× C**, so C parity is open.

The independent C-bootstrap compiler passes **378 quick checks**, and the final
full suite passes **6,013 checks in 158.39 seconds**. Frame regressions cover both
field reads and read-only methods, including debug-visible owned storage.
All **52** performance comparisons pass after focused rechecks of default
compilation and release graph traversal; every original sample is retained.
Large default/release compile ratios are **0.981× / 0.984×** versus the previous
stage, and compiler self-build is **0.990×**. The initial stage's fresh throughput
is about **91k root lines/CPU-second** under varying host load, still short of
250k. This absolute number is not a comparison with earlier host conditions.
[Full evidence](audits/2026-10-19/checker-exposure.json).

## Deferred masked-index versioning

An isolated prototype used a constant bitmask as an unsigned upper bound for
array indexes, removing the repeated check behind one entry guard. It passed
382 quick checks after independent C bootstrap and all 6,017 full-suite checks.
A focused pilot suggested a 3% release gain, but the permanent method and
managed-parameter workloads did not reproduce a useful improvement. Four of
52 stage comparisons were inconclusive. The compiler change is reverted;
there is no reason to keep adding loop copies without a demonstrated benefit.

The tests retain negative/unsigned indexes, empty loops, conditional assignment,
shrinking arrays and effects before the first failure. The experimental patch,
identities and every sample remain in
[the deferred experiment](audits/2026-10-19/masked-checks-experiment.json).
The accepted compiler remains `94952e82`, whose four platform CI jobs passed.

## Deferred shared-builder word emission

A further word-emission prototype uses the runtime's existing buffer builder
once per word, avoiding the separate reserve/length/data operations of the
previous experiment. It covers x86-64, ARM64 and ELF byte writers, keeps explicit
little-endian byte stores, and passes 384 quick checks after independent C
bootstrap. Seven matched compilation pairs remain flat: default **1.000×**,
release **1.010×**, and compiler self-build **1.016×** (inconclusive).

The compiler changes are reverted. Additional 16/32/64-bit buffer tests remain,
covering unaligned positions, repeated growth, signed limits and retained
snapshots. No full suite or stage gate was run for this flat prototype.
[Patch and measurements](audits/2026-10-19/byte-emission-experiment.json).

## Compiler code-generation quality probe

A scratch C translation of the accepted compiler's scalar register IR establishes
meaningful code-generation headroom. Seven matched fresh-build pairs put the
C-optimized host compiler at **0.754×** accepted CPU time for default Dewy builds,
**0.747×** for release and **0.806×** for fixed compiler self-build. The matching
scalar-native build gives similar comparisons; retired instructions fall about
29%. This is useful evidence, but does not reach the 250k target by itself.

The C-built compiler passes 300 selected core quick tests, the language tour and
fresh generated-program/rebuilt-compiler output checks. Building this diagnostic
itself takes **219 seconds**, sequentially, with about **259 MiB** peak child RSS.
The normal native build path remains unchanged. This limited Linux x86-64 C
translator is a diagnostic, not another supported implementation. Its scope,
limitations, scripts, identities and measurements are retained in
[the code-quality probe](audits/2026-10-19/c-codegen-probe.json).

One concrete difference is dispatch: the native emitter jumps into a table of
jump instructions, whereas C optimization uses compact address tables and bit
tests. That gives the next native-backend experiment a measured motivation.

## Deferred relative branch tables

Two native table layouts were tested after the code-quality probe. Entry-relative
32-bit offsets reduced table size but regressed a computed-arm dispatch kernel:
**1.054×** previous CPU time in default and **1.046×** in release. A simpler
base-relative layout removed one address calculation but still showed no gain:
**1.022×** and **1.009×**, both inconclusive. Compiler changes are reverted.
Both variants passed independent C bootstrap and quick checks (384 and 387).
No full suite or stage gate was run for these unsuccessful pilots.

The new `branch_dispatch` benchmark remains: existing `match_dispatch` becomes a
constant-result lookup and does not exercise branch tables. Three retained tests
cover holes, duplicate targets, extreme keys, multiple tables and loop exits in
default/release/debug; they also pass on the accepted compiler. The stage now
covers eleven runtime kernels, or **56** fixed/previous comparisons including
compilation. [Patches and samples](audits/2026-10-19/relative-table-experiments.json).

## Resolve method effects from checked parameter modes

Read-only method calls now work inside mutable loops and parallel callbacks.
Previously, `loop @item in values {item+=values.first()}` was rejected as a
possible resize, even when `first` only read its argument. Lowering effect scans
mistook the receiver's syntactic permission to select a mutable method for the
resolved method's actual argument modes.

Direct calls now reuse the cached checked signature; indirect calls use their
function type. Writes, resizes, loop footprints, ownership, race/determinism
checks and closure argument pinning share that information. Source permissions
remain intact. Tests retain rejection of mutable arguments, indirect mutating
calls and hidden global resizing, and verify independent local/field/global
snapshots plus read-only captured methods in parallel callbacks.

Independent C bootstrap passes **402 quick checks**; the full suite passes
**6,041 checks in 153.98 seconds**, with two pytest workers. All **56** fixed and
previous-stage comparisons pass. Against the previous stage, paired CPU ratios
are **1.00454** for default compilation, **1.00190** for release and **1.00238**
for self-build: within the gate's resolution, not a compilation speedup. Three
initially inconclusive compilation comparisons retain all 15 original samples
plus 31 recheck pairs. Existing identical artifacts reuse their accepted runtime
evidence; the new computed-arm dispatch workload is measured. The throughput
and broad C parity targets remain unmet.
[Validation and measurements](audits/2026-10-19/checked-call-effects.json).

## Default optimization is a measured tradeoff

An isolated experiment disabled default vectorization, local optimization, or
all three default optimizer/inliner/vectorizer passes, leaving release alone.
Removing just vectorization saved little. Removing local optimization cut fresh
compile CPU time by about 20% on Jo and 14% on the large Dewy program, but made
six default application kernels roughly **20–130% slower**. For example, array
updates went from 312 to 526 ms, record updates from 209 to 344 ms, and text
processing from 284 to 639 ms. Outputs were checked against the same C references.
The current default therefore retains these passes; frontend representation
improvements avoid that generated-code penalty.
[Compile samples](audits/2026-10-18/default-passes-compile.json),
[runtime samples](audits/2026-10-18/default-passes-runtime.json),
[isolated variant identities](audits/2026-10-18/default-pass-variants.json).

## What the comparison establishes

Sloppy already has a compact per-function IR, dense aggregate storage,
native and web backends, a fast/default versus optimizing build split, and
substantial game/platform libraries. Its CLI, LSP and watch loop reuse its
compiler. Its C stage-zero compiler is an independent bootstrap implementation
of a smaller subset, rather than a second implementation of every feature.

Fresh single-worker builds on the i7-6700 development machine, three runs of
the existing Sloppy binary, fresh processes/output builds, OS caches retained:

| Program | Whole-build wall times |
| --- | --- |
| hello | 0.0336, 0.0339, 0.0723 s |
| Sloppy compiler | 1.6143, 1.3875, 1.2708 s |
| Rebound | 0.1619, 0.1612, 0.1634 s |
| Breakwater | 0.2114, 0.2173, 0.2175 s |

These use the source files' build settings, including the ordinary library:
the compiler requests release optimization; hello and the games use the
default development mode. They are not runtime results or a
line-count-normalized comparison of two different self-hosting workloads.
Sloppy's README/report source sizes and test counts
are already behind its current checkout; use the source and recorded binary
identity rather than treating those descriptions as current certification.

Dewy's existing records tell a consistent story:

- `bootstrap/PERFORMANCE.md` records a 36.4 s native self-build at the October
  3 checkpoint: time spread across frontend, validation, lowering and shared
  runtime helpers. A single emitter peephole cannot remove that whole cost.
- `benchmarks/apps/RESULTS.md` records October 4 native particle updates at
  4.57–5.78 times the C kernel time. The representation is an array of boxed
  records, with sharing checks on field writes. The C array is dense.
- `ROADMAP.md` records roughly 1.5 hours for a local gate and three hours for
  integration certification. The test harness repeatedly builds substantial
  portions of the compiler with Python. Forking bounds retained memory but
  does not remove that compilation work.
- Native-source checks are interwoven with a large mirrored Python suite,
  multiple emission routes, metadata generation and certification. Useful
  independence has become part of the innermost edit/test loop.

These Dewy numbers are **historical measurements**, not fresh results for
this branch. The installed September seed rejects today's library
(`linux/files.dewy`, `else` in a match), and the October 5 cached compiler
rejects newer explicit-copy source. The usable seed was recovered from
`../dewy-build-artifacts/integration-15e57975/native/`: its source manifest
matches the current compiler/library and its binary manifest verifies.
Its saved certification records all stages passing, including 6,496 tests
(13 skipped) in 6,954 seconds, and the complete integration in 10,445 seconds.
That is prior certification of the compiler revision, not certification of
the new test-harness changes. A redundant hosted recovery build was stopped
after this verified pair was found.

## Reuse boundaries

| Sloppy component | Intended use in Dewy | Constraint |
| --- | --- | --- |
| `compiler/ir.jo`, `opt.jo`, `inline.jo`, `loops.jo` | Compact function IR; separate cheap legalization from optional optimization | Preserve Dewy effects, ownership, numeric operations and checked obligations in lowering |
| `x64.jo`, `arm64.jo`, `wasm.jo`, executable writers | Backend/allocator algorithms and possibly substantial source reuse | These import frontend/lowering state; they are not a drop-in standalone backend today |
| `types.jo`, `lower.jo`, core containers | Dense concrete records, explicit layout/stride, cheap scalar calls and aggregates | Preserve value independence, resource hooks, borrows and array-growth invalidation |
| `lib/game`, `lib/web`, `lib/std` | Game/platform, audio, renderer, asset and numeric infrastructure | Isolate an ABI/runtime adapter; audit raw operations at the boundary rather than weakening safe code |
| CLI/LSP/watch/test workflows | One compiler pipeline serving build, check, editor and reload | Keep diagnostics/source identity and reload state compatibility explicit |
| benchmarks, expected-output tests, fuzzers, speed checks | Continuous compile/runtime budgets and independent expected behavior | Check every important workload; a geometric mean cannot hide a severe regression |

Sloppy's MIT code is reusable with its notices. Preserve third-party asset
licenses when copying libraries; its logo is not a Dewy asset.

Wholesale renaming is insufficient. Sloppy documents wrapping integers,
truncating integer division, bounds panics and a different type/generic system.
Dewy has richer type algebra, juxtaposition, refinements, proof/effect
contracts and lifecycle behavior. The current Dewy frontend is the best
available specification-by-example for those commitments. Runtime bounds
checks in Sloppy are not evidence that Dewy's proof obligations are satisfied.

## Execution sequence and decision gates

1. **Make each change cheap to check.** Native-built compiler test drivers,
   explicit focused tests, and retained hosted-seeded certification. Report
   cold driver construction separately from cache reuse. Initial budget:
   representative focused work under 60 s, eventually a core smoke gate
   under 30 s. Measure remaining long files before broad test rewrites.
2. **Build the performance-core experiment.** Pin a Sloppy revision on a
   separate branch and isolate its IR/code-generation/runtime boundary. Feed
   one existing Dewy scalar/record program through it with existing Dewy
   semantic checks. This first probe measures backend/runtime benefit **and
   the frontend cost still left**; it is not a fast-compiler claim. Use the
   particle workload, value-copy/alias/growth counterexamples and negative
   proof cases as acceptance tests. Do not attempt a whole compiler port
   before this integration boundary works.
3. **Make the semantic frontend fast.** If retained frontend/proof work
   dominates the probe, move its hot representation and passes onto compact
   IDs/arenas and bounded analyses in the new engine, retaining old compiler
   differential tests for the supported slice. Unused code may avoid emission
   but must still satisfy the declarations/contracts Dewy promises to check.
   One checked representation should feed effects, ownership and codegen;
   avoid repeated high-level tree reconstruction between those stages.
4. **Ship an application slice.** Floats, dense particles, useful closures,
   platform adapter and headless deterministic update/render test, then an
   interactive native/web game. Port a Sloppy example/library slice with
   measured build latency, frame time, memory and output correctness. This is
   the integration test for ergonomics and batteries, not another isolated
   syntax demonstration.
5. **Converge.** Move supported features in batches, preserving acceptance,
   rejection and behavior tests. Keep the old hosted compiler as a frozen
   reference for that scope and a bootstrap recovery route until a replacement
   is proven. Retire duplicate production paths only after coverage exists.

Proposed performance-core decision budgets: fresh hello build under 100 ms;
the small particle application under 250 ms; release particle updates within
1.5 times the C median at both large inputs; a small native/web game that
actually runs; ultimately a compiler self-build in a few seconds. These are
targets for the experiment, not claims or permission to drop language rules.
If the Sloppy boundary cannot deliver those benefits without compromising
semantics, keep the benchmark and backport the demonstrated improvements to
the current engine. The experiment must settle that question before a broad
source migration.

## Work started on this branch

`tests/python_misc/driver_artifacts.py` now accepts an explicit
`DEWY_TEST_DRIVER_COMPILER=/absolute/path/to/dewy`. Existing `isolated_codegen`
users gain native text emission, keeping the tests' own backend choices and
their hosted oracle calls. Shared checker, lowerer, program, stream and prelude
drivers build directly to executables, removing an additional hosted µDewy
pass. These execution-only drivers omit their own debugger metadata in either
mode; tests of user-program debugging retain their own options. Cache identities
include the native executable's bytes; invalid compiler configuration and
failed/missing emissions fail visibly. Every emission uses a fresh temporary
workspace. Tests explicitly requesting driver metadata use the text path;
the native debug CLI preserves requested locations and additionally generates
debug value metadata.

```sh
# Explicit test selection; no full-suite path is prepended.
DEWY_TEST_DRIVER_COMPILER=/path/to/current/dewy tools/certify.sh focused \
  tests/python_misc/test_bootstrap_type_interning.py

# Independent hosted route for the same selected checks.
env -u DEWY_TEST_DRIVER_COMPILER tools/certify.sh focused \
  tests/python_misc/test_bootstrap_type_interning.py
```

Integration certification explicitly unsets that override and disables driver
reuse, retaining its independent hosted-built coverage. The existing broader
`local` gate remains available. A focused pass is not release certification.

`benchmarks/apps/records.jo` is an algorithm-matched Sloppy counterpart of
the existing Dewy/C particle benchmark. `tools/compare_sloppy.py` builds all
four variants in fresh directories, runs every build at zero/one/small/large
sizes, requires matching checksums on every repetition, and writes JSON with
commands, compiler hashes, checkout state, cold compilation time, kernel time
and peak RSS:

```sh
python tools/compare_sloppy.py --dewy /path/to/current/dewy \
  --sloppy-root /var/home/david/dev/slop-lang --output /tmp/particles.json
```

No claim of completing the language, replacing the compiler, or certifying
the full suite follows from this first feedback-loop improvement.

Fresh measurements and validation logs are in
[`audits/2026-10-16/`](audits/2026-10-16/README.md). The matched particle
workload compiles in 1.702 s with Dewy, 0.037 s with Sloppy debug and 0.050 s
with Sloppy release. At a million records, medians are 711.7 ms (Dewy),
171.8 ms (Sloppy release) and 171.4 ms (C), with every checksum matching.
The current native Dewy compiler's cold self-build takes 39.0 s and 2.52 GiB
RSS in one new sample. These make dense representation and the whole compiler
pipeline concrete priorities; they do not imply every Sloppy subsystem is
already compatible with Dewy's semantics.

Validation of this first implementation: 47 focused tests passed with native
drivers and reuse disabled; the standalone 15-test harness suite also passes,
including its independent hosted build/run. Four unchanged kernel tests went
from 40.16 s with hosted driver emission to 14.72 s with native emission.
The full test suite has not been rerun for these harness changes. The next
implementation milestone is the bounded compiler-core experiment described
above.

The first bounded backend experiment is now implemented in
[`../tools/sloppy_bridge/`](../tools/sloppy_bridge/README.md). It runs the
unchanged particle source through Dewy's checks and runtime lowering, then
Sloppy's pinned register IR/optimizer/x86 emitter. Its 22 focused tests pass
in 10.59 s. This establishes an executable boundary without changing language
rules; it retains the old boxed layouts and frontend costs. It is opt-in,
Linux x86-64 only, and does not yet carry debug metadata or every intrinsic.

The completed probe now also compiles the full Dewy compiler. Its final
33-test acceptance selection passes with that Sloppy-built compiler, and it
rebuilds a native Dewy compiler byte-identical to the certified reference's
output. The Sloppy backend itself has an independent pinned C-seeded fixed
point. No compiler was installed or made the default.

The decision is to keep the boundary and move **above old runtime lowering**,
not ship a backend-only replacement. The final 450-run comparison improves
million-particle time from 710.5 to 609.4 ms with unchanged boxed layouts,
against 172.7 ms for Sloppy's dense counterpart. Cold builds remain slower
(1.99 versus 1.74 s), and the Sloppy-built Dewy compiler self-builds in 47.79 s
versus the reference's 38.21 s. Compact frontend data and typed dense aggregate
lowering remain necessary. See the
[full experiment evidence and next boundary](audits/2026-10-16/README.md#checked-dewy-through-sloppys-backend).

The first typed representation change now works: `DEWY_DENSE_RECORDS=1`
selects dense arrays of flat scalar records from checked HIR, before runtime
lowering. The same change feeds the native emitter and Sloppy bridge. It
reduces the million-particle native kernel from 702.6 to 435.6 ms and peak
process memory from 76.8 to 62.6 MiB in the matched comparison. Its 44-test
development gate passes. Compilation remains around 1.7 s cold; the remaining
runtime overhead and frontend cost still need substantial work.

This switch is an experimental implementation boundary, not a new language
feature. Resource-bearing records, subtype families, dictionaries, sorting,
and raw exposure retain the current representation for now. That fallback is
temporary scope control, not a commitment to preserve their internal ABI.

Entry setup for simple dense kernels now brings the native million-particle
result to **223.9 ms versus 698.7 ms boxed**, with C at 172.5 ms. The Sloppy
backend is slower on this version; retain the native emitter as the leading
path and reuse Sloppy ideas where measurements support them.

Checked native preludes now live in the user cache directory rather than in
each build directory. Fresh projects/tests reuse validated library inputs:
after one initial check, the tiny-program median drops from **1.662 s to
0.462 s**. Cold measurement tools still isolate the cache. A combined focused
gate passes 34 tests in 19.83 s. The remaining frontend cost—particularly the
allocation-heavy prelude restoration—still needs architectural work.

Warm tiny builds are now around **305 ms** in the latest comparison. Bounded
cache word reads, shared snapshot strings, and pruning unused runtime helpers
before normalization each remove measured work. Snapshot restore allocation
is down from 205.7 to 138.4 MB. These are useful intermediate gains; the
frontend still needs a more compact working representation and selective
analysis to reach the proposed 100 ms small-build budget.

Dense storage now also handles nested scalar records, so particle source can
use position/velocity vectors directly. The matched nested workload runs in
217 ms for a million particles versus 713 ms boxed and 172 ms C; it is within
1.5 times C at both large sizes. The direct CLI smoke gate passes 39 tests in
21 seconds. Building the compiler with the earlier flat dense representation
works but did not improve its self-build time; compact compiler metadata is
the next representation target.

Indexed binding pages improved an isolated lookup loop but not compiler build
time, so that representation experiment was discarded. Sharing the frozen
call graph and parameter effects across validation passes is retained: a
cold compiler-sized pilot fell from 38.89 to 37.72 seconds, with validation
itself down from 11.87 to 10.77 seconds. Small builds remain about 300 ms.
The next target is duplicate legalization/optimization work before native
emission; these incremental gains do not yet meet the restart's build budgets.
