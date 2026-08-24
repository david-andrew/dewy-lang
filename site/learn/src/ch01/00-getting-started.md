# Getting Started

This section gets a Dewy program from a source file to a running process.

1. [Install Dewy](01-installation.md), or open the browser playground for µDewy experiments.
2. [Write and run your first program](02-hello-world.md).
3. Continue into the core language with [A Few Ideas That Organize Dewy](../ch05/00-general.md).

Dewy source conventionally uses the `.dewy` suffix. A directory may begin as one source file and grow into several modules without adopting a separate project language.

The compiler accepts top-level executable code, so small programs do not need a `main` wrapper. Applications may define `main` when an explicit entry function is useful.

Current installer, platform, and playground limitations are recorded in [Language Design and Compiler Support](../appendices/language-and-compiler.md#platform-notes).
