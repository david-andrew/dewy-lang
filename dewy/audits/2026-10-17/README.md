# Compact-core development, October 17

## Direct Pool updates

Ordinary scalar updates through the bundled Pool's getter/setter pair now use
the item storage directly, with checked handles, array bounds and copy-on-write.
The compiler accepts only side-effect-free reads for the indices and right
operand. Custom accessors and complex expressions retain read/edit/writeback.
Compiler-generated helper lookup is qualified to avoid shadowing by user names.

The independent C bootstrap passes all 1,608 checks in 74.10 seconds.
[Build manifest](source-core/pool-direct-build.json),
[full gate](source-core/pool-direct-full-tests.log),
[82 focused checks](source-core/pool-direct-focused-final.log).

Seven alternating native release measurements of one million nested inventory
updates improved from **100.48 to 23.96 ms**, about **4.2×**. The program holds a
snapshot throughout; Python independently checks both its unchanged contents
and the updated inventory checksum, with zero/small-count preflights. Timing
excludes setup and checksums. This compares the same program across compiler
versions, not Dewy against C or native against web.
[Complete runtime samples, source and compiler/library hashes](source-core/pool-direct-runtime.json).

Seven warmed compile pairs were pool inventory 54.01/54.49 ms, entities
77.95/76.73 ms, physics 342.57/334.09 ms and compiler self-build
1,318.76/1,330.85 ms before/after. The small mixed differences do not demonstrate
an overall compile-time change. Raw wall and CPU samples are in
[the compile comparison](source-core/pool-direct-compile.json).

Reproduce with `python3 -m tools.sloppy_core.benchmark_pool`, supplying the new
compiler, `--baseline` and `--output`. The source is
[`pool_inventory.dewy`](../../../examples/sloppy_core/pool_inventory.dewy).

## Scalar expressions in Pool updates

The direct path also accepts checked scalar arithmetic, numeric conversions and
boolean expressions. Overloaded operators become calls during checking and keep
read/edit/writeback, including when nested inside an arithmetic expression.
Short-circuit expressions containing calls also retain that fallback.

The inventory example now adds `delta+1` inside the assignment, with the same
Python reference results. Seven alternating warmed native release samples gave
**140.82 / 37.01 ms** before/after, about **3.8×** for this expression workload.
Other projects were using substantial CPU (load average about 8.95), so these
absolute times should not be compared with the quieter earlier measurements.
No compile-latency conclusion is drawn from this run.
[Runtime evidence](source-core/pool-expression-runtime.json).

The fresh C bootstrap passed **1,621 checks in 103.18 s** under that contention;
the focused selection passed **58 checks in 3.38 s**. This includes float and
integer arithmetic, arithmetic indices, snapshots, overloaded-operator side
effects and short-circuit behavior, on native/web in debug/release.
[Build manifest](source-core/pool-expression-build.json),
[full gate](source-core/pool-expression-full.log),
[focused gate](source-core/pool-expression-focused.log).

## Exact-integer bit operations

`BigInt` now supports `and`, `or`, `xor`, `not`, `<<` and `>>`, with infinite
two's-complement sign extension and arithmetic right shift. The library converts
limbs while consuming them; input values remain independent and only the bitwise
result needs storage. Right shift detects discarded magnitude bits to round
negative values down, without constructing a power-of-two divisor.

Record `and`/`or`/`not` dispatch through ordinary named operator functions.
Boolean short-circuiting is unchanged. Shift compound assignments also work,
including nested indexed places. The lexer/parser splits `>>=` in a nested type
context so existing compact declarations such as `Pool<array<BigInt>>=[]` remain
valid.

An independent Python oracle checks 470 boundary/random inputs through 4,096
bits on native/web in debug/release. Additional cases cover mixed signed/unsigned
words, enormous right shifts, negative-count errors, index evaluation order,
snapshots, eager record-operand evaluation and allocation lifetime.
The focused gate passed **163 checks in 9.03 s**. A fresh C bootstrap passed
**1,649 checks in 97.20 s**, with other CPU-heavy projects still running.
[Focused gate](source-core/bigint-bits-validation.log),
[full gate with slowest-test timings](source-core/bigint-bits-full.log),
[build manifest](source-core/bigint-bits-build.json).

Seven warmed compile pairs gave CPU medians of 88.87/89.30 ms for exact integers,
94.86/95.83 ms for exact rationals, and 77.81/77.44 ms for the tour. Wall medians
were 96.46/113.91, 101.19/100.10 and 82.48/80.55 ms respectively; load averages
were around eight. The wall/CPU difference is a reason not to infer a compile
regression from this busy-host run. This is a feature addition, with no claimed
compile-time speedup. [Complete samples](source-core/bigint-bits-compile.json).

## Share membership and string test builds

Membership and string-result cases now use the existing isolated-module batching
fixture. Selected tests are grouped only after pytest selection, with at most 16
modules per program. Individual IDs and results remain separate. The constant
interpolation warning check retains a dedicated build. Runtime output is decoded
without newline normalization, and four new carriage-return checks exercise that
requirement across native/web and debug/release.

