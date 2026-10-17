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

## Grapheme-aware strings on compact storage

The earlier scanner's Unicode 16 rules and property data now run on the compact
byte-string representation. Dewy length, index, slice and ordinary/combined loop
iteration use graphemes. Index/slice scan only as far as necessary; length scans
the string. Iteration currently materializes one array of graphemes per iterable,
so repeated loop indexing does not rescan the string. `.jo` libraries keep byte
semantics. Invalid UTF-8 returns `none` from the boundary API and panics when
encountered by ordinary grapheme operations. This is not an eager validation or
boundary-cache invariant on every core string.

The independent conformance driver derives expectations from the existing
official 1,093-case corpus and adds all ASCII pairs, empty text and invalid UTF-8:
17,490 cases on each native/web debug/release combination, batched into four
builds. Dewy-expression regressions exercise emoji, combining marks, slices,
combined loops and source replacement during bound evaluation. These tests also
exposed a WebAssembly backend omission: noreturn calls require an explicit wasm
unreachable instruction after release optimization removes their following code.
That is fixed and a small panic-ended-search regression covers it independently.

The complete C bootstrap and 254-check gate pass (`graphemes-build.json`,
`graphemes-tests.log`, 17.91 seconds for tests). Seven alternating fresh-process
release builds found particle medians of 91.80 ms before and 93.35 ms after, and
paddle medians of 336.89 ms before and 332.89 ms after, with OS caches retained
and one worker (`graphemes-build-times.json`). These observations show no large
compile-time penalty; they do not establish a general performance bound.

