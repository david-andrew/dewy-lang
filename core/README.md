# Dewy compact core

This is the implementation being developed on `restart/sloppy-frontend`. It
connects Dewy's native syntax parser to the compact compiler, runtime, native/web
backends and game libraries derived from Sloppy. Edit these sources directly;
there is no generated patch layer and no separate Sloppy checkout is required.

The supported language and measured results are documented in
[the implementation notes](../tools/sloppy_core/README.md). This is still an
experimental subset, not a replacement for the published Dewy compiler.

## Build

From the repository root, using a working native Dewy compiler to build the
syntax parser, and a C compiler plus `make` for the compact core:

```sh
python3 -m tools.sloppy_core.build \
  --dewy /path/to/native/dewy --bootstrap --output /tmp/dewy-core
/tmp/dewy-core/bin/dewy-core --version
/tmp/dewy-core/bin/dewy-core new /tmp/my-dewy-game
/tmp/dewy-core/bin/dewy-core watch /tmp/my-dewy-game/main.dewy
/tmp/dewy-core/bin/dewy-core examples/sloppy_core/paddle.dewy
/tmp/dewy-core/bin/dewy-core build examples/sloppy_core/paddle.dewy \
  --target wasm -o /tmp/paddle
```

The output directory must be new. It contains a standalone `bin/` and `lib/`,
source snapshots, build logs and a hash manifest. No installed compiler is
changed. Python is build tooling only; program compilation and execution are
native. The compiler host currently requires Linux x86-64; native Linux and web
programs are covered by the development gate. Other inherited targets are not
certified for this frontend.

Once a core and parser have been built, rebuild into a new toolchain without the
old compiler or C bootstrap:

```sh
python3 -m tools.sloppy_core.build \
  --parser /tmp/dewy-core/bin/dewy-parse --seed /tmp/dewy-core/bin/dewy-core \
  --output /tmp/dewy-core-next
```

For a quick compiler edit, reuse the existing toolchain's parser and libraries:

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
  .venv/bin/python -m pytest -q -n0 \
  tests/python_misc/test_sloppy_core.py \
  tests/python_misc/test_sloppy_core_editor.py \
  tests/python_misc/test_sloppy_core_watch.py \
  tests/python_misc/test_sloppy_core_upstream.py
```

The gate tests expected Dewy behavior, native/web game simulation, a headless
render, unsaved editor changes, and focused shared-core regressions. The upstream
fixtures are included under `tests/upstream/`; the original checkout is not used.

`check file.dewy` and `lsp` use the same compiler as `build`. `new <directory> [game|program]` creates a Dewy starting point with build/run
instructions. `watch` reruns terminal programs and reloads native game code in
place. Imported-module edits, recovery from compiler errors, and preserving live
state through a record layout change are covered by the gate. A changed global
initializer deliberately resets that global; new record fields take supported
literal defaults. More complex reload scenarios remain experimental.

Dewy formatting, package editing, an interactive prompt and automatic updates
are not yet exposed; their inherited versions would produce or install the
wrong language.

## Source layout and bootstrap

- `compiler/frontend.jo` dispatches Dewy and implementation-language source.
- `compiler/dewy_parse.jo` projects the Dewy syntax tree into the compact AST.
- `compiler/` contains checking, lowering, code generation and tools, currently
  written in the inherited implementation language (`.jo`).
- `lib/` contains containers, platform support, graphics, input, audio and other
  libraries. Dewy programs can import `.jo` library modules directly.
- `stage0/` is the small independent C bootstrap.
- `bootstrap/frontend.jo` selects only the implementation-language parser for
  the initial bootstrap generation. That compiler then builds the complete
  frontend, which builds itself again.
- `../tools/sloppy_core/parse.dewy` is the native syntax-parser driver. This is
  the remaining bootstrap dependency on the older Dewy compiler.

The C bootstrap intentionally implements a smaller language. The frontend seam
allows the main compiler to evolve without implementing every feature twice.
Build hashes identify provenance; byte-identical executables are not required.

## Origin and licensing

Imported from Sloppy revision `235e19a271bccad3fe72e36d03264807a632dc1b`, with
Dewy frontend, editor, CLI and lowering changes. `UPSTREAM.json` records the
original imported file hashes so the baseline can be compared independently of
later edits. `LICENSE` and `NOTICE` retain the upstream license and notices;
`lib/game/assets/OFL.txt` covers the included font. No Sloppy logo is included.