With the same compiler, the selected families improved from **112 checks in
11.71 s** to **116 checks in 2.68 s**, about **4.4×** for that selection.
Compiler launches fall from 112 to 12, despite the four added cases.
[Before](source-core/literal-membership-before.log),
[after](source-core/literal-membership-after.log).
Selecting one native debug case from each family passes just those two cases in
1.09 s: [selection check](source-core/batched-extra-selection.log).

All **1,653 checks pass** with the same independently bootstrapped compiler.
The whole run took 108.75 s while other projects were busy; this is correctness
evidence, not a controlled whole-suite speed comparison.
[Full log](source-core/batched-extra-full.log).
The aggregated [timing profile](source-core/validation-profile.json) identifies
further setup costs: the 76 exact-number panic checks still spend about nine
seconds compiling and launching separate programs.

## Share exact-number error builds

The 76 exact-number panic checks now share compilation in groups of at most 16
modules. A selector executes one case per fresh process, preserving its own exit
status, diagnostic and isolated globals. The runner is checked with two distinct
panics and a normal return on both native and web. Compile failures still fail
the batch; a missing or invalid selector is not treated as a successful test.

With the same compiler, the selected 76 cases improved from **13.88 to 6.43 s**,
about **2.2×**, with **76 compiler launches reduced to eight**. The broader
84-check selection, including the batch runner's success/failure checks, passed
in 8.83 s. Selecting one native debug invalid-rational case passed just that case
in 1.60 s. [Before](source-core/exact-errors-before.log),
[after](source-core/exact-errors-after.log),
[runner checks](source-core/exact-errors-focused.log),
[selection check](source-core/exact-errors-selection.log).

All **1,655 checks pass in 90.64 s** with the existing independently bootstrapped
compiler. The machine remains shared with other CPU-heavy work, so compare the
focused setup changes rather than attributing the entire whole-suite wall-time
difference to this patch. [Full gate](source-core/exact-errors-full.log).

## Counted stepped integer loops

Single loops and comprehensions accept `[first,second..end]` and
`[first,second..end)`, including descending and open-ended progressions.
Starting values and endpoints evaluate once in source order. Zero steps panic;
an open-ended progression reports exhaustion of its machine-integer type.
Combined stepped headers, stepped slices and stepped membership have explicit
unsupported diagnostics.

Bounded iteration computes an unsigned distance and trip count once, instead of
checking for wraparound on each step. This handles signed/unsigned endpoints
and step magnitudes across the full word without constructing an array. It also
reuses the existing array-path optimization. Ordinary unit-step loops retain
their existing lowering.

A Python oracle compares **1,216** bounded cases on native/web in debug/release.
Additional checks cover endpoint side effects, counter reassignment, `continue`,
comprehensions, snapshots, narrow words, zero steps and open-range exhaustion.
The independent C bootstrap passed **1,703 checks in 83.11 s**.
The final **48-case focused gate passed in 3.46 s**, including added early-break
prefix checks for progressions whose full mathematical length is 2^64.
[Build manifest](source-core/stepped-range-build.json),
[full gate](source-core/stepped-range-full.log),
[final focused gate](source-core/stepped-range-final-check.log).

Seven alternating native release measurements of a 30-million-iteration strided
integer accumulation gave **105.78 / 25.99 ms**, about **4.1×**, for the initial
per-step-check prototype versus the counted lowering. This is an implementation
comparison within the new feature, not a speedup over a released compiler or a
claim about every loop. Python checks the result independently, including
zero/small-count preflights. The report includes the complete program, runner,
compiler manifests and samples. The shared host's load average was about 7.67.
[Runtime evidence](source-core/stepped-range-runtime.json).

Seven compile pairs against the preceding compiler gave tour 64.36/57.39 ms,
physics 328.07/339.41 ms and compiler self-build 1,299.18/1,300.80 ms wall time.
CPU medians were 63.01/55.54, 323.81/333.66 and 1,279.58/1,286.11 ms. The mixed
differences do not establish an overall compile-time improvement.
[Complete compile samples](source-core/stepped-range-compile.json).

## Keep bounds checks when a range variable changes

A range's internal counter remains valid when its user-visible variable is
reassigned, but the latter no longer proves that an array access is in bounds.
The lowering now requires a stable loop variable before removing checks or
propagating its nonnegative range into nested loops. Array-path hoisting remains
available independently. Arithmetic on positive words no longer counts as a
nonnegative proof because a sum or product can wrap. Nested stepped loops are
excluded from unit-step assumptions.

The previous compiler returned an unchecked value for a one-element array after
`i=values.length`; the isolated [regression](source-core/loop-bounds-before.log)
records that failure. Checks now cover reassignment, references, record fields,
a prior valid read, nested starts, overflow and descending steps. They share
error-case builds and keep independent executions/results.

