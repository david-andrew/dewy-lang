# Getting Started

Getting from nothing to a running program takes a minute:

1. [Install Dewy](01-installation.md) with one command. The toolchain is a single folder with the compiler and its libraries; it needs no Python, no C compiler and no system packages.
2. [Write your first program](02-hello-world.md), run it, and build an executable.
3. Learn the edit loop: `dewy watch` reruns on every save, `dewy test` runs your tests, and the [VS Code extension](/tools/) shows errors as you type.
4. When something surprises you, [stop and look](03-debugging.md).

If you would rather read first, the [tour](../pitch.md) shows the whole language on one page.

## What you get

| Command | What it does |
|---|---|
| `dewy file.dewy` | compile and run a program |
| `dewy` | the interactive prompt |
| `dewy check file.dewy` | report errors without building |
| `dewy build file.dewy -o name` | build a native executable (`--release` to optimize) |
| `dewy build file.dewy --target wasm32 -o name.html` | build a web page that runs the program |
| `dewy watch file.dewy` | rerun the program after each edit |
| `dewy test file.dewy` | run the file's `$test` functions |
| `dewy new name program` | start a project (`arcade`, `platformer`, `3d`, `story` and `online` start a game) |

Native builds target Linux on x86-64 and ARM64, macOS on Apple silicon and Windows on x86-64. Building for another system takes only `--target` (for example `--target x86_64-windows`): the compiler writes the executable itself, with no external linker or C toolchain.
