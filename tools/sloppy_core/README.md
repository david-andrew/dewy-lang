# Source-level Dewy core experiment

This branch connects an in-process Dewy syntax frontend to the compact AST,
checker, code generator, runtime, and libraries from a pinned Sloppy revision.
It bypasses Dewy's existing semantic IR and backend pipeline. The point is to
recover fast development while retaining useful Dewy language behavior, rather
than reproducing internal representations or executable bytes.

The compiler and libraries now live directly in [`core/`](../../core/README.md).
Build entirely from the included C bootstrap sources:

```sh
python3 -m tools.sloppy_core.build \
  --bootstrap --output /tmp/dewy-core
/tmp/dewy-core/bin/dewy-core build example.dewy -o /tmp/example
DEWY_CORE_COMPILER=/tmp/dewy-core/bin/dewy-core \
  .venv/bin/python -m pytest -q -n0 tests/python_misc/test_sloppy_core.py
```

No separate Sloppy checkout is needed. Sources originated at
`235e19a271bccad3fe72e36d03264807a632dc1b` and are maintained directly in this
repository, with licenses and original file hashes retained. The old patch-based
builder has been removed. See `core/README.md` for seeded rebuilds, source layout,
and the independent C bootstrap route. Normal builds no longer compile the old
syntax parser or require an older Dewy compiler. Its optional compressed C seed
is retained for investigation; see `core/bootstrap/README.md`.
Hashes record provenance, not a byte-equality gate.
The complete build steps take about 17 seconds on the development machine.


Nothing replaces the installed Dewy compiler. Lexing and parsing run inside the
compiler process and consume its source snapshots directly. Against the same
compiler with its legacy frontend, nine alternating measurements gave median
physics-game checks of 119 ms versus 192 ms and release builds of 350 ms versus
413 ms. Paddle release builds fell from 336 ms to 295 ms. These are local whole
process times with warm filesystem caches and one emission worker.

The current slice supports typed and inferred functions, generic calls, default
arguments, closures with captured state, higher-order calls, mutable `@` arguments,
independent value parameters, fixed-width arithmetic, based integer and decimal
scientific literals, floating-point records,
arrays and dictionaries with value copies, array slices, grapheme string operations, optional values, type aliases, callable types, union
narrowing, typed/literal/catch-all `match` arms, nested record mutation, conditionals, while loops,
interpolated strings, entry-point arguments, file imports (Dewy and Sloppy), named library imports,
array/range iteration, import aliases, forward local record declarations, and
combined `and` loop headers. Combined loops reuse
the core's lowering, including correct advancement on `continue`.
Diagnostics retain UTF-8 source locations. A semicolon explicitly discards a result.

This is an opt-in compiler experiment, not a full language implementation or a
release-certified replacement. The core supplies runtime bounds checks, not the
old proof engine. Proof directives, effect contracts, unbounded integer types,
and unsupported syntax produce diagnostics.
Signed floor division/modulo currently use the core's int64 helpers. Floating
point `/` is supported; integer `/` is rejected until its result semantics are
implemented. Calls/indexing use adjacent brackets. Literal coefficients such as
`2x`, `2f(x)` and `2(x + 1)` multiply; separated values remain arguments or block
elements. Other multiplication uses `*`. Multiline infix expressions are supported;
`[40\n-2\n4]` remains three elements. This deterministic syntax is an intentional
subset of the old ambiguity resolver, not a promise to preserve every historical
juxtaposition case. Unsupported string escapes and excessive nesting are diagnosed.

`match value { name:Type => body <literal> => body _ => fallback }` supports
exact union member types (including aliases), concrete types, optional payloads,
integer/string/boolean literals, and named catch-alls. `else` and `else if` attach
a fallback. The scrutinee is evaluated once; bindings are independent values.
Boolean and optional coverage is checked directly, and union coverage reuses the
core's tag checker. Other matches require a catch-all. Refinement, structural,
sequence, union-subset and literal-on-union patterns are not implemented yet;
there is no proof-engine dependency.

Named and positional call arguments may be interleaved; positional values fill
the next unassigned parameter. Explicit Dewy arguments evaluate in source order,
followed by omitted defaults in parameter order, including record construction.
Already evaluated scalar and managed values survive changes made by later
arguments. Named arguments on first-class function values remain unsupported.
Defaults may refer to earlier parameters: `combine=(a b=a)=>a+b` accepts
`combine(next())` and evaluates `next()` once. Explicit values are captured in
source order, followed by defaults in parameter order. Defaults resolve globals
in the declaring module, respect local shadowing, and may capture earlier values
in returned closures. A directly referenced parameter also supplies the inferred
default type; more complex defaults can use an explicit annotation. Combining
dependent defaults with mutable `@` arguments is currently diagnosed; supply
those arguments explicitly.

