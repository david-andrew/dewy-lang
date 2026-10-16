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

## Checked Dewy through Sloppy's backend

The [bridge](../../../tools/sloppy_bridge/README.md) now adapts checked UBC2
into Sloppy's register IR. The production compiler and language rules remain
unchanged. The emitter uses pinned Sloppy source, with a small dynamic-stack
allocation extension; its final seed was built from the pinned C bootstrap.
Sloppy generations two and three matched byte-for-byte
([bootstrap identity](bridge-bootstrap.json)).

Final comparison: three fresh builds and five runs per build/size, for all six
modes and sizes 0, 1, 10, 100,000 and 1,000,000. **All 450 checksums match.**
No other compiler/test jobs from this task ran during these measurements.
These are a new run, not mixed with the earlier four-mode results above.

| Mode | Cold build median | 100,000 records | 1,000,000 records | Peak run RSS |
| --- | ---: | ---: | ---: | ---: |
| C `-O2` | 96.2 ms | 10.411 ms | 166.303 ms | 32.2 MiB |
| Sloppy debug, dense | 36.1 ms | 32.628 ms | 358.818 ms | 34.0 MiB |
| Sloppy release, dense | 55.6 ms | 13.355 ms | 172.685 ms | 34.0 MiB |
| Dewy native, boxed | 1737.5 ms | 68.621 ms | 710.454 ms | 76.8 MiB |
| Dewy → Sloppy debug, boxed | 2015.0 ms | 58.713 ms | 626.181 ms | 76.8 MiB |
| Dewy → Sloppy release, boxed | 1988.7 ms | 58.470 ms | 609.351 ms | 76.8 MiB |

[Raw commands, samples, source and compiler identities](bridge-particles.json).
Bridge release stage medians are 1.7182 s for existing Dewy checking/lowering/
stream emission, 0.1146 s for Python adaptation and 0.0211 s for native
codegen. The externally timed build also includes Python startup/shutdown;
stage medians need not sum to its median. Release includes bounded inlining,
loop-invariant arithmetic and allocation, but not loop versioning/vectorization.

This improves the large particle kernel about 14%, while compilation is slower
and memory is effectively unchanged. Sloppy's ordinary dense-record program is
still about 3.5 times faster than the bridge at a million particles. This
supports changing typed aggregate lowering/representation, not promoting a
backend-only swap. It does **not** isolate boxing as the sole cause of the gap:
generated helpers, alias rules and optimization opportunities also differ.

### The compiler itself

The bridge compiled all of `dewy/bootstrap/main.dewy`. The first end-to-end
build took 59.25 s: 40.25 s existing frontend/lowering/stream, 15.60 s adaptation,
3.40 s codegen, with peak process RSS 3,121,876 KiB (about 2.98 GiB).
[Build metadata](bridge-compiler-build.json),
[frontend phase/memory counters](bridge-compiler-frontend.log).

Batching instruction serialization subsequently reduced adaptation to 11.07 s
on the same saved stream, producing **identical IR bytes** (134,106,356 bytes).
Final backend re-emission took 4.06 s. This reused the checked intermediate;
it is not a second measured end-to-end build.
[Re-emission and binary identities](bridge-compiler-reemit.json).

The final Sloppy-built compiler and the certified reference each rebuilt Dewy
through the existing native route, in fresh directories with fresh preludes.
They emitted **byte-identical native compilers**, SHA256
`2325266bdb913f38f17b5bfe2dd17676ffbfe9fdf3f9d84619d6efe38c97a10b`.
Both outputs run `--version`. The reference took 38.21 s; the Sloppy-built
compiler took 47.79 s, about 25% slower. These are single final self-build
samples, not a statistical self-build benchmark.
[Commands, full counters, hashes and equality result](bridge-compiler-self-check.json).

The final emitter and Sloppy-built Dewy compiler pass **33 focused tests in
33.66 s**: words/division/booleans, short-circuiting, calls and stack arguments,
repeated dynamic allocation, sized memory, large BSS and static relocations;
checked strings/containers/functions; record growth/copies, subtypes,
alias-sensitive arguments, resource copy and move/drop hooks; rejected bounds
proofs including unused invalid functions and invalidated indices.
[Test log](bridge-tests.log). The compiler equality check is additional
coverage, **not full integration certification**. Neither compiler was installed
or made the default.

### Decision

