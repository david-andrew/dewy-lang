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

Experimental. The current compiler is a compact native/web compiler forked from
Sloppy and adapted to Dewy syntax and behavior; it implements a growing subset
of the language. The previous implementation (the Python/native compiler, µDewy
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
| `tools/` | `tools/dewy` launcher, `tools/core.py` driver, `tools/compiler/` build, packaging and benchmark tooling |
| `bench/` | application benchmarks with C counterparts |
| `docs/` | goals, language guide, development guide, design notes, origin |
| `editors/vscode/` | VS Code extension |
| `site/` | the dewy-lang.org website |

## Documentation

[Goals](docs/GOALS.md) · [language guide and tour](docs/LANGUAGE.md) ·
[developing the compiler](docs/DEVELOPMENT.md) · [design notes](docs/design/README.md) ·
[origin and licensing](docs/origin/ORIGIN.md)

## Published installer

`curl -fsSL https://dewy-lang.org/install.sh | bash` installs the **previous
implementation**, not the compiler in this repository.
