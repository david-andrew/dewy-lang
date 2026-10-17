# Dewy on the compact core

[`settings.dewy`](settings.dewy) loads typed JSON with defaults, updates a record
copy, and saves/loads a full-width player ID without rounding. Run it with
`python3 -m tools.core run examples/sloppy_core/settings.dewy`.

Start with [`tour.dewy`](tour.dewy) and the [language guide](../../core/LANGUAGE.md)
for a terminal example of functions, records, copies, comprehensions, Unicode
text, optional values and destructuring. [`entities.dewy`](entities.dewy) adds
user generics, the bundled `Pool<T>` and `Heap<T>`, stable entity handles and a
priority queue of damage events. It shows that removing/replacing an entity does
not redirect old events to the replacement, and that a copied world remains
independent:

```sh
python3 -m tools.core run examples/sloppy_core/entities.dewy
```

```text
Guard health: 75
Snapshot health: 100
Replacement health: 100
Old handle valid: false
```

[`pool_inventory.dewy`](pool_inventory.dewy) measures repeated scalar updates
inside managed inventories through stable handles, while keeping an independent
snapshot. It prints the updated checksum, snapshot checksum and kernel time in
nanoseconds. Run the paired benchmark with independent Python checks:

```sh
python3 -m tools.sloppy_core.benchmark_pool /tmp/dewy-core/bin/dewy-core \
  --baseline /tmp/previous-core/bin/dewy-core --output /tmp/pool-results.json
```

Seven alternating native release runs at one million updates measured 100.48 ms
before direct Pool updates and 23.96 ms after, about 4.2× faster for this workload.
The snapshot is retained throughout the measured loop. This is a before/after
comparison of the same Dewy program; native/web correctness is tested separately.
See [the source-core audit](../../dewy/audits/2026-10-17/README.md).

[`history.dewy`](history.dewy) demonstrates a bounded game-position history.
Its [`ring.dewy`](ring.dewy) module is a generic container written entirely in
Dewy: `push` overwrites the oldest entry when full, `ring[i]` uses its indexing
protocol, and nested assignments write back through its setter. The history
keeps an independent rewind snapshot while editing the current position.

```sh
python3 -m tools.core run examples/sloppy_core/history.dewy
```

The container exposes `new_ring<T>(capacity)`, `.push(value)`, `.len()` and indexing
from oldest to newest. Invalid capacity or indices panic. Use the factory to
construct it; its public storage fields are implementation details. Copying is
cheap until a copy is modified, when ordinary array value semantics apply.

[`exact_integers.dewy`](exact_integers.dewy) uses the bundled `bigint` module to
compute 100!, choose 50 items from 100, perform signed floor division and print
2^256. Its arithmetic and decimal formatting are exact on native and web.

```sh
python3 -m tools.core run examples/sloppy_core/exact_integers.dewy
```

[`exact_rationals.dewy`](exact_rationals.dewy) builds on the same integers to
compute harmonic sums and dice probabilities as reduced fractions, with exact
`+`, `-`, `*`, `/`, floor/remainder operations and signed powers.

```sh
python3 -m tools.core run examples/sloppy_core/exact_rationals.dewy
```

`paddle.dewy` is a playable mouse-controlled paddle game. Its model and drawing
code are Dewy. The pinned Sloppy platform library supplies the window, input,
font, renderer, native frame loop, and WebAssembly browser host.

`physics.dewy` is a larger interactive playground adapted from the pinned Sloppy
physics example: a 57-body scene with a box pyramid, pinned bridge, rope and
wrecking ball. Left-drag a body, right-click to add a box, press B or middle-click
to add a ball, and R to reset. `physics_scene.dewy` contains scene construction
and simulation; the repository-owned `physics` library supplies collision and
joint solving. These programs run natively and in the browser.

`forest.dewy` brings the same workflow to 3D: rolling terrain, 600 instanced tree
meshes, a moving beacon, shadows, fog and bloom. Drag to orbit, use the wheel to
zoom, Space to pause automatic orbit, R to reset and Escape to quit. Terrain
callbacks, placement, camera control and drawing are Dewy; `forest_model.dewy`
keeps deterministic scene construction separate from the window.

[`dunes.dewy`](dunes.dewy) is a playable desert journey adapted from Sloppy's
MIT-licensed Dunes example. Walk with WASD/arrows or the left stick, jump with
Space/gamepad A, and hold it while falling to glide. Q/E, right-drag or the right
stick turn the camera. Collect glyphs to lengthen your scarf and head toward the
beacon. Terrain, animated cloth, custom sand/shadow and beam shaders, input,
sound and game logic are Dewy. [`dunes_model.dewy`](dunes_model.dewy) contains
the geometry and shader functions without starting a window.

After building the compiler as described in `tools/sloppy_core/README.md`:

