# Dewy compact core

This is the implementation being developed on `restart/sloppy-frontend`. It
connects an in-process Dewy frontend to the compact compiler, runtime, native/web
backends and game libraries derived from Sloppy. Edit these sources directly;
there is no generated patch layer and no separate Sloppy checkout is required.

The supported language and measured results are documented in
[the implementation notes](../tools/sloppy_core/README.md). This is still an
experimental subset, not a replacement for the published Dewy compiler.
Start with the [language guide and executable tour](LANGUAGE.md) to try it.

## Work on this checkout

```sh
python3 -m tools.core test --quick               # edit-loop smoke suite
python3 -m tools.core test                       # full compact-core gate
python3 -m tools.core test -k record             # select relevant checks
python3 -m tools.core test -n 0                  # run the full gate serially
python3 -m tools.core test -n 2                  # choose the worker count
python3 -m tools.core test -k shader_driver      # compile/link shaders with GLES
python3 -m tools.core watch examples/sloppy_core/paddle.dewy
python3 -m tools.core check examples/sloppy_core/tour.dewy
python3 -m tools.core build examples/sloppy_core/tour.dewy --release -o /tmp/tour
python3 -m tools.core path                       # executable for editor settings
python3 -m tools.core --bootstrap test           # also verify the independent C seed
```

The first command builds from C. Later commands reuse the compiler when its
sources/libraries/build inputs are unchanged, or rebuild with the previous core.
Failed builds stop the command and leave the previous toolchain intact; tests
never silently fall back to it. Changes during a build also stop publication.
Concurrent invocations share a build lock and use separate immutable snapshots.
The cache and build logs live in `__dewycache__/compact-core/`; removing that
generated directory resets it. No installed compiler is changed.

`test` uses the checkout's `.venv/bin/python` when available, otherwise the current
Python. Install pytest and pytest-xdist in that environment and have Node available
for the web checks. A full `test` uses up to four workers when pytest-xdist is
available, grouping compilation batches by test function and build mode. Without
pytest-xdist it runs serially. Commands with additional pytest arguments, such as
`test -k record`, stay serial unless given `-n`; focused runs avoid worker startup.
`-n 0` forces serial execution and `-n 2` selects two workers (both require xdist).
Tests stop at the first failure by default; use `test --maxfail=0` to
collect every failure. Extra arguments go to pytest; compiler commands forward
their arguments.
`test --quick` selects a small set of existing checks: language/value behavior,
imports, diagnostics, a headless game model and the development driver. Runtime
cases cover native/web and default/release builds. It runs serially by default
to avoid worker startup, and `-k` can narrow it further. The compiler is still
rebuilt when its inputs change, and the test programs compile afresh. The full
gate adds the broader regression corpus, rendering, networking, watch and editor
coverage; CI continues to run that full gate.
The initial build needs Python, a C compiler and `make`. CI always bootstraps
independently from C, regardless of the local cache.

## Use the current compiler from another project

`tools/dewy` is an executable development launcher with the same arguments as
the native compiler:

```sh
/path/to/dewy-lang/tools/dewy main.dewy
/path/to/dewy-lang/tools/dewy build main.dewy --release -o game
/path/to/dewy-lang/tools/dewy --version
```

It preserves the caller's working directory and replaces itself with the current
compiler, so relative paths, terminal input and signals work normally. It checks
compiler inputs and rebuilds only when needed; program compilation remains fresh.
The launcher needs Python, while a built standalone toolchain runs without it.

Set VS Code's `dewy.core.path` to the absolute path of `tools/dewy` for checkout
development. After changing compiler sources, **Dewy: Restart Core Language
Server** starts the current implementation without changing the setting. The
`path` command still prints a particular immutable compiler binary for benchmarks
or other callers that deliberately want that toolchain version.

## Build a standalone toolchain

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
  tests/python_misc/test_sloppy_core_format.py \
  tests/python_misc/test_sloppy_core_network.py \
  tests/python_misc/test_sloppy_core_watch.py \
  tests/python_misc/test_sloppy_core_upstream.py \
  tests/python_misc/test_core_dev.py