Numeric `as` performs value conversion, including integer/float and float-width
conversions. Float-to-integer conversions truncate toward zero and saturate to
the destination range (NaN becomes zero), using the same core lowering on native
and web. `transmute` is still unsupported. Named libraries are available as
`import physics`, `import physics as dynamics`, or `from physics import World`;
`p"..."` remains an explicit file path. Tuple results from libraries support
literal indexing such as `world.ends(joint)[0]`.

Record construction and collection `.length` are resolved from types, including
imported/qualified record constructors and records with their own `length` field.
Record literals such as `[x=20 y=22]` use the expected record type in variables,
returns, arguments and nested fields, including defaults and optional payloads.
Without an expected type, their field names and inferred types determine an
anonymous record type; field order does not affect type identity. Values still
evaluate in source order and retain independent copies. Empty `[]` constructs a
record when context supplies its type. Inferred fields must have concrete value
types; annotate the record when a field is an otherwise untyped empty collection.
Named record types remain distinct, and structural conversions between already
constructed named and anonymous values are not implemented.

Comprehensions build arrays or dictionaries eagerly:

```dewy
let squares = [loop i in [0..10) i*i]
let selected = [loop x in squares if x >? 20 x]
let lengths = [loop word in ["café" "🙂"] word -> word.length]
```

Nested loops, combined loop headers, branches, `match`, and block bodies work
through the ordinary control-flow lowering. A block's final value is collected;
assignments, declarations, `break` and `continue` do not add an element. An `if`
without `else` filters elements. Array annotations and parameter types supply
element context, including empty comprehensions. Inputs are evaluated according
to the normal loop rules and collected managed values remain independent copies.
Dictionary comprehensions currently collect pairs and use the core's map builder;
later entries replace earlier values for the same key.

`let [x y] = value` unpacks an array/tuple by position or a record by field name.
Record targets can select a subset in any order. Arrays require exactly as many
elements as targets, checked at runtime; `_` discards an array/tuple element.
There is no two-to-four-element restriction. `[x y] = [y x]` reads the source
once before writing either target. Bare targets also declare when all names are
new; `let` explicitly declares/shadows. Managed values retain independent copies,
and module-level unpacking is supported. Nested, annotated and `const` targets
are not implemented yet; omit unwanted record fields instead of using `_`.

The combined Dewy/editor/shared-core gate now contains 739 checks and takes
about a minute on the development machine, including separate compiler
processes and program execution.
Value cases run in debug and release modes. It includes the paddle game model
on native and WebAssembly targets in both modes, and a
display-independent render of the actual game. The playable example and build
instructions are in `examples/sloppy_core/`.
Evidence is in `dewy/audits/2026-10-16/source-core/`.

For the editor protocol gate, include
`tests/python_misc/test_sloppy_core_editor.py` in the pytest command above.
`dewy-core check file.dewy` checks all source functions, including unused ones,
and performs lowering checks without code emission. Five-process medians were
62 ms for the particle benchmark and 121 ms for the paddle game.
`dewy-core lsp` serves diagnostics, hover types, and definitions for unsaved
Dewy text. The parser reads the compiler's source snapshot in memory;
the experimental compiler host currently requires Linux. Syntax errors
use the core's diagnostic transport, including original file/byte locations.
Hover text uses Dewy type spellings and function signatures, including for
imported implementation-language functions. Defaulted parameters are marked `= …`. Formatting Dewy is deliberately
unavailable: the CLI rejects it and LSP returns no edits, instead of applying
Sloppy's syntax formatter. Other inherited editor features remain experimental.

The existing nested-record particle benchmark runs unchanged except for its
platform harness import: `benchmark_harness.jo` replaces raw compiler-specific
syscalls with the core library. Three cold builds and five runs at each of five
sizes per build gave these initial medians (OS caches retained, one compiler worker):

| Compiler | Whole build | Million-particle kernel |
| --- | ---: | ---: |
| Current Dewy, boxed default | 1,656 ms | 706 ms |
| Current Dewy, opt-in dense records | 1,703 ms | 218 ms |
| Source core, debug | 72 ms | 617 ms |
| Source core, release | 90 ms | 257 ms |
| C (`cc -O2`) | 94 ms | 170 ms |

All 375 runs matched checksums, including empty and single-element arrays.
The initial source core was about 18.5× faster to compile this supported workload;
its initial runtime did not beat the existing opt-in dense runtime. These are workload results,
not a self-hosting or full-language speedup claim. Reproduce with
`tools/compare_sloppy.py --source-core /path/to/bin/dewy-core`, selecting
`--dewy-source dewy/benchmarks/apps/records_nested.dewy` and the desired modes.

