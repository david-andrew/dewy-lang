# Installation

The current quick installer supports x86-64 Linux with glibc 2.34 or newer:

```bash
curl -fsSL https://dewy-lang.org/install.sh | bash
```

It installs the verified native `dewy`/`udewy` pair and its matching library under `~/.dewy`; Python is not needed. Open a new terminal and check the installation:

```bash
dewy --version
```

The native compiler is still a development version with some hosted-parity gaps. From a source checkout, the hosted compiler remains available with Python 3.14 or newer:

```bash
python -m dewy program.dewy
```

The [browser playground](../../playground/) is useful for small experiments without a local installation. It currently runs µDewy, Dewy's bootstrap subset, rather than every construct described in this book.

These are current tooling constraints, not intended language restrictions. See the [implementation appendix](../appendices/language-and-compiler.md#platform-notes) for context and the website's [installation page](../../install/) for up-to-date platform details.
