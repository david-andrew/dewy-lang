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
arguments, closures with independent private state and explicit shared captures,
higher-order calls, mutable `@` arguments,
independent value parameters, fixed-width arithmetic, based integer and decimal
scientific literals, floating-point records,
arrays and dictionaries with value copies, array slices, grapheme string operations, optional values, type aliases, callable types, union
narrowing, typed/literal/catch-all `match` arms, nested record mutation, conditionals, while loops,
interpolated strings, entry-point arguments, file imports (Dewy and Sloppy), named library imports,
array/range iteration (including single stepped integer loops), import aliases, forward local record declarations, and
combined `and` loop headers, and `in?`/`not in?` membership for arrays,
dictionaries, strings and integer range literals. Combined loops reuse
the core's lowering, including correct advancement on `continue`.

Dewy closure literals snapshot enclosing locals; `[@name]()` opts specific
locals into lexical sharing. Copying a closure duplicates mutable private
captures and retains explicit shared cells. Immutable private environments can
be retained without an allocation. Calls pin the environment being invoked so
replacing the callable during argument evaluation does not free it prematurely.
The implementation-language `.jo` closures retain their existing lexical
sharing behavior. See [closure examples and limits](../../core/LANGUAGE.md).

For now, value copies of arrays that can contain functions eagerly duplicate
their elements' private environments, including through recursive record types.
Other arrays keep their usual copy-on-write storage. This makes callback copies
independent even across borrowed implementation-library APIs; it is a focused
correctness path, with further copy-on-write optimization still possible.
Diagnostics retain UTF-8 source locations. A semicolon explicitly discards a result.

This is an opt-in compiler experiment, not a full language implementation or a
release-certified replacement. The core supplies runtime bounds checks, not the
old proof engine. Proof directives, effect contracts, the old numeric refinement
types, and other unsupported syntax produce diagnostics. Exact `BigInt` and
`Rational` values are bundled; fixed-width machine arithmetic retains its width.
Floor division/modulo support signed and unsigned machine words and exact
library numbers. Integer `/` constructs an exact Rational, loading its bundled
implementation only when required by the checked operand types; floating `/`
keeps floating arithmetic. Calls/indexing use adjacent brackets. Literal coefficients such as
`2x`, `2f(x)` and `2(x + 1)` multiply; separated values remain arguments or block
elements. Other multiplication uses `*`. Multiline infix expressions are supported;
`[40\n-2\n4]` remains three elements. This deterministic syntax is an intentional
subset of the old ambiguity resolver, not a promise to preserve every historical
juxtaposition case. Raw and triple-quoted strings, standard escapes and static Unicode scalar
escapes are supported. Multiline whitespace is preserved. Interpolation scanning
handles nested strings and comments; unsupported escapes and excessive nesting
are diagnosed.

`match value { name:Type => body <literal> => body _ => fallback }` supports
exact union member types (including aliases), concrete types, optional payloads,
integer/string/boolean literals, and named catch-alls. `else` and `else if` attach
a fallback. The scrutinee is evaluated once; bindings are independent values.
Boolean and optional coverage is checked directly, and union coverage reuses the
core's tag checker. Union-subset type arms also work, including aliases and
generic parameters: they cover all selected tags, narrow the arm's source and
bind an independent smaller union when named. Overlapping arms retain source
order. Other matches require a catch-all. Refinement, structural and sequence
patterns are not implemented yet; there is no proof-engine dependency. Integer, string and boolean literals also match union
members, with tag checks before payload reads and member narrowing in the arm.
Literal bindings receive that member's value. Literal coverage does not remove
an entire type from later fallbacks, except that both boolean literals cover
`bool`. Numeric literal member selection follows ordinary union assignment.

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

Array spreading uses postfix `...` inside literals, as in `[head... item tail...]`.
It reuses the core's append/extend lowering, evaluating operands once in source
order and retaining independent nested values. Typed empty arrays and generic
helpers work. Record literals also compose with `[base... field=value]` or
`[left... right...]`; later entries replace earlier fields, with operands evaluated
once in source order. Expected record types supply field context, and inferred
results use ordinary anonymous record shapes. Set spreading and spread call
arguments remain unsupported.
Record literals such as `[x=20 y=22]` use the expected record type in variables,
returns, arguments and nested fields, including defaults and optional payloads.
Without an expected type, their field names and inferred types determine an
anonymous record type; field order does not affect type identity. Values still
evaluate in source order and retain independent copies. Empty `[]` constructs a
record when context supplies its type. Inferred fields must have concrete value
types; annotate the record when a field is an otherwise untyped empty collection.
Named record types remain distinct, and structural conversions between already
constructed named and anonymous values are not implemented.

Generic records and top-level functions use Dewy's `<T U>` prefix:
`Box:type=<T>[value:T]` and `first=<T>(xs:array<T>):>T|none=>...`.
General type applications (including qualified imported types) now use the core's
ordinary generic instances. Explicit calls use `first<string>(words)`; generic
aliases use `Values:type=<T>(array<T>)`. Type-dependent defaults resolve the
instantiated parameters in the declaring module. Constrained parameters and
explicitly generic local closures are diagnosed. A generic function can still be
passed with an expected concrete callable type or return a closure.

Anonymous records are interned by their sorted field-name shape, with field
types as ordinary type arguments. This shares matching/substitution with named
generics, including structural parameter and return annotations containing `T`.
It does not implement structural conversion between nominal record types.
The bundled `Pool<T>` and `Heap<T>` are exercised on native and web; see
`examples/sloppy_core/entities.dewy` for stable handles and queued game events.
Nested custom-index assignments now compose read/edit/writeback through fields,
arrays and nested pools. Receiver indices and custom keys are captured for
writeback, including variable keys changed by the right side. Selected type
imports find indexing operators in the receiver’s module. Native/web checks in
both modes cover independent copies, side effects and shared `.jo` behavior.
This retains the collection-copy cost of explicit read/edit/writeback; it does
not introduce a mutable borrow through a getter.

Module-level `f = (signature => body) & (signature => body)` overload groups
expand directly into compact function declarations. Parentheses, nested groups,
`let`/`const`, generic members, defaults, recursion and imports use the existing
checker. Expected callable types select a member for first-class use, and editor
hover reports the selected signature. No runtime overload object is introduced.
Local groups, groups containing existing values, and grouped entry points are
diagnosed rather than given a second dispatch mechanism.

Dewy-defined dunder functions now participate in custom-record operator lookup:
arithmetic, comparisons, unary minus, shifts and bit operations, and
`__index__` / `__setindex__`.
Their names remain ordinary function names for explicit calls and imports.
Receiver/operand modules supply protocols even after a selected type import;
Dewy and `.jo` clients share specialization and dispatch. Comparisons require
`bool`, and comparisons derived from `<` preserve written operand evaluation
order. Record `and`/`or`/`not` use `__and__`/`__or__`/`__not__`; binary record
operators evaluate both arguments once in source order. Built-in boolean
`and`/`or` keep short-circuit evaluation. Optional `value ?? fallback` reuses
the inherited checked coalescing operation, evaluates its left operand once,
and only evaluates the fallback for `none`. It associates right, above
comparisons and below arithmetic. Netpong uses it for configuration and parsed
message fields. Floor division/modulo and power use
their corresponding protocols too. Compound `//=`, `%=`, `/=` and `^=` use
those same numeric and record operations, with index capture and custom-index
writeback. Fixed-width results wrap to the destination width; exact `/=` needs
a fractional destination (or floating operands and a floating destination).

`examples/sloppy_core/ring.dewy` is a generic bounded container implemented in
Dewy. Its history example covers wraparound, nested indexed edits, independent
snapshots and direct iteration. Indexed records with `len` and `__index__` now
use the existing counted-loop lowering: retain the source, capture its length,
and read positions in order. Comprehensions, combined headers, tuple/array
unpacking, labels and fallback arms compose with it. Method lookup makes a
selected import of the container constructor sufficient for its length/index
operations. Native/web debug/release checks also cover managed elements, capacity
one, empty length, invalid capacity and invalid indices. The checker now rejects
non-void/non-integer entry-point results, which previously could emit invalid
WebAssembly for an aggregate result.

Compare the ring's scalar insertion path with the same algorithm written in the
core's implementation language:

```sh
python3 -m tools.sloppy_core.benchmark_ring "$(python3 -m tools.core path)" \
  --output /tmp/ring-times.json
```

The runner checks empty, partial, full and wrapped checksums before measuring,
then alternates warmed runs. The report includes complete sources and raw kernel
and process timings. This comparison measures frontend/representation overhead
for the same algorithm; it is not a C comparison or a copied-container workload.
Seven measured runs of 10 million insertions into a 1,024-slot ring gave median
kernel times of 71.10 ms for Dewy and 69.37 ms for `.jo`; all checksums matched.
These are similar results on the development desktop, not a general parity claim.

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
and module-level unpacking is supported. Nested patterns in declarations and
assignments recurse through arrays, tuples and records using those same rules.
For example, `let [[x y] [z]] = [[20 1] [21]]` reads its source once and checks
both inner array lengths before writing destinations. Nested managed values keep
independent copies, and duplicate target names are diagnosed across the entire
pattern. Annotated and `const` targets are not implemented yet; omit unwanted
record fields instead of using `_`.
The nested-unpacking change passes 2,957 checks from the independent C seed,
including native/web default/release cases for globals, discards, mixed tuples,
swaps, nested value copies and length failures. `nested-unpack-compile.json`
records fresh-build timings; `nested-unpack-validation.json` records the tested
toolchain and gate scope.

Loop binders reuse this destructuring path. Dictionary entries can bind a key
and nested value, multiple names can unpack array/tuple/record elements, and
indexed user sequences support nested groups. Combined sequence
`and` headers use the same checked declarations. A single binder followed only
by conditions now retains native iteration, fixing dictionary key/value loops
with guards or fallback arms instead of routing them through integer indexing.
This step passes 3,010 checks from the independent C seed. Five fresh-build CPU
pairs pinned to CPU 2 give ratios of tour 0.999, Dunes 0.991 and compiler 1.027;
there is no compilation speedup claim. Benchmark reports now record CPU affinity.
The pinned follow-up for the preceding nested-assignment change is also neutral
(self-build ratio 0.996). See `nested-loop-*` and
`nested-unpack-compile-affinity.json` in the source-core audits.

Counted dictionary headers now bind the zero-based position and key, rather than
mistaking those bindings for a key/value pair. General combined headers iterate
keys or unpack key/value pairs from a retained, compacted snapshot, including
deleted entries, nested values and comprehensions. `or` headers yield optional
keys. Tests cover source evaluation order, mutation during iteration, empty maps
and full-width unsigned keys. All 3,054 checks pass from the independent C seed
in 61.98 seconds. Five paired fresh-build CPU measurements pinned to CPU 2 are
neutral: tour 0.999, Dunes 1.000 and compiler 1.001. See `dictionary-zip-*` in
the source-core audits.

