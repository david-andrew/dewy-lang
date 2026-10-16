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
- `collections-build.json`, `collections-tests.log`: 93 checks in 5.34 seconds,
  adding aliases, callable types (including mutable arguments), union narrowing,
  dictionary value copies, typed empty dictionaries, and key/value iteration.
- `editor-build.json`, `editor-tests.log`: 95 checks in 5.81 seconds. The LSP
  gate opens unsaved source, requests hover/definition, introduces semantic and
  syntax errors, and clears them without saving the file. Dewy formatting is
  disabled in the inherited formatter. Parser snapshots use Linux memfd files.
- `editor-checks.json`: five fresh `check` processes per workload, with OS caches
  retained. Medians: particle source 62 ms; paddle game 121 ms. This includes
  checking unused source functions and lowering without emission.
- `typed-application-build.json`, `typed-application-tests.log`: 101 checks in
  5.95 seconds. Bracket constructors and `.length` now resolve using actual
  types, removing the parser adapter's separate list of record names. Imported
  records (Dewy/Sloppy, qualified/unqualified, named/positional fields) and a
  record field named `length` are covered.
- `cached-length-build.json`, `cached-length-tests.log`: 109 checks in 6.46
  seconds, including arrays changing size in the body, through mutable arguments,
  through globals, and through the loop condition. The old fixed-path analysis
  missed calls in the condition; `condition-before-tests.log` reproduces an
  incorrect bounds panic in the prior core. The fixed analysis covers both sites.
- `cached-length-upstream-tests.log`: 22 pinned Sloppy array/copy/bounds/loop
  regressions, debug and release, pass in 1.33 seconds.
- `cached-length-initial-particles.json`: preliminary measurement before adding
  the condition-call safety fix; this prototype is not the retained compiler.
- `cached-length-particles.json`: retained compiler, three release builds and
  225 executions, alternating before/after/C within each input and repetition.
  All checksums agree. Million-particle medians: 257.44 → 197.06 ms, C 172.71 ms.
  Compile medians: 82.70 → 84.32 ms. The algorithm and live-loop source are unchanged.
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

## Fast default builds

Fixed-path loop analysis now runs in development builds as well as release.
This reuses stable array pointers, lengths and uniqueness checks without running
the full optimizer. `default-loops-particles.json` records three builds of each
core mode and 300 alternating executions across five sizes. Default kernel time
fell from 624 ms to 396 ms, while whole compilation moved from 71 ms to 73 ms.
Release was 203 ms and C (`-O2`) 174 ms in this run. Every checksum agreed.
`default-loops-tests.log` records 131 Dewy, LSP and pinned upstream checks passing
in 7.77 seconds, including mutation from loop conditions and bodies.

## Repository-owned compiler

`core/` now contains the compiler, libraries, C bootstrap and focused upstream
fixtures. The Sloppy checkout is no longer an input to building or testing. The
imported baseline is recorded in `core/UPSTREAM.json`; only seven imported files
changed initially, plus the new Dewy frontend and bootstrap dispatch seam.
The adapter moved from `tools/sloppy_core/dewy_parse.jo` to
`core/compiler/dewy_parse.jo`. The patch-generation layer was removed.

`repository-bootstrap-build.json` records the C → implementation frontend →
Dewy frontend → self-build route, reusing the previously built native syntax
parser. `repository-bootstrap-tests.log` records all 137 checks passing in
7.68 seconds on the resulting compiler. `repository-seeded-build.json` also
exercises rebuilding the syntax parser with the old native Dewy seed and building
the core with the newly bootstrapped compiler; its native/web model, CLI identity
and unsaved editor smoke are recorded in `repository-seeded-tests.log`.

The compiler identifies itself as `dewy-core 0.1.0-dev`. Its inherited automatic
Sloppy updater is removed. Dewy-inappropriate REPL, package editing and project
scaffolding commands are explicitly unavailable until adapted; `.jo` remains
the implementation/library language. The existing installed compiler and the
user's dirty Sloppy checkout are unchanged.

## Live reload and new projects

`dewy-core new <directory> [game|program]` now creates Dewy sources and local
instructions. The game template builds natively, renders a headless frame, and
builds to a self-contained web page. An existing directory is never overwritten.
Watch messages/cache names identify Dewy. The native watch tests save by atomic
rename, update an imported function, retain working code across a compiler error,
and preserve a live counter when a new record field is added with a default.
Ordinary terminal programs rerun after an edit. All 142 combined checks pass in
9.53 seconds (`projects-tests.log`, compiler identity in `projects-build.json`).

