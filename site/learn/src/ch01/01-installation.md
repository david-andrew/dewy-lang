# Installation

The current quick installer supports x86-64 Linux:

```bash
curl -fsSL https://dewy-lang.org/install.sh | bash
```

It installs the `dewy` hosted compiler and the `udewy` bootstrap compiler under `~/.dewy`. Open a new terminal and check the installation:

```bash
dewy --version
```

From a source checkout, run the hosted compiler with:

```bash
python -m dewy program.dewy
```

The [browser playground](../../playground/) is useful for small experiments without a local installation. It currently runs µDewy, Dewy's bootstrap subset, rather than every construct described in this book.

These are current tooling constraints, not intended language restrictions. See the [implementation appendix](../appendices/language-and-compiler.md#platform-notes) for context and the website's [installation page](../../install/) for up-to-date platform details.
