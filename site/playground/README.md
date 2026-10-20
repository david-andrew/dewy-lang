# Compiled browser examples

`examples.json` contains complete Dewy programs with explicit check/run intent and exact stdout for run entries. The site build
compiles them to wasm with the current toolchain, executes run entries under Node, and
ships self-contained HTML pages. Native ladder results are never web coverage.

The public page shows source and expected output, then runs a fresh opaque-origin
iframe with network denied, bounded output, Stop and a 15-second lifetime.
There is no user-editable compiler. The optional in-browser compiler pilot was
not attempted; it is not required for publication.
