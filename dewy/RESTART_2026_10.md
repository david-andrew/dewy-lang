# Restart: fast feedback and a Sloppy-derived implementation core

Assessment begun 2026-10-16 at Dewy `15e57975` and Sloppy `235e19a`.
Sloppy's checkout already had edits to `compiler/main.jo` and `CHANGELOG.md`;
it is a reference, and this work does not modify it. Measurements of its
existing binary identify that binary separately from its source revision.

## Recommendation

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

The development gate now has over 5,300 checks; recent local full runs took
151–186 pytest seconds with two workers, excluding the independent C bootstrap. The quick smoke
suite selects a small cross-section of those checks. Focused
selections also typically take seconds. Value
checks are batched into small programs: a controlled 674-case comparison reduced
compiler launches from 674 to 44 and test time from 73.49 to 7.93 seconds, while
retaining individual results and test selection. The local driver caches an
immutable current toolchain and stops at the first failure by default. Hosted CI
always starts from C and exercises language behavior, native/web programs,
editor integration, live reload and shared-core regressions.

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
