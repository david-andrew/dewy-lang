# Developing the Dewy compiler

The compiler connects an in-process Dewy frontend to a compact checker, runtime,
native/web backends and libraries, forked from Sloppy (see
[`origin/ORIGIN.md`](origin/ORIGIN.md)). It is an experimental subset of Dewy;
start with the [language guide and executable tour](LANGUAGE.md).

Projects can use native `test "description" { assert(...) }` blocks and run them
with `./tools/dewy test file.dewy [name filters...]`; see the
[project testing guide](LANGUAGE.md#test-a-project). `./tools/dewy test --watch
file.dewy` reruns them after edits, including changes to imports and embedded
assets. The Python commands below validate the compiler itself.

## Work on this checkout

```sh
python3 -m tools.core test --quick               # edit-loop smoke suite
python3 -m tools.core test                       # full gate
python3 -m tools.core test -k record             # select relevant checks
python3 -m tools.core test -n 0                  # run the full gate serially
python3 -m tools.core test -n 2                  # choose the worker count
python3 -m tools.core test -k shader_driver      # compile/link shaders with GLES
python3 -m tools.core watch examples/paddle.dewy
python3 -m tools.core repl                       # interactive Dewy session
python3 -m tools.core check examples/tour.dewy
python3 -m tools.core build examples/tour.dewy --release -o /tmp/tour
python3 -m tools.core path                       # immutable executable for scripts/benchmarks
python3 -m tools.core --bootstrap test           # also verify the independent C bootstrap
```

The first command builds from C. Later commands reuse the compiler when its
sources, libraries and build inputs are unchanged, or rebuild with the previous
compiler. Failed builds stop the command and leave the previous toolchain
intact; tests never silently fall back to it. Concurrent invocations share a
build lock and use separate immutable snapshots. Unchanged launches compare file
metadata rather than hashing every source. `--bootstrap` forces a fresh C build.
The cache and build logs live in `__dewycache__/compact-core/`; removing that
directory resets it.

`test` uses the checkout's `.venv/bin/python` when available, otherwise the
current Python. Install pytest, pytest-xdist and Pillow there (`uv sync` installs
the dev group) and have Node available for the web checks. A full `test` uses up
to four workers when pytest-xdist is available, grouping compilation batches by
test function and build mode. Commands with extra pytest arguments stay serial
unless given `-n`. Tests stop at the first failure; `test --maxfail=0` collects
every failure.

`test --quick` selects language/value behavior, imports, diagnostics, a headless
game model and the development driver, on native/web and default/release builds.
The full gate adds the broader regression corpus, rendering, networking, watch
and editor coverage. Value checks share small compilation batches; a failing
batch is split to identify the responsible cases, and `-k <case-name>` gives a
single-case reproducer. Shader checks need EGL/GLES3 libraries and are skipped
locally when unavailable. The initial build needs Python, a C compiler and `make`.

For routine edits, start with a relevant `test -k ...` selection and use the
quick suite when a change crosses language/tooling boundaries. CI
(`.github/workflows/ci.yml`) bootstraps from C, runs the full gate on Linux
x86-64 and smoke checks on Windows x64, macOS ARM64 and Linux ARM64 using
cross-built compilers, then uploads `dewy-core-<host>-<commit>` toolchains.

## Use the current compiler from another project

`tools/dewy` is an executable launcher with the same arguments as the compiler:

```sh
/path/to/dewy-lang/tools/dewy main.dewy
/path/to/dewy-lang/tools/dewy build main.dewy --release -o game
/path/to/dewy-lang/tools/dewy --version
```

It keeps the caller's working directory and replaces itself with the current
compiler, rebuilding it only when its inputs changed. `dewy-core --print-lib`
reports the active library directory, including `DEWY_CORE_LIB` overrides.

## Editor

The [VS Code extension](../editors/vscode/README.md) uses the compiler for
diagnostics, completions, hover and definitions on unsaved text, and for
debugging with CodeLLDB. Set `dewy.core.path` to the absolute path of
`tools/dewy` for checkout development, or to a standalone
`bin/dewy-core`. **Dewy: Restart Core Language Server** picks up compiler edits.

## Build a standalone toolchain

```sh
python3 -m tools.compiler.build --bootstrap --output /tmp/dewy-core
/tmp/dewy-core/bin/dewy-core --version
/tmp/dewy-core/bin/dewy-core new /tmp/my-dewy-game
/tmp/dewy-core/bin/dewy-core watch /tmp/my-dewy-game/main.dewy
/tmp/dewy-core/bin/dewy-core build examples/paddle.dewy --target wasm -o /tmp/paddle
```

The output directory must be new. It contains a standalone `bin/` and `lib/`,
source snapshots, build logs and a hash manifest (`build.json`). The independent
bootstrap requires Linux x86-64. Rebuild from an existing compiler without C:

```sh
python3 -m tools.compiler.build --seed /tmp/dewy-core/bin/dewy-core --output /tmp/dewy-core-next
```

For a quick compiler edit, reuse an existing toolchain's libraries:

```sh
/tmp/dewy-core/bin/dewy-core build compiler/main.jo -o /tmp/dewy-core/bin/dewy-core
```

Changes in `lib/` require rebuilding the toolchain or setting
`DEWY_CORE_LIB="$PWD/lib"` for the compiler under test. Package a toolchain with
the layout CI uses; packaging verifies the payload against the build manifest:

```sh
python3 -m tools.compiler.package /tmp/dewy-core --output /tmp/dewy-core-linux-x86_64.tar.gz
```

The compiler cross-builds for Windows x64, macOS ARM64 and Linux ARM64
(`python3 -m tools.compiler.hosts build`); the `compiler_hosts` check covers
those builds.

### Optional optimized compiler host

On Linux x86-64 the compiler itself can additionally be optimized by GCC:

```sh
python3 -m tools.compiler.build_optimized_host "$(dirname "$(dirname "$(python3 -m tools.core path)")")" \
  --output /path/to/new-optimized-toolchain
```

Add `--lto` for cross-file optimization, `--pgo` to train on a fixed set of
builds, `--optimization 2|3` to choose the level, and `--frame-pointers` for
profilers that walk frame chains. `HOST_BUILD.json` records provenance. This
changes only the compiler host, not application code generation, and
`tools.core test` keeps using the native development build.

## Measure

Runners in `tools/compiler/` compare compiler executables with sequential,
alternating samples and write JSON reports:

- `benchmark_compile`: compile latency on representative programs and a
  compiler self-build. `build --time` reports compiler phases and loaded source.
- `benchmark_throughput`, `benchmark_types`, `benchmark_corpus`: compile throughput
  and type-checking scale.
- `benchmark_apps`: the [application benchmarks](../bench/README.md) against C;
  `benchmark_recursive`, `benchmark_graphemes`, `benchmark_callbacks`,
  `benchmark_matrix`, `benchmark_broadcast`, `benchmark_parallel` and others cover
  specific runtime features.
- `performance_gate`: compile and runtime regressions against a pinned reference
  (`performance_reference.json`) and the previous stage.
- `benchmark_instructions`: retired-instruction counts via
  `count_instructions.c`, for locating extra compiler work on a busy host.
- `fuzz`: bounded differential testing of native/web, default/release and `-g`
  builds on generated programs.

Run timing comparisons on a quiet machine with matched inputs and one emission
worker. `SLOPPY_PAR_TIME=1` adds optimizer and emission timing.

## Source layout and bootstrap

- `compiler/frontend.jo` dispatches Dewy and implementation-language source.
- `compiler/dewy_fast.jo` lexes and parses Dewy inside the compiler process;
  `compiler/dewy_parse.jo` projects the syntax tree into the compact AST.
- `compiler/` contains checking, lowering, code generation and tools, written in
  the inherited implementation language (`.jo`).
- `lib/` contains containers, platform support, graphics, input, audio and other
  libraries. Dewy programs can import `.jo` library modules directly.
- `stage0/` is the small independent C bootstrap. It implements a smaller
  language; `bootstrap/frontend.jo` and `bootstrap/dewy_fmt.jo` stand in for the
  Dewy frontend while it builds the first compiler generation. That compiler
  builds the complete compiler, which builds itself again.

Build hashes identify provenance; byte-identical executables are not required.
Runtime tuning variables inherited from Sloppy keep their `SLOPPY_*` names for now.