IR cleanup tracks reachable exits through nested blocks, both conditional arms
and jump tables. An inner `end` no longer revives code after an unconditional
exit to an outer block. Loop backedges remain distinct from exits, and explicit
unreachable markers keep WebAssembly validation sound. Tests cover nested
returns, managed values, labeled exits and jump-table returns, and check that
unreachable printing is absent from the emitted IR. All 3,074 checks pass from
C in 54.03 seconds. Five paired application CPU ratios are 0.998 (helpers),
1.003 (arrays), 0.987 (records), 0.995 (text) and 0.982 (graph); there is no broad
runtime speedup claim. Fresh-build CPU ratios are 1.002 for the tour and 1.004
for the compiler. The noisy initial Dunes ratio of 1.070 becomes 1.002 in a
seven-pair follow-up. All measurements use CPU 2; see `reachability-*` in the
source-core audits.

Dictionary declarations and assignments can unpack entries too:
`let [[key value] [_ other]] = mapping`. They reuse the retained dense snapshot
and key/value pair helper, check the number of live entries, and preserve nested
value copies. Flat targets can retain whole pairs; `_` discards a pair or one of
its members. Focused checks cover deleted entries, swaps, nested containers,
global initialization, source evaluation and length failures on native/web
default/release builds. The independent C gate passes 3,118 checks in 77.02
seconds; see `dictionary-unpack-validation.json` and its full test log.

Insertion-ordered sets now use the existing dictionary hashing and COW storage:
`set[1 2 2]`, `set<T>`, membership, mutation, set algebra, comprehensions,
spreads, counted/zipped iteration and unpacking. Equality and hashing ignore
insertion order, including sets nested inside arrays, optionals, records and
unions. Copies and iteration preserve independent values. Generated aggregate
comparisons participate in effect analysis when a set key's equality calls user
code; checks include a callback that clears the original collection while a
borrowed argument is still in use. Native/web default/release checks include an
independent oracle for all pairs of four-member subsets. The independent C gate
passes 3,226 checks in 46.26 seconds. Five alternating fresh-build pairs on CPU 2
show no material compilation change: median paired CPU ratios are 0.984 for the
tour, 1.012 for Dunes and 1.004 for the compiler. See `sets-*` in the October 17
source-core audit directory.

Record/enum instantiation now searches only instances of the same declaration,
preserving structural matching for arguments still undergoing inference. The
independent C gate passes 3,226 checks in 47.34 seconds. Seven alternating
type-check pairs on CPU 2 give median paired CPU ratios of 0.975, 0.933 and 0.905
for synthetic programs with 500, 1,000 and 2,000 distinct records wrapped in one
generic type. Representative fresh builds remain neutral: tour 1.009, Dunes
1.003 and compiler 0.999 over five pairs. These are scaling results, not a broad
application build speedup; the reproducible generator is
`python3 -m tools.sloppy_core.benchmark_types`. See `struct-index-*` in the same
audit directory.

The ordinary type interner also sizes a rebuild for all accumulated types.
Record, union and type-value creation can grow the type arena between interner
calls; doubling the old table just once could leave it too small and make
rehashing loop forever. A generated program with 5,000 generic record instances
exposed this hang and is now a timeout-bounded regression check. The independent
C-bootstrap gate passes 3,421 checks in 49.29 seconds. See `type-capacity-*`;
this is a completion fix, not a claimed finite baseline speed ratio.

Concrete generic record/enum arguments now also have an index. Unresolved
requests retain structural matching; finishing inference produces the canonical
concrete instance rather than an earlier instance still marked unresolved.
Seven alternating type-check pairs against the capacity-fixed baseline, measured
before this inference correction, gave CPU ratios of 0.969, 0.662 and
0.353 for 500, 2,000 and 5,000 record specializations. Five fresh-build pairs give
tour 0.989, Dunes 1.004 and compiler 1.015, with no ordinary build speedup claimed.
All 3,431 checks pass on the independently C-built compiler in 45.19 seconds,
including late inference bindings, ordered type arguments and recursive managed
records. See `record-index-*` for the sources, samples and toolchain identities.

Concrete union member lists now have a canonical index instead of scanning all
records and unions. Inference-bearing unions retain structural matching; resolving
an inference variable rebuilds a flattened concrete union. Structural comparison
also checks member counts, fixing asymmetric equality and invalid unification of
a concrete union with a larger one. An open type variable can still infer several
remaining alternatives.

Seven alternating CPU-2 type-check pairs give candidate/baseline CPU ratios of
0.951, 0.752 and 0.531 for 500, 2,000 and 5,000 distinct record/string unions.
Reproduce with `python3 -m tools.sloppy_core.benchmark_types --kind unions`.
Five fresh-build pairs give tour 0.755, Dunes 0.995 and compiler 0.991. The small
tour result varied substantially from an earlier exploratory run on the busy
shared host, so no general build-speed gain is claimed. The independent C gate
passes 3,525 checks in 97.26 seconds. See `union-index-*` for samples, toolchain
identities and inference regressions; these measurements exclude program runtime.

Generic record constructors now infer contextual arguments using the same partial
type binding as function calls. `Box([20 22])`, record/set literals, callbacks,
and imported constructors work without spelling their type arguments. Known
fields provide types for empty collections and callback parameters; later writes
within a function can settle an initially empty array's element type. Finishing
record inference now interns fully resolved arguments instead of reusing an
instance permanently marked unresolved. This also removes the intermediate
index's separate list of inference-bearing instances.

The independent C gate passes 3,455 checks in 40.71 seconds, covering independent
copies, argument order/effects, recursive records, callback context and rejected
conflicts/unresolved types. Five fresh-build CPU pairs remain neutral: tour
0.996, Dunes 0.998 and compiler 1.008. See `constructor-context-*`.

Generic functions now look up concrete specializations by declaration and
interned type arguments. Arguments still carrying inference variables retain
the existing structural comparison path. Seven alternating fresh type-check
pairs on CPU 2 give candidate/baseline CPU ratios of 0.972, 0.757 and 0.470 for
500, 2,000 and 5,000 distinct records passed to one generic function. Five paired
ordinary builds remain neutral (tour 0.992, Dunes 1.004, compiler 0.999).
The scaling workload is reproducible with
`python3 -m tools.sloppy_core.benchmark_types --kind functions`; no code generation
or program runtime is included in that measurement. All 3,364 checks pass on the
independently C-built compiler in 68.19 seconds. See `function-index-*`.

Aggregate helpers now consult the existing transitive effect analysis before
retaining set-containing values. Integer-set equality/hashing use the pure read
path; unknown calls and global-writing callbacks keep their snapshots. The
independent C gate passes 3,226 checks in 44.48 seconds, including the callback
and borrowed-argument regressions. In a focused native release benchmark of
1.28 million dictionary lookups, records containing integer sets take 0.412
times the baseline kernel CPU time across seven alternating pairs. Direct set
keys are neutral at 1.007. Inputs use reversed insertion order and every run
checks an independent expected sum. This is an isolated nested-key improvement,
not a general application claim. Five fresh-build pairs remain neutral (tour
1.008, Dunes 0.999, compiler 0.992). See `set-effects-*` for sources and samples.

Dictionary and set hashing now uses method lookup, finding a key's custom
`hash` function in its defining module just as equality finds its operator.
Previously, imported keys whose equality ignored a label could be stored as
distinct entries despite a matching custom hash. Checks cover selected imports,
generic keys, updates, removals, nested sets and a hash callback that clears the
source while a borrowed argument remains in use. The independent C gate passes
3,238 checks in 53.98 seconds. Five paired fresh-build CPU ratios are neutral:
tour 0.999, Dunes 1.000, compiler 0.991. See `hash-discovery-*`.

Dictionaries now retain their association-based equality inside arrays, records,
optionals and unions. Their new order-independent hash lets equivalent maps act
as keys or set members despite different insertion/deletion histories and
capacities. This reuses the collection helper/effect machinery introduced for
sets, including snapshots when key or value callbacks can mutate the source.
Checks cover nested custom keys/values and mutation during both comparison and
hashing. The independent C gate passes 3,258 checks in 42.71 seconds. Five paired
fresh-build CPU ratios are 1.000 for the tour, 1.018 for Dunes and 1.011 for the
compiler; this is a behavior improvement, not a compilation speedup.
See `map-values-*` for the full gate and samples.

`min_by` and `max_by` now scan by index instead of copying the array tail.
Checks verify first-match ties, one key evaluation per element, custom ordering,
managed result independence, source mutation from a callback and no extra live
tail-array allocation during the scan. The independent C gate passes 3,278 checks
in 42.43 seconds. Seven alternating release benchmark pairs on CPU 2 select both
extremes from 20,000 values 50 times: median kernel CPU ratios are 0.905 for
integers and 0.627 for records containing arrays and strings. Each run checks a
Python-computed expected result. Five paired fresh-build ratios remain neutral
(tour 0.996, Dunes 0.991, compiler 1.005). See `minmax-*` for sources and samples.

Ordinary read-only loops over contiguous array slices now retain the source and
iterate the selected bounds without materializing a slice. Bounds are checked
before the first iteration, including empty and early-exit loops. A body that
can modify its source keeps the copied-slice path to avoid forcing a larger COW
detach. The shared bounds lowering also captures the lower value before an
upper-bound expression can assign its variable. The independent C gate passes
3,322 checks in 39.20 seconds. Seven paired release runs scanning 20,000 values
500 times give kernel CPU ratios of 0.330 for integers and 0.066 for records
containing arrays and strings. Taking only the first selected element from a
200,000-element array 500 times drops from 28.56 ms to about 0.005 ms; the latter
is a very short kernel, so the useful result is removal of the up-front copying,
not a precise speedup multiplier. These are focused slice-loop results. Five
fresh-build ratios are neutral (tour 0.988, Dunes 0.991, compiler 0.992).
See `slice-loop-*` for source programs, samples and validation.

Dictionary `get(key)` calls whose only use is testing the outer optional tag now
lower to `has(key)`. This skips the value read and optional result while keeping
written argument order and custom key hash/equality callbacks. Custom methods
and the default-valued `get` overload keep their normal behavior. The independent
C gate passes 3,344 checks in 68.46 seconds. Seven alternating release pairs on
CPU 2 give a median candidate/baseline thread-CPU ratio of 0.934 for the unchanged
million-node graph traversal, with matching boundary and full-size checksums.
The candidate is still 1.498 times the C reference in this run; its insertion-ordered
dictionaries and per-node neighbor arrays differ from C's flat representation.
Five paired fresh-build CPU ratios are neutral: tour 0.992, Dunes 0.995 and
self-compilation 1.006; no compilation-speed improvement is claimed.
See `map-presence-*` for samples, compiler identities and validation.

An already-typed optional can now be wrapped as the payload of another optional.
This repairs generic `T -> T?` returns when `T` is itself optional, including
dictionary `get`: a missing key and a present value of `none` remain distinct.
Managed payload copies remain independent. The independent C gate passes 3,356
checks in 69.79 seconds; this is a correctness fix with no speedup claim.
See `nested-optionals-*` for the validation record.

Named records retain equality and hashing defined in their own module when
nested in arrays, records, optionals and unions. Generated helpers call those
protocols instead of comparing or hashing the record's representation. An outer
protocol overrides its fields; absent operations retain field-based behavior.
Only the requested operation is instantiated, so a generic record can be compared
without compiling an unsupported hash specialization. The existing callback
effect analysis keeps borrowed values alive when a protocol replaces their owner.
Checks include generic records, nested dictionary keys, independent operations,
unsigned narrow hash results and source-clearing callbacks. The independent C
gate passes 3,384 checks in 68.91 seconds. Five paired fresh-build CPU ratios are
neutral: tour 0.996, Dunes 1.003, compiler 1.009. See `value-protocol-*`.