The focused gate passed **100 checks in 4.08 s**. A fresh C bootstrap passed
**1,739 checks in 57.67 s**. Whole-suite times vary with other desktop workloads;
this is a correctness change, not a claimed overall performance improvement.
[Focused gate](source-core/loop-bounds-focused.log),
[full gate](source-core/loop-bounds-full.log),
[build manifest](source-core/loop-bounds-build.json).

## Eliminate proved bounds checks in strided array loops

Ascending literal steps such as `[0,3..values.length)` now reuse the range
facts for ordinary loops. Both use the same implementation for array paths,
nonnegative indices and nested-loop checks. The facts require an unchanged
index and array extent; dynamic or descending steps retain runtime checks.
Native/web checks cover nested indices, record fields, saved lengths, empty
arrays, reassigned indices, resized arrays and retained snapshots.

Seven alternating native release runs update every third slot of a 12,288-item
array for 12,000 passes. The median fell from **44.81 to 24.55 ms**, about
**1.8×**. Python independently checks the complete final array checksum and the
unchanged snapshot, with zero/small-count preflights. The report contains the
full source, runner, compiler identities and individual samples. This is one
kernel, not an overall runtime claim. [Runtime](source-core/stride-array-runtime.json).

Seven compile pairs measured tour **54.55/54.45 ms**, physics **318.57/327.94 ms**,
and compiler self-build **1,203.62/1,203.31 ms** wall time. CPU medians were
53.37/53.39, 315.53/324.61 and 1,189.00/1,191.90 ms respectively. Physics was about
3% slower while the others were essentially unchanged; no compilation speedup
is claimed. [Compile samples](source-core/stride-array-compile.json).

The focused gate passed **124 checks in 4.66 s**.
[Focused gate](source-core/stride-array-focused.log).

The independent C bootstrap passed **1,763 checks in 57.90 s**.
[Full gate](source-core/stride-array-full.log),
[build manifest](source-core/stride-array-build.json).

## Unit ranges at integer limits

Single-header inclusive ranges no longer compute `end+1`, which overflowed at
the largest integer value. They count remaining iterations using unsigned word
arithmetic, including the full 2^64-value span. Open-ended single ranges use the
same count and report exhaustion of their integer type; a `break` exits normally.
The common exclusive loop keeps its existing comparison-based lowering.
Combined headers still have their separate parser lowering and are not included
in this boundary fix.

The earlier compiler fails the new [maximum-endpoint case](source-core/unit-range-before.log).
The focused gate passed **168 checks in 6.03 s**, including **238** Python-generated
unit ranges and the existing 1,216 stepped ranges on native/web in both modes.
Additional checks exercise all eight integer widths, endpoint evaluation order,
mutable indices, `continue`, open exhaustion and early exits from full spans.
[Focused gate](source-core/unit-range-focused.log).

Seven paired release runs of a 30-million-iteration inclusive accumulation
measured **17.25/15.45 ms** before/after; the strided array kernel remained close
at **24.10/24.34 ms**. Complete inputs and independent checksum checks are in the
[inclusive kernel report](source-core/unit-range-runtime.json) and
[array kernel report](source-core/unit-range-array-runtime.json).

Seven compile pairs gave tour **54.93/55.79 ms**, physics **321.20/322.27 ms**, and
self-build **1,230.01/1,218.33 ms** wall time. The corresponding CPU medians were
53.97/53.08, 316.95/317.49 and 1,218.74/1,198.40 ms. These small mixed differences
are not an overall compilation improvement claim.
[Compile samples](source-core/unit-range-compile.json).

The independent C bootstrap passed **1,807 checks in 59.46 s**.
[Full gate](source-core/unit-range-full.log),
[build manifest](source-core/unit-range-build.json).

## Discarded loop-analysis scratch experiment

An experiment replaced per-scan boolean arrays with reusable generation marks
and removed tiny child-list allocations. Seven alternating compile pairs gave
tour 48.05/49.19 ms, physics 289.93/293.25 ms, and self-build 1,101.75/1,093.93 ms
wall time. CPU results were similarly small/mixed. The experiment passed its
242-check focused gate, but did not establish a useful speedup and was reverted.
No scratch arrays or new generation state were retained in production.
[Samples](source-core/analysis-scratch-rejected.json).

## Combined range headers and longest-input iteration

Combined ranges now capture their starts once and stop at inclusive integer
maxima without wrapping. Open counters report exhaustion. A range followed by
conditions uses the single-range lowering; ordinary zero-based sequence indexes
retain their existing fast path. A condition before a binder continues to see
outer variables, including when the binder uses the same name.

Dewy also now exposes the core's `or` iterator headers: all inputs advance until
the longest finishes, with `none` for each exhausted input. An exhausted range
arm remains exhausted. Pure boolean `or` conditions keep their ordinary behavior.
The language guide describes these forms. The [previous compiler](source-core/combined-range-before.log)
fails the computed-start/evaluation-order case.

