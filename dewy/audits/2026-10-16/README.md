# Restart measurements, 2026-10-16

Machine: Intel Core i7-6700, Linux x86-64, GCC 16.2.1, Python 3.14.7.
Ordinary desktop environment; OS page caches were not flushed. Compilation
and runtime measurements were run sequentially, without this task's other
compiler/test jobs running alongside them.

## Recovered certification

The saved `../dewy-build-artifacts/integration-15e57975/` run had completed
successfully before development paused: independent hosted seed, native fixed
points, native execution checks, all 698 paired cases, copy-report
classification and 6,496 pytest passes (13 skips). The progress ledger still
listed these as open; it now records the recovered evidence.

[Saved summary](recovered-certification.txt),
[compiler/library source hashes](compiler-source-sha256.txt),
[native directory's binary hashes](compiler-binary-sha256.txt).
Both manifests were verified on October 16; source paths are relative to the
repository root and binary paths to the saved `native/` directory. This is
certification of `15e57975`, not a new full-suite run for the harness changes.

## Identical particle workload

Sources: [`records.dewy`](../../benchmarks/apps/records.dewy),
[`records.jo`](../../benchmarks/apps/records.jo),
[`records.c`](../../benchmarks/apps/records.c). Same input generator,
50 indexed update passes, checksum algorithm and integer widths. Sloppy uses
dense records and runtime bounds checks; Dewy uses boxed records and proves
bounds; C uses dense records without bounds checks. No algorithmic or manual
SoA/pointer tuning was applied to the Sloppy counterpart.

Three fresh compilations per mode (including a fresh Dewy prelude each time),
five executions per build and size. Thus each kernel median uses 15 samples.
Sloppy code generation uses one worker. C uses `-O2`. Sizes 0, 1, 10, 100,000
and 1,000,000 agree across all builds and all repetitions: **300 checked runs**.

| Mode | Cold compile median | Compile peak RSS | 100,000 records, kernel median | 1,000,000 records, kernel median | Run peak RSS |
| --- | ---: | ---: | ---: | ---: | ---: |
| C | 90.0 ms | 30.9 MiB | 11.289 ms | 171.378 ms | 32.2 MiB |
| Sloppy debug | 37.0 ms | 22.2 MiB | 30.785 ms | 350.809 ms | 34.0 MiB |
| Sloppy release | 50.1 ms | 26.3 MiB | 13.021 ms | 171.756 ms | 34.0 MiB |
| Dewy native | 1702.3 ms | 109.0 MiB | 67.929 ms | 711.743 ms | 76.8 MiB |

[Raw samples, commands, binary hashes and source/checkout identities](particles.json).
The source compiler/library hashes match the saved certified `15e57975`
native pair. The current branch changes the harness, benchmark and documents,
not those compiler/library sources. Sloppy's existing binary is identified by
its SHA256; its checkout was `235e19a` with pre-existing uncommitted edits.
No backend fallback occurred in these Dewy builds.

Reproduce from the repository root:

```sh
python tools/compare_sloppy.py --dewy /path/to/dewy --udewy /path/to/udewy \
  --sloppy-root /path/to/slop-lang --output /tmp/new-particles.json
```

## Self-build and game build latency

One fresh Dewy native self-build: **38.996 s**, peak process RSS
**2,647,032 KiB** (2.52 GiB). Inclusive root phases: frontend 11.369 s,
validation 11.724 s, initialization/reachability 1.099 s, lowering 14.079 s.
Nested counters must not be added to their parents. This is one compilation,
not a new multi-generation certification.
[Metadata](self-build-metadata.json), [phase/memory results](self-build-results.jsonl).

Sloppy's existing binary built its compiler in 1.614/1.388/1.271 s (the
compiler's source requests release optimization), Rebound in
0.162/0.161/0.163 s and Breakwater in 0.211/0.217/0.218 s (default development
mode), with one code-generation worker. These are different programs and
languages, not a normalized compiler-throughput ratio.
[Recorded build samples and binary identity](sloppy-builds.json).

## Focused validation

The same four existing tests, with persistent driver reuse disabled:

| Tests | Hosted-built drivers | Native-emitted drivers |
| --- | ---: | ---: |
| type interning (executes both x86-64 and C output) | 18.79 s | 7.53 s |
| invocation options, x86-64 | 1.82 s | 2.23 s |
| invocation options, C | 16.41 s | 2.23 s |
| source locations | 2.56 s | 2.08 s |
| pytest total | **40.16 s** | **14.72 s** |

Both runs passed all four tests. [Hosted log](hosted-kernels.log),
[native log](native-kernels.log). These measure the `isolated_codegen` text
path, where the tests retain control of their downstream backend. The tiny
x86-64 options case is slower in the native mode; the improvement is not
uniform. This is not a measured prediction of the whole suite's speedup.

The broader shared-driver path also builds executables directly, avoiding
hosted µDewy compilation. The final integration selection passed **47 tests
in 319.57 s**, with driver reuse disabled: harness behavior, source checking,
stored refinement contracts, lowering (hundreds of source cases), prelude,
structural text (hosted/native comparison and x86-64/C execution), bytecode,
type interning, invocation options and source locations.
[Final native-direct log](native-direct-drivers.log).

An earlier intermediate version using native text emission followed by the
hosted µDewy backend took 488.03 s for 41 tests
([log](native-text-drivers.log)). The final selection includes those tests
plus two harness tests and the four kernel tests above. This is an observed
development comparison, not a prediction for all 6,496 tests; a short harness
unit run also overlapped the final selection. The slow structural-text and
scalar-lowering cases still do substantial per-case compilation, including
independent hosted checks. They remain next targets for test decomposition
and avoiding redundant setup without weakening oracle coverage.

The final standalone harness suite passed **15 tests in 1.95 s**, including
a real hosted build/run, native selection, content-based cache invalidation,
source-location/target propagation, failed and missing output handling, and
separation from the pre-existing `DEWY_TEST_NATIVE` program-output override.
[Harness log](harness-tests.log). Relevant Python lint checks, shell syntax
and `git diff --check` also pass. The full suite and release certification
were **not rerun for this harness branch**.
