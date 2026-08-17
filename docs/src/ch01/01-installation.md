# Installation

Linux x86_64. The installer puts the `udewy` bootstrap compiler in `~/.dewy` (a `dewy` binary will land next to it later):

```bash
curl -fsSL https://raw.githubusercontent.com/david-andrew/dewy-lang/master/install.sh | bash
```

Open a new terminal, then:

```bash
udewy --help
```

From a source checkout, the Python Dewy compiler is `python -m dewy`, and udewy can be run with `python -m udewy`.
