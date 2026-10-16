# Source-level Dewy core experiment

This branch connects Dewy's actual native syntax parser to the compact AST,
checker, code generator, runtime, and libraries from a pinned Sloppy revision.
It bypasses Dewy's existing semantic IR and backend pipeline. The point is to
recover fast development while retaining useful Dewy language behavior, rather
than reproducing internal representations or executable bytes.

Build from two existing native compiler seeds:

```sh
PYTHONPATH=. .venv/bin/python -m tools.sloppy_core.build \
  --sloppy-root /path/to/slop-lang \
  --sloppy-seed /path/to/sloppy \
  --dewy /path/to/native/dewy \
  --output /tmp/dewy-core
/tmp/dewy-core/bin/dewy-core build example.dewy -o /tmp/example
DEWY_CORE_COMPILER=/tmp/dewy-core/bin/dewy-core \
  .venv/bin/python -m pytest -q -n0 tests/python_misc/test_sloppy_core.py
```

The output directory must be new. The builder archives committed Sloppy sources
at `235e19a271bccad3fe72e36d03264807a632dc1b`; it never edits that checkout or
incorporates its uncommitted changes. `build.json` records seed and output hashes.
Use `--bootstrap` in place of `--sloppy-seed` to build pristine Sloppy with its
independent C bootstrap, build the adapted core, and then have that core build
itself. This route needs a C compiler and `make`, but no installed Sloppy binary.
The final self-built core passes the same 77-check behavior gate. The Dewy parser
still needs the existing native Dewy seed; this is not yet a complete C-only
bootstrap of the combined compiler. Hashes record provenance, not a requirement
for byte-identical self-builds.

The exported tree includes Sloppy's license and notices. Nothing replaces the installed Dewy
compiler. The parser currently runs as a subprocess for each Dewy source file;
this intentionally simple boundary can be replaced after measuring the result.

The current slice supports typed and inferred functions, generic calls, default
arguments, closures with captured state, higher-order calls, mutable `@` arguments,
independent value parameters, fixed-width arithmetic, floating-point records,
arrays and dictionaries with value copies, type aliases, callable types, union
narrowing, nested record mutation, conditionals, while loops,
interpolated strings, entry-point arguments, file imports (Dewy and Sloppy),
array/range iteration, import aliases, forward local record declarations, and
combined `and` loop headers. Combined loops reuse
the core's lowering, including correct advancement on `continue`.
Native parser diagnostics and
UTF-8 source locations are retained. A semicolon explicitly discards a result.

This is an opt-in compiler experiment, not a full language implementation or a
release-certified replacement. The core supplies runtime bounds checks, not the
old proof engine. Proof directives, effect contracts, unbounded integer types,
grapheme string length/indexing, and unsupported syntax produce diagnostics.
Signed floor division/modulo currently use the core's int64 helpers. Floating
point `/` is supported; integer `/` is rejected until its result semantics are
implemented. Ambiguous syntax
currently prefers the unique candidate with fewer juxtaposed multiplications;
ties are rejected. This is a deliberate experimental simplification of the old
semantic disambiguator, not a claim to support every juxtaposition case.

Record construction and collection `.length` are resolved from types, including
imported/qualified record constructors and records with their own `length` field.

The behavior gate now contains 109 checks and takes about 6.5 seconds on the
development machine, including separate compiler processes and program execution.
Value cases run in debug and release modes. It includes the paddle game model
on native and WebAssembly targets in both modes, and a
display-independent render of the actual game. The playable example and build
instructions are in `examples/sloppy_core/`.
Evidence is in `dewy/audits/2026-10-16/source-core/`.

For the editor protocol gate, include
`tests/python_misc/test_sloppy_core_editor.py` in the pytest command above.
`dewy-core check file.dewy` checks all source functions, including unused ones,
and performs lowering checks without code emission. Five-process medians were
62 ms for the particle benchmark and 121 ms for the paddle game.
`dewy-core lsp` serves diagnostics, hover types, and definitions for unsaved
Dewy text. The parser reads the compiler's snapshot through a Linux anonymous
file; the experimental compiler host currently requires Linux. Syntax errors
use the core's diagnostic transport, including original file/byte locations.
Hover text still uses the core's type spelling. Formatting Dewy is deliberately
unavailable: the CLI rejects it and LSP returns no edits, instead of applying
Sloppy's syntax formatter. Other inherited editor features remain experimental.

The existing nested-record particle benchmark runs unchanged except for its
platform harness import: `benchmark_harness.jo` replaces raw compiler-specific
syscalls with the core library. Three cold builds and five runs at each of five
sizes per build give these medians (OS caches retained, one compiler worker):

| Compiler | Whole build | Million-particle kernel |
| --- | ---: | ---: |
| Current Dewy, boxed default | 1,656 ms | 706 ms |
| Current Dewy, opt-in dense records | 1,703 ms | 218 ms |
| Source core, debug | 72 ms | 617 ms |
| Source core, release | 90 ms | 257 ms |
| C (`cc -O2`) | 94 ms | 170 ms |

All 375 runs matched checksums, including empty and single-element arrays.
The source core is about 18.5× faster to compile this supported workload; it
does not yet beat the existing opt-in dense runtime. These are workload results,
not a self-hosting or full-language speedup claim. Reproduce with
`tools/compare_sloppy.py --source-core /path/to/bin/dewy-core`, selecting
`--dewy-source dewy/benchmarks/apps/records_nested.dewy` and the desired modes.

Subsequent lowering improvement: collection length now reuses the length already
cached when the core proves the array fixed during a loop. The proof checks calls
in the condition as well as the body; otherwise growth/shrinking remains live.
Three builds and 225 alternating comparative runs give 84 ms compilation and
197 ms for the million-particle kernel, down from 257 ms, versus C at 173 ms in
that run. All checksums agree. This brings the unchanged nested-record algorithm
within about 14% of the C kernel, and ahead of the earlier dense Dewy measurement.
It is still a single workload, not a claim about all generated programs.

Shared-core optimization changes also run pinned Sloppy regressions:

```sh
DEWY_CORE_COMPILER=/tmp/dewy-core/bin/dewy-core DEWY_SLOPPY_ROOT=/path/to/slop-lang \
  .venv/bin/python -m pytest -q -n0 tests/python_misc/test_sloppy_core_upstream.py
```

The 22 array, copy, bounds, and loop cases take about 1.3 seconds. Fixtures come
from the pinned Git revision, so local changes in the reference checkout do not
affect the gate.
