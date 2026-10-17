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