Integer and boolean array equality now recognizes shared storage and compares
narrow elements in 8-byte chunks, finishing with whole element loads. Single
elements take a direct comparison. Emitting these loops in the equality helper
avoids the extra call that initially regressed tiny arrays. Floating-point and
record comparisons keep their element semantics, including NaN, signed zero and
custom callbacks. The independent C gate passes 3,396 checks in 48.80 seconds.
Seven alternating release pairs on CPU 2 compare 200,000-element arrays 300 times:
median candidate/baseline kernel CPU ratios are 0.112 for uint8, 0.243 for uint16,
0.491 for uint32 and 0.985 for int64. Comparing shared 20,000-element integer
storage 2,000 times drops from 43.33 ms to about 0.036 ms by removing the linear
scan. Two million single-element comparisons show no regression (ratios
0.959/0.953/0.987/0.943 for those four types); a shared four-element case is 0.773.
These focused kernels mutate an element between comparisons and verify every
result. Five fresh-build CPU pairs remain neutral: tour 0.987, Dunes 1.001,
compiler 1.003. See `array-word-equality-*` for programs and samples.

The bundled `bigint.dewy` supplies exact signed integers using owned arrays of
base-2^32 limbs. It reuses Dewy's magnitude algorithms, with ordinary compact-core
records and no refinement-proof representation. Constructors accept signed and
unsigned machine words or decimal text; checked word conversions, interpolation,
comparisons, arithmetic, floor division/modulo, nonnegative powers and GCD work
on native and web. Literals beyond the machine-word range automatically construct
`BigInt` values from limbs computed at compilation. Small literals adopt an
expected `BigInt` type; machine-word arithmetic retains its fixed width and does
not automatically widen on overflow. See the language guide and
`examples/sloppy_core/exact_integers.dewy`.

Exact integers also support sign-extending `and`/`or`/`xor`/`not` and shifts.
Right shift rounds negative values down without allocating a power-of-two
divisor. Shift counts are nonnegative `int64`; `<<=` and `>>=` capture indexed
places once and preserve snapshots. The bit-operation oracle compares 470
boundary/random cases through 4,096 bits with Python, in all four native/web
debug/release combinations. Mixed signed/unsigned words, huge right shifts,
negative-count errors and allocation lifetime are checked separately.

The differential gate compares 622 signed operand pairs against Python integers,
including limb boundaries, random values up to 512 bits and Algorithm D quotient
correction/add-back cases, in native/web debug/release builds. It also checks
invalid input, zero division, checked conversions, map keys and allocation balance.
Named imports now find either `.dewy` or `.jo`, preferring the importing language
within each search directory; watch tracks a missing higher-priority candidate.
An explicit `p"@lib/physics.jo"` path selects the bundled implementation even
when a neighboring Dewy game has the same basename.

`python3 -m tools.sloppy_core.benchmark_bigint COMPILER --output /tmp/bigint.json`
measures factorial arithmetic, 512-bit division and 2048-bit decimal round trips.
Use `--baseline OLDER_COMPILER` to compare compatible toolchains. Seven warmed,
alternating runs of 2,000 iterations gave factorial medians of 107.70 ms before
removing redundant proof-era guards and 86.48 ms after (about 20% less time).
Division medians were 3.73/3.29 ms; decimal round trips were 139.45/139.64 ms.
These compare two versions of this library on a shared desktop, not Python/GMP
runtime performance. Python independently validates every measured checksum.
Raw timings, compiler/library hashes and complete programs are recorded in
`bigint-runtime.json` in the source-core audit. Seven warmed builds of the exact
integer example took a median 91.84 ms (92.26 ms before cleanup); tour builds
were 85.06/82.22 ms. These small differences do not establish a compilation
speed change. See `bigint-compile.json`.

The bundled `rational.dewy` builds reduced exact fractions over `BigInt`, with
ordinary record/operator protocols and no compiler changes. It adapts the old
rational library's denominator-GCD addition and cross-cancellation multiplication,
and avoids repeated GCDs when raising a reduced fraction to a power. Signed
powers include the full `int64` exponent range; division by zero is a runtime
error. Parsing, formatting, checked construction, floor/remainder operations,
independent copies and dictionary keys are supported. Integer `/` constructs an
exact fraction directly, including mixed signed/unsigned words and `BigInt`.
The type checker loads the bundled fraction library only after finding exact
operands; floating and custom record division keep their existing dispatch.
Ordinary fixed-width arithmetic still does not widen automatically on overflow.

Native/web debug/release differential checks compare 216 fraction pairs with
Python's `Fraction`, including random parts up to 256 bits. The executable
`exact_rationals.dewy` example covers harmonic sums and exact dice probabilities.
The numeric benchmark's `--workload harmonic100` measures 2,000 sums of the first
100 harmonic terms: seven warmed runs gave a 585.26 ms median. Checksums are
validated independently with Python fractions, and measured compiler/library
identities and all raw samples are in `rational-runtime.json`. This is a first
runtime measurement, not a speed comparison with another rational library.
Seven warmed release builds of the fraction example took a median 63.96 ms
(`rational-compile.json`). The full 1,340-check gate passes with this library;
the unchanged compiler was independently C-bootstrapped at the bigint checkpoint.

`BigInt` and `Rational` now provide explicit `.to_float32()` and `.to_float64()`
conversions for floating APIs. Both round once to nearest, ties to even, including
subnormal results, signed zero and overflow to signed infinity. Fraction parts
are divided at sufficient integer precision instead of individually rounded;
even ratios of two enormous integers can produce a finite, accurate result.
Native/web debug/release checks compare boundary and seeded random inputs through
4,096 bits with CPython's fraction-to-double conversion and libc's decimal-to-float
parser. The latter receives 5,000 decimal digits and avoids double rounding
through Python's float. Allocation-lifetime and vector-use cases are included.
See `exact-float-full-tests.log` and `exact-float-build.json` in the source-core audit.
The full gate passes 1,532 checks in 70.42 seconds. Seven alternating warmed
builds measured the fraction example at 71.00/74.99 ms before/after (CPU
69.77/73.44 ms), and the integer example at 66.48/68.01 ms (CPU 65.27/65.47 ms).
The added library functions have a small checking cost; this is a capability
change, not a compile-time improvement. See `exact-float-compile.json`.

Dewy `^` now parses as right-associative power above multiplication, literal
coefficients and unary minus. Records use `__pow__`; `xor` remains `__xor__`.
BigInt and Rational expose their existing exact power algorithms through this
syntax. Machine `int64`/`uint64` power uses exponentiation by squaring, wraps like
fixed-width multiplication and rejects negative exponents with guidance to use a
rational or floating base. The implementation language's own `pow` contract is
unchanged. Both float widths use the inherited floating math implementation.
The gate checks precedence, evaluation order, custom protocols, error behavior,
and 252 signed/unsigned word-power results against Python modular arithmetic on
native/web in debug/release modes. Both exact-arithmetic examples now use `^`.
A fresh C bootstrap and all 1,381 checks pass. Seven alternating warmed build
pairs gave tour 73.82/78.00 ms, physics 490.94/491.78 ms and compiler self-build
1,961.99/1,879.92 ms (before/after). Shared-desktop variability and mixed results
do not establish a compilation speed change; raw samples are in `power-compile.json`.

The optimizer now retains available values from the straight-line prefix of an
unconditional block after that block ends. Values computed after an earlier
branch stay local, and conditional arms and loops do not export their values.
Operand versions and memory generations still invalidate computations after
mutation. This lets repeated short-circuit array reads reuse an already successful
bounds check and load. In the text application's optimized kernel, byte-load
sites fall from seven to three. Native/web debug/release regressions cover
scanning, skipped branches, changed indices, changed array contents/lengths,
subsequent loop iterations and bounds failures. The independent C bootstrap and
all 1,413 checks pass (83 seconds for the test phase).

Seven alternating application runs gave text medians of 326.92 ms before and
277.14 ms after (about 15% less kernel time); an earlier seven-run text comparison
was 428.66/383.97 ms. The first broad run showed slower record/graph medians amid
large load variation, so both were repeated with nine samples: records were
174.93/173.46 ms and graph 614.46/615.67 ms. Those follow-ups do not show a
consistent regression. Other first-run medians were helpers 1,140.86/1,123.09 ms
and arrays 269.22/256.33 ms; small differences are not speed claims. All measured
checksums match C, with the existing graph representation differences retained.
Raw samples and workload/compiler hashes are in `block-cse-applications.json`,
`block-cse-text-initial.json` and `block-cse-regression-check.json` in the source-core
audit. These are shared-desktop native results, not web performance claims.
Seven warmed compile pairs were tour 51.40/50.53 ms, physics 306.05/305.37 ms
and compiler self-build 1,187.41/1,224.69 ms (before/after). The self-build was
about 3% slower in this run; retain that tradeoff alongside the runtime result.
See `block-cse-compile.json`.

The available-expression lookup now reads operand versions directly and reuses
its hash-table slot when inserting a new value, removing the temporary operand
list and repeated hash probes from that path. Five alternating warmed build
pairs measured physics at 359.01/339.90 ms and compiler self-build at
1339.46/1305.96 ms (before/after). CPU-time medians were 353.31/334.67 ms and
1315.22/1282.47 ms respectively: modest improvements of about 5% and 2.5% in
this run. Earlier partial prototypes were inconclusive. `benchmark_compile.py`
now retains user-plus-system CPU time alongside elapsed time, making scheduler
delays easier to distinguish on the shared desktop. It sums the compiler and
its waited-for children, so multiple emission workers can exceed elapsed time.
See `cse-probe-compile.json` in the source-core audit.

Loop-effect metadata now stores definitions once in a flat list, with nested
loops sharing subranges. Memory-write categories propagate to the parent when
a loop closes. The prepass no longer walks every enclosing construct for every
instruction or allocates a definition array for each loop. A fresh C bootstrap
and all 1,536 checks pass in 79.66 seconds, including nested integer/float/header
mutations, dead loops, sibling loops and `continue`.

Seven alternating warmed builds with the C-bootstrapped compiler measured tour
at 58.60/58.00 ms, physics at 342.98/336.50 ms and compiler self-build at
1,721.33/1,598.65 ms before/after. CPU medians were 56.29/57.05, 338.01/332.81
and 1,642.45/1,516.93 ms respectively. An earlier seven-pair run gave physics
344.83/328.92 ms and self-build 1,389.36/1,292.01 ms. These shared-desktop
measurements show about 7% less self-build time; the smaller physics improvement
varied between runs, and tiny builds were effectively unchanged. See
`flat-loop-compile-final.json`, `flat-loop-compile.json`, `flat-loop-build.json`
and `flat-loop-full-tests.log` in the source-core audit. A preceding experiment
replacing operand-list scans with masks gave conflicting results and was discarded.

Dewy call arguments now keep array literals open to the selected parameter's
element type. `[1]` can directly supply `array<uint64>`, `array<float32>` or
`array<BigInt>` without a cast on each element. Overload selection checks the
elements and their conversion costs before choosing a candidate; the children
are checked once without prematurely fixing the container's type. This also
supports nested arrays, optional array parameters, generic calls and arrays of
contextual records. Existing array variables retain their concrete element type.
Out-of-range literals and incompatible typed elements remain errors. The focused
32-check selection takes 3.20 seconds; evidence for the independent C bootstrap
and full gate is in `context-array-build.json` and `context-array-full-tests.log`.
All 1,564 checks passed in 93.54 seconds. Seven alternating warmed builds were
tour 61.19/59.06 ms, physics 351.79/346.08 ms and self-build 1,303.71/1,329.33 ms
before/after. CPU medians were 58.30/56.53, 346.99/342.46 and 1,261.12/1,309.96 ms.
The self-build cost was slightly higher in this run; this change improves typing
ergonomics, with no compile-speed claim. See `context-array-compile.json`.