Keep this as a bounded backend service and acceptance harness. Do not extend
the UBC adapter into a second general language frontend. The next dense-record
slice must branch before pointer/ownership lowering in
`bootstrap/backend/udewy/graph.dewy`, retaining the complete validation pipeline
and explicit initialization, effect and copy-policy obligations. Preserve type
IDs, aggregate layouts and value/place identity into Sloppy's IR/runtime.
Start with fixed scalar records, then apply the copy/alias/growth/resource
counterexamples before widening supported types. Unsupported cases must remain
explicitly unsupported; never silently lower their semantics differently.

Also compact the frontend's allocation-heavy type/HIR representation and
repeated traversals.
The backend boundary is now executable at compiler scale, but these measurements
do not justify changing parsing or other user-visible language rules.

### Complete layout-key memoization

The native lowerer now retains successful complete layout keys in its own
compilation state. Nested recursive traversals remain uncached because their
cycle markers depend on the current root. Failed queries remain uncached so
diagnostics keep the requesting source location.

Three fresh self-builds per compiler, alternating order and run sequentially,
produce six byte-identical binaries. Median lowering time falls from 14.310 to
13.697 s, with reported allocation traffic falling from 9,514,974,200 to
9,081,905,368 bytes. Whole-build medians are 39.147 and 38.993 s: this is a
modest local improvement, not a solution to cold-build latency or peak memory.
[Commands, hashes and all samples](layout-key-cache.json).

### Dense scalar-record arrays

`DEWY_DENSE_RECORDS=1` selects inline array storage using checked type IDs
and HIR before legalization. Value copies acquire independent record storage;
array detachment copies scalar bytes; growth relocates the buffer; field
mutation reaches an inline place. Pop snapshots the value before shifting
the remaining elements. The public source syntax and validation remain intact.

The initial slice is flat fixed-width integer/bool records without lifecycle
hooks or dynamic brands. Unsupported representations and operations retain
boxed storage. This is a temporary development boundary, not an internal ABI
compatibility requirement.

Three fresh builds and five runs per size/build across nine modes give **675
checksum-checked executions**. All measurements run sequentially without
other compiler/test jobs from this task. Cold builds include a fresh prelude.

| Mode | Cold build median | Million-particle kernel |
| --- | ---: | ---: |
| C -O2 | 90.7 ms | 172.5 ms |
| Sloppy release | 51.5 ms | 173.8 ms |
| Dewy boxed, native | 1749.3 ms | 702.6 ms |
| Dewy dense, native | 1704.5 ms | 435.6 ms |
| Dewy boxed, Sloppy release | 2011.7 ms | 632.0 ms |
| Dewy dense, Sloppy release | 1977.1 ms | 448.4 ms |

Dense native storage is 38% faster on this kernel and cuts peak run RSS from
76.8 to 62.6 MiB. This still misses the runtime target, and barely changes
cold compilation. Repeated runtime ownership checks and the old frontend
remain targets; this does not justify spending time preserving their design.

[Full samples](dense-particles.json), [source identities](dense-source-sha256.txt).
The 44-test focused gate passes in 49.46 s: planner selection, copy/growth,
place mutation, insert/pop/truncate, narrow fields, spread/iteration, returned
snapshots, aliasing arguments, plus the existing bridge resource/rejection
cases. [Test log](dense-tests.log). This is development validation, not a full
release certification run.

### Dense kernel entry setup

Simple indexed kernels now acquire unique array storage once on entry and
reuse the buffer address and length. A structural HIR check excludes resizing,
whole-array copies, captures, raw access, and calls that can acquire another
owner. User-defined functions with operator names do not count as builtins.
The caller still observes independent value snapshots when its array detaches.

The final three-build/five-run comparison covers 225 executions at five sizes,
all with matching checksums. At one million particles, native Dewy falls from
698.7 to **223.9 ms** (3.12 times faster), while C takes about 173 ms. At
100,000 particles the new path takes 18.6 ms; it still has headroom against C.
Cold builds remain approximately 1.74 s. A smaller comparison found Sloppy's
release backend slower on this kernel than the native emitter, so backend
replacement is not the leading performance route.

[Full kernel samples](kernel-particles.json). The combined kernel/cache/harness
gate passes **34 tests in 19.83 s**, including an interior snapshot that must
prevent entry-only detachment and a source function shadowing an operator.
[Test log](kernel-cache-tests.log). Test-driver cache keys now distinguish
the dense-representation switch.

### Shared native prelude cache

The native CLI now uses the user cache directory for checked preludes, with
`DEWY_PRELUDE_CACHE_DIR` available for explicit isolation. Existing compiler
identity, transitive source validation, checksums, and atomic writes remain
in force. This changes where reusable analysis lives, not whether each user
program is compiled. Cold benchmark tools explicitly select an empty cache.

