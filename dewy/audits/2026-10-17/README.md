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