```

The gate needs pytest and Node (for web/client tests). Shader compilation/linking
also uses EGL/GLES3 libraries; local runs skip those checks when unavailable,
while CI ensures that the driver is installed. The
`Compact core` GitHub workflow bootstraps from C and runs it independently of
the earlier compiler suite. The gate has over 3,500 checks and typically takes
one to two minutes locally, depending on host load. It tests expected Dewy
behavior, Unicode grapheme conformance, native/web game simulation, a headless
render, unsaved editor changes, and focused shared-core regressions. The upstream
fixtures are included under `tests/upstream/`; the original checkout is not used.

Ordinary value, membership and string-result checks compile groups of up to 16 source modules and execute one
program per group. They retain separate pytest IDs and expected results: `-k`
selects only the requested cases before grouping. A failure reports the generated
source directory; rerun with `-k <case-name>` for a single-case reproducer. Each
case has its own module globals, and returned values/output are checked per case.
String output retains carriage returns and other control characters. The string
compiler-warning check keeps its own build. Process failures and build failures
fail the batch. Exact-number, range and bounds panic checks share builds but execute each selected
case in a fresh process, retaining its own exit status and diagnostic. Compiler
diagnostic, editor, watch and game integration checks keep their dedicated processes.

`check file.dewy` and `lsp` use the same compiler as `build`. `new <directory> [game|program]` creates a Dewy starting point with build/run
instructions. `watch` reruns terminal programs and reloads native game code in
place. Imported-module edits, recovery from compiler errors, and preserving live
state through a record layout change are covered by the gate. A changed global
initializer resets that global and initializers that directly read it; new record fields take supported
literal defaults. Embedded asset changes are watched even inside functions. Derived globals refresh
in dependency order, including through imports, and same-layout replacements
release their previous managed values. Deleting/restoring a watched asset keeps
the last working game and recovers automatically. Failed builds also watch newly
referenced inputs: creating a missing asset, imported file or parent directory
retries the build, including on first launch. Arbitrary initializer reads
inside helper functions and more complex reload scenarios remain experimental.

`fmt file.dewy` formats in place; `fmt --check directory` reports files needing
formatting without changing them. `fmt -` reads Dewy from stdin. Dewy formatting
normalizes four-space indentation, declaration spacing and trailing whitespace;
it preserves physical line breaks, literal contents, comments and meaningful
adjacency. Ordinary operator spacing stays as written. The editor uses the same
formatter on unsaved text. `.jo` files retain their own formatter.

Package editing, an interactive prompt and automatic updates
are not yet exposed; their inherited versions would produce or install the
wrong language.

## Measure compilation

Compare two compiler executables with warm caches and sequential, alternating
samples (one emission worker by default):

```sh
python3 -m tools.sloppy_core.benchmark_compile /tmp/new/bin/dewy-core \
  --baseline /tmp/old/bin/dewy-core --output /tmp/compile-times.json
```

The default workloads cover the tour, generic entity/event storage and history, physics checking/building, native/web
paddle and forest builds, and compiler self-compilation. Use `--workload physics --samples 9`
for a focused comparison. Keep the source tree fixed during a run and avoid
other CPU-heavy work. The report records all samples, binary/source identities,
working-tree state and system load; small desktop differences are not a speedup
claim. `build ... --time` reports checking, lowering/code generation and output
times. `SLOPPY_PAR_TIME=1` adds optimizer and emission timing.

To measure type-checking growth separately, generate increasing numbers of
distinct records wrapped in one generic type:

```sh
python3 -m tools.sloppy_core.benchmark_types /tmp/new/bin/dewy-core \
  --baseline /tmp/old/bin/dewy-core --output /tmp/type-times.json
```

This checks 500, 1,000 and 2,000 record types by default. Use `--count` to select
sizes. It measures synthetic type-checking scale, not whole-build or application
performance; pair it with the representative compile workloads above.

## Measure generated programs

Run the original helper, array, particle-record, text and graph workloads against
C (`-O2`), optionally including a previous compact compiler:

```sh
python3 -m tools.sloppy_core.benchmark_apps "$(python3 -m tools.core path)" \
  --baseline /tmp/old/bin/dewy-core --output /tmp/app-times.json
```

This takes about a minute for five measured runs per workload on a development
machine. `--workload helpers --samples 3` focuses a run; `--count 1000` is a quick
smoke check. The runner compares checksums at small boundary inputs and every
measured run. Reports retain raw alternating samples, kernel and whole-process
times, build times and source/toolchain identities. Kernel timing excludes input
generation; whole-process timing includes it. The C graph uses flat edges and a
handwritten hash table, while Dewy uses per-node arrays and an insertion-ordered
dictionary, so that comparison includes representation and library costs.
The correctness gate also runs all five workloads on native and web targets.

String iteration has a separate full-scan/early-exit measurement:

```sh
python3 -m tools.sloppy_core.benchmark_graphemes "$(python3 -m tools.core path)" \
  --baseline /tmp/old/bin/dewy-core --output /tmp/grapheme-times.json
```

It records alternating kernel/wall samples and live allocations at the first
loop body. A 100,000-grapheme input now needs one live cluster allocation there,
instead of an up-front array and 100,000 cluster strings. Input construction is
outside the kernel measurement; total allocations and RSS are not measured.

## Editor

The repository's [VS Code extension](../dewy/vscode-dewy/README.md) can use this
compiler for unsaved diagnostics, completions, hover and definitions. Set `dewy.core.path` to
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
