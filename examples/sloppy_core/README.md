# Dewy on the compact core

`paddle.dewy` is a playable mouse-controlled paddle game. Its model and drawing
code are Dewy. The pinned Sloppy platform library supplies the window, input,
font, renderer, native frame loop, and WebAssembly browser host.

After building the compiler as described in `tools/sloppy_core/README.md`:

```sh
CORE=/tmp/dewy-core/bin/dewy-core
# Live editing: save changes and the running game takes the new code.
$CORE watch examples/sloppy_core/paddle.dewy

$CORE build examples/sloppy_core/paddle.dewy -o /tmp/paddle
/tmp/paddle

# The wasm target emits a self-contained HTML file, including its web runtime.
$CORE build examples/sloppy_core/paddle.dewy --target wasm -o /tmp/paddle
# Open /tmp/paddle.html in a browser.
```

Use `--release` for the optimizing compiler. The default development build
already runs the game. The current example uses a 1280×720 logical playfield.
It is a small integration example, not a complete port of Sloppy's larger games.

For display-independent rendering and scripted mouse input:

```sh
SLOPPY_SOFTWARE=1 SLOPPY_SCREENSHOT=/tmp/paddle.png SLOPPY_FRAMES=30 \
  SLOPPY_INPUT=1:mouse=800x620 /tmp/paddle
```

`paddle_model.dewy` has no graphics dependency. The core test suite checks
movement, independent record copies, paddle returns, misses, and paddle limits
on native and WebAssembly targets. It also builds the actual game and exercises
its software renderer. Web execution was separately checked in Chromium,
including mouse input and a rendered frame, with no console errors.

The first native development build reported 150 ms across compiler phases;
the web build reported 97 ms. These are initial observations for this small game,
not repeated build medians. See the restart audit for evidence and limitations.

For a smaller starting point, run `dewy-core new my-game`, then
`dewy-core watch my-game/main.dewy`. The generated README includes native and web
build commands. `dewy-core new my-program program` starts a terminal program.
