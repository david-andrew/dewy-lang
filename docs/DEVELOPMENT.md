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

## Golden cases and the acceptance ladder

```sh
python3 -m tools.core cases [-k WORDS] [--update]   # tests/cases golden files
python3 -m tools.core ladder [--update-ratchet]     # acceptance-ladder scoreboard
```

- Language behavior that only needs stdout, an exit code or a diagnostic is a
  golden case: `tests/cases/<area>/<name>.dewy` with `.out`/`.err` files and an
  optional header ([format](../tests/cases/README.md)). Pytest
  (`tests/test_core_*.py`, shared helpers in `tests/support.py`) is for
  multi-file programs, servers, timing, the editor and IR inspection.
- `test` runs the cases first (`--quick`: those marked `# quick`), then, for
  the full gate, the ladder's core versions and its ratchet, then pytest. `-k`
  and `-n` apply to all of them.
- The [ladder](../tests/ladder/README.md) builds each program's `design.dewy`
  and `core.dewy` natively in release mode and compares stdout with
  `expected.out` from independent Python oracles. Every core version must pass;
  design programs listed in `ladder.json`'s `design_passing` must keep
  passing, and `--update-ratchet` adds newly passing ones.

## Fuzzing Dewy programs

```sh
python3 -m tools.core fuzz [--seed N] [--count N] [--minutes M]   # default: 50 seeds
python3 -m tools.core fuzz --seed 259 --print                      # one program and its oracle output
```

- `tools/compiler/dewy_fuzz_programs.py` generates typed, bounded programs in
  the documented surface: fixed-width and checked `int` arithmetic, floats,
  records, arrays, dicts and sets, snapshots, `@` places, closures, loops,
  ranges, comprehensions, `if`/`match`, optionals and unions, errors with
  `or_throw`, interpolation, recursion and `$runtime_assert`. A Python
  interpreter of the same tree is the oracle; it copies values eagerly and
  shares nothing with the compiler.
- Each seed also yields metamorphic variants that must print the same output:
  an identity copy, reordered independent statements, an outlined helper and a
  loop rewritten as a comprehension.
- `tools/compiler/dewy_fuzz.py` compiles a batch of programs as modules of one
  program in each mode (native and web, default and release), runs it once and
  compares each program's output with the oracle. A failure is confirmed alone,
  shrunk, and written to `~/dev/tmp/dewy-fuzz-failures/<kind>-seed<N>/`
  (`--failures DIR` elsewhere) with the program, expected and actual output.
- To add a feature: a node with `render` and `eval`, a `Generator.block_<feature>`
  listed in `FEATURES`; variants and shrinking need nothing more. Programs the
  oracle cannot judge (an out-of-range index, too much work) are discarded and
  regenerated.
- The full gate runs a three-seed smoke check; `.github/workflows/fuzz-nightly.yml`
  fuzzes a fresh seed range for 25 minutes each night and uploads failures.
- `python3 -m tools.compiler.fuzz` is the older differential check of generated
  implementation-language (Jo) programs across build modes.

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

## Speed and bench

```sh
python3 -m tools.core speed                       # compile speed vs HEAD~1
python3 -m tools.core speed --base master --release
python3 -m tools.core speed --checkpoint speed-checkpoint
python3 -m tools.core bench                       # runtime kernels vs C
python3 -m tools.core bench -k "graph records"
```

`speed` is the compile-speed gate. It counts the user-space instructions that
compiling a fixed panel takes: the compiler's own source, a synthetic 22k-line
Dewy program and `examples/dunes.dewy` (`--release` adds the synthetic program
in release mode). It compares this checkout's compiler (working tree included)
with the base commit's and fails when any item needs more than `--limit`
percent (default 1) more. Each compiler is its commit's own fixed point and uses
its commit's library; base compilers are built in a temporary git worktree
(with the current compiler, or the base's C bootstrap when needed) and cached
by commit under `__dewycache__/speed/`. Counts come from `perf_event_open`
(`tools/compiler/count_instructions.c`), or from valgrind's cachegrind where
hardware counters are unavailable, as on CI. Every item runs twice and must
agree within 0.01%. A cached run takes about 10 s with counters, about 4
minutes under valgrind.

When a cost is intended, add a line `speed: accept <reason>` to the commit
message; any such line between the base and HEAD waives the base comparison.
`--checkpoint TAG` also compares with a fixed revision so that sub-limit losses
cannot compound silently; accept lines never waive it. The coordinator moves
the tag after reviewing accepted costs:
`git tag -f speed-checkpoint <commit> && git push -f origin speed-checkpoint`.
CI runs the gate (default panel) on every push against the previous pushed
commit.

`bench` builds the [application kernels](../bench/README.md) in Dewy default
and release modes and in C (`cc -O2`), runs each binary a few times
(`--runs`, default 3) and prints median kernel milliseconds, the Dewy/C ratios
and whether all outputs match. It is a quick look on a shared machine, not a
gate. `build --time` reports compiler phases; `SLOPPY_PAR_TIME=1` adds
optimizer and emission timing. `python3 -m tools.compiler.fuzz` runs bounded
differential checks of native/web, default/release and `-g` builds on
generated programs.

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

## Releasing the VS Code extension

Versions: the language stays at 0.0.0 until David decides otherwise. The extension
(`editors/vscode/package.json`) only gets **patch** bumps, at most **one release per day**;
a minor bump needs David's approval.

1. Bump the patch version in `editors/vscode/package.json`, commit, push.
2. `git tag vscode-vX.Y.Z && git push origin vscode-vX.Y.Z`.

`.github/workflows/extension.yml` packages `editors/vscode` and publishes it to the VS Code
Marketplace and Open VSX with no stored tokens (GitHub OIDC exchanged for short-lived
credentials). It runs in the GitHub environment `marketplace-publish`, which only admits
`vscode-v*` tags and the main branches.

One-time setup (mirrors Sloppy's):

- **Marketplace:** Azure managed identity → Federated credentials → GitHub Actions:
  organization `david-andrew` (ID `41205753`), repository `dewy-lang` (ID `141009909`),
  entity Environment `marketplace-publish`. Subject:
  `repo:david-andrew@41205753/dewy-lang@141009909:environment:marketplace-publish`.
  Put the identity's Client ID and Tenant ID in repository variables `AZURE_CLIENT_ID` and
  `AZURE_TENANT_ID`. Run the Extension workflow by hand with *whoami* to print the identity's
  Marketplace id and add it as a Contributor member of the RedFoxLabs publisher.
- **Open VSX:** Settings → Trusted Publishers → namespace RedFoxLabs → GitHub Actions: owner
  `david-andrew`, repository `dewy-lang`, workflow `extension.yml`, environment
  `marketplace-publish`.