Source files now retain their language classification when loaded, so checking
and lowering read a flag instead of repeatedly examining filename suffixes.
Implementation-language array arguments also skip an extra context-dependent
walk needed only by Dewy literals. Seven warmed pairs were tour 57.41/59.54 ms,
physics 333.14/334.66 ms and self-build 1,305.37/1,283.98 ms before/after; CPU
medians were 56.30/56.25, 325.88/330.06 and 1,283.78/1,267.16 ms. These small,
mixed differences do not establish an overall speedup. The retained change
removes repeated classification work. See `source-language-compile.json`,
`source-language-build.json` and `source-language-full-tests.log`.

The bundled `Pool` now updates scalar fields/elements directly when its getter
and setter are the library implementations and every index/right operand is an
ordinary read or checked scalar arithmetic/boolean expression. It uses a
qualified library helper to validate the handle, then
the existing array place lowering, including bounds checks and copy-on-write.
Custom indexers, side-effecting calls and other complex updates retain
read/edit/writeback. The fast path removes an avoidable nested-array copy on
each ordinary inventory edit while preserving independent snapshots.

The new `benchmark_pool.py` runs `pool_inventory.dewy`: 64 entities, each with 32
integer inventory slots, one million updates, and a snapshot retained throughout.
Seven alternating native release runs measured **100.48 / 23.96 ms** before/after,
about **4.2× faster for this workload**. Python independently validates the final
data and unchanged snapshot, including empty/small preflights. Kernel timing
excludes setup and checksums. This is not a claim about every Pool operation or
web performance. Seven compile pairs were pool inventory 54.01/54.49 ms, entities
77.95/76.73 ms, physics 342.57/334.09 ms and self-build 1,318.76/1,330.85 ms;
mixed small differences do not establish a compilation speed change.

A fresh C bootstrap and all 1,608 checks pass in 74.10 seconds. The focused
82-check selection takes 3.99 seconds and covers copies, allocation lifetime,
custom accessors, side effects, stale handles and bounds failures on native/web
in debug/release. Evidence and complete benchmark inputs are in
[`dewy/audits/2026-10-17/`](../../dewy/audits/2026-10-17/README.md).

The scalar-expression extension also handles updates such as `+= delta+1`
directly. That variant measured 140.82/37.01 ms before/after, about 3.8×, while
other projects were using substantial CPU. Those absolute times are not
comparable to the quieter initial run. Its fresh-bootstrap gate passed 1,621
checks in 103.18 seconds; the same audit directory records inputs and results.

Stepped integer loops use `[first,second..end]` or an exclusive `)` endpoint.
Their bounded form computes its trip count once, retaining full signed/unsigned
word behavior without a per-iteration overflow check. The Python range oracle
checks 1,216 cases on native/web in both modes. Open-ended steps report integer
exhaustion; zero steps panic. Bounded signed-word steps now also support combined
loops, stored `IntRange` values, membership and array selections.
See the language guide and the October 17 audit for the
bootstrap gates and measured lowering/compilation comparisons. Proved ascending
strides over a stable array extent also omit redundant bounds checks: a repeated
every-third-slot update with a live snapshot measured 44.81/24.55 ms before/after
(about 1.8×), with 1,763 checks passing from a fresh C bootstrap.

Combined loop headers also accept `or`, continuing until every input is
exhausted and supplying `none` for exhausted arms. Range starts evaluate once;
bounded ranges stop at integer maxima and open counters report exhaustion.
Range-plus-condition loops use the counted lowering, and zero-based sequence
indexes retain their fast path. The October 17 audit records the 1,864-check
C-bootstrap gate and the paired compilation measurements.

The combined Dewy/editor/shared-core gate now contains over 1,800 checks and takes
roughly one to one-and-a-half minutes locally, including compiler processes and program execution.
Value cases run in debug and release modes. It includes the paddle game model
on native and WebAssembly targets in both modes, and a
display-independent render of the actual game. The playable example and build
instructions are in `examples/sloppy_core/`.
Evidence is in `dewy/audits/2026-10-16/source-core/` and
`dewy/audits/2026-10-17/source-core/`.

At the first batching checkpoint, the ordinary value gate retained 674 individual
debug/release/native/web pytest checks while grouping up to 16 independent
modules into each build and execution, using 44 compiler launches instead of 674. Selection happens before grouping,
so `-k` still gives a small reproducer, and each case's full result and captured
output are checked separately. Harness checks exercise module isolation, output
attribution, incorrect results, compile failures and panics. Process-specific
and integration tests keep their dedicated runs.

One sequential comparison with the same compiler and identical case-source
hashes took 73.49 seconds before batching and 7.93 seconds after, including pytest
startup. This is about 9.3× faster for the 674 value checks; it is a shared-desktop
measurement of orchestration, not a compiler performance claim. See
`value-batch-timing.json` in the source-core audit for commands, counts, hashes,
system load and limits.

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
imported implementation-language functions. Defaulted parameters are marked `= …`.
The Dewy formatter uses the Dewy lexer to preserve meaningful adjacency and literal
contents. CLI `fmt` and editor Format Document normalize indentation and declaration
spacing; `fmt --check` checks without writing. Tests in
`tests/python_misc/test_sloppy_core_format.py` cover CLI, unsaved buffers and
native/web execution before and after formatting. Other inherited editor features
remain experimental.

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
bounds panic at runtime. String slices use grapheme boundaries too. Bounded
signed-word ranges can be stored as lazy `IntRange` values, reused in loops,
returned or passed between functions, and tested with membership. They retain
constant storage even across the full signed-word domain. Ordinary stored-range
loops use scalar state and the existing counted-loop backend.

Stored ranges also select array elements, including descending and exclusive-first
ranges. Direct stepped slices such as `xs[0,2..]` and `xs[5,3..0]` reuse the same
selection helpers. Scalar assignments fill selected positions; array assignments
require one replacement per position and preserve overlapping input snapshots.
Contiguous slice assignments, including omitted bounds, use the same fixed-length
replacement/fill operation. Explicit bounds evaluate once before the replacement.
Selection validates the full interval with unsigned distance/division before
accessing elements, then traverses it without constructing an index array.
Stepped string slices and compound selection updates remain unsupported.

Optional types accept `T?` and `T | none`, with `none` values and `is?`/`isnt?`
narrowing. This includes dictionary `.get`, arrays of optional values, optional
unions, and independent copies of optional records. The earlier compiler's
`dewy/tests/optional_values.dewy` runs unchanged in both build modes.

Dewy string `.length`, `len(s)`, indexing, slicing and loop iteration now use
Unicode 16 extended grapheme clusters. Combining marks, emoji ZWJ sequences,
regional indicators, Indic conjuncts and CR/LF follow the existing Unicode
conformance corpus. The compact byte representation remains: length scans,
index/slice scan up to the requested boundary, and string loops stream from a
retained input snapshot. Each yielded grapheme is an independent string; early
exit leaves the remaining text unscanned. `graphemes(s)` explicitly collects an
array when one is wanted. Explicit `bytes(s)` exposes bytes;
implementation `.jo` libraries retain byte-oriented operations. Text supplied by
those libraries is validated as it is scanned, including boundary lookahead; malformed UTF-8 panics in Dewy
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
Changing a global initializer also refreshes initializers that read it directly
or through statically resolved helper calls, in dependency order across imports.
Assets embedded inside those helpers also refresh their derived globals.
Recursive helper calls are scanned once; creating a closure does not read its
body's dependencies or reset captured state when those assets change. Repeated same-layout replacements
release old managed values; unrelated live state remains. The watch gate checks
asset deletion/recovery, stable live allocation counts and a counter continuing
across repeated asset edits. Dependency discovery does not yet follow calls through arbitrary function values.

Unsigned `uint64` floor division and modulo now use the core’s unsigned divide
and remainder operations, including literal power-of-two fast paths. Native/web
debug/release checks compare 876 quotient/remainder pairs per mode with Python
integers, spanning zero through `2^64−1` and every power-of-two divisor. Zero
divisors fail in both modes, and signed literal/narrow-input inference is retained.

Default and release builds recognize nonnegative, bounded integer expressions
before a positive constant floor remainder. A local's initializer and every
assignment must establish an independent bound; captured, address-taken and aliased locals
are excluded. Addition and multiplication must fit signed 64-bit arithmetic.
This lets a byte-hashing recurrence use unsigned remainder without negative-sign
correction, while overflow, arbitrary mutations and user overloads retain their
existing behavior. The analysis runs lazily only in functions with eligible calls.

The initial release-only change, over seven alternating thread-CPU pairs on
the unchanged text-scanning application, gave a median candidate/baseline ratio
of 0.894 (251.79/225.04 ms separate medians).
The candidate/C ratio is 1.251 for this workload. Five fresh-build CPU pairs give
tour 0.979, Dunes 1.003 and compiler 0.966; no general compile-time gain is claimed.
The independent C-bootstrap gate passes 3,420 checks in 39.51 seconds, including
overflow, negative writes, reference/closure mutation and native/web codegen.
See the `positive-mod-*` source-core audits for samples and toolchain identities.

Dictionaries support `insert_if_absent(key value)`, returning true only when a
new entry was added. Existing values and insertion order are preserved; ordinary
argument evaluation and independent value copies still apply. It combines an
absence check and insertion without hashing/probing a missing key twice.
`reserve(count)` on dictionaries and arrays avoids growth when the eventual
size is known, without changing their contents.

The graph-discovery benchmark compares the original lookup/assignment loop,
`insert_if_absent`, and an additional capacity-reserving variant, all with the
same compiler and graph. It checks small and full-run checksums against the C
program and alternates run order. C uses a different graph/map layout, so this
is an application comparison, not a universal map ranking:

```sh
python3 -m tools.sloppy_core.benchmark_map /tmp/dewy-core/bin/dewy-core \
  --samples 7 --output /tmp/map-results.json
```

`benchmark_apps` and `benchmark_map` also accept `--clock thread-cpu` on Linux.
This measures CPU time inside the kernel on both Dewy and C, excluding time the
thread was descheduled. The default remains elapsed wall time. Both modes retain
process wall time and record the measured harness hashes. CPU timing still
depends on clock frequency and shared caches; it does not make a busy host an
isolated benchmark machine.

Typed `to_json(value)` now writes directly from typed fields into the output
buffer. It no longer formats text, reparses it into a `Json` tree, and formats
that tree again. Full-width signed/unsigned IDs survive a typed round trip;
finite floats preserve their width-specific representation and negative zero.
Record, tuple, fixed-array, vector, enum and union writers are selected at
compile time. Payload enum variants now read back from their JSON representation,
and custom variants named `number`, `text` or `list` keep their tags.
`json_value` uses the same schema, but its explicit `Json.number` remains f64.
See [the settings example](../../examples/sloppy_core/settings.dewy).