The focused **186-check gate passed in 7.38 s**, covering native/web debug/release,
integer widths, optional arms, string graphemes, snapshots, empty inputs,
conditions, source order, shadowing, and `continue`.
[Focused gate](source-core/combined-range-focused.log).

The fresh C bootstrap passed **1,864 checks in 61.63 s**.
[Full gate](source-core/combined-range-full.log),
[build manifest](source-core/combined-range-build.json).
Seven compile pairs with the final compiler measured tour **51.18/49.37 ms**,
physics **290.97/293.22 ms**, and self-build **1,108.23/1,097.61 ms** wall time.
CPU medians were 50.29/48.70, 288.44/290.69 and 1,100.55/1,090.44 ms. These small
mixed changes do not support an overall speed claim.
[Final samples](source-core/combined-range-compile.json).
An [earlier run](source-core/combined-range-compile-initial.json), before the
last shadowing guard, encountered substantially higher shared-machine load.

## Current compiler profile and discarded entry layouts

An instrumented copy of the current compiler, built outside the checkout,
separately times lowering, emission and five optimizer stages. Three runs per
workload put the self-build's median expression-reuse stage at **245 ms**, with
metadata at 92 ms, scalar replacement at 67 ms, dead-code work at 66 ms and cleanup
at 44 ms. These are instrumented wall-clock observations under varying desktop
load, not independent benchmark speed claims. The complete script and raw
phase logs are preserved in the [profile report](source-core/compiler-profile.json).
The installed and repository compilers contain none of this instrumentation.

A 64-byte entry record was tested in place of the expression table's ten parallel
arrays. Its 332-check focused gate passed. Seven compile pairs for the
constructor-assignment variant measured tour **54.63/52.30 ms**, physics
**303.61/307.08 ms**, and self-build **1,164.21/1,151.73 ms** wall time. A second
variant wrote fields in place to avoid whole-record temporary copies; it measured
**51.41/51.04**, **301.97/298.20**, and **1,136.38/1,123.12 ms** respectively.
Neither established a substantial, consistent benefit. Both were reverted;
the simpler existing implementation remains. [Constructor variant](source-core/cse-entry-rejected.json),
[field-write variant](source-core/cse-entry-fields-rejected.json).

## Contextual array comparisons and operand snapshots

Dewy equality/inequality now uses a typed array operand to provide element
context for a literal on either side. This covers narrow/unsigned words,
floats, nested arrays, optional arrays, BigInt and record elements. Literals
outside the element range and incompatible constructed arrays still fail.
Checking the typed operand first does not reorder runtime evaluation.

The side-effect cases also exposed an existing lowering error: a right operand
could mutate a local array or record before the left operand had been retained
or copied. Binary operations now use the existing mutation analysis for managed
values and aggregate equality, including explicit references, intrinsics and
assignments. Keeping an object's reference also freezes its mutable register;
string/array concatenation follows the same order. The old compiler fails the
[record and concatenation regressions](source-core/array-equality-before.log).

The **56-check focused gate passed in 1.55 s**, on native/web in both modes.
[Focused gate](source-core/array-equality-focused.log).
Seven paired builds measured tour **50.56/51.64 ms**, physics **295.55/298.75 ms**,
and compiler self-build **1,143.13/1,140.06 ms** wall time. CPU medians were
49.71/50.53, 293.13/296.22 and 1,133.30/1,131.07 ms. This is a language/correctness
change, with small mixed timing differences rather than a claimed speedup.
[Compile samples](source-core/array-equality-compile.json).

The fresh C bootstrap passed **1,896 checks in 62.85 s**.
[Full gate](source-core/array-equality-full.log),
[build manifest](source-core/array-equality-build.json).

## Scalar, vector and matrix operand values

Binary expressions now capture a scalar left value before evaluating the right
operand, reusing the existing argument-capture operation. Vectors and matrices
use the same mutation analysis and aggregate copying as record equality. This
fixes ordinary expressions such as `x + {x = 2; 3}` reading the new value of `x`.
The [previous compiler fails all four regression groups](source-core/operand-values-before.log).

The focused native/web debug/release gate passed **48 checks in 1.82 s**.
[Focused gate](source-core/operand-values-focused.log). The independent C bootstrap
passed **1,912 checks in 61.24 s**. [Full gate](source-core/operand-values-full.log),
[build manifest](source-core/operand-values-build.json).

Seven compile pairs measured baseline/candidate wall medians of **77.28/71.08 ms**
for the tour, **302.46/305.45 ms** for physics and **1,302.42/1,285.48 ms** for
self-build. CPU medians were 75.10/64.62, 296.73/299.38 and 1283.63/1272.17 ms.
These mixed results under variable desktop load do not establish a compiler
speedup. [Compile samples](source-core/operand-values-compile.json).

Five paired application samples retained matching checksums against independent
C implementations. Baseline/candidate medians were helpers **1207.40/1211.21 ms**,
arrays **272.88/252.81 ms**, records **163.41/164.88 ms**, text **372.35/288.65 ms**
and graph **612.58/591.19 ms**. This correctness change shows no broad runtime
regression in these workloads; the varying host load limits stronger claims.
[Runtime samples](source-core/operand-values-runtime.json).

