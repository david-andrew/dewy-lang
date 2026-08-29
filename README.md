<p align="center">
  <img src="https://raw.githubusercontent.com/david-andrew/dewy-lang/master/assets/dewy_logo_128x128.png" alt="Dewy logo" />
</p>

# The Dewy Programming Language

[![Tests](https://github.com/david-andrew/dewy-lang/actions/workflows/tests.yml/badge.svg?branch=master)](https://github.com/david-andrew/dewy-lang/actions/workflows/tests.yml)

Dewy is a general purpose programming language with a focus on engineering.

> **NOTE: Still very work in progress, and the docs (including this README) are frequently out of date!**

## Current Status

### dewy

The main compiler lives under [dewy/](dewy/)

A VS Code extension with a TextMate grammar for Dewy lives under [dewy/vscode-dewy/](dewy/vscode-dewy/) (not yet published to the marketplace; install it from the folder with `code --install-extension` after packaging, or symlink it into `~/.vscode/extensions`).

### udewy

The micro subset, udewy, is largely feature complete and available under [udewy/](udewy/). Currently only supports linux x86_64.

A vscode extension for syntax highlighting is available at https://marketplace.visualstudio.com/items?itemName=RedFoxLabs.udewy

## Installation

Linux x86_64. This installs the `udewy` bootstrap compiler and the current Python-backed `dewy` compiler into `~/.dewy`:

```
curl -fsSL https://dewy-lang.org/install.sh | bash
```

The first `dewy` invocation checks for Python 3.14 or newer and caches the compatible interpreter path for later runs. You can then run a program with:

```
dewy path/to/my_script.dewy
```

From a checkout, the equivalent command is:

```
python -m dewy path/to/my_script.dewy
```

`udewy` programs can also be run with `python -m udewy` from a checkout.

## Examples

The hero program on the [dewy-lang.org](https://dewy-lang.org) front page lives at [examples/hero.dewy](examples/hero.dewy) and runs today:

```
python -m dewy examples/hero.dewy
```

For more working programs, see the executable fixtures in [dewy/tests/](dewy/tests/) (each one compiles and runs in CI) and the curated, status-labeled examples on the [site examples page](https://dewy-lang.org/examples/). Implementation status for every language feature is tracked in [dewy/status.md](dewy/status.md).

Programs written for the previous interpreter implementation are archived in [examples/old/](examples/old/); most have not yet been ported to the current compiler.

## Buzzwords

Just an (unsorted) collection of common buzzwords that apply to Dewy

- expression oriented
- statically compiled
- strongly typed
- type inference
- parametric polymorphism
- refinement types / liquid types
- effects system
- first-class types
- value semantics
- hybrid nominal-structural type system
- first-class functions
- function overloading
- array programming / broadcasting
- units of measure
- (mostly) automatic memory management, no GC
- ergonomic strings (extended grapheme clusters, interpolation, multilin, flexible delimiters)
- compiletime evaluation for metaprogramming
- juxtaposition (type-directed call, multiply, index)

## Documentation

The language website, learning guide, reference, examples, and µDewy playground are built from [`site/`](site/) and published at https://dewy-lang.org/.
