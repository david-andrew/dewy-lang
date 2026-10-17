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
