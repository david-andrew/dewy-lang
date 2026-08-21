# Installation

On Linux x86-64, the installer puts the `udewy` bootstrap compiler and
the Python-hosted `dewy` compiler in `~/.dewy`:

```bash
curl -fsSL https://dewy-lang.org/install.sh | bash
```

Open a new terminal, then:

```bash
dewy --version
```

The first `dewy` invocation finds Python 3.12 or newer and caches its
path. From a source checkout, use `python -m dewy`. µDewy can be run
with `python -m udewy`.

See the website's [installation page](../../install/) for current target
and platform limits.
