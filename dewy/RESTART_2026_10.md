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

This changes the **order of implementation**, not Dewy's language contract.
The existing Phase 1 guarantees and their regressions remain requirements.
Additional proof sophistication should earn its place by enabling ordinary
programs within measured compile-time budgets. A budget-exhausted query stays
unknown; it cannot silently authorize an operation.

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
