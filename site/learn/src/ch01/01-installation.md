# Installation

On Linux or macOS, run:

```sh
curl -fsSL https://dewy-lang.org/install.sh | bash
```

On Windows, in PowerShell:

```powershell
irm https://dewy-lang.org/install.ps1 | iex
```

The installer downloads a toolchain for your system, checks its digest, and puts `dewy` on your `PATH` (open a new terminal afterwards). Supported hosts are Linux x86-64 and ARM64, macOS ARM64 and Windows x64. Check that it worked:

```sh
dewy --version
```

Later, `dewy update` installs the newest toolchain and `dewy rollback` returns to the previous one. The [installation guide](/install/) covers custom locations, pinned releases and what the installer changes.

Dewy has no stable release yet: the installer follows the development channel, and the language can still change between versions.

## From a checkout

To work on Dewy itself, or to try the very latest compiler, clone the repository. The first run builds the compiler from a small C seed, which needs Python 3, a C compiler and `make`, and takes well under a minute:

```sh
git clone https://github.com/david-andrew/dewy-lang
cd dewy-lang
./tools/dewy examples/tour.dewy
```

`./tools/dewy` accepts the same commands as `dewy` and rebuilds the compiler when its sources change.
