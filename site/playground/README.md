# Compiled browser examples

`examples.json` contains complete Dewy programs with explicit check/run intent and exact stdout for run entries.
Games (`kind: game`) are check entries built from `examples/`; terminal programs (`kind: program`) are run entries. The site build
compiles them to wasm with the current toolchain, executes run entries under Node, and
ships self-contained HTML pages. Native ladder results are never web coverage.

The public page shows each game's poster and each program's source and expected output, then runs a fresh
opaque-origin iframe with network denied, bounded output and Stop. Programs stop after 15 seconds;
one game runs at a time, for at most ten minutes.
There is no user-editable compiler. The optional in-browser compiler pilot was
not attempted; it is not required for publication.
