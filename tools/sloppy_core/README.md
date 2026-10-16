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
The exported tree includes Sloppy's license. Nothing replaces the installed Dewy
compiler. The parser currently runs as a subprocess for each Dewy source file;
this intentionally simple boundary can be replaced after measuring the result.

The current slice supports typed and inferred functions, generic calls, default
arguments, closures with captured state, higher-order calls, mutable `@` arguments,
independent value parameters, fixed-width arithmetic, floating-point records,
arrays with value copies, nested record mutation, conditionals, while loops,
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

The behavior gate now contains 77 checks and takes about 4.4 seconds on the
development machine, including separate compiler processes and program execution.
Value cases run in debug and release modes. It includes the paddle game model
on native and WebAssembly targets in both modes, and a
display-independent render of the actual game. The playable example and build
instructions are in `examples/sloppy_core/`.
Evidence is in `dewy/audits/2026-10-16/source-core/`.

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