Ten serializations of 10,000 records take 17.4 ms versus 167.7 ms with the previous
writer in a seven-pair release/thread-CPU comparison (median paired ratio 0.103).
The input is prepared before timing and both programs produce the same length
checksum. Fresh-build paired CPU ratios are 0.992 for the tour, 1.005 for Dunes,
and 0.985 for the compiler itself; these do not establish a compilation change.
Raw samples and compiler identities are in `typed-json-runtime.json` and
`typed-json-compile.json` in the 2026-10-17 source-core audit. The independent
C-bootstrap gate passed 2,811 checks in 130 seconds. A final malformed-enum
rejection additionally passed all 76 JSON/upstream checks; the settings example
agrees in native/web default/release modes.

`sort_by` / `sorted_by` cache each key as before, then sort integer positions with
statically typed comparisons. The reorder builds its result once instead of
copying the original array and replacing every copied field. Equal keys stay
stable in ascending and descending order, and record/array snapshots remain
independent. This also removes comparator closures from the compiler's internal
keyed sorts.

For ten sorts of 20,000 entity records, seven alternating thread-CPU pairs against
the previous implementation reduce release integer-key sorting by about 57–58%
across random, ordered, reversed and equal-key inputs. String keys improve by
about 17%. Default builds improve by 50–53% for integer keys and 10% for string
keys. Every result checksum matches Python's stable sort; setup and checksum
work are outside the timed region. These workloads do not establish a general
sorting/C performance ranking. Raw results are in `keyed-sort-runtime.json` and
`keyed-sort-default-runtime.json` in the source-core audit.
Fresh-build paired CPU ratios are tour 0.998, Dunes 0.965 and compiler 1.003;
there is no broad compilation speedup claim. Independent C-bootstrap validation
passes 2,831 checks in 129 seconds, including native/web tuple-key ordering
against Python and managed-copy checks.

The separate `sort_with` comparator path now shifts insertion-sort entries instead
of swapping managed records repeatedly, leaves already-ordered entries untouched,
and merges with separate remainder-copy loops. In seven alternating thread-CPU
pairs on the same 20,000-record inputs, release random/reversed integer ordering
improves by 17–23%, ordered/equal inputs by 52–55%, and string ordering by about 5%.
Default builds improve by 11–27% on random/reversed integer inputs and about 40%
on ordered/equal inputs; the string result is near neutral (paired ratio 0.975).
Independent Python checksums agree, and 64 focused native/web default/release
checks pass. See `comparator-sort-{release,default}-runtime.json` and
`comparator-sort-validation.json` for the measured toolchains and scope.

Constant interval tests on an ordinary signed 64-bit local now lower to one
unsigned comparison. For example, `x <? 0 or x >=? BOX` checks the same interval
without separate negative/upper-bound branches. Bounds may cross zero or span
the entire signed range; calls, aliases, floats and overloaded comparisons keep
their existing evaluation. Native/web default/release checks compare 2,800
interval results per mode with Python, including open/closed endpoints, empty
intervals and both integer extremes. Separate cases retain short-circuit effects.

Five alternating thread-CPU application pairs show a median candidate/baseline
ratio of 0.865 for the particle-record kernel; helpers, arrays, text and graph are
0.991, 1.013, 1.025 and 1.013 respectively. The other workloads do not establish
an improvement. Fresh-build paired CPU ratios are 1.004 for the tour, 1.018 for
Dunes and 0.992 for the compiler: no compilation improvement is claimed.
Raw samples are in `interval-applications.json` and `interval-compile.json`.

A guarded open unit range such as `loop i in 0.. and i <? values.length` now uses
bounded-range lowering when the stopping value is an unchanged local/constant
or a provably fixed array length. This removes the redundant integer-exhaustion
counter and lets the existing bounds analysis apply. Resizing, changing limits,
captured/assigned indices and effectful conditions retain live evaluation.
Additional header conditions keep their order; empty loop/else, `continue`, signed
integer extremes and still-invalid indices are covered on native and web.

Five alternating release/thread-CPU pairs against the previous compiler give
candidate/baseline ratios of helpers 0.993, arrays 0.980, records 0.809, text 0.989
and graph 0.997. The record kernel is 0.857 times the C reference in this run;
that is a workload result, not a general compiler ranking. Default-build pairs
at the smaller development counts give arrays 0.951 and records 0.923, with the
other three workloads near neutral. Fresh-build paired CPU ratios are tour
0.999, Dunes 0.989 and self-compilation 1.031; the latter's samples vary widely,
so no compilation gain is claimed. See the `guarded-range-*` source-core audits.
The independent C-bootstrap gate passes 2,899 checks in 169 seconds.

The full `python3 -m tools.core test` gate now uses up to four pytest workers when
pytest-xdist is installed. The compact-core plugin groups by test function and
build mode, preserving reuse of compiled case batches while letting the large
source-core test file use multiple workers. Other repository tests keep file
isolation. Focused commands such as `test -k record` stay serial; `test -n 0`
forces serial execution and `test -n 2` selects two workers. Without pytest-xdist,
the default gate falls back to serial execution. CI explicitly uses two workers.

`python3 -m tools.core test --quick` selects an edit-loop smoke suite from the
same cases: values and language behavior on native/web in default/release modes,
imports, diagnostics, a headless game model and driver checks. It defaults to
serial execution and accepts `-k` to narrow the selection. A local run passes
130 checks in 2.78 pytest seconds (3.35 seconds including the driver); the full
gate passes 3,398 checks in 48.23 seconds using the same C-built compiler. These
are different coverage levels, not a faster execution of the full suite. Compiler
input changes still rebuild before either command, and test programs compile
afresh. The ordinary `test` command and CI keep the full gate. See
`quick-validation.json` and its logs for this run.

On the same 2,899 checks, a local four-worker grouped run took 88.10 seconds,
versus 168.61 seconds serially and 169.33 seconds with whole-file grouping.
These are pytest times excluding bootstrap, from one run per strategy on a
shared host. All checks passed; the subsequent worker-selection changes pass
19 serial driver checks and 59 two-worker JSON/driver checks. See
`parallel-validation.json` and its full-run logs for scope and toolchain identity.

Scalar integer selections now simplify when inlining makes their condition
constant, an enclosing branch establishes the condition, or both alternatives
are the same value. Argument evaluation and other effects remain intact; only
the selection and subsequently unused pure arithmetic disappear.

An isolated helper with a constant mode selecting between two integer mixing
formulas now performs one multiplication per iteration instead of two. Seven
alternating thread-CPU pairs pinned to CPU 2 measured 206.20/140.43 ms for 100
million iterations, with a median paired candidate/baseline ratio of 0.679.
Python independently checks the result by composing the recurrence. This is a
helper-specialization result, not an application-wide speedup. Fresh-build paired
CPU ratios are tour 0.968, Dunes 0.988 and compiler 1.025; no compilation gain is
claimed. The independent C-bootstrap gate passes 2,910 checks in 56.38 seconds.
See the `constant-select-*` source-core audits for sources, samples and toolchains.

Plain scalar conditionals with two value-producing arms now omit the initial
zero write that both arms overwrite. This also leaves a single definition when
the optimizer turns the branches into a selection. Existing checks cover narrow
integers, floats, booleans, full-width unsigned values, nested conditionals and
early exits. All 2,910 checks pass from the independent C seed. Five fresh-build
CPU pairs give ratios of tour 1.011, Dunes 1.012 and compiler 1.008, so this is a
lowering simplification with no compile-speed claim. See `conditional-init-*`.


The camera-roll and menu-width changes from Sloppy commits `0f4d68e` and
`d113c79` are incorporated into the bundled game libraries. `camera3d` accepts
an optional `up` vector, shared by rendering, world/screen conversion, particle
billboards and positional audio. Menu rows accommodate long labels/choice values
and share their width across frames. `camera_roll.dewy` exercises camera roll,
projected labels, cursor-ray picking and a long-label settings menu. Native/web
checks cover projection, inverse picking, audio orientation and restoring the
default camera orientation. The original Sloppy checkout is not modified.


The Dewy rollback lab exercises the inherited generic `netplay` library with
Dewy state/input records and a Dewy tick callback. Two peers predict, retain COW
snapshots and replay late inputs over a deterministic simulated link. Native/web,
default/release checks run 900 frames both without delay and with 120 ms latency,
30 ms jitter and 10% loss. Python independently computes the state at a confirmed
tick and checks both peers, zero desynchronization reports, actual rollbacks and
an unchanged original snapshot. The interactive example also has software-render
and web-build checks. Seven focused checks pass in 10.00 seconds using the same
C-built compiler as the preceding full 3,525-check gate. No compiler or library
inputs changed for this example; see `rollback-validation.json` for scope.


Dictionary `keys()` and `values()` now collect only the requested live field
after removals. They retain the existing shared-storage fast path when no entries
are gone. Previously a projection copied and compacted the whole dictionary,
including its other field, cached hashes and probe table. Set operations that
request member arrays use the improved key projection too.

Seven alternating thread-CPU pairs pinned to CPU 2 on an 8,192-entry dictionary
with one quarter removed measured keys at 305.53/48.41 ms and values at
305.15/93.19 ms (baseline/candidate). Median paired ratios are
0.157/0.303. The 2,000 projections retain insertion order;
values are two-element integer arrays. Setup/removal is outside the kernel,
and Python independently checks checksums, including wraparound through the live
entries. This is an isolated collection workload, not an application-wide claim.
`python3 -m tools.sloppy_core.benchmark_projection --help` documents the rerun.
The independent C-bootstrap gate passes 3,552 checks in 102.46 pytest seconds;
see the `map-projection-*` source-core audits.

Dictionary loops and unpacking now use a separate dense snapshot containing only
keys and values. Dictionaries with no removals share those arrays; sparse inputs
collect live entries without copying hashes or rebuilding the probe table.
The compiler hoists the snapshot's array bounds and addresses outside ordinary
key/value loops. Mutation, insertion order, counted/zipped loops and early exits
retain their existing language behavior.

Seven alternating thread-CPU pairs on 8,192-entry dictionaries (1,000 traversals,
managed array values, construction/removal outside the kernel) measured sparse
ordinary/counting/zipped/early-exit ratios of 0.504/0.465/0.617/0.429 against the
preceding compiler. Dense ordinary traversal measured 0.865, while counted and
zipped traversal were effectively unchanged at 0.985/0.998. These are isolated
iteration workloads, not application-wide gains. A streaming cursor experiment
was rejected because it slowed dense traversal; the retained dense snapshot is
the implemented approach. `python3 -m tools.sloppy_core.benchmark_iteration --help`
documents the benchmark and independent Python checksum checks.

The independent C-bootstrap gate passes 3,580 checks in 83.30 pytest seconds
with two workers. Added checks cover sparse snapshots under source mutation,
ordering, a two-array allocation budget, combined exhaustion and cleanup through
continue/break/return. See the `map-entries-*` source-core audits for the toolchain,
runtime measurements and separate fresh-compilation comparison.

Set `pop()` now retains a tail cursor instead of collecting all live members
before each removal. Insertions reset the upper bound; removal/compaction clamps
it, and successive pops scan each removed tail only once. The cursor is a scalar
part of the set value, so copies remain independent. This removes repeated
whole-set projection and avoids retaining the key array across its mutation.