## Optional generic suffixes

The fast frontend now reads `array<uint16>?` and nested
`array<array<uint16>?>?` types in declarations, parameters and returns. The
closing generic angle is split from its adjacent optional suffix. A spaced
` >? ` inside an angle-bracket refinement remains a comparison.

The focused native/web gate passed **281 checks in 5.17 s**. The fresh C
bootstrap passed **1,920 checks in 71.62 s**.
[Focused gate](source-core/optional-generic-focused.log),
[full gate](source-core/optional-generic-full.log),
[build manifest](source-core/optional-generic-build.json).

## Conditional moves for small integer expressions

The optimized IR already inlines the helper workload's hot functions. Increasing
inlining limits would not address its remaining branches. A bounded cleanup now
recognizes small integer value conditionals after inlining and emits an integer
selection operation. x86 uses `cmovne`, ARM64 uses `csel`, and web uses Wasm
`select`. Only cheap, nontrapping arithmetic is speculated; memory reads, calls,
division, managed values and observable writes retain their conditional paths.
The join writes are renamed before selection, preserving overlapping operands.

The **196-check focused gate passed in 6.09 s**, including side effects, lazy
unselected paths, narrowing and a Python oracle for 272 boundary/random results
per mode/target. The oracle executes on native, web and ARM64 under QEMU and
checks that the release helper actually contains selection IR.
[Focused gate](source-core/integer-select-focused.log).
The independent C bootstrap passed **1,942 checks in 59.28 s**.
[Full gate](source-core/integer-select-full.log),
[build manifest](source-core/integer-select-build.json).

Seven paired full application measurements show the helper kernel improving
from **1,195.65 to 994.79 ms (16.8% less time)**, versus C at 802.60 ms. The
earlier three-pair trial measured 1,196.26/994.06 ms. Every checksum matches the
independent C implementation. Other baseline/candidate medians are arrays
**246.53/245.40 ms**, records **167.99/164.80 ms**, text **263.10/261.44 ms** and
graph **595.42/588.91 ms**; these small differences are not claimed as speedups.
[Full runtime samples](source-core/integer-select-runtime.json),
[initial trial](source-core/integer-select-runtime-initial.json).

The tradeoff is a small compilation cost. Seven pairs measured tour
**49.90/50.20 ms**, physics **293.51/295.44 ms**, and compiler self-build
**1,124.38/1,151.57 ms** (about 2.4% slower) wall time. CPU medians were
48.81/49.22, 290.51/291.35 and 1,111.18/1,137.78 ms. The transformation has a
fixed 32-instruction search limit and an eight-operation speculation budget.
[Compile samples](source-core/integer-select-compile-initial.json).

## Discarded floor-arithmetic mask trial

A branch-free sign correction for signed floor division/modulo passed the
90-check arithmetic/application selection, but three paired runtime samples
made helpers slower (**997.55/1049.25 ms**). Text was effectively unchanged
(**285.84/282.25 ms**) under varying load. The trial was reverted; ordinary
branches remain in these helpers. [Samples](source-core/floor-mask-rejected.json).

## Reuse allocated registers for integer selection

The x86 selection emitter now reads its true value and condition directly from
their allocated registers, loading scratch registers only for spilled/constant
operands. The false value stays in a reserved scratch register until all operands
have been read, so overlapping result/input allocations remain safe.

The **126-check focused gate passed in 3.77 s**. The fresh C bootstrap passed
**1,942 checks in 61.83 s**. [Focused gate](source-core/select-registers-focused.log),
[full gate](source-core/select-registers-full.log),
[build manifest](source-core/select-registers-build.json).
Seven paired helper runs improved **992.67 to 924.04 ms**, about **6.9% less time**,
with C at 789.15 ms and all checksums matching.
[Runtime samples](source-core/select-registers-runtime.json).

Seven compile pairs measured baseline/candidate tour **49.24/49.38 ms**, physics
**299.79/294.43 ms**, and self-build **1,164.64/1,121.82 ms** wall time. CPU medians
were 48.54/48.67, 296.27/290.92 and 1150.80/1109.24 ms. These show no compilation
regression in this run; host load and the different workload sizes limit broader
claims. [Compile samples](source-core/select-registers-compile.json).

## Live-reload dependencies through initializer helpers

A global initialized by `decode()` previously stayed stale when `decode` read
an embedded global asset that changed. The watcher rebuilt and patched code,
but did not know to rerun the derived initializer.
[Reproduction on the preceding compiler](source-core/watch-helper-before.log).

Initializer discovery now follows statically resolved calls, collecting global
reads and asset inputs together. It scans each function specialization once per
initializer, so recursive helpers terminate; paths inside imported helpers use
the helper's module. Changed dependencies initialize before their consumers.
Creating a closure does not execute its body, and changing assets used by a
closure preserves its captured state. Arbitrary indirect calls remain opaque.

