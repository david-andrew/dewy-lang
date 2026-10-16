# Dewy compact core

This is the implementation being developed on `restart/sloppy-frontend`. It
connects an in-process Dewy frontend to the compact compiler, runtime, native/web
backends and game libraries derived from Sloppy. Edit these sources directly;
there is no generated patch layer and no separate Sloppy checkout is required.

The supported language and measured results are documented in
[the implementation notes](../tools/sloppy_core/README.md). This is still an
experimental subset, not a replacement for the published Dewy compiler.
Start with the [language guide and executable tour](LANGUAGE.md) to try it.

## Build

From the repository root, using Python, a C compiler and `make`:

```sh
python3 -m tools.sloppy_core.build \
  --bootstrap --output /tmp/dewy-core
/tmp/dewy-core/bin/dewy-core --version
/tmp/dewy-core/bin/dewy-core new /tmp/my-dewy-game
/tmp/dewy-core/bin/dewy-core watch /tmp/my-dewy-game/main.dewy
/tmp/dewy-core/bin/dewy-core examples/sloppy_core/paddle.dewy
/tmp/dewy-core/bin/dewy-core examples/sloppy_core/physics.dewy
/tmp/dewy-core/bin/dewy-core build examples/sloppy_core/paddle.dewy \
  --target wasm -o /tmp/paddle
```

No prebuilt Dewy or Sloppy compiler, or separate reference checkout, is needed.
The complete C-bootstrap build steps take about 17 seconds on the development
machine. The output directory must be new. It contains a standalone `bin/` and `lib/`,
source snapshots, build logs and a hash manifest. No installed compiler is
changed. Python is build tooling only; program compilation and execution are
native. The compiler host currently requires Linux x86-64; native Linux and web
programs are covered by the development gate. Other inherited targets are not
certified for this frontend.

Once a core has been built, rebuild into a new toolchain without the
old compiler or C bootstrap:

```sh
python3 -m tools.sloppy_core.build \
  --seed /tmp/dewy-core/bin/dewy-core \
  --output /tmp/dewy-core-next
```

For a quick compiler edit, reuse the existing toolchain's libraries:

```sh
/tmp/dewy-core/bin/dewy-core build core/compiler/main.jo \
  -o /tmp/dewy-core/bin/dewy-core
```

Changes in `core/lib/` require rebuilding the standalone tree or setting
`DEWY_CORE_LIB="$PWD/core/lib"` for the compiler under test. `SLOPPY_LIB` is still
accepted for existing implementation tooling. Runtime tuning variables inherited
from Sloppy retain their names for now.

## Validate

```sh
DEWY_CORE_COMPILER=/tmp/dewy-core/bin/dewy-core \
  .venv/bin/python -m pytest -q -o addopts='' \
  tests/python_misc/test_sloppy_core.py \
  tests/python_misc/test_sloppy_core_editor.py \
  tests/python_misc/test_sloppy_core_watch.py \
  tests/python_misc/test_sloppy_core_upstream.py
```

Only pytest and Node (for web/client tests) are needed for this gate. The
`Compact core` GitHub workflow bootstraps from C and runs it independently of
the earlier compiler suite. The 734-check gate takes about 50 seconds locally. It tests expected Dewy
behavior, Unicode grapheme conformance, native/web game simulation, a headless
render, unsaved editor changes, and focused shared-core regressions. The upstream
fixtures are included under `tests/upstream/`; the original checkout is not used.

`check file.dewy` and `lsp` use the same compiler as `build`. `new <directory> [game|program]` creates a Dewy starting point with build/run
instructions. `watch` reruns terminal programs and reloads native game code in
place. Imported-module edits, recovery from compiler errors, and preserving live
state through a record layout change are covered by the gate. A changed global
initializer resets that global and initializers that directly read it; new record fields take supported
literal defaults. Embedded asset changes are watched even inside functions. Derived globals refresh
in dependency order, including through imports, and same-layout replacements
release their previous managed values. Deleting/restoring a watched asset keeps
the last working game and recovers automatically. Arbitrary initializer reads
inside helper functions and more complex reload scenarios remain experimental.

Dewy formatting, package editing, an interactive prompt and automatic updates
are not yet exposed; their inherited versions would produce or install the
wrong language.

## Measure compilation

Compare two compiler executables with warm caches and sequential, alternating
samples (one emission worker by default):

```sh
python3 -m tools.sloppy_core.benchmark_compile /tmp/new/bin/dewy-core \
  --baseline /tmp/old/bin/dewy-core --output /tmp/compile-times.json
```

The default workloads cover the tour, physics checking/building, native/web
paddle builds and compiler self-compilation. Use `--workload physics --samples 9`
for a focused comparison. Keep the source tree fixed during a run and avoid
other CPU-heavy work. The report records all samples, binary/source identities,
working-tree state and system load; small desktop differences are not a speedup
claim. `build ... --time` reports checking, lowering/code generation and output
times. `SLOPPY_PAR_TIME=1` adds optimizer and emission timing.

## Editor

The repository's [VS Code extension](../dewy/vscode-dewy/README.md) can use this
compiler for unsaved diagnostics, hover and definitions. Set `dewy.core.path` to
the built executable, for example `/tmp/dewy-core/bin/dewy-core`. An empty setting
keeps compiler-backed features disabled. The client is dependency-free and has a
native-server integration test in the editor gate above.

## Source layout and bootstrap

- `compiler/frontend.jo` dispatches Dewy and implementation-language source.
- `compiler/dewy_fast.jo` lexes and parses Dewy inside the compiler process.
- `compiler/dewy_parse.jo` projects the Dewy syntax tree into the compact AST.
- `compiler/` contains checking, lowering, code generation and tools, currently
  written in the inherited implementation language (`.jo`).
- `lib/` contains containers, platform support, graphics, input, audio and other
  libraries. Dewy programs can import `.jo` library modules directly.
- `stage0/` is the small independent C bootstrap.
- `bootstrap/frontend.jo` selects only the implementation-language parser for
  the initial bootstrap generation. That compiler then builds the complete
  frontend, which builds itself again.
- `bootstrap/dewy_parse.c.gz` is the optional legacy syntax-parser seed. Its
  [regeneration instructions](bootstrap/README.md) and source provenance are
  included. The parser source still lives in `dewy/bootstrap/parser/`, with
  the driver at `../tools/sloppy_core/parse.dewy`.

The default frontend reads source snapshots directly, including unsaved editor
text. It does not need a parser executable, temporary files or a syntax transport.
For investigation, build with `--legacy-parser` (or reuse one with `--parser`),
then select it with `DEWY_CORE_FRONTEND=legacy`. There is no automatic fallback.

The C bootstrap intentionally implements a smaller language. The frontend seam
allows the main compiler to evolve without implementing every feature twice.
Build hashes identify provenance; byte-identical executables are not required.

## Origin and licensing

Imported from Sloppy revision `235e19a271bccad3fe72e36d03264807a632dc1b`, with
Dewy frontend, editor, CLI and lowering changes. `UPSTREAM.json` records the
original imported file hashes so the baseline can be compared independently of
later edits. `LICENSE` and `NOTICE` retain the upstream license and notices;
`lib/game/assets/OFL.txt` covers the included font. No Sloppy logo is included.