Five fresh project directories with the old CLI each rebuilt the prelude:
median **1.662 s** for a tiny program. With the new CLI, the first directory
took 1.649 s; five further fresh directories with changed program source took
a median **0.462 s** (72% less time), each reusing the checked library and
executing the newly compiled result. Runs were sequential without other
compiler/test work from this task. [All samples](shared-prelude-latency.json).

The CLI test checks reuse across directories, changed program output, corrupt
entry recovery, and explicit cache isolation. The remaining warm-build cost
is substantial: one sample spends 226 ms restoring the prelude, 80 ms in
validation, and 122 ms in lowering. This cache change removes repeated work;
it does not make the frontend representation compact.

### Bounded cache word reads

Restore phase timings isolate file reading, checksumming, decoding, and
input validation. Native/C cache decoding now checks the remaining length
once and borrows the byte buffer for an unaligned word load. Other targets
keep the portable byte loop. This is an internal implementation choice.

Three alternating warm tiny-program runs per compiler give median total
compilation **465 ms before / 429 ms after**, with decoding **182 / 148 ms**.
The first iteration is excluded: the new compiler had no prelude entry.
Each build uses a fresh directory and changed source, and its result is
executed. [Samples and compiler identities](cache-word-reads.json).

The primitive codec runs on x86 and C, covering all truncated word lengths,
unaligned words, invalid UTF-8, and malformed values. Shared-cache recovery
and transitive invalidation tests also pass: **3 tests in 48.96 s**, including
a fresh compiler-sized cache driver. [Test log](cache-word-tests.log).

### Prune unused runtime helpers before normalization

Ordinary builds now retain only reachable lowered functions before
normalization, using the walk already used for proof-only bodies. Previously
normal builds retained the entire declared helper set. Source checking still
runs before this pass; global startup, callbacks, generated helpers, and argv
decoding are roots. Debug builds retain their existing behavior.

Three alternating warm runs give **438 ms before / 376 ms after** for the
tiny program, and normalization **44.4 / 4.6 ms**. Executable size falls from
131,152 to 53,496 bytes. Each newly built program executes with its changed
expected result. [Samples and identities](runtime-pruning.json).

The remaining allocator functions in a tiny executable are reachable from
prelude global initialization; eliminating those needs a separate change.

### Shared strings in checked snapshots

Native cache format 10 stores each distinct string once per stream. Repeated
names, paths, and literal metadata use a bounded index; restoring them shares
immutable string storage. Headers and payloads have independent tables. Old
cache entries are disposable and rebuilt; their binary format is not a
compatibility target. Invalid and forward references fail the whole restore.

Three alternating warm runs give **388 ms before / 305 ms after**, with
decoding **152 / 82 ms**. Restore allocation falls from **205.7 / 138.4 MB**
and peak arena payload from **111.5 / 75.9 MB** (decimal units). Cache files
shrink from 12,244,282 to 10,748,677 bytes. The single cold comparison is
1.518 / 1.548 s; more cold samples are needed before claiming a cold change.
[Measurements](interned-cache-results.json).

Primitive tests and a complete typed snapshot execute on x86 and C. Shared
cache repair and transitive-input invalidation also pass: **4 tests in
103.54 s**, including new compiler-sized drivers and the C compilation of
the full snapshot codec. [Test log](interned-cache-tests.log).

### Native development smoke gate

`tools/certify.sh smoke /path/to/dewy` compiles existing source cases directly
with the supplied CLI. It covers normal scalar/control/container behavior,
callbacks, initialization, resource hooks, storage-lifetime rejection, dense
record values, Unicode argv, and shared cache repair. The pinned Sloppy
backend remains an optional separate check. No compiler-sized driver is built
for this gate. **37 tests pass in 20.54 s**; seven bridge variants are explicitly
excluded. [Run log](native-smoke.log). The changed subsystem still needs its
focused checks; this is an inner-loop gate, not a full release certification.

A pre-scan intended to skip storage-lifetime analysis was tried and reverted.
The reporting prelude contains sorts, so it still triggered full analysis
even for tiny programs. Warm compilation was about 316 / 314 ms and the
pass about 41 / 39 ms: insufficient benefit for an extra scan.
[Experiment samples](storage-prescan-experiment.json). The useful direction
is to reuse or selectively compute analysis summaries, not add scans around
the unchanged whole-program pass.
