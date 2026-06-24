# AGENTS.md

Guidance for cloud agents and automated development environments working in this repository.

## Cursor Cloud specific instructions

### What this repo is

**dewy-lang** is a programming-language toolchain (not a client/server app). There is no docker-compose stack or database. End-to-end validation means compiling and running Dewy/udewy programs, or running pytest.

| Component | Role |
|-----------|------|
| **Dewy** (`src/`) | Main language compiler/interpreter (WIP) |
| **udewy** (`udewy/`) | Bootstrappable subset compiler; default target is Linux x86_64 ELF |
| **Tests** (`tests/`) | pytest integration and compiler tests |

### Required system tools

- **Python 3.12+** — use `python3` (the `./dewy` shell wrapper invokes `python`, which may not exist on minimal Linux images)
- **GNU `as` + `ld`** — required for udewy x86_64 compile-and-run

### Python dependencies

Dev tools are declared in `pyproject.toml` under `[dependency-groups] dev`. After startup refresh:

```bash
export PATH="$HOME/.local/bin:$PATH"
python3 -m pytest ...
python3 -m ruff check ...
```

Optional: `pip install rich` for nicer Dewy error output.

### Core commands (hello world)

```bash
# Dewy interpreter
python3 -m src.frontend examples/hello.dewy --interpret

# udewy compile + run (x86_64)
python3 -m udewy udewy/tests/test_hello.udewy

# Compile only
python3 -m udewy -c udewy/tests/test_hello.udewy
```

Build artifacts land in `__dewycache__/` in the working directory.

### Tests and lint

```bash
# Fast udewy-focused subset (94+ tests pass without optional toolchains)
python3 -m pytest tests/ --ignore=tests/python_misc/test_udewy_sdl_import_demo.py

# Lint (many pre-existing findings; ruff should run successfully)
python3 -m ruff check src udewy tests
```

Some tests require optional tooling and will fail or error without it:

- **SDL demos** — run `python3 udewy/third_party/sdl/setup_sdl.py` first; `test_udewy_sdl_import_demo.py` may fail collection if `udewy.backend.sdl_desktop` is absent
- **Web playground / WASM parity** — `wat2wasm` (wabt), Node.js, and `python3 udewy/third_party/web/setup_web_compiler.py`
- **riscv / arm backends** — cross toolchains + QEMU
- **mdBook docs** — `mdbook` CLI (`cd docs && mdbook serve`)

### No persistent dev server

Unlike web apps, there is nothing to `npm run dev`. The only ephemeral server is udewy’s built-in `--serve-wasm` for WASM HTML output.