The watch gate passed **18 checks in 20.75 s**. It covers local/imported recursive
helpers, assets embedded in helper bodies, repeated replacements with stable
allocation counts, asset deletion/recovery, and counters/closures retaining state.
[Focused gate](source-core/watch-helper-focused.log). The fresh C bootstrap
passed **1,947 checks in 89.79 s**. [Full gate](source-core/watch-helper-full.log),
[build manifest](source-core/watch-helper-build.json).

## Discarded specialization for positive literal divisors

A second floor-arithmetic trial specialized positive non-power-of-two literal
divisors using reflected unsigned magnitudes. It passed the fresh C-bootstrap
gate (**1,947 checks in 76.89 s**) and the independent integer oracles, including
additional literal divisors. [Trial gate](source-core/floor-positive-full.log),
[trial build](source-core/floor-positive-rejected-build.json).

Text improved in three comparisons: **396.97/362.72 ms** (three pairs),
**389.72/327.96 ms** (seven pairs), then **259.42/243.23 ms** (five pairs using
the C-bootstrapped candidate). Shared-machine load varied substantially between
runs. The final full application comparison showed costs elsewhere: arrays
**239.52/253.04 ms** and graph **591.17/622.16 ms**; helpers **916.76/914.24 ms**
and records **161.97/161.22 ms** were close. All checksums matched C.
[Initial run](source-core/floor-positive-runtime-initial.json),
[repeat](source-core/floor-positive-runtime.json),
[final applications](source-core/floor-positive-runtime-final.json).

Seven compile pairs also put self-build at **1150.76/1189.41 ms** wall and
1129.47/1169.60 ms CPU; tour was **49.70/49.74 ms**, physics **344.01/339.86 ms**.
[Compile samples](source-core/floor-positive-compile.json). The mixed application
tradeoff and compiler cost do not justify another arithmetic specialization.
The implementation was reverted. The expanded independent arithmetic oracle
remains; its eight native/web checks pass on the restored compiler in 2.80 s.
[Restored implementation gate](source-core/floor-positive-restored.log).

## Dunes: procedural game and real shader validation

The pinned Sloppy Dunes game now runs as Dewy on native and web. Its terrain,
robe/scarf/banner meshes, sand/shadow and beacon shaders, movement, gliding,
collectibles and audio are in `examples/sloppy_core/dunes.dewy` and
`dunes_model.dewy`. The initial player/camera heights follow the terrain, fixing
an initially underground view. The source retains MIT attribution.

Running the game in WebGL exposed an invalid shader parameter copy: Dewy's
ordinary value parameters introduced local copies of uniform records containing
samplers, which GLSL cannot assign. The GLSL emitter now aliases read-only copies
of immutable parameters; changed or addressed values retain their copies.
An offscreen EGL/GLES3 test compiles and links generated shaders with the actual
driver, including nested texture records, texture helper parameters and mutable
numeric fields. CI ensures that the driver is installed; local runs skip these
two tests if unavailable. Browser rendering also verifies the complete game.

The shader work exposed a reference parser bug: `@point.x`, `@items[i]` and
`@items[i].x` marked only the base name. References now include the full postfix
place. Tests verify caller mutation, independent snapshots and one evaluation of
an index expression on native/web in development/release builds.

All 14 shader/reference regressions fail on the preceding compiler.
[Before](source-core/dunes-before.log). The **21 focused checks passed in 5.08 s**,
including geometry bounds/normals, animated meshes, the native software renderer
and web module validation. [Focused gate](source-core/dunes-focused.log).
The fresh C-bootstrap gate passed **1,968 checks in 127.04 s**.
[Full gate](source-core/dunes-full.log), [build manifest](source-core/dunes-build.json).
This is correctness and rendering evidence, not a frame-rate comparison.

Seven warmed sequential builds measured **452.27 ms native / 270.96 ms web**
median wall time, with **432.17 / 233.77 ms** CPU time. Shared-machine load was
high; these are current build observations, not before/after improvements.
[Compile samples](source-core/dunes-compile.json).

![Dunes in WebGL](source-core/dunes-web.png)
![Dunes in the native software renderer](source-core/dunes-native.png)

Live shader editing is also checked with a 64×64 software-rendered scene. Editing
an imported fragment shader changes the sampled pixel from red to blue to green,
recreates the generated GPU program, and preserves the running frame counter.
The focused check passed in **4.15 s** on the busy development host.
[Reload gate](source-core/shader-watch.log). This exercises actual rendered colors
and resource replacement rather than matching generated shader text.

## Discarded remainder-sign simplification

A smaller arithmetic trial selected a strict remainder sign test from the
divisor's sign, removing the separate zero comparison. It passed **28 arithmetic
checks in 5.54 s**, including native/web signed/unsigned boundaries and zero
divisors. Five paired runs showed no text gain (**402.28/403.92 ms**) and a helper
regression (**1404.40/1661.60 ms**). The shared host was busy; the results do not
justify keeping the change. The original helper was restored exactly.
[Focused gate](source-core/remainder-sign-focused.log),
[runtime samples](source-core/remainder-sign-rejected.json).