Seven alternating thread-CPU pairs draining sets created from 4,096 members,
with every fourth member removed before timing, measured scalar keys at
12.03/0.138 ms and two-integer-array keys at 36.72/0.483 ms (baseline/candidate).
Median paired ratios are 0.0111/0.0133. At 16,384 initial members, five pairs
measured 297.19/0.797 ms and 584.29/1.937 ms respectively. Construction/removal
is outside the timed drain; the Python oracle checks both values and pop order.
This measures draining uniquely owned sets, not arbitrary applications or the
necessary copy-on-write cost when another set snapshot is retained.
`python3 -m tools.sloppy_core.benchmark_set_pop --help` documents the rerun;
see `set-pop-*` source-core audits for measurements and validation.

Known-size arrays now use Dewy's `array<T length=N>` syntax and the inherited
inline-array backend. Positive constant lengths work with generic aliases,
record/dictionary fields, optionals, value copies, counted/zipped loops and
nested unpacking. Growable-to-inline conversion checks the length once and
copies; the reverse conversion creates a growable array. Mutable parameters
still require an exact type. Reading a fixed array's `.length` preserves receiver
effects and bounds checks even though its result is constant.

Seven paired thread-CPU graph runs with one million nodes measured 703.71 ms
with ordinary growable neighbor arrays and 628.83 ms with explicitly inline
four-element neighbors (median paired ratio 0.858). The C reference measured
475.17 ms. This is a source representation choice, not automatic specialization
or a speedup to unchanged code. C uses a custom table and one flat neighbor
allocation; graph construction is outside the timed BFS kernel. The benchmark
checks matching outputs for empty, single-node, small and measured graphs.
Run `python3 -m tools.sloppy_core.benchmark_fixed_graph --help` to reproduce it.

The independent C-bootstrap suite passes 3,696 checks in 81.17 pytest seconds
with two workers. New checks run natively and on WebAssembly in default/release
modes, including managed-value cleanup, runtime shape failures, generic context,
side effects and mutable-argument rejection. See `fixed-array-*` source-core
audits for raw measurements and validation.

Inline arrays now compose with contiguous read slices, stepped selections,
index arrays, masks and stored ranges. Contiguous slices copy only the selected
range into one growable result; they retain a snapshot before bound expressions
run. Stepped/indexed selections currently convert through the ordinary array
helpers. Fixed-array slices used in loops own their result through the loop,
including managed values and temporary receivers. Slice assignment is rejected
with guidance to update individual elements.

Spread literals infer their element type from inline operands and accept fixed
array contexts, including narrow integers and generic parameters. The existing
runtime shape check handles an expanded literal of the wrong length. See
`fixed-slice-*` audits for focused native/web checks, allocation cleanup and
invalid bounds; the full independent C-bootstrap gate runs in hosted CI.


Joined polylines now follow Sloppy's `64b6646` band geometry: adjacent segments
share their corner vertices, including the closing edge, and sharp joins are
capped. Repeated points are skipped. Dewy's adaptation streams normals and joins
without scratch arrays and reserves each quad individually, so a long path can
cross the renderer's batch boundary. A COW snapshot protects the active path if
an effect callback changes the caller's points during a flush.

Seven alternating thread-CPU pairs drawing 512-point paths 1,000 times measured
71.33/55.17 ms for open paths and 69.15/52.40 ms for closed paths, comparing the
initial temporary-array adaptation with the streaming version. Median paired
ratios are 0.773/0.737. These measure vertex generation only, excluding GPU work,
window setup and input construction. The initial adaptation already reserves
quads safely; the comparison isolates streaming work, not an unsafe baseline.
Use `python3 -m tools.sloppy_core.benchmark_polyline --help` to repeat it.

The `outlines.dewy` example shows thick zigzags, a closed star, rounded outlines,
repeated inputs and a 6,000-point plot crossing multiple batches. Fifteen focused
native/web checks pass in 3.91 seconds and the 149-check quick suite in 3.41.
See `polyline-*` source-core audits for raw results, baseline patch and limits.


Inline-array selections now also support assignment: contiguous/stepped slices,
stored ranges, index arrays and masks accept scalar fills or an exact number of
replacement values. The compiler supplies storage and element types to shared
library helpers, which write inline storage directly. This retains narrow literal
context, overlap snapshots, parameter value copies and nested writeback through
records, dictionaries and custom containers. Compound selection assignment still
requires an explicit loop.

Read selections use the same storage-generic helpers. Stepped/index/mask/stored
range reads no longer materialize a growable copy of the complete inline source;
only the selected result needs growable storage. Source snapshots still precede
side-effecting index expressions. Contiguous slices retain their existing direct
copy path. `fixed-update-*` source-core audits record validation and paired
selection measurements; `benchmark_fixed_selection.py` reruns unchanged source
against two standalone toolchains.

Seven alternating thread-CPU pairs selecting from 512 inline integers 100,000
times measured 18.63/10.42 ms for stepped reads and 13.80/4.80 ms for index-list
reads (baseline/candidate). Median paired ratios are 0.560/0.336. Both toolchains
compile the same source; input construction is excluded and result allocation
and summation are included. These are isolated selection workloads, not a broad
application speed claim. Five fresh-build pairs show no compile-speed gain.
The independent C-bootstrap suite passes 3,824 checks in 83.61 pytest seconds
with two workers; the focused selection passes 448 checks in 6.86 seconds.


Interval comparison lowering now covers narrow integers and ordinary reads from
local growable/inline arrays. Adjacent comparisons after a leading guard can
share one unsigned interval test: the guard still runs first, and even an empty
interval performs the original first array read and its bounds check. Calls,
mutable parameters, deferred aliases, raw pointers, overloaded comparisons and
full-width unsigned integers retain the existing path.

The final five-pair application run gives a median candidate/baseline thread-CPU
ratio of 0.969 for unchanged text scanning; an earlier seven-pair run of the
regrouped implementation measured 0.917. Helpers, arrays, records and graph give
0.995, 0.994, 1.019 and 0.981 in the broad run, so there is no general speedup
claim. Seven fresh-build CPU pairs give tour 0.988, Dunes 0.998 and compiler 0.999;
separate medians fluctuate substantially with host load and are not evidence of
a compilation gain. The independent C-bootstrap suite passes 3,860 checks in
68.57 pytest seconds with two workers. See `range-load-*` and `range-chain-*`
audits for measurements, the initial neutral experiment and validation limits.


Release builds now avoid the redundant copy from a value parameter into Dewy's
same-named local when that local only reads the input. Existing caller-side
snapshot handling protects the borrowed value; returned values still acquire
their own ownership. Mutation, captures, address-taking, raw-buffer access and
variable-debug builds keep independent local storage. This needs no source
annotation and does not change parameter value semantics.

The selection benchmark's `--helper` option runs the same selections through an
ordinary Dewy function. Seven alternating pairs at 500,000 calls give median
candidate/baseline thread-CPU ratios of 0.483 for stepped and
0.294 for indexed reads. These are isolated helper calls over 512 inline
integers; result allocation and summation stay timed. An earlier run before the
debugger exclusion is also retained. Five pairs on unchanged text/graph programs
give 0.939/0.970. Seven fresh-build pairs give tour 0.982, Dunes 1.029 and compiler
0.963: Dunes release compilation has a measured cost, and no general compile-speed
gain is claimed. The independent C-bootstrap suite passes 3,872 checks in 88.06
pytest seconds with two workers. See `parameter-view-*` audits for samples,
source/binary identities and scope.


Index lists and boolean masks may now be inline arrays too. The shared selection
helpers specialize on selector storage as well as receiver and element types,
so both reads and writes avoid converting an inline selector to a growable one.
Repeated indexes retain their written order, overlapping selectors retain their
value snapshots, and masks still require the receiver's length. A bare empty
selector (`values[[]]`) now infers integer indexes and selects no elements.
The focused gate passes 272 checks in 10.92 seconds after an independent C
bootstrap, and the quick suite passes 149 in 4.78 seconds. See `fixed-selector-*`
audits; this increment makes no runtime performance claim.


Bundled library functions inside top-level `when` / `else` branches now defer
body parsing until needed, as ordinary top-level library functions already did.
The lexer tracks declaration scopes and each header's indentation, so nested
target branches work without treating local closures as module declarations.
This cuts initial prelude AST construction from 79,697 nodes to 41,709 in the
instrumented profile. It does not introduce a persistent program cache or defer
checks in ordinary user modules.

Seven alternating fresh-build pairs give median candidate/baseline compiler-CPU
ratios of 0.888 for the tour, 1.011 for physics checking, 1.008 for native Dunes,
0.929 for web Dunes and 0.982 for self-compilation. The small and web builds
benefit; native Dunes and physics checking are approximately neutral in this
run. The independent C-bootstrap gate passes 3,912 checks in 134.74 pytest
seconds with two workers. Sixteen focused cases cover nested branches, spaces,
tabs, multiline strings, local closures and original source locations for a
body first parsed when called. See `lazy-when-*` and `check-profile*.json` audits
for measurements, commands and toolchain identities.


The local optimizer now indexes known branch conditions directly by virtual
register, with separate entries for true and false. Scope and branch-count
checks remain the same, and new registers plus each optimization pass reset
fact state. Ordinary expression/load CSE keeps its existing hash table. Seven
alternating fresh-build pairs give modest median compiler-CPU ratios of 0.993
for the tour, 0.987 for Dunes and 0.975 for self-compilation. The focused
optimizer/bounds/loop selection passes 600 checks; the independent C-bootstrap
suite passes 3,916 in 82.39 pytest seconds with two workers. See `direct-fact-*`
audits. No generated-program speedup is claimed for this lookup change.


`dewy-core repl` now uses the Dewy frontend with the inherited native session
engine. Variables, functions, types and imports persist; assignment updates an
existing binding, while explicit `let` redeclaration creates a new one. New
imports are registered, checked and initialized in dependency order once per
session. Failed inputs restore both program values and compiler declarations,
including failed module imports. External output and file effects remain.
Result display wraps the checked AST, avoiding a second compilation and fragile
text splicing. Multiline input shares Dewy's quote scanner, including raw,
interpolated and triple-quoted strings. Type queries use Dewy spellings without
running code. Terminal completion, history and Ctrl-C/Ctrl-D are exercised with
a real PTY. The local driver exposes `python3 -m tools.core repl` too.

