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