## Read-only calls through mutable parameters and dictionary discovery

Release builds now borrow a value reached through a mutable parameter when a
direct callee writes no globals, invokes no unknown code, and later arguments
cannot change that parameter. Shared/captured/aliased places remain conservative,
as do calls with mutable arguments. This reuses the existing write analysis;
it introduces no language annotations or proof obligations.

The motivating case was a dictionary passed to its read-only lookup helper.
It previously copied the six-field map and retained/released its managed arrays
on every call. The new lowering removes that snapshot. A focused two-million-
lookup workload over 64 entries, half hits, improved from **63.64 to 21.25 ms**
median thread CPU time in seven alternating pairs, about **3× faster**. The
expected hit count is independently calculated, including boundary preflights.
[Input source, compiler identities and samples](source-core/borrow-mut-probe.json).

Checking this optimization exposed a missing implicit call in write analysis:
custom string formatting can change a previously evaluated argument. The
prototype's native/web release runs returned the changed array value instead of
its snapshot. [Reproduction](source-core/borrow-mut-formatter-before.log).
Formatting pairs now contribute their resolved calls; nested field formatting
and foreign calls are conservatively opaque. Tests use a grown, uniquely owned
array so literal storage cannot hide the bug. They cover direct/global/callback
writes, later arguments and nested formatting. **24 focused checks passed in
2.23 s**; the C-bootstrapped compiler passed **2,013 checks in 136.52 s**.
[Focused gate](source-core/borrow-mut-focused.log),
[full gate](source-core/borrow-mut-full.log), [build manifest](source-core/borrow-mut-build.json).

Whole-application results are mixed under shared-machine load. Five wall-clock
pairs measured baseline/candidate helpers **896.22/902.45 ms**, arrays
**251.26/268.17 ms**, records **247.80/250.31 ms**, text **376.95/382.89 ms** and
graph **841.16/769.88 ms**. A seven-pair thread-CPU comparison gave arrays
**295.54/290.56 ms**, records **245.33/245.54 ms**, and graph **760.74/779.28 ms**.
All checksums matched C. These do not establish a broad application speedup;
the focused lookup benefit is much clearer.
[Wall samples](source-core/borrow-mut-apps.json), [CPU samples](source-core/borrow-mut-cpu-apps.json).

Seven compile pairs measured tour **95.35/73.89 ms**, physics **475.74/490.02 ms**
and self-build **1879.87/1853.21 ms** wall time. CPU medians were **78.42/68.83**,
**447.10/452.60** and **1748.47/1719.84 ms**. Compiler self-build stayed close to
the baseline. [Compile samples](source-core/borrow-mut-compile.json).

Dictionaries also expose `insert_if_absent(key value)`, returning whether a new
entry was added while preserving existing values, ordering and independent
copies. Its arguments evaluate eagerly once in order. The **102-check focused
dictionary/membership selection passed in 4.83 s**; growth, deletion, copied
managed values and duplicate keys are covered on native/web in both modes.
[Focused gate](source-core/map-insert-focused.log).

The graph benchmark compares the original lookup/assignment loop, insertion
through this API, and insertion with dictionary/queue capacity reserved. The
first API prototype was slower because it paid the map snapshot cost on every
visit. [Initial samples](source-core/map-insert-before-borrow.json). With the
final compiler, five runs measured **797.70 / 821.78 / 690.45 ms** respectively,
with C at **531.66 ms**. Reservation helps this workload; one-probe insertion
alone is not consistently faster. C uses a different graph/map layout.
[Final samples](source-core/map-insert-runtime.json).

The application and graph benchmark tools now offer Linux `--clock thread-cpu`
alongside default wall timing, using matching clocks in Dewy and C and recording
the adapted harness hashes. It excludes descheduling, but frequency and cache
contention still affect results.

## Dewy formatting in the CLI and editor

`fmt` now accepts Dewy files, directories, `--check`, and Dewy on stdin. It
uses the Dewy lexer to preserve meaningful adjacency, physical line breaks,
comments and original literal spelling while normalizing indentation, declaration
spacing and trailing whitespace. Ordinary arithmetic spacing stays as written.
Multiline/raw/interpolated strings and CRLF are preserved. Malformed literals
or unbalanced delimiters leave the file unchanged and report failure.

VS Code Format Document uses the unsaved buffer and discards results if the
document version has changed. Replacement ranges use UTF-16 positions. Tests
exercise the actual client transport, error recovery, implementation-language
formatting, the example corpus, and native/web execution before and after
formatting spacing-sensitive programs. The C bootstrap uses a formatter stub
only while building the first implementation-language compiler, as it already
does for the Dewy frontend; subsequent stages compile the real formatter.

The independent C bootstrap succeeded and **2,028 checks passed in 76.09 s**.
Ruff, JavaScript syntax checking and diff whitespace checks also passed.
[Full gate](source-core/formatter-full.log),
[build manifest](source-core/formatter-build.json).