```sh
CORE=/tmp/dewy-core/bin/dewy-core
# Live editing: save changes and the running game takes the new code.
$CORE watch examples/sloppy_core/paddle.dewy
$CORE watch examples/sloppy_core/physics.dewy
$CORE watch examples/sloppy_core/forest.dewy
$CORE watch examples/sloppy_core/dunes.dewy

$CORE build examples/sloppy_core/paddle.dewy -o /tmp/paddle
/tmp/paddle

# The wasm target emits a self-contained HTML file, including its web runtime.
$CORE build examples/sloppy_core/paddle.dewy --target wasm -o /tmp/paddle
# Open /tmp/paddle.html in a browser.
$CORE build examples/sloppy_core/physics.dewy --release -o /tmp/physics
$CORE build examples/sloppy_core/physics.dewy --target wasm --release -o /tmp/physics
$CORE build examples/sloppy_core/forest.dewy --release -o /tmp/forest
$CORE build examples/sloppy_core/forest.dewy --target wasm --release -o /tmp/forest
$CORE build examples/sloppy_core/dunes.dewy --release -o /tmp/dunes
$CORE build examples/sloppy_core/dunes.dewy --target wasm --release -o /tmp/dunes
```

Use `--release` for the optimizing compiler. The default development build
already runs the game. The current example uses a 1280×720 logical playfield.
The physics playground exercises imported library types, named/default arguments,
mutable receivers, optional handles, tuple results, record copies and rendering.

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

The physics model gate checks gravity, dragging, joint/body removal and independent
world copies on both targets and in both modes. The browser was also exercised
with mouse/keyboard input and no console errors. A 1,200-step native release
simulation of the 57-body scene took a median 178.32 ms versus 178.64 ms for the
corresponding pinned Sloppy example, compiled with the same owned core and
libraries. Seven alternating measured runs agreed on the position checksum;
setup and drawing were excluded. This demonstrates that the Dewy frontend adds
no measurable simulation cost for this workload, not a general physics benchmark.
See the source-core audit for inputs and measurements.

The forest model gate checks deterministic placement, height callbacks and
independent instance-array copies on both targets in both modes. The actual game
also runs through the native software renderer; all five games' web modules are
validated in debug/release. The forest was separately rendered in Chromium with
drag, zoom and reset exercised, with no console errors. Seven warmed compiler
runs gave median release builds of 323.08 ms native and 160.24 ms web on the
development machine. These are build measurements, not frame-rate claims.

![The Dewy forest running in the browser](../../dewy/audits/2026-10-16/source-core/forest-browser.png)

Dunes adds geometry checks on native/web in development/release modes, a native
software-rendered frame, and compilation/linking of generated shaders with a real
offscreen GLES driver. The full game was also rendered in Chromium with movement
input. Shader validation needs EGL/GLES3 libraries; CI installs them when absent.

![The Dewy Dunes game running in the browser](../../dewy/audits/2026-10-17/source-core/dunes-web.png)

## Multiplayer

[`netpong.dewy`](netpong.dewy) adapts Sloppy's two-player game, including its input,
invite screens and network library. The host simulates the ball and paddles;
the joining player sends movement and receives game state 30 times a second.
The winning state is sent immediately. Start two native instances in separate
terminals:

```sh
python3 -m tools.core build examples/sloppy_core/netpong.dewy -o /tmp/dewy-netpong
HOST=1 /tmp/dewy-netpong
JOIN=localhost /tmp/dewy-netpong
```

The default port is 47200; `DEWY_NETPONG_PORT` changes it. The host shows a
copyable `ws://` address including the port. A client can pass that complete
address through `JOIN` or enter it in the game's Join an address screen.
Arrows/WASD, a gamepad, and held mouse/touch input move the paddle.

A browser can join the same native host. Build and serve the page locally:

```sh
mkdir -p /tmp/dewy-netpong-web
python3 -m tools.core build examples/sloppy_core/netpong.dewy --target wasm -o /tmp/dewy-netpong-web/index
python3 -m http.server 8000 --bind 127.0.0.1 --directory /tmp/dewy-netpong-web
```

Open `http://localhost:8000/?join=ws://127.0.0.1:47200`. Browser pages connect to
native hosts; they cannot listen for WebSocket clients. HTTPS-hosted pages need
a secure WebSocket endpoint. The web build currently warns that native hosting
is unavailable; its host button is hidden.

Invite a friend and Join a friend retain the bundled direct-connection flow.
Native games share codes unless `WEB_PAGE` names a hosted build; browser games
use their own page address. Cross-network invite negotiation is not covered by
the local validation gate. That gate tests native peers, Node WebSocket clients,
Unicode/binary messages, clean disconnects and delivery of a winning game state.
The actual browser game was also connected to a native host and driven with
keyboard input.

![Netpong connected to a native host](../../dewy/audits/2026-10-17/source-core/netpong-browser.png)
