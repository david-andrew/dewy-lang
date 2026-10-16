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

The first slice supports explicitly typed functions, mutable `@` arguments,
independent value parameters, fixed-width arithmetic, floating-point records,
arrays with value copies, nested record mutation, conditionals, while loops,
interpolated strings, and entry-point arguments. Native parser diagnostics and
UTF-8 source locations are retained. A semicolon explicitly discards a result.

This is an opt-in compiler experiment, not a full language implementation or a
release-certified replacement. The core supplies runtime bounds checks, not the
old proof engine. Proof directives, effect contracts, unbounded integer types,
grapheme string length/indexing, and unsupported syntax produce diagnostics.
Signed floor division/modulo currently use the core's int64 helpers. Integer
`/` is rejected until its result semantics are implemented. Ambiguous syntax
currently prefers the unique candidate with fewer juxtaposed multiplications;
ties are rejected. This is a deliberate experimental simplification of the old
semantic disambiguator, not a claim to support every juxtaposition case.

The initial behavior gate contains 18 cases and runs in under a second on the
development machine, including separate compiler processes and program execution.
Evidence is in `dewy/audits/2026-10-16/source-core/`. Subsequent workload measurements
must distinguish this supported slice from the old compiler's broader features.