The full gate passes 3,933 checks in 78.19 pytest seconds with two workers using
the independently C-bootstrapped compiler. Five fresh, CPU-2 sessions each
processed 100 checked mutable-block inputs: median startup through the first
value was 45.37 ms and median subsequent input latency 6.09 ms. These are simple
interactive inputs in a retained session, not general fresh-build timings.
See `repl-*` audits and the [language guide](../../core/LANGUAGE.md#interactive-prompt)
for behavior, commands and limits.


Rollback sessions now reject packets acknowledging local inputs the session has
never produced, before updating acknowledgment, timing or remote input state.
This carries Sloppy fix `f0d1ce9`: a late packet from a previous round on the same
peers could otherwise stop the new round from sending its inputs. A reproduced
second-round stall at tick 25 now passes three 240-frame rounds, with and without
late packets, on native/web in both build modes. Python checks each peer's state
against an independent arithmetic result. The rollback, restart and local
network selection passes 17 checks in 6.91 seconds. This is a bounded stale-packet
check, not a new session-ID protocol. See `netplay-restart-*` audits.


The software renderer incorporates Sloppy `5a1e0b9`: triangle setup runs in
independent chunks before stable band binning, and built-in 3D lighting uses a
512-square shadow map with four samples in CPU fallback mode. GPU rendering
retains 2048-square maps and nine samples. New `LitParams` fields have defaults
matching the previous GPU settings; custom parameters can choose their own
texel spacing and sample count. The CPU fallback's shadows are softer.

Seven paired release runs at 1280×720, two software-rendering threads on CPUs
2/3 and 31 fixed-step frames give median candidate/baseline frame-time ratios
of 0.767 for forest, 1.024 for Paddle and 0.991 for Dunes. Whole-process CPU
ratios are 0.784, 1.011 and 1.012 respectively. Forest improves; the other two
are approximately neutral. These are software-rendering results, not GPU frame
rates. Dunes has its own shader and still uses its existing shadow sampling in
this comparison. Saved forest/Dunes frames were visually inspected. The 33-case
focused gate includes game renders/web builds, real GLES lighting shader
compilation, default parameters and overlapping triangles crossing worker chunks
with one/two threads. See `software-render-*` audits and reproduce with
`python3 -m tools.sloppy_core.benchmark_render --help`.


Dunes' custom sand shader now follows the renderer's actual shadow texture size
and selects four samples for software rendering, nine for GPU rendering. It no
longer assumes a 2048-square texture in the CPU fallback. A frozen copy of the
previous example and the updated example, built with the same compiler/library
snapshot, give median paired frame-time/process-CPU ratios of 0.907/0.914 across
seven 31-frame runs with the same two-thread software-rendering setup. Scene
content was visually checked; shadow edges are softer. Ten focused checks cover
Dunes' headless model, software frame, native/web builds and real GLES shader
compilation. See `dunes-shadow-*`; `benchmark_render --baseline-sources` compares
example changes while keeping the compiler fixed.


The UI/font portions of Sloppy `1529a25` are incorporated: menu sliders accept
low/high ranges, snapping applies while dragging, and the pressed slider keeps
its pointer until release. HUD sliders can be placed directly in a game panel;
descending ranges have correctly oriented tracks. A light menu style, bounded
row sizing and touch-specific highlights support different game interfaces.
The bundled SDF font adds Greek, common mathematical symbols, arrows and
sub/superscripts, with Noto Sans Math/Symbols 2 notices retained.

`controls.dewy` demonstrates these controls in a pendulum with ordinary Dewy
state and native/web rendering. Its final software frame was visually inspected.
The broader game/font selection passes 57 checks in 11.26 seconds; the final
9-check controls selection passes in 3.70 seconds, including mouse/touch drag
capture, crossing another control, release, keyboard steps and descending HUD
ranges. Font lookup checks run on native and web. See `controls-*` audits.


`format(value spec)` exposes numeric/text formatting through ordinary library
overloads, including computed specs and calls inside Dewy interpolation. It
supports precision, decimal grouping, radix prefixes, padding and alignment;
invalid/incompatible specs panic. Narrow integers keep their signedness, full
`uint64` decimal/radix output remains exact, and floating formats on integer
values explicitly use `float64`. Text width counts graphemes, preserves existing
content and accepts ASCII fill. The pendulum now uses this API for display
precision. There are no parser/compiler changes or new performance claims.
After an independent three-generation C bootstrap, 263 formatting, string and
controls checks pass in 9.99 pytest seconds. The final example frame was visually
reviewed. See `value-format-*` audits and the language guide for supported specs.


Landscape browser games now show Sloppy `64b6646`'s orientation hint on portrait
displays with a coarse primary pointer. `sideways_hint(false)` opts out for
responsive layouts; native windows and fine-pointer displays are unaffected.
The game continues under the hint. The 33 focused game checks pass, and Chromium
viewport/pointer simulation verifies portrait, landscape and opt-out behavior.
See `orientation-*` audits; this is not a physical-phone compatibility claim.


Release emission now removes functions whose last caller disappeared during
inlining or constant folding. Initializers, main, exit/flush, exports, callbacks
and stored function addresses remain reachable roots/edges. Watch and REPL keep
their existing function availability. After an independent three-generation C
bootstrap, all 4,103 checks pass in 71.40 pytest seconds.

Output sizes fall from 192,592 to 181,128 bytes for the tour, 1,779,880 to 1,713,568
for native Dunes, and 1,076,474 to 1,043,514 for its HTML build. Timing is mixed:
seven paired runs give native Dunes a 0.973 candidate/baseline latency ratio; a
web recheck gives 0.964 after a noisy first run, while compiler self-builds regress
(1.039 initially, 1.079 on recheck). This is a code-size improvement, not a blanket
compile-speed claim. `benchmark_compile.py` now records final output bytes outside
the timed interval. See `dead-functions-*` audits for measurements and limits.


The chart portion of Sloppy `1529a25` adds integer/float32 series, dashed lines,
annotations, legend corners and equal-axis scaling. Explicit colors and notes
leave the automatic palette unchanged. Dewy's port bounds the carried dash
phase and explicitly crosses fractional boundaries, fixing a loop that could
stop advancing after accumulated floating-point rounding. Positive subpixel
dashes use a one-pixel minimum.

`charts.dewy` demonstrates these features; both native software output and browser
rendering were visually reviewed. Nine focused checks pass in 2.92 seconds,
covering native/web series, native headless PNG export, dash continuity and the
fractional stall regression. See `charts-*` audits and the language guide.


Function parameters now accept Dewy unpacking patterns, including nested arrays,
record fields, dictionaries and imported tuple values. Whole-parameter types and
defaults reuse ordinary specialization and argument evaluation; callbacks can
infer their parameter types. Body bindings remain independent values, including
when a returned closure mutates a nested array. Duplicate bindings and mutable
patterns are diagnosed. Named parameters can accompany positional patterns.

Default-argument dependency analysis now sees every leaf of a nested declaration
or loop pattern. This prevents a default callback's local name from being
mistaken for an earlier outer parameter, including when that outer parameter is
mutable. See `parameter-unpack-*` audits for the native/web checks and C gate.
The final independent three-generation C bootstrap passes all 4,216 tests in
72.73 pytest seconds; 462 focused and adjacent checks pass in 8.66 seconds.


One-element loop patterns now retain their brackets: `[x]` extracts an element
or named field, and `[[x]]` traverses two levels. This fixes a frontend collapse
that made them behave differently from declaration and parameter patterns.
Older fixtures that used a redundant bracket level now supply genuinely nested
inputs. The 571 unpacking, sequence and comprehension checks pass in 8.62 seconds;
see `single-loop-*` audits. No additional full local gate was needed after the
preceding 4,216-test C gate; hosted CI covers the final parser adjustment.


Sloppy `4d8c4b3`'s rollback diagnostics now follow directly supplied tick functions
and user helper calls, including recursion. They warn about known clock, random,
input and global-write operations. Seeded RNG use remains quiet, as does the
pure `unix_time(Date)` conversion, which was a false positive upstream. Check-only
mode visits checked calls too, including entry functions it does not lower.
These are advisory warnings, with no new proof requirement.

The independent three-generation C bootstrap passes all 4,349 checks in 79.51
pytest seconds; 111 focused checks pass in 14.49 seconds. Seven alternating
compilation samples show similar latency: tour 44.41/44.41 ms, native Netpong
347.58/353.28 ms and compiler 1153.33/1142.68 ms (baseline/candidate). These are
local warmed-process observations, not a speedup claim. See `netplay-warning-*`.


Native WebSocket polling reuses Sloppy `b0796e3`'s 64 KiB scratch buffer instead
of allocating and zeroing one for every peer on each poll. Message storage
remains independent. Eleven networking/Netpong checks pass in 4.02 seconds,
including two large messages whose receives overwrite the scratch buffer.

The reusable `benchmark_network.py` driver compares library sources with the
same compiler over inherited local sockets. Across seven paired 10,000-poll runs,
median CPU ratios are 0.423/0.425/0.428 at 1/8/32 idle peers: about 57% less CPU
in this polling workload. This is not a game FPS or network-throughput claim.
See `network-buffer-*` audits and `python3 -m tools.sloppy_core.benchmark_network --help`.


Sloppy `b0796e3`'s short-code rooms and rendezvous service now work with Dewy
Netpong. `DEWY_MATCH_SERVER` selects a service; the existing invite screens
exchange connection offers automatically. Larger lobbies can use `arrivals`,
`room_busy` and `close_room`. Manual invite codes remain available. See the
[room setup](../../examples/sloppy_core/README.md#short-code-rooms).

Seventeen focused checks pass in 9.49 seconds, including three native peers,
browser-compatible signaling, saved room loading and host reconnection. A new
fragmentation regression first reproduced an existing WebSocket bug, then passed
after storing incomplete messages per peer; total message limits now span polls.
The actual browser Netpong also connected through a room to a native host and
played with no console errors. See `rooms-*` audits; public TURN/cross-router
behavior was not tested and no public service was deployed.


Open-ended stepped counters now compose with finite iterables and conditions:
`loop i in [0,2..] and item in items { ... }`. Combined `or` headers and
comprehensions use the same cursor. Bounds evaluate once in source order, zero
steps are rejected, and requesting a value beyond the signed-word domain panics.
Existing standalone integer-width inference is unchanged. The 586 focused checks
pass in 12.11 seconds; the independent C bootstrap/full gate passes all 4,388
checks in 85.18 seconds. See `open-step-*` audits.


`dewy-core new coin-race online` now creates a playable ordinary-Dewy multiplayer
starter, adapted from Sloppy's bundled online template. Its value-based tick,
practice mode, rollback session and invite screens demonstrate the game stack in
one editable file. Online source filenames come from the project directory, so
new games need not all share the `main` save/room namespace. The generated README
covers native/web builds and optional room service setup. Dewy web-save warnings
now recommend a distinct source filename rather than Jo-only build syntax.

Thirty-five focused checks pass in 17.69 seconds, including model snapshots and
two generated native games agreeing on a completed, confirmed state through a
room in default/release builds. The generated browser game was also exercised
in Practice mode with keyboard movement and no console errors. See
`online-starter-*` audits; this does not establish public-network connectivity.


The bounded-positive-remainder lowering now runs in default builds too. Seven
alternating thread-CPU pairs on the byte-scanning application give a median
candidate/baseline ratio of 0.533 (841.69/447.21 ms separate medians): about 47%
less kernel CPU. The array workload is unchanged (0.996). This preserves floor
semantics and the existing exclusions for negative writes, overflow and escapes.

Paired fresh compilation remains similar: default Netpong 224.18/225.22 ms,
Netpong web 121.52/118.76 ms, compiler 1166.65/1154.88 ms (baseline/candidate).
The independent three-generation C bootstrap passes all 4,400 checks in 89.90
pytest seconds; native/web IR checks now cover both modes. See
`default-positive-mod-*` audits. These are workload-specific observations.

`benchmark_apps --mode both` now compares default and release output with the
same C baseline, alternating runs and recording each variant's flags. `--mode
default` also supports compiler-to-compiler comparisons; the original default
remains release. `benchmark_compile` has `tour-default`, `netpong-default`,
`netpong-web-default` and `dunes-default` workloads. The earlier five-workload
mode comparison is retained in `default-modes-baseline.*` as a baseline before
this change, not a current scorecard.

The same application runner accepts `--target wasm` to run generated web code
under Node, including `--baseline` and `--mode both` comparisons:

```sh
python3 -m tools.sloppy_core.benchmark_apps "$(python3 -m tools.core path)" \
  --target wasm --mode both --workload helpers --count 1000000 --samples 3 \
  --output __dewycache__/apps-web.json
```

It compares checksums with the native C reference at sizes 0, 1, 17 and 1000
before timing the requested size. Every sample starts a fresh process; the
discarded warmup warms host/filesystem caches, not persistent web JIT state.
Kernel timers exclude process startup and input construction, but include JIT
work during the measured kernel. Reports record Node version/options, compiler
flags, artifact and runner hashes, kernel time and whole-process time. Web
artifact sizes describe the complete generated HTML; C remains a native binary.
Use `--node` to select another Node executable. Web runs require `--clock wall`;
`thread-cpu` uses native syscalls and is rejected for WebAssembly. These are CPU
workload comparisons, not browser rendering or general cross-platform parity.

Default builds now lower bundled integer floor division and modulo by positive
literals directly to arithmetic. Powers of two use shifts/masks; other signed
divisors retain the negative-result correction. Dividends evaluate once, and
zero/negative divisors and user overloads retain ordinary calls. Release builds
keep their existing inlining path: applying the new selection form there
regressed the array workload in an initial experiment.

Seven alternating thread-CPU pairs with the final C-bootstrapped compiler give
default candidate/baseline ratios of 0.528 for helper loops, 0.623 for arrays and
0.818 for byte scanning. Absolute timing shifted between runs; these are local
paired observations, not general speed guarantees. Release ratios were
0.998/1.052/1.001 respectively, with no release speedup claim. Checksums matched
at the boundary inputs and full workload sizes. The independent three-generation
C gate passes all 4,410 checks in 89.85 pytest seconds with two workers; the
focused arithmetic selection passes 150 checks in 4.56 seconds. See
`constant-floor-*` audits for final runtime/compilation samples and limits.

Ordinary default builds now expand tiny leaf functions before their existing
single local optimization pass. Candidates have at most 24 unoptimized IR
instructions, no frame slots, loops or calls. The shared inliner preserves
argument evaluation, mutation and early returns; `@noinline`, exports and C ABI
boundaries remain calls. Debug, watch and REPL builds retain their existing
paths. This avoids the release pipeline's callee ordering and repeated passes.

The final C-bootstrapped compiler reduced byte-scanning kernel CPU by about 18%
across seven alternating pairs (ratio 0.815; baseline/candidate medians
261.43/212.99 ms). Graph traversal was unchanged by paired ratio (0.997), and
remains slower than the differently represented C reference. The initial
five-workload experiment gave ratios 0.991/0.956/0.998/0.807/1.010 for
helpers/arrays/records/text/graph. Compilation ratios were
1.020/0.930/1.017/0.955 for tour/default Netpong/web Netpong/compiler; no general
compilation speedup is claimed. All 4,412 checks pass in 90.68 pytest seconds
after three independent C bootstrap generations, with 197 focused checks in
5.19 seconds. See `fast-inline-*` audits for sample timing, source identities
and the distinction between initial and final measurements.

Dewy `const` now retains one initialized value. The inherited expansion behavior
called `next()` twice when reading `const first=next()` twice, and a saved const
array followed changes to its source. Both regressions were reproduced before
the fix. Runtime initializers now run once per declaration execution, including
unused constants; copied values preserve COW snapshots. Fields, elements, mutable
arguments and captured/narrowed bindings enforce the same write barrier. A
`let` copy is mutable. Literal constants can still fold, and constant integer
expressions remain usable as fixed-array lengths. Jo's own const behavior is
unchanged.

The 301 focused checks pass in 7.43 seconds, and the independent three-generation
C gate passes all 4,466 checks in 90.51 seconds with two workers. The quick suite
now includes the once-only initializer case: 153 checks in 3.21 seconds.
Seven fresh-build pairs gave ratios 0.986/1.070/0.994/1.001 for tour/default
Netpong/web Netpong/compiler: Netpong was about 7% slower in this run, with no
general compilation-speed claim. See `constant-values-*` audits.

Unpacking declarations now accept `const` and a type for the whole pattern:
`const [[left] [right]]:array<array<int64>>=[[20] [22]]`. Every extracted name
is read-only, including captured and module-level bindings; `let` copies remain
mutable. The annotation supplies context before extraction, so
`let [a b]:array<uint8>=[20 22]` gives byte-valued bindings. Nested fixed arrays,
records and dictionaries share the existing once-only source evaluation,
snapshot and exact-length checks. Individual leaf annotations remain unsupported.

The 769 focused checks pass in 12.73 seconds and again in 12.60 seconds after
three independent C bootstrap generations. This focused increment relies on
hosted CI for the full gate. See `const-unpack-*` audits.

Integer array literals now prefer generic integer arithmetic over implicit
floating conversion: `sum([9007199254740993 1])` returns the exact integer
9007199254740994. Previously it returned 9007199254740992.0, while the same
array stored in a variable summed correctly. Mixed literals, variables and
function results behave consistently in either order. Concrete narrow overloads
still accept fitting literals, and floating inputs retain floating overloads.
Unconstrained machine-integer literal arrays can also infer `uint64` when a
literal exceeds `int64.max`.

The final focused gate passes 509 checks in 6.64 seconds after three independent
C bootstrap generations; the quick suite passes 157 in 3.25 seconds. An earlier
version passed 4,557 full checks before the mixed-element refinement; hosted CI
runs the final full gate. Fresh compilation is similar across seven alternating
pairs (tour 56.62/56.18 ms, default Netpong 370.26/366.13 ms, web Netpong
197.73/197.55 ms, compiler 1820.50/1830.19 ms). These measurements include
unrelated system load. See `literal-array-overloads-*` audits.

Follow-up: hosted CI caught a fixed-array slice-update regression from that
change. An array literal could still compete for a generic scalar parameter
already bound to `uint8`. Rejecting that incompatible candidate restores the
array overload. The corrected source passes all 4,569 checks in 93.33 seconds
after three independent C bootstrap generations, including explicit and inferred
generic bindings. The earlier focused selection had missed this interaction.

Unpacking now accepts individual name annotations, such as
`let [x:int64 y:float64]=[20 22]`. Local/module declarations, `const`, function
parameters and loop patterns share ordinary assignment conversions on each
extracted value. Arrays, fixed arrays, tuples, records and dictionaries retain
once-only source evaluation and independent values. Whole-source annotations
still supply literal context; leaf annotations do not silently narrow machine
integers or change a function's call signature.

The final focused selection passes 906 checks in 16.20 seconds, including all
pinned Jo regressions. A preceding selection passed 884 checks in 15.95 seconds
after three independent C bootstrap generations; the final source adds a guard
keeping the new assignment diagnostic specific to Dewy. Native/web execution,
both build modes, tuple interop and formatter round trips are covered. Hosted CI
runs the final full gate. See `unpack-leaf-types-*` audits.

Array overload ranking no longer counts the same conversion once per element.
With `choose<T>(T)` and `choose<T>(array<T>)`, `[1 2]` and `[1 2 3 4]` now both
choose the array overload; the latter previously chose the catch-all. Typed
elements and spreads determine a generic element type before scoring earlier
literals, so their range/conversion checks are independent of source order.
Existing context-dependent generic-element and standard-library priority rules
remain in place. The focused selection passes 1,391 native/web, default/release
checks in 20.35 seconds; hosted CI runs the full C-bootstrap gate. See
`array-overload-length-*` audits.

Successful compact-core CI runs now publish a standalone Linux x86-64 archive
after the full gate passes. It contains the tested compiler, bundled libraries
and templates, licenses and provenance, with a sibling SHA-256 checksum.
`python3 -m tools.sloppy_core.package TOOLCHAIN --output NEW.tar.gz` makes the
same package locally and rejects payloads changed since their build.

The package integration test extracts and relocates the archive to a path with
spaces, empties `PATH`, executes native/web sample programs and builds a generated
game for both targets. Compiler/library discovery, executable permissions and
payload hashes are checked. The package and driver selection passes 31 checks in
2.53 seconds. The download workflow is documented in `core/README.md`.

The first published archive passed the hosted C-bootstrap gate with 4,678
checks passing and three platform-dependent skips in 76.18 seconds. Downloading
that exact artifact and running a native typed-unpacking/exact-integer example
with an empty `PATH` also passed; see `package-core-ci-download.json`.

Failed value-test batches now bisect into smaller batches, so one invalid case
does not report failures under fifteen unrelated case names. Compile failures,
panics and early successful process exits are isolated. Healthy batches still
compile once, and failures requiring the combined program remain failures.
The 12 targeted native/web checks pass in 3.63 seconds; the quick suite still
passes 157 checks in 3.17 seconds. This adds work only on the failure path.

Dewy projects now run named `test "description" { assert(...) }` blocks through
the standalone compiler's `test [--release] file.dewy [name filters...]` command.
The inherited runtime isolates tests in child processes on Linux/macOS and keeps
running after a failure. Normal builds omit test bodies; `check` includes them.
A headless paddle-model example and the project testing guide show the workflow.
The C-bootstrap compiler passes 141 focused checks in 8.91 seconds and all 4,707
checks in 110.08 seconds with two workers. See `native-tests-*` audits.

`check` now retains the ordinary `main` entry point while also validating test
blocks. The inherited test-mode flag had suppressed it, hiding errors in `main`
and helpers reachable only from it. Running tests still skips `main`; checking
never executes it. The C-bootstrap compiler passes 94 focused entry-point, test
runner and editor checks in 13.06 seconds; hosted CI runs the full gate.

The inherited CPU worker-pool APIs now have Dewy-native coverage and a particle
simulation example: `parallel_map`, `parallel_range` and `parallel_update` retain
ordinary value copies with named/literal callbacks. Native one/two-thread and web
fallback execution, nested/repeated work, managed lifetimes and rejected shared
writes pass 20 checks; example formatting brings the focused selection to 21 in
3.22 seconds. The quick suite passes 159 checks in 4.63 seconds.

For 2,048 particles over 16 all-pairs force steps, seven alternating release
samples measured 329.87 ms serial versus 173.31 ms with two threads. The median
paired ratio is 0.525 (about 47% less kernel wall time). Next-frame allocation is
included; initialization and pool warmup are excluded. This is one substantial
numerical workload, not a claim for tiny callbacks or all games. Several parallel
samples were affected by other system work. See `parallel-dewy-*` audits.

The VS Code extension now exposes default/release project-test commands using
the configured compiler. They save open files, preserve literal paths, and use
editor-owned process tasks for output, cancellation and reruns. Real compiler
execution behind VS Code API doubles passes alongside the existing client/debug
integration: 25 focused checks in 4.51 seconds. This is not a desktop extension-host
certification; see `editor-test-tasks-*` audits.

Healthy value-result batches now hold up to 64 source modules. A controlled
comparison of all 2,946 native/web value checks, using two workers on two fixed
CPUs, reduced compiler launches from 186 to 48. The 16/64/64/16 comparison gave
about 21.5 versus 13.9 pytest seconds, with aggregate child CPU time falling from
34.88 to 23.06 seconds. Individual IDs, selection and failure isolation remain.
All 4,735 checks passed in the full gate in 141.38 seconds under different host
conditions; this is a value-suite improvement, not a paired full-gate speed claim.
See `value-batch-size-*` audits.