## Follow-up compiler profile and discarded bookkeeping changes

A fresh instrumented profile after formatting measured the self-build's expression
reuse phase at a median **213 ms**, metadata **85 ms**, and dead-code work **64 ms**.
Its 1,693,764 hash lookups visited 385,307 occupied slots in total (including
hits), with a longest occupied run of 10. Hash collisions are not the main issue.
[Profile and instrumentation script](source-core/compiler-profile-formatter.json).

Halving the expression table size measured tour **52.13/51.53 ms**, physics
**297.18/297.96 ms**, and self-build **1182.45/1160.11 ms** baseline/candidate
wall time in seven alternating pairs. This small mixed result did not justify
a capacity change. [Samples](source-core/cse-half-table-rejected.json).

An operand-field mask replaced scratch-list construction in metadata and
use-count passes. **299 focused checks passed in 9.76 s**, but seven compile pairs
showed self-build CPU time regressing **1674.10 to 1751.57 ms**. Retaining the
original scratch-list decoder for other consumers produced **1743.97/1749.18 ms**
CPU time, effectively no gain. Neither prototype was applied to repository
compiler sources. These trials ran sequentially, but host load varied; the
stronger runtime/compile benefit needed to keep them was absent.
[Focused gate](source-core/operand-mask-focused.log),
[first prototype](source-core/operand-mask-compile-rejected.json),
[limited prototype](source-core/operand-mask-hot-compile-rejected.json).

## Lazy stored ranges and bounded stepped combinations

Bounded range expressions now produce an `IntRange`: a small signed-word value
that captures its endpoints once. It can be copied, returned, passed to functions,
kept in records/arrays and reused in independent loops. Membership checks bounds
and stride without materializing elements. Default values are empty. Full-width
distances/counts use unsigned arithmetic, including an interval with 2^64 elements.
Stored ranges require both endpoints; direct open loops retain their existing
behavior. Bounded signed-word stepped literals also work in combined headers.

The first iterator-record implementation took **31.82 ms** for ten million
values versus **8.58 ms** for the literal loop. Keeping hot state in scalar locals
and reusing the existing counted-loop backend eliminated the repeated record
loads/stores and termination flag. Seven alternating runs with the final C-built
compiler measured literal/stored **8.68/8.12 ms** thread CPU time. This supports
roughly comparable loop throughput for this simple workload, not a general
speedup claim. Checksums use an independent arithmetic-series formula, with
boundary preflights. [Initial source and measurements](source-core/stored-range-runtime-initial.json),
[final source and measurements](source-core/stored-range-runtime.json).

The new `contains` overload exposed an overload-resolution issue: a checked empty
array receiver could be reconsidered as a default record. Candidate filtering
now retains its array shape while still inferring its element type. Explicit
record arguments keep their contextual initialization.
[Existing membership failure](source-core/stored-range-overload-before.log),
[321 focused checks in 9.69 s](source-core/stored-range-focused.log).

The full independently C-bootstrapped gate passed **2,093 checks in 121.58 s**.
Coverage includes Python-generated iteration/membership expectations, native/web
in both modes, endpoint evaluation order, copied values, early exits, nested and
combined loops, exact signed-word boundaries, empty defaults and no per-range
allocation. [Full gate](source-core/stored-range-full.log),
[build manifest](source-core/stored-range-build.json).

Seven compile pairs measured baseline/candidate tour **83.20/81.92 ms**, Dunes
**441.71/439.76 ms**, and self-build **1863.06/1863.41 ms** wall time. CPU medians
were **77.68/77.78**, **429.74/428.22** and **1785.10/1781.12 ms**. These show no
material compilation change on the loaded shared host.
[Compile samples](source-core/stored-range-compile.json).

## Exclusive first bounds

Bounded signed-word ranges now accept `(first..last]` and `(first..last)`,
including stepped forms. They exclude the first specified element and retain
the existing stride. A constant-size range transformation drops that element;
loops reuse the counted lowering above. Empty/singleton intervals and full-width
counts remain correct without overflowing a signed endpoint. This applies to
stored ranges, ordinary/combined loops and membership. Left-exclusive slices
and open-ended left-exclusive ranges remain unsupported.

The existing `range_values.dewy`, `range_bound_forms.dewy` and `range_stepped.dewy`
programs now run unchanged through the compact core in both modes and targets.
Python-generated iteration and membership expectations additionally cover both
left-exclusive forms and signed boundaries; formatter execution checks include
mixed `(]` delimiters. **120 focused checks passed in 6.03 s**, followed by the
extended **96-check oracle/format selection in 6.32 s**. The independent C
bootstrap and full gate passed **2,121 checks in 110.59 s**.
[Focused gate](source-core/range-bound-focused.log),
[extended oracle](source-core/range-bound-oracle.log),
[full gate](source-core/range-bound-full.log),
[build manifest](source-core/range-bound-build.json).
