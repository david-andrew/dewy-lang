# Source-level core evidence

- `initial-build.json`, `initial-tests.log`: first compact-core slice, 18 cases.
- `loops-build.json`, `loops-tests.log`: imports and combined loops, 25 cases.
- `particles-initial.json`: three builds and 25 executions per build for each of
  five compiler modes. All 375 checksums agree. Each compilation uses a fresh
  directory/prelude cache; OS caches are retained. Runtime medians and limits
  are reported in `tools/sloppy_core/README.md`.
- `game-build.json`, `game-tests.log`: 31 cases, including float division,
  inverted comparisons, model execution on native and wasm, and native software
  rendering. Node executes the compiler's generated web host for model tests.
- `ergonomics-build.json`, `ergonomics-tests.log`: 77 checks in 4.39 seconds,
  extending coverage to inferred/generic functions, closures, higher-order calls,
  defaults, aliases, forward record declarations, and live loop bounds when an
  array grows. Value cases now run in debug and release; model tests run both
  modes on both native and wasm targets.
- `bootstrap-build.json`, `bootstrap-tests.log`: independent C bootstrap →
  pristine pinned Sloppy → adapted core → core self-build. The last executable
  passes all 77 checks in 4.51 seconds. The syntax parser still comes from the
  recorded native Dewy seed. The C bootstrap's smaller accepted syntax could
  not compile the adapter directly; building pristine Sloppy first avoids
  constraining adapter implementation to that bootstrap subset.
- `paddle-native.png`, `paddle-web.png`: inspected integration screenshots, not
  golden images constraining future rendering. The native frame used software
  rendering, 30 frames, and scripted mouse input at (800,620); the web frame
  used Chromium and mouse input at (900,620).
- `paddle-native.log`, `paddle-browser.json`: native render observations and
  independent browser check. T3's browser snapshot timed out twice, so the web
  check used local Playwright/Chromium. The browser had no page/console errors.

The browser and native screenshots were built with the immediately preceding
game compiler (`game-render-build.json`), before the inverted-comparison fix.
That fix is covered by the native/wasm model tests; the drawing example does not
use inverted comparisons. Native build phase times were 93.9/52.5/3.4 ms
(check/codegen/write); web times were 69.7/10.8/16.3 ms. These are initial single
observations, not a benchmark series. No full-language certification is claimed.
