<p align="center">
  <img src="https://raw.githubusercontent.com/david-andrew/dewy-lang/master/assets/dewy_logo_128x128.png" alt="Dewy logo" />
</p>

# The Dewy Programming Language

Dewy is a general purpose programming language with a focus on engineering.
A binding names a value: assignment, argument passing and return give the
receiver its own value, and sharing is either unobservable or written in the
source. Ordinary programs should be comfortable to write, run well without
pervasive annotations, and compile from source quickly enough to stay in the
edit loop. Games are a primary customer. See [docs/GOALS.md](docs/GOALS.md).

## Status

Experimental (version 0.0.0). The compiler is a compact native/web compiler
that implements a growing part of the designed
language; the acceptance ladder in [ROADMAP.md](ROADMAP.md) tracks how much. The previous implementation (the Python/native compiler, µDewy
and their library) is archived in git tag `archive/master-pre-restart`.

## Build, run and test

Needs Python 3.14, a C compiler and `make` (Linux x86-64 for the C bootstrap),
plus pytest, pytest-xdist, Pillow and Node for the test suite (`uv sync`).

```sh
./tools/dewy examples/tour.dewy                  # build the compiler if needed, then run
./tools/dewy test examples/paddle_tests.dewy     # run a program's test blocks
python3 -m tools.core test --quick               # smoke suite
python3 -m tools.core test                       # full suite
python3 -m tools.core --bootstrap test           # rebuild from C, then the full suite
python3 -m tools.compiler.build --bootstrap --output /tmp/dewy-core   # standalone toolchain
```

## Layout

| Path | Contents |
| --- | --- |
| `compiler/` | the compiler (implementation language `.jo`) |
| `lib/` | runtime and libraries |
| `stage0/`, `bootstrap/` | the C bootstrap and its stand-in frontend |
| `examples/` | example programs and games |
| `tests/` | the test suite; `tests/legacy_corpus/` holds untested pre-restart programs |
| `tools/` | `tools/dewy` launcher, `tools/core.py` driver, `tools/compiler/` build, packaging, speed gate and fuzz tooling |
| `bench/` | application benchmarks with C counterparts |
| `docs/` | goals, language guide, development guide, design notes |
| `editors/vscode/` | VS Code extension |
| `site/` | the dewy-lang.org website |

## Documentation

[Goals](docs/GOALS.md) · [roadmap](ROADMAP.md) · [language guide and tour](docs/LANGUAGE.md) ·
[developing the compiler](docs/DEVELOPMENT.md) · [design notes](docs/design/README.md)

## Install

```sh
curl -fsSL https://dewy-lang.org/install.sh | bash        # Linux x86-64/arm64, macOS arm64
irm https://dewy-lang.org/install.ps1 | iex                 # Windows x64 (PowerShell)
```

This installs the latest development toolchain (a GitHub prerelease, version 0.0.0) into
`~/.dewy`; `dewy update` and `dewy rollback` manage it. The VS Code extension
(RedFoxLabs.dewy on the Marketplace and Open VSX) bundles the compiler.