Subsequent lowering improvement: collection length now reuses the length already
cached when the core proves the array fixed during a loop. The proof checks calls
in the condition as well as the body; otherwise growth/shrinking remains live.
Three builds and 225 alternating comparative runs give 84 ms compilation and
197 ms for the million-particle kernel, down from 257 ms, versus C at 173 ms in
that run. All checksums agree. This brings the unchanged nested-record algorithm
within about 14% of the C kernel, and ahead of the earlier dense Dewy measurement.
It is still a single workload, not a claim about all generated programs.

Shared-core optimization changes also run pinned Sloppy regressions:

```sh
DEWY_CORE_COMPILER=/tmp/dewy-core/bin/dewy-core \
  .venv/bin/python -m pytest -q -n0 tests/python_misc/test_sloppy_core_upstream.py
```

The focused shared-core gate covers arrays, copies, bounds, loops, optionals and
unions in both build modes. Fixtures are copied from the pinned Git revision into `core/tests/upstream/`;
the gate no longer needs the reference checkout.

Fixed-path loop lowering now also runs in default development builds. It is a
local analysis, independent of the release optimizer, and keeps runtime bounds
checks for indices that have not been proved safe. On the particle workload,
three builds and 300 alternating executions show development runtime improving
from 624 ms to 396 ms (37%), for a build change from 71 ms to 73 ms. Release was
203 ms and C 174 ms in that run. All checksums matched, and the combined 131-check
Dewy/editor/shared-core gate passed in 7.8 seconds.

The default `new` template is a small mouse-controlled Dewy game with a trail;
`new <directory> program` creates a terminal program. Both include a README.
`watch` tests exercise imported-function reload, retaining the last working
version after errors, and preserving game state through record layout changes.
Include `tests/python_misc/test_sloppy_core_watch.py` for this gate.

Fixed-width literals include binary, octal, hexadecimal and the other Dewy bases
through 16. All signed/unsigned widths from 8 through 64 bits are available.
Positive literals above `int64` infer `uint64`; assigning one to a signed type
requires a representable value. Negative `int64.min` and narrow signed minima
are accepted, while literals outside the available width are diagnosed.
Decimal scientific notation uses the core's correctly rounded float parser and
rejects overflow to infinity. Binary exponents and nondecimal fractions remain
unsupported. Typed integer arithmetic retains the core's wrapping behavior;
these additions do not implement Dewy's unbounded `int` or exact real arithmetic.

Array slices support inclusive `xs[a..b]`, exclusive `xs[a..b)`, omitted bounds
and `xs[..]`. Slices are independent values, including nested managed elements.
The source value is held across bound evaluation, so calls in bounds can mutate
or replace the original array without changing the value being sliced. Invalid
bounds panic at runtime. String slices use grapheme boundaries too; stored range values remain a separate,
unfinished feature.

Optional types accept `T?` and `T | none`, with `none` values and `is?`/`isnt?`
narrowing. This includes dictionary `.get`, arrays of optional values, optional
unions, and independent copies of optional records. The earlier compiler's
`dewy/tests/optional_values.dewy` runs unchanged in both build modes.

Dewy string `.length`, `len(s)`, indexing, slicing and loop iteration now use
Unicode 16 extended grapheme clusters. Combining marks, emoji ZWJ sequences,
regional indicators, Indic conjuncts and CR/LF follow the existing Unicode
conformance corpus. The compact byte representation remains: length scans,
index/slice scan up to the requested boundary, and string loops currently
materialize one grapheme array per iterable. Explicit `bytes(s)` exposes bytes;
implementation `.jo` libraries retain byte-oriented operations. Text supplied by
those libraries is validated as it is scanned; malformed UTF-8 panics in Dewy
operations, while `grapheme_boundaries(s)` returns `none`. No global boundary cache
or old string descriptor is required.

The conformance check batches 17,490 inputs per mode/target (the 1,093 official
cases, all ASCII pairs, empty input and malformed UTF-8) into one program build.
It runs on native and WebAssembly in debug/release without importing the earlier
compiler or its Unicode implementation into the test runner.

`$include_bytes(p"assets/file.png")` embeds source-relative bytes; the statement
form `$include_bytes(p"…") as name` binds them. The inherited image/audio loaders
accept those byte arrays, including in self-contained web builds. Power-of-two
based strings (`0b`, `0q`, `0o`, `0x`, `0u`, `0g`) pack bits into independent byte
arrays, including Dewy's zero-padded final partial byte. `text as array<uint8>`
encodes bytes, and `bytes as string|none` (or `string?`) checks UTF-8 and returns
`none` for malformed data. Both conversions preserve independent values.

Native watch tracks embedded files inside functions as well as declarations.
Changing a global initializer also refreshes initializers that directly read it,
in dependency order, including across imports. Repeated same-layout replacements
release old managed values; unrelated live state remains. The watch gate checks
asset deletion/recovery, stable live allocation counts and a counter continuing
across repeated asset edits. Dependency discovery does not yet follow arbitrary
global reads hidden inside initializer helper functions.