Hosted CI for the preceding editor checkpoint also passed: [run 38972007553](https://github.com/david-andrew/dewy-lang/actions/runs/38972007553),
44 seconds including setup, complete C bootstrap and all 219 checks. Its exact
commit and step outcomes are recorded in `ci-editor-types.json`.

## Embedded assets and checked UTF-8 decoding

Dewy's `$include_bytes` expression and binding forms now use the core embedding
machinery with paths relative to the originating source. Based strings pack
power-of-two digits into bytes. String/byte-array conversion preserves value
independence, and decoding to `string|none` validates UTF-8. The Unicode
conformance batch also exercises this checked decoding on every valid/invalid
input, on both targets and in both modes. The original `include_bytes.dewy`
program runs unchanged. A generated 1×1 PNG is embedded and its source deleted
before native/web execution; the inherited decoder returns the expected pixel.
All 279 checks pass in 19.78 seconds (`assets-tests.log`, `assets-build.json`).

A read-only survey of 211 existing Dewy source fixtures took 9.18 seconds
(`existing-syntax-survey.json`). It is a gap inventory, not a compatibility score:
many fixtures intentionally exercise rejection, proof features, or implementation
contracts. It identified practical asset/string interfaces to carry forward.

## Asset reload, derived state and ownership

Before the fix, function-local embedded files were not watched, and changing a
global asset refreshed its bytes but left derived text stale (`asset-watch-before.log`).
The compiler now records actual embedded inputs. Watch initializer hashes include
direct global dependencies and reinitialize in dependency order across imports.
Replacing an existing same-layout global uses ownership-aware assignment instead
of first-time initialization, releasing its old managed value. Closure bodies are
not initializer reads; arbitrary helper-function global reads are not yet followed.

Tests change assets repeatedly by atomic rename, verify derived values refresh,
the live frame counter advances, and allocation counts stay steady. Deleting an
asset shows the compiler error while retaining the working game; restoring it
recovers. The existing layout-migration and compiler-error reload tests still
pass. A fresh C bootstrap passes all 282 checks in 22.53 seconds
(`asset-watch-build.json`, `asset-watch-tests.log`).

## Compact match dispatch

Dewy's typed, literal and catch-all arms now project into the existing compact
match machinery. Type aliases resolve before selecting union tags; optional and
boolean coverage uses finite cases. The scrutinee is evaluated once, and named
Dewy bindings use ordinary value-copy initialization. Native/WebAssembly,
debug/release checks cover dispatch, generics, narrowing, managed copies,
fall-through chains and early returns. Three pinned upstream fixtures cover the
shared enum, integer switch, payload and field/global narrowing machinery.
Refinement/structural patterns and proof-based coverage remain unsupported.

A fresh C bootstrap passes all 348 checks in 27.20 seconds
(`match-build.json`, `match-tests.log`). No legacy semantic engine or binary
parity gate is involved.

## Optimizer scratch allocation

Cleanup sized a fresh slot lookup table by the high-water size of a reusable
register-use array, so every later small function inherited the cost of the
largest earlier function. It now allocates only for the current function.
Eight alternating measured release builds per compiler/workload (after warm-up,
one emission worker) gave median game build times of 337.89 → 321.70 ms,
compiler self-build times of 1.295 → 1.273 s, and particle builds of
92.13 → 92.30 ms (effectively unchanged). See
`optimizer-scratch-benchmark.json` for every sample and compiler identities.
This changes scratch allocation, not optimization decisions. All 348 checks
pass in 26.59 seconds (`optimizer-scratch-tests.log`).

## Named calls and argument snapshots

Mixed named/positional calls no longer overwrite already filled parameter slots.
Dewy calls and constructors keep parameter slots canonical while evaluating
explicit arguments in source order, then omitted defaults in parameter order.
Lowering captures scalar vregs before later arguments can reassign their locals;
managed-value borrowing follows the actual evaluation order. Focused tests cover
side effects, generics, defaults, constructors, mutable parameters, scalar locals,
and retained arrays/records on native and web, in debug and release.

The new regression cases exposed 24 failing target/mode combinations before the
fix. A fresh C bootstrap passes all 389 checks in 29.85 seconds
(`call-order-build.json`, `call-order-tests.log`). Six alternating measured
release game builds after warm-up gave 323.06 ms before and 324.04 ms after
(`call-order-perf.json`), effectively unchanged.

## Physics playground and library integration

The new `examples/sloppy_core/physics.dewy` ports the pinned Sloppy physics
example into Dewy, with scene construction/simulation in `physics_scene.dewy`:
57 bodies, a box pyramid, pinned bridge, balls, rope and wrecking ball. Mouse
input drags bodies and adds boxes; B adds balls and R resets. Named library
imports, numeric value conversions, qualified record construction and literal
tuple indexing make the existing library usable directly. A nested qualified
constructor regression is covered without a selected import masking its scope.

Native/software rendering and native/WebAssembly simulation tests cover gravity,
dragging, removals and independent world copies. The collaborative browser ran
the actual web game, added a box and ball with mouse/keyboard input, and reported
no console errors (`physics-browser.png`). A fresh C bootstrap passes 412 checks
in 32.78 seconds (`physics-build.json`, `physics-tests.log`); four additional
NaN/infinity conversion boundary checks pass in 0.52 seconds. The gate now has
416 checks, with both modes and targets covered for numeric conversions.

Seven alternating measured native release runs of 1,200 steps gave medians of
178.64 ms for the pinned Sloppy scene and 178.32 ms for the Dewy scene, using the
same owned core/compiler libraries. Every run gave position checksum
80576.62176513672. Setup and drawing are excluded; this measures frontend/runtime
parity on this workload, not the whole engine's performance. The harnesses and
samples are in `physics-reference.jo`, `physics-benchmark.dewy` and
`physics-benchmark.json`. The captured Dewy harness has the source path from this
workspace. One-off model build times were 120 ms and 177 ms respectively: syntax
frontend overhead remains an improvement opportunity.


## In-process Dewy frontend

The compact compiler now lexes/parses Dewy directly, sharing its existing AST
projection. It no longer launches a parser per source or serializes syntax
through TSV/JSON. The deterministic grammar supports the existing behavior gate,
multiline infix expressions and literal coefficients (`2x`, `2f(x)`, `2(x+1)`).
This intentionally avoids rebuilding the earlier semantic ambiguity resolver.
Malformed strings/delimiters and excessive nesting produce located diagnostics;
unsaved editor recovery and UTF-16 diagnostic positions are exercised.

The old parser is available only through an explicit `DEWY_CORE_FRONTEND=legacy`
selection and optional `--legacy-parser` build. Default bootstrap contains no
parser executable and takes 17.17 seconds across its four build steps, versus
about 24 seconds previously (`frontend-build.json`). The source parser builds
through the independent C seed and self-hosts. No AST or executable byte-equality
gate was added.

Nine sequential alternating measurements after warm-up, with the same compiler
binary and one emission worker, gave these median whole-process times:

| Workload | Legacy frontend | In-process frontend |
| --- | ---: | ---: |
| Physics check | 191.55 ms | 119.31 ms |
| Physics release build | 412.96 ms | 349.74 ms |
| Paddle check | 134.10 ms | 107.50 ms |
| Paddle release build | 335.93 ms | 294.79 ms |
| Particle check | 68.64 ms | 32.69 ms |
| Particle release build | 92.90 ms | 53.37 ms |

Every sample and compiler identity is in `frontend-benchmark.json`. Filesystem
caches were warm; there were no concurrent CPU tests/builds. The fresh bootstrap
passes 434 checks in 31.09 seconds, followed by three focused checks for default
selection, invalid selection, and editor diagnostics/recovery. The combined gate
now has 436 checks (`frontend-tests.log`, `frontend-extra-tests.log`).


## Contextual and anonymous record literals

`[field=value ...]` now constructs records using a variable, parameter, return or
nested-field type. Optional payloads and defaults use the same constructor path;
empty `[]` also uses a supplied record type. Without context, concrete field
names/types form an interned anonymous record. Canonical field ordering makes
reordered schemas agree without reordering value evaluation. Ordinary constructor
lowering preserves ownership, managed copies and the earlier source-order fix.
Overload selection considers the supplied field names and types instead of
choosing an unrelated library record overload. Editor hovers display the shape.

The unchanged `array_moves.dewy`, `object_fields.dewy` and `object_nested.dewy`
now execute on native and web in both debug and release. Focused cases also cover
nested managed copies, arrays of records, inferred generic calls, overloads,
optional arguments, defaults, empty construction and field evaluation order.
Malformed, duplicate and unknown fields are diagnosed. An otherwise untyped empty
collection field needs a record annotation; coercions between already constructed
named and anonymous record values are not added here.

A fresh C bootstrap takes 17.68 seconds and passes all 513 checks in 36.17 seconds
(`records-build.json`, `records-tests.log`). This adds record representation to
the existing compact type system; it does not restore the old proof engine.


## Dependent default arguments

Defaults referring to earlier parameters now use ordinary compiler-generated
value bindings instead of cloning the supplied expression. Calls such as
`combine(next())` evaluate the explicit argument once, and later arguments cannot
change that captured value. Explicit values are bound in source order, followed
by omitted defaults in parameter order. The default expression is checked in its
declaring module with earlier bindings in scope, so local shadowing, nested calls
and escaping closures use normal lexical semantics. A direct `b=a` default can
infer its type from `a`. Managed values use existing ownership/lifetime lowering.

The before probes rejected both a computed argument and a caller local used by
a later default. Focused tests now cover those, chains, reordered named arguments,
managed copies and returns, numeric conversion, global initialization, nested
calls, lexical shadowing, and closures that outlive the call. Imports from both
Dewy and implementation-language modules keep declaration-site global lookup.
Dependent defaults with mutable `@` parameters currently produce an explicit
diagnostic directing the caller to supply those arguments; place capture is not
silently approximated as a value copy.

A fresh C bootstrap took 17.36 seconds and passed 570 checks in 39.54 seconds;
three additional import/editor checks passed in 0.54 seconds. The gate now has
573 checks (`defaults-build.json`, `defaults-tests.log`,
`defaults-extra-tests.log`). Six sequential alternating release builds after a
warmup pair gave median paddle build times of 288.46 ms before / 300.23 ms after,
and compiler self-build times of 1.334 s / 1.302 s. These small desktop differences
are recorded without claiming a speedup (`defaults-performance.json`).


## Array and dictionary comprehensions

Dewy `[loop ... value]` now uses Sloppy's approach of an accumulator, ordinary
control flow, and pushes. Dictionary entries use `key -> value` and the existing
map builder. The frontend supports nested/combined loops, filters, branches,
match, block bodies, break/continue and grapheme iteration. Final assignment or
declaration statements do not emit values; contextual array types also work for
empty results and typed parameters. Generated accumulator names cannot collide
with source names. Inputs follow normal loop evaluation and managed elements
keep the existing independent-copy semantics.

The original `array_elements.dewy` runs unchanged on native and web in both
modes. Additional checks cover arrays, dictionaries, duplicate keys, narrowing
context, empty results, nested arrays, records, managed copies, side effects,
control flow, defaults and editor type displays. The default interaction exposed
a remaining shadow-only case: defaults with no free earlier parameter must avoid
the legacy substitution path altogether. Scope analysis now also treats loop and
match binders as local, and the regression is covered.

A fresh C bootstrap takes 17.69 seconds and passes all 664 checks in 45.57 seconds
(`comprehensions-build.json`, `comprehensions-tests.log`). No runtime generator or
new ownership model was added.


## Array, tuple and record destructuring

`let [a b] = source` now declares array/tuple elements by position or record
fields by name. Records allow subsets and reordered fields. Array/tuple `_`
targets discard values. Bare assignments support swaps and existing targets;
when all names are new they declare, following the core's existing assignment
rule. Simple module-level bindings and all-discard module initializers work too.
Nested, annotated and const patterns remain explicit gaps.

Dewy unpacking snapshots its input through ordinary owned locals. Arrays check
exact length once, then read compiler-known in-bounds indices; any positive
number of targets works. Records select typed fields and reuse tuple assignment
lowering, which reads values before writing targets. No generated per-arity
library helpers or proof machinery are needed. The physics example now unpacks
joint endpoints directly.

Checks cover source evaluation once, array/record copies, fields by name,
one/five-element patterns, discards, swaps, declarations, globals, diagnostics,
default-scope shadowing and editor types. Tuple interop and the length guard are
executed on native/web in both modes. A clean C bootstrap caught an inline-if
syntax form outside the small seed's grammar; using an ordinary assignment
resolved that without changing the language. The final bootstrap takes 17.61
seconds and all 729 checks pass in 49.81 seconds (`unpack-build.json`,
`unpack-tests.log`), including the updated physics renderer.


## Optimizer measurement and operand-list cleanup

Phase instrumentation identifies release optimization/inlining as a substantial
remaining game-build cost. The loop-effects prepass only needs instruction
destinations; it now uses the existing destination classifier rather than
constructing unused operand lists. The 36 pinned shared-core regressions pass.
A larger pass-fusion experiment was discarded because it did not establish a
reliable improvement.

`loop-defs-performance.json` contains nine alternating measurements after warmup
with one emission worker. Physics medians were 565.92/558.53 ms and paddle
481.24/518.38 ms before/after. Other work heavily loaded the desktop during this
run; these results do **not** establish a latency improvement. The reusable
`tools.sloppy_core.benchmark_compile` command now records raw samples, identities
and load so future comparisons are easier to reproduce and interpret.


## Watch startup ordering

A full local run exposed a startup race: the program could print its first
output before its file watches existed, and an immediate embedded-asset edit was
lost. The driver now installs watches before launching a fresh program and
before sending a game patch, including newly introduced input directories.
The watch suite passes all six checks, including a new program that updates its
own embedded input immediately on startup. The separate optimizer cleanup's
733-check hosted gate also passed (`38982258675`).


## Recovering missing watch inputs

Failed compiler children now return their discovered source/asset paths through
a separate small input manifest. The watcher keeps the last successful game's
link map and state, installs watches for these new dependencies, and retries when
they appear. Missing directory chains are watched through the nearest existing
ancestor. Readiness messages follow watch installation. The polling fallback
keeps the original full input path even when its parent is missing.

Four initial-build regressions cover missing assets/imports with existing and
missing parent directories; a live-game regression introduces a new missing asset
and checks state preservation through recovery. The pre-fix compiler fails the
initial missing-asset test (`watch-recovery-before.log`). A fresh C bootstrap
passes all 739 checks (`watch-recovery-build.json`, `watch-recovery-tests.log`).
The bootstrap took 28.76 seconds and the gate 102.97 seconds while other desktop
work was consuming CPU and filesystem resources; these are loaded-machine
validation timings, not a latency comparison.


## One-command development gate

`python3 -m tools.core test` now builds the current compact compiler when needed
and runs only its focused suite. Cached build identities cover compiler, library,
bootstrap and builder inputs. Changed sources rebuild with the previous core;
`--bootstrap` independently starts from C. Failed/incomplete builds never replace
the current cache entry or silently run tests against an older compiler. A build
lock prevents duplicate concurrent builds, while immutable toolchain directories
keep already-running invocations stable. Compiler commands replace the Python
driver process so signals and LSP streams reach the compiler directly.

Twelve focused driver checks cover reuse, source/library/bootstrap/builder
invalidation, missing/corrupted seeds, forced bootstrap, failure retention,
concurrent source edits, gate environment and cache path containment. The full
command bootstrapped from C in 19.11 seconds and passed all 751 checks in 56.75
seconds (`dev-driver-tests.log`). Subsequent `path` and `run` commands reused the
same cache entry; the executable tour printed the expected six lines. A single
cached path lookup took 0.13 seconds including Python startup/input hashing;
compiler latency measurements continue to invoke the executable directly.


## Inline record annotations

Parameters, returns and other type positions now accept `[field: Type ...]`.
Annotations and inferred anonymous literals share one canonical field/type
interner, so field order and module boundaries do not create distinct types.
The implementation uses ordinary compact records, constructors and ownership;
there is no new runtime representation or conversion pass. Named declarations
remain nominal and supply field defaults. Inline fields require concrete value
types without defaults.

Checks cover parameters, returns, global/nested records, arrays/maps, optionals,
function types, mutable places, empty records, match, overloads, argument defaults,
declaration-site aliases across modules and editor displays. Duplicate/defaulted/
void/mutable field annotations receive diagnostics. The new cases run in native
and web debug/release modes. A fresh independent C bootstrap took 17.84
seconds; all 814 checks pass in 58.14 seconds (`inline-record-build.json`,
`inline-record-full-tests.log`).


## Dewy editor completions

The VS Code client now exposes the native server's completions, including locals,
functions, record fields, methods, collection `.length` and type annotations.
Dewy keywords and primitive type spellings replace implementation-language ones.
Function details are rendered from declarations, keeping generic names and
Dewy parameter/default/return spelling without checking all library bodies.
Explicit annotations also describe globals that the completion check has not
needed to evaluate. Named aliases retain their own names.

Completion tests cover unsaved and unfinished code, imported signatures, arrays,
strings, dictionaries, type positions and UTF-16 positions within interpolation.
Literal text/comments suppress completion. Dictionary storage fields, numeric
tuple-field spellings and array-only string intrinsics are not offered. The
actual dependency-free client transport checks item kinds, details, opt-in/trust,
restart and close against the native server; desktop extension-host certification
remains separate. Setup documentation no longer requires the removed parser
subprocess.

A fresh C bootstrap takes 17.53 seconds, and all 826 checks pass in 57.84
seconds (`completion-build.json`, `completion-full-tests.log`).

## Floor arithmetic and application performance

`floor-build.json` records a fresh independent C bootstrap. The compiler passes
838 checks (`floor-full-tests.log`), then all 20 additional application checks
(`application-tests.log`): each of the five original application workloads runs
on native/WebAssembly in debug/release, checked against the C checksum at 1,000
inputs. The combined gate is 858 checks. Arithmetic coverage includes signed
extremes, every positive int64 power-of-two literal divisor, variable divisors,
and runtime zero-divisor failure on both targets in both modes.

Floor modulo now uses one remainder operation plus sign correction; floor
division recovers its remainder from the quotient instead of dividing again.
Positive power-of-two literal divisors select tiny typed mask/shift helpers,
which inline without the general sign-adjustment branches. This also handles
negative numerators. The backend already supplies defined wrapping division and
zero remainder for the signed minimum divided by -1; no extra guard is needed.

`floor-application-performance.json` comes from the new reproducible
`tools.sloppy_core.benchmark_apps` command: one warmup and five measured runs,
sequentially alternating baseline/candidate/C, all checksums equal. Median
kernel times in milliseconds:

| Workload | Count | Before | After | C -O2 |
|---|---:|---:|---:|---:|
| Helpers | 2,000,000 | 1861.60 | 1230.30 | 820.89 |
| Arrays | 10,000,000 | 280.35 | 284.97 | 279.56 |
| Records, 50 steps | 1,000,000 | 239.74 | 229.53 | 190.06 |
| Text tokens | 10,000,000 | 361.21 | 356.84 | 198.17 |
| Graph nodes | 1,000,000 | 720.35 | 723.96 | 428.96 |

Helpers improved about 34%; small changes elsewhere are not claimed as gains.
This is a shared desktop measurement, with unrelated work running. Reports
retain raw samples and load averages, complete-process times (including input
generation), one build timing per binary, and source/compiler/build identities.
Only the platform harness import and old `addr` index annotation are adapted.
C graph storage is flat and uses a handwritten table; Dewy's per-node arrays and
insertion-ordered dictionary have different representation/library costs.

## Scalar conditional results

`scalar-if-build.json` and `scalar-if-full-tests.log` record a fresh C bootstrap
and all 862 checks passing in 64.67 seconds. Scalar `if` results now flow through
virtual registers instead of a zeroed stack temporary, stores in each branch,
and a reload. Aggregate/managed results keep their existing ownership path.
Coverage includes signed narrow values, uint64's high bit, float32, booleans,
nested branches, branch-local arrays, early return, break/continue and side effects
on native and web in debug/release modes.

`scalar-if-application-performance.json` compares the preceding floor-arithmetic
compiler with this lowering change, using five alternating warmed samples and
matching checksums throughout. Helper kernel medians improved from 1242.68 to
1005.27 ms (19%); C was 836.11 ms. Arrays were unchanged (288.38/289.81 ms),
records 215.23/207.90 ms, text 355.17/345.35 ms and graph 746.77/694.80 ms.
Only the large helper improvement is claimed here; the desktop was shared with
other running work. See raw kernel/wall samples and source/build identities in
the report. These measurements used the seeded compiler, before the independent
C bootstrap recorded above.

`scalar-if-compile.json` uses seven alternating samples per workload. Compiler
latency is effectively unchanged: physics builds 349.93/349.16 ms, paddle
306.50/308.22 ms, compiler self-build 1365.10/1377.14 ms. This change is retained
for its simpler scalar lowering and generated-program improvement, not as a
compiler-speed claim.

## Practical string literals

`strings-build.json` and `strings-full-tests.log` record the independent C
bootstrap and 933 checks passing in 71.31 seconds. The fast frontend now accepts
raw strings, triple single/double quotes, raw triple quotes, four-digit and
braced Unicode scalar escapes, standard control escapes and escaped newlines.
Multiline whitespace is preserved. Unicode escapes are static hex scalars;
surrogates, out-of-range values, expressions and oversized literals are diagnosed.

Interpolation extent scanning is shared between tokenization and construction;
it skips nested raw/triple strings and line comments. Editor masking follows
these forms, including comments at the cursor and Dewy's block interpolations.
The inherited numeric-interpolation warning is suppressed for Dewy because it
suggested implementation-language brace escaping for valid Dewy source.

The gate exercises literal content on native/web in debug/release, malformed
inputs and unsaved editor completions. The new language-guide example also runs
and prints `He said "go".` and `Next frame: 42` without warnings.
`strings-compile.json` records five alternating samples before/after the frontend
and editor changes (before the final warning-only correction). Results are mixed
within desktop variability: tour 56.80/64.07 ms, physics check 145.49/135.59 ms,
physics release build 357.36/352.55 ms. No latency gain is claimed.

## Collection membership

`membership-build.json` and `membership-full-tests.log` record the independent
C bootstrap and 1,000 checks passing in 76.31 seconds. `in?`, `not in?` and
`notin?` reuse the core's array equality, dictionary lookup and substring search.
Integer range literals lower to comparisons without constructing an array,
including open endpoints and signed extrema. Stepped/stored ranges remain out
of this slice. Custom `contains` overloads return bool; callable fields are
explicitly diagnosed rather than evaluated in the wrong order.

The needle is evaluated before its container, using the ordinary call-order and
snapshot machinery. Dependent defaults on a custom `contains` overload retain
this order. Range operands are captured in order before either comparison, so
both bounds run even when the lower comparison is false. Native/web debug/release
coverage includes narrow values, records, empty containers, managed/scalar
snapshots, globals, bounds with side effects and the original unmodified
`dewy/tests/dict_runtime.dewy` application.

`language-survey-before-membership.json` is a read-only check of 215 existing
Dewy programs, completed in 8.45 seconds before membership was added. 50 passed
checking; this is not a runtime compatibility certification or a gate. Most
failures involved unsupported type/proof constructs; ordinary membership was
one actionable gap that did not require recreating those old internals.

## Native and web 3D scene

The Dewy forest adapts pinned Sloppy `examples/scene3d.jo`: terrain callbacks,
deterministic placement of 600 tree instances, a moving beacon, orbit controls,
shadows, fog and bloom. Native software rendering and browser WebGL rendering
were visually checked; browser drag/zoom/reset worked without console errors.
`forest-render.json` records the manual observations and HTML identity;
`forest-native.png` and `forest-browser.png` retain frames. The screenshot HUD's
FPS value is not a performance benchmark.

`forest-full-tests.log` records 1,011 checks passing in 78.02 seconds, using the
unchanged membership compiler. New coverage includes scene construction and
copy independence on native/web in both modes, native software rendering, and
WebAssembly module validation for all three actual games in both modes. The
module check alone does not certify WebGL execution; the manual check above does.

`forest-compile.json` records seven warmed sequential builds per target, one
emission worker: medians 323.08 ms native release and 160.24 ms web release. No
compiler changes or additional bootstrap were needed for this example.