## Practical numeric literals

Based integers, decimal scientific notation, all 8/16/32/64-bit signed and
unsigned type spellings, signed minima and unsigned 64-bit inference are now
supported. Numeric parsing checks bounds. High unsigned values pass through
typed lowering instead of the old signed literal fold, retaining correct shifts
and comparisons. Unary plus now returns its operand rather than falling through
to bitwise inversion; nonnumeric operands are rejected.

`numeric-tests.log`: 165 language/editor/watch/shared-core checks pass in 10.75 s.
`numeric-web-tests.log`: six additional debug/release WebAssembly checks cover
high unsigned constant arithmetic, narrow types and scientific literals. The
compiler is identified by `numeric-build.json`. Runtime integer arithmetic is
still fixed-width/wrapping; this is not an unbounded-number implementation.

## Array slices

Inclusive/exclusive end bounds, omitted bounds, full slices and independent
nested values now work through Dewy syntax. The pre-fix side-effect regression
(`slice-side-effects-before.log`) returned 121 instead of 42 when a bound call
mutated a uniquely owned source array. Shared lowering now holds the source value
across bound evaluation. Mutation and replacement cases pass natively and in
WebAssembly, in both build modes. A bad dynamic bound produces a slice panic.
All 186 combined checks pass in 12.07 seconds (`slices-tests.log`), including the
upstream loop/container regressions and live reload. `slices-build.json` identifies
the compiler. Stored range values and grapheme string slicing remain unsupported.

## VS Code integration

The existing extension now has an opt-in `dewy.core.path` setting and a small
client derived from the pinned Sloppy extension, with its MIT notice retained.
It exposes diagnostics, hover and definitions for file-backed Dewy documents,
sends unsaved text, watches Dewy/implementation imports, and supports restart and
configuration changes. No compiler is downloaded or installed. It starts the
configured executable only in a trusted workspace; an empty path disables it.

`vscode-client-tests.log` records three checks passing in 1.37 seconds: the direct
LSP protocol test, the actual extension transport against the native compiler
with VS Code API doubles, and the existing debugger argument-splitting test.
The transport test covers opt-in/trust, source snapshots, diagnostics, Unicode
locations, hover, definitions, syntax recovery, restart and document close, and
verifies the file on disk was not changed. No desktop extension-host certification
or marketplace publication is claimed.

## Optional values

Dewy's `T?`, `T | none`, and `none` now use the core's optional representation,
including narrowing, dictionary lookups, arrays and managed record copies.
Numeric literals can now match optional union parameters: overload selection
previously only considered optional numeric types directly. Four pinned upstream
optional/union fixture pairs were added alongside the Dewy cases. The existing
`dewy/tests/optional_values.dewy` runs unchanged. All 211 combined checks pass in
13.94 seconds (`optionals-tests.log`), including native/web debug/release optional
union and managed-copy checks and the new VS Code client test.

## Complete C bootstrap and independent CI

The syntax parser now has a compressed generated C snapshot with source and
generator provenance under `core/bootstrap/`. The default bootstrap needs Python,
a C compiler and make, with no prebuilt Dewy/Sloppy executable. The 24.40 seconds
of build steps include the syntax parser, stage zero, implementation frontend,
full frontend and self-build (`complete-c-build.json`). The resulting toolchain
passes all 211 checks in 14.19 seconds (`complete-c-tests.log`). Repeating with
pytest plugin autoload disabled, as in the new CI workflow, passes in 14.46 seconds
(`complete-c-ci-tests.log`). These are local results, not hosted CI certification.

The maintainer regeneration command was exercised separately and completed in
17.92 seconds. It still uses the earlier native compiler pair; ordinary builds
and program development do not. No executable byte parity gate was introduced.
The independent `Compact core` workflow builds from C and checks language,
native/web applications, editor transport and reload under a five-minute limit.

## Dewy editor type displays

The editor now prints fixed-width and collection types in Dewy syntax, recursively
through optionals, unions and callable types. Function hovers use `@` parameters
and `:>` results, including generic instances and functions imported from `.jo`.
Defaulted parameters are marked `= …`. Rendering walks the type representation;
it does not replace substrings in user names or modify internal type identities.
All 219 checks pass in 14.95 seconds (`editor-types-tests.log`). The initial CI
workflow was rejected before jobs started because `runner.temp` was used at job
scope; moving it to step scope fixes the workflow expression.
