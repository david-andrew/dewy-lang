# Cleanparse implementation status

This document tracks language features in the cleanparse compiler. Checked items are supported through parsing, semantic analysis, udewy lowering, and emission.

## Core declarations and expressions

- [x] `let` and `const` declarations, assignment, and combined assignment. Plain `name = value` implicitly declares a `let` binding when no visible binding exists; otherwise it remains reassignment.
- [x] Unannotated `let` bindings initialized from integer literals widen the binding to abstract `int` rather than retaining a singleton integer type.
- [x] Lexical binding identities, nested scopes, and shadowing.
- [x] Boolean, fixed-width integer, `void`, `never`, and exact integer-literal types within the supported operations described below.
- [x] Contextual integer-literal typing for declarations, calls, returns, and operators. A literal can inhabit any fixed-width integer type that contains its value; out-of-range literals are rejected.
- [x] Type-directed operator resolution, including distinct signed and unsigned right-shift lowering.
- [x] `transmute` for values whose source and destination representations are supported by the udewy backend, including function pointers.
- [x] A juxtaposed semicolon (`expression;`) evaluates the expression while suppressing its value, including for function return inference and udewy lowering.
- [ ] An unattached semicolon is reserved for selecting the next array dimension, analogous to MATLAB; that array syntax is not implemented yet.

## Type expressions and type-valued inference

- [x] Explicit compile-time aliases using `let T:type = ...` or `const T:type = ...`, including a single type expression grouped as `<...>` in that expected type position.
- [x] Contextual value typing from annotations, function parameters and returns, and supported container element or field types.
- [x] Standalone non-juxtaposed `<...>` expressions producing compile-time values of type `type`.
- [x] Inferring `let T = <...>` as a compile-time type alias without requiring the explicit `:type` annotation.
- [ ] Runtime type values, reflection, and general compile-time evaluation of type expressions.

## Generics

The type system instantiates generic function types for built-in operator overloads, such as `<T of int>(left:T right:T):>T`. Source-defined bounded generic type aliases are also available as compile-time type constructors. User-written generic functions and explicit type arguments at function call sites are not implemented. Non-juxtaposed `<...>` as a type-valued group is tracked under Type expressions above; here `<T>` is a type-parameter list.

- [x] Internal generic parameters, call-site inference, and instantiation used by built-in operator overloads.
- [x] Parameterized built-in types in annotations, including `array<T>` and `array<T length=N>`.
- [x] Named generic type aliases such as `const Duration:type = <T of real>(T * Time)`, including explicit alias application with `Duration<uint64>`.
- [x] Source-level alias bounds such as `T of real`, with arity and bound diagnostics and substitution through the resulting type expression.
- [ ] User-written generic functions such as `identity = <T>(value:T):>T => value`.
- [ ] Explicit type arguments at generic function call sites.
- [ ] User-defined parameterized types and generic object types.
- [ ] Monomorphization or other udewy lowering for user generic values.

## Structured control flow

- [x] Boolean `if`/`else if`/`else`, including scalar expression-valued conditionals.
- [x] `loop`, `break`, and `continue`.
- [x] Labeled loop exits using scope metatags. Labels have scope-wide visibility; duplicate declarations and shadowing an active label are errors.
- [x] Boolean short-circuiting for the operator syntax of `and`, `or`, `nand`, and `nor`, including their symbolic spellings. Explicit dunder calls remain ordinary eager calls.
- [x] Return-coverage checking through exhaustive conditional flow.

## Basic callable use

- [x] Direct calls, forward references from function bodies, recursion, and mutual recursion.
- [x] Structural function types with named or unnamed parameter contracts.
- [x] Function values, parameters, returns, indirect calls, and pipe calls.
- [x] Non-capturing local functions, which are hoisted with readable, scope-qualified names.

## Compilation-unit execution

- [x] Top-level executable statements run in source order.
- [x] A zero-argument `main`, when present, runs after top-level execution and must return an integer exit code or `void`.
- [x] Programs without `main` receive an empty generated entry point.
- [x] Global initialization is lowered through private startup storage while preserving source-order execution.
- [ ] Optional `main` argument `argv:array<string>`.
- [ ] Optional `main` environment argument. The environment structure is still TBD.

## Udewy intrinsics and host interoperability

- [x] Typed source access to udewy's portable memory, allocation, signed-shift, and unsigned-operation intrinsics.
- [x] Direct Dewy access to every fixed-arity intrinsic advertised by a udewy backend, including static word data, floating-point bit conversions, and the wasm host APIs. Availability when compiling remains target-dependent.
- [x] Typed access to Linux `__syscall0__` through `__syscall6__`, emitted as direct udewy intrinsic calls.
- [x] Executable x86-64 Linux bare-metal hello world using a UTF-8 byte view, its byte length, and the `write` syscall.
- [x] Linux x86_64 `print`/`printl` in the prelude (`library/io.dewy`) via `write`, including overloaded string and signed-integer output needed by streamed interpolation. Other targets still need host-write capability selection.
- [x] Linux x86_64 `sleep(Duration<uint64>)` in the system prelude, lowered through `nanosleep` with a nanosecond integer representation.
- [ ] Target-specific non-Linux host intrinsics and capability selection.
- [ ] Foreign symbols, external linkage, and a stable FFI surface.

## Initialization and callable-effect analysis

- [x] Eager top-level and local expressions cannot use values before initialization.
- [x] Function bodies may refer to later declarations, with required initialization checked at each call site.
- [x] Initialization requirements propagate through direct calls, callbacks, callable alternatives, and statically reachable control flow.
- [ ] Reassigned callable values do not yet have resolved callable effects.
- [ ] Capturing local functions are analyzed but cannot yet be lowered as closures.

## Function overloads

- [x] Static overload composition with `&`, nested overload sets, and type-directed call selection.
- [x] Inline overloads lower to readable signature-based symbols with an ordinal when signatures collide.
- [ ] Runtime multifunction values cannot yet be represented or lowered.

## Function signatures and calls

- [x] Positional parameters and arguments, named parameter contracts in structural function types, and pipe calls.
- [x] Explicit position-only parameters written as `<name:type>`. The name remains available inside the body but is absent from the keyword-call interface; required and defaulted forms use the ordinary positional/default rules.
- [x] Positional-or-named parameters may have per-call defaults; explicit post-`...` parameters are keyword-only and participate in semantic checking and initialization analysis.
- [x] Positional or named arguments and per-call defaults lower through a positional udewy ABI for direct, piped, overload-selected, indirect, and method calls.
- [ ] Rest parameters, argument spreading, and partial application do not yet lower to udewy calls.
- [ ] Vectorized function calls. `.` with a non-identifier right-hand side (`f.(xs)`, `putchar."text"`, `f.[1 2 3]`) applies the left-hand callable to each element of the right-hand side, equivalent to `[loop xi in rhs f(xi)]`. A bare identifier on the right remains member access (`obj.field`), so a sequence in a variable is written `f.(xs)`, not `f.xs`. The parser already produces `BinOp(.)` for these forms; only `.` glued to a following operator becomes `BroadcastOp` (`.*`, `.|>`). Semantic analysis currently rejects non-identifier RHS as unimplemented computed member access. No parser change.

## Integer representations and operations

- [x] Exact integer-literal types and contextual selection of all signed and unsigned widths from 8 through 64 bits.
- [x] udewy lowering for the fixed-width scalar operations exercised by the executable fixture suite.
- [x] Width-correct rollover lowering for narrow add, subtract, multiply, floor-divide, modulo, unary negation/inversion, and bitwise operations.
- [x] Unsigned floor division, modulo, and ordered comparisons lower through portable udewy intrinsics.
- [x] Width-correct fixed-width shifts with unsigned counts and one-time operand evaluation. Negative counts are rejected at compile time; counts at or beyond the width continue shifting in zero bits, or sign bits for signed right shifts, rather than inheriting the target CPU's masked-count behavior.
- [ ] Abstract `int` has arbitrary-precision semantics but no bigint runtime representation in the udewy backend.

## Compile-time numeric range analysis

Unannotated integers behave as arbitrary precision. Explicit fixed-width annotations rollover as that width. Range analysis is the pass that proves whether a particular `int`, iterator, or arithmetic intermediate can be represented with a concrete `intN` under the hood without changing those semantics.

- [x] Flow-sensitive integer intervals for bindings, used to prove array-index bounds from comparisons, arithmetic, loops, and range iterators.
- [x] A right-unbounded integer iterator can use a concrete `int64` counter when a finite companion and the multiiterator formula prove the loop stops, and the complete observed range fits.
- [ ] Selecting a hidden `intN` representation for values annotated or inferred as `int` when every reachable value fits that width.
- [ ] General proofs that a right-unbounded iterator such as `0..` never overflows a chosen fixed-width counter when termination is not established by a finite multiiterator companion.
- [ ] Using the same proofs to specialize other layouts, such as optional niches for narrow integers.

## Physical quantities and time

- [x] Compile-time `DimensionType` and `QuantityType` representations, with physical dimensions excluded from runtime layout.
- [x] Direct type products such as `int * Time`, resolved through the ordinary binary-expression syntax rather than a separate type grammar.
- [x] Representation-parameterized `Duration<T of real>`, including `int`, fixed-width integer, exact integer-literal, and floating-point type arguments at semantic-checking time.
- [x] Exact nanosecond, millisecond, and second unit constants. Their scale is folded into constant expressions, so `300ms` becomes the nanosecond value `300000000` without a runtime unit object.
- [x] Juxtaposition multiplication between numbers and physical quantities, preserving the numeric representation for nonconstant values.
- [x] `sleep(300ms)` typechecks against `Duration<uint64>`, rejects dimensionless input, and lowers to the Linux x86_64 system implementation.
- [x] The current hero program compiles and runs end to end, combining a bounded `0..` counter, grapheme iteration, streamed interpolation, and typed sleeping while producing the expected grapheme indexes.
- [ ] Physical base dimensions beyond `Time`, dimension division and powers, conversions between chosen canonical scales, and a complete units library.
- [ ] Runtime arithmetic for non-integer quantity representations, pending the corresponding floating-point, rational, and real-number backend support.
- [ ] Target-specific system preludes and portable sleep implementations outside Linux x86_64.

## Homogeneous arrays

- [x] Homogeneous literals of fixed-width scalar and handle elements.
- [x] Exact length refinements, `array<T length=N>`, and `.length`.
- [x] Width-correct local and global storage for all fixed-width integer types.
- [x] Constant and flow-proven dynamic indexing, indexed assignment, and const mutation checks.
- [x] Bounds facts from comparisons, arithmetic, loops, and range iterators.
- [x] `bool`, string/grapheme, function, nested-array, and object-handle element layouts.
- [x] Non-escaping function-local `let` and `const` bindings initialized by an exact-length array literal use only a fresh stack element buffer when every use is `.length`, an indexed read, or an indexed write.
- [x] Exact-length scalar/function array return values use caller-owned descriptor and element storage, including direct literals, returned locals, forwarding calls, and indirect or method calls with an exact return type.
- [x] Left-to-right iteration over arrays of settled scalar, function, and immutable string-like elements. Dynamic-length arrays work as single iterators, and exact-length arrays compose with other multiiterator leaves.
- [ ] Empty-array inference.
- [ ] Arrays whose exact runtime length is not known where indexing requires it.
- [ ] Returning arrays whose storage requirement is not known at the call site, arrays of handles that require nested ownership handling, and other escapes into longer-lived storage.

## Ranges and range iteration

- [x] Inclusive and explicitly open or closed bounds.
- [x] Static integer ranges, descending ranges, and stepped `first,second..last` ranges.
- [x] Right-unbounded range semantics and integer bounds in HIR.
- [x] Rejection of zero steps and iteration over ranges without a left anchor.
- [x] udewy lowering for finite ranges whose values and iteration arithmetic fit the supported `int64` representation.
- [x] Default one-grapheme character ranges, including descending and stepped forms, scalar-order iteration, and skipping the Unicode surrogate gap.
- [x] Explicit `range<uint32>` context for one-scalar string endpoints.
- [x] Exact and runtime `int64` membership in unstepped ranges with `in?`, plus runtime candidates against statically anchored stepped ranges. Runtime operands are evaluated once.
- [x] The contextual `end` index, direct bound-delimited string slices such as `text[3..12)`, and fixed-range slicing of exact-length array bindings.
- [x] Runtime-computed string-slice endpoints when flow-sensitive interval analysis proves every effective boundary remains in range, including open and closed bound adjustments.
- [ ] Runtime-computed stepped-range anchors and general runtime range iteration.
- [ ] Bigint lowering for right-unbounded or finite out-of-`int64` ranges.
- [ ] Using general range values beyond the currently supported iterator normalization.

## `undefined`, optional values, and type narrowing

- [x] `undefined` as a value distinct from `void`.
- [x] `T | undefined` for currently lowerable single-layout payloads.
- [x] Flow-sensitive narrowing with `is?`, `isnt?`, and supported short-circuit conditions; assignment invalidates affected refinements.
- [x] Optional locals, globals, assignment, parameters, returns, and direct, indirect, or overloaded calls.
- [x] A correct tag-and-payload udewy ABI with value semantics.
- [ ] General heterogeneous runtime unions such as `int64 | string | undefined`.
- [ ] Compact niche layouts and scalar-replaced optional calling conventions.

## Multiiterators

- [x] Arbitrarily many normalized iterator leaves combined by `and`, `or`, `xor`, `nand`, `nor`, or `xnor`, including symbolic spellings and grouped formulas.
- [x] Eager left-to-right iterator advancement.
- [x] Exhausted targets become `undefined`, with optional target types inferred from statically known iterator lengths and the complete logical formula.
- [x] Literal post-exhaustion truth-table behavior and labeled exits.
- [x] Grapheme iteration over strings.
- [x] Mixed range/string multiiteration, including pairing a right-unbounded counter with finite grapheme iteration as in `loop i in 0.. and c in text`.
- [x] Exact-length array leaves in multiiterator formulas.
- [ ] Dynamic-length array leaves and multiiterator sources other than normalized integer ranges, strings, and exact-length arrays.
- [ ] Conditions that mix iterator clauses with ordinary Boolean predicates.
- [ ] Iterator fusion and scalar replacement of the baseline per-leaf state.

## Objects

- [x] Anonymous object literals with named fields in source order.
- [x] Structural object types and named compile-time `type` aliases used in annotations.
- [x] Field read and write, nested objects, and exact name/type/order matching.
- [x] Object parameters, returns, and constructors (functions that return literals), with value-semantics copies.
- [x] Function fields, including parenthesis-free zero-argument calls on member access, and object-local reads or compound assignment of sibling fields.
- [x] Sequential udewy layout for `bool`, fixed-width integers, function pointers, string/array handles, and nested objects of those types.
- [ ] Dictionary and bidictionary `[]` forms.
- [ ] sets `set[1 2 3 4]`
- [ ] Extracting an object method as a naked function value.
- [ ] Packing, field reordering, dunder methods, and width subtyping.

## Strings

- [x] Power-of-two based strings (`0b`, `0q`, `0o`, `0x`, `0u`, and `0g`) have exact binary singleton types, contextual `array<uint8>` materialization, and udewy lowering. Digits contribute fixed-width `log2(base)` chunks in source order; the final byte is right-zero padded. Base-64 `_` is digit 63 and trailing `=` contributes no bits. Lowering emits canonical packed `0x"..."` data without target-endian or text reinterpretation.
- [ ] Non-power-of-two based strings (`0t`, `0s`, `0d`, `0z`, and `0r`) are reserved for future dense packing. For an `n`-digit base-`b` sequence, fold the digits by rank accumulation (`rank = rank * b + digit`), encode that rank in the sequence-derived width `ceil(log2(b**n))`, then right-zero pad the final storage byte. This width is not generally additive across concatenated subsequences, so compositionality and chunk boundaries remain unresolved. Balanced ternary also needs a defined ordering/rank for its negative digit before it can share this scheme.
- [x] Exact string-literal types with contextual materialization as immutable grapheme strings, `array<uint8>`, `array<uint32>`, or `array<grapheme>`. `char` is the one-grapheme string refinement.
- [x] Unicode 16.0.0 UAX #29 extended-grapheme segmentation from checked-in generated property tables, including combining marks, Hangul, emoji ZWJ sequences, regional indicators, modifiers, and Indic conjuncts.
- [x] One-word udewy string descriptors over immutable UTF-8 plus byte-offset grapheme boundaries. Literals, calls, returns, globals, objects, optionals, and handle-element arrays use the descriptor ABI.
- [x] Grapheme `.length`, indexing, static and flow-proven dynamic slicing with all bound forms, iteration, exact byte equality, and supported character ranges.
- [x] `string as array<uint8>` borrowing with copy-on-write mutation, materialized `array<uint32>` scalar views, string-to-grapheme arrays, and grapheme-array-to-string conversion with UAX #29 re-segmentation.
- [x] `as` performs representation-changing conversions; `transmute` remains bit-preserving and rejects string/array layout reinterpretation.
- [x] Runtime re-segmentation uses current grapheme-array values, including mutations that cause adjacent clusters to merge.
- [x] Interpolated strings preserve alternating literal chunks and typechecked expression fields in HIR.
- [x] `print`/`printl` specialize interpolated strings into streamed writes, avoiding a materialized interpolation container; this includes integer and grapheme fields used by the hero program.
- [ ] Materializing an interpolated string as a first-class runtime string value. Only the streamed `print`/`printl` consumer is currently lowered.
- [ ] A general conversion protocol such as overloadable `__as__`/`__string__` for formatting arbitrary interpolation fields.
- [ ] `array<uint8>` or `array<uint32>` to string. These conversions require future refinement proofs for valid UTF-8 or Unicode scalar contents.
- [ ] Normalization APIs and normalization-aware comparisons. String equality currently preserves and compares the exact scalar spelling.

## Conditional values

- [x] Exhaustive conditionals can produce one scalar value and lower through a typed temporary.
- [x] Non-exhaustive conditionals are statement-valued `void`.
- [ ] Multi-value conditional results.

## Array, object, and other compile-time versus runtime representations

The source-level type of a value describes its semantics, not a mandatory machine layout. Lowering should retain only information that can affect the program at runtime. Facts already established by typing, refinement, control-flow, or effect analysis should normally become constants in the emitted program rather than fields stored beside every value.

The current backend still uses a canonical pointer to a 48-byte descriptor containing `data`, `length`, `capacity`, `stride`, `flags`, and `owner` for most arrays. Two proven cases omit it:

- Module-scope `const` arrays whose binding-identity use set contains only `.length`, indexed reads, and proven-safe direct-call boundaries can use raw static storage. Compatible one-word literals and function references use udewy's internal `__static_words__`, while exact based bytes use their static data pointer.
- A function-local `let` or `const` binding initialized directly by an exact-length `ArrayLiteral` uses a fresh `__alloca__` element buffer when all uses are `.length`, indexed reads or writes, simple same-function aliases, or proven-safe direct-call boundaries. Transitive aliases copy the raw pointer, so reads and writes share the same storage. Length is folded from the exact type, element stride is compiled into address arithmetic, and width-correct loads and stores address the buffer directly. Semantic checking still rejects indexed writes through a `const` binding.

For a statically resolved direct or selected-overload call, a parameter whose alias closure only observes length or indexed reads/writes is adapter-safe. Lowering wraps raw local/static data in a temporary canonical descriptor in the call prelude without copying elements; the callee ABI and indexing remain descriptor-based. Read-only exact static bytes use borrowed-static flags.

Exact-length scalar/function array returns use a hidden destination supplied by the caller. The caller allocates the descriptor and element buffer in its own frame, and the callee initializes or copies into that storage before returning; a directly returned call forwards the same destination through wrapper functions. No callee-local array storage escapes. Handle elements remain rejected until their nested backing storage can receive the same ownership treatment. Whole-array assignment, object storage, other escapes, casts, parameter forwarding, nonliteral/control-flow initializers, aliases outside one function, and unclassified uses conservatively retain the descriptor. Static-byte mutation retains the descriptor and copy-on-write path. Control-flow representation joins, general or transitive effect analysis, indirect/method adapters, and descriptor-free specialized direct-call ABIs remain pending. At present arrays cannot change length; `capacity`, `stride`, and `owner` are not read by generated programs.

The intended rule is that each value receives the least runtime representation needed by all of its reachable uses. For arrays this includes:

- An immutable literal used directly by another operation can lower to static element data, or directly to an udewy literal operand, with no descriptor.
- A fixed-length mutable local array needs writable element storage, but does not inherently need metadata beside that storage.
- A view whose length is known only at runtime may need `(data, length)`.
- A borrowed byte view that may be mutated needs enough dynamic state to distinguish borrowed from owned storage and perform copy-on-write. If analysis proves that it is never mutated, that state is unnecessary.
- A future growable array may need `(data, length, capacity)`. Capacity should not exist merely in anticipation of operations that the value never performs.
- Element stride follows from `array<T>` and should be compiled into address arithmetic. A runtime stride is justified only by genuine type erasure, such as an existential container or an FFI contract whose element layout is not statically available. Merely placing differently typed arrays in different fields of one object does not erase their element types.
- Ownership or lifetime metadata is needed only when the selected memory management strategy must inspect it dynamically. It need not be a field on every array merely because some arrays borrow storage.

This produces a spectrum rather than a second universal layout: no runtime value, raw data only, a scalar tuple such as `(data, length)`, or a full descriptor. Known `.length` operations and element widths are substituted directly at their uses. A descriptor is materialized only at a boundary that actually requires the canonical handle representation.

The same principle applies beyond arrays:

- Object fields can remain independent scalar values, and unused fields can be absent, while an object that escapes or crosses a canonical ABI boundary may require materialization into memory. Scalar replacement must preserve the language's object value and mutation semantics.
- Exact string literals should remain semantic singletons until context selects UTF-8 bytes, Unicode scalars, graphemes, or a runtime string. UTF-8 data, grapheme boundaries, byte length, and grapheme length should be materialized only when the selected operations require them.
- Optional and union tags can disappear after exhaustive narrowing, or be encoded in an unused payload value when a valid niche is proven. A general tag-and-payload representation remains the fallback.
- Ranges and iterators whose bounds and state transitions are known can lower directly to loop scalars instead of heap- or stack-resident iterator records.
- Function values need only a code pointer when no environment is captured; closures require an environment only when captures survive lowering.

Representation selection must happen after semantic typing. Two values with the same Dewy type may therefore use different machine representations without that difference becoming observable in Dewy. The compiler must insert an adapter or materialize the canonical form when differently represented values meet at control-flow joins, indirect calls, separately compiled interfaces, FFI boundaries, or unspecialized function parameters. Direct calls may instead be specialized so that compile-time facts continue across the boundary.

Choosing a smaller representation requires proofs about every relevant use:

- use analysis determines which metadata and operations are observed;
- escape and lifetime analysis determines whether storage or descriptors must survive the current scope;
- mutation, effect, and alias analysis determines whether facts remain true across assignments and calls, and whether borrowed storage needs copy-on-write;
- control-flow analysis selects a representation valid for every path and identifies where values with different representations merge;
- ABI analysis determines where a stable canonical layout is externally observable or needed for indirect access.

When a proof is unavailable, lowering should use the canonical representation rather than changing semantics or inserting speculative behavior. This makes the full descriptor a correctness fallback, not the default cost paid by every value.

Incremental implementation work:

- [x] Record an initial representation requirement per semantic binding for module `const` arrays, selecting raw storage only when every reachable use is `.length`, an indexed read, or a proven-safe direct-call boundary.
- [x] Emit eligible module `const` arrays of stable 64-bit words, compatible non-extern function references, or exact based bytes as raw static data with compile-time length and stride.
- [x] Scalar-replace eligible non-escaping exact local array literals with a fresh raw stack-data buffer, direct width-aware indexed reads and writes, and compile-time `.length`.
- [x] Propagate raw stack data through simple same-function alias chains and materialize canonical descriptors without copying for proven-safe direct and selected-overload call boundaries.
- [x] Return exact-length scalar/function arrays through caller-owned result storage, copying direct literals or existing arrays and forwarding destinations through wrapper calls without exposing callee-local allocations.
- [ ] Generalize representation requirements across control-flow joins, general/transitive effects, cross-function aliases, indirect or method calls, and additional element/storage classes.
- [ ] Elide array length, capacity, stride, flags, and ownership metadata for additional runtime array representations when each fact is unused or available statically.
- [ ] Add indirect/method boundary adapters and descriptor-free direct-call ABI specialization where profitable.
- [ ] Extend the same analysis to objects, strings, optionals/unions, iterators, and closures.
- [ ] Remove or redesign canonical descriptor fields that remain unused once dynamic arrays and lifetime management have defined semantics.

## Paths, imports, and modules

- [x] An ordered source prelude is checked and merged once, with shadowable fallback bindings injected independently into each module.
- [x] `Path` and the literal-preserving `p` constructor are ordinary Dewy definitions in `library/path.dewy`; imports accept any exact structural `[path:string]` value rather than requiring the standard alias.
- [x] `print` and `printl` are ordinary Dewy definitions in `library/io.dewy`. Linux x86_64 only (`write` is syscall 1). Unused prelude bindings are omitted from the merged program.
- [x] Physical time definitions and Linux system facilities are separate implicit prelude modules (`library/units.dewy` and `library/system-linux.dewy`), are included by the installer, and remain removable when unused.
- [x] `$no_prelude = true` disables prelude bindings only for its containing module. Prelude and prelude-free modules can coexist in one import graph.
- [x] File-relative semantic imports support selective names, aliases, parenthesized or comma-separated name collections, reversed `import ... from ...` order, compile-time namespaces, and whole-module splats.
- [x] Reachable source modules, independent of filename extension, are checked with one type system and binding registry, reject cycles and collisions, initialize once in dependency order, receive module-qualified target symbols, and merge into one udewy executable.
- [ ] ~~Installed package lookup, directory/glob imports, explicit export control,~~ non-source artifact loading, ~~and incremental per-module artifacts.~~

- [ ] Add a strict project-wide freestanding policy, likely selected by a freestanding target and potentially by a separate project-wide `$` metatag. Unlike file-local `$no_prelude`, it should prohibit preludes throughout the graph without per-module overrides.

## Completely unimplemented

In no particular order

- [ ] Floating-point, rational, and real numbers
- [ ] Dictionaries, bidirectional maps, and sets
- [ ] Pattern matching (`match`)
- [ ] Partial application (`@`)
- [ ] expression returning assignment (`:=`) (i.e. python walrus operator) and compile-time assignment (`::`)
- [ ] General juxtaposition multiplication and broadcasting beyond the implemented number/physical-quantity case. Vectorized calls (`f.(xs)`) are a `BinOp(.)` interpretation, not operator broadcasting; see Function signatures and calls.
- [ ] Math
  - [ ] Linear algebra, multidimensional array syntax, etc.
  - [ ] Geometric algebra
  - [ ] math standard lib
  - [ ] complex and quaternion math
- [ ] Generators (`yield`)
- [ ] Unpack and collect
- [ ] Effects and error values
- [ ] Compile-time evaluation and meta-programming
  - [ ] metatags for things historically passed as compiler flags
- [ ] bootstrap compiler implementation in dewy
- [ ] full end to end self-hosted compiler via dewy->udewy frontend, udewy->asm backend
- [ ] standard library
  - [ ] OS agnostic interfaces on top of OS-dependent implementations per supported OS/environment
- [ ] LSP for syntax highlighting, type narrowed lookup, struct member listing, etc
- [ ] implementation of hello world examples from the different domains
- [ ] test harness system.
  - [ ] self hosted unit tests with automation for running on all updates
- [ ] basic optimizations
  - [ ] use-dependent lowering and scalar replacement as described in "Array, object, and other compile-time versus runtime representations" above

### Liquid Refinement System

Dewy does not have a fully arbitrary refinement type system. Refinements are restricted to a well-behaved liquid proposition language that the compiler can normally infer and prove automatically. General Dewy expressions do not become valid refinement predicates merely because they produce a Boolean.

The intended proof boundaries are:

- an automatically proven refinement has no runtime cost
- an explicit runtime check refines the value on every path where the check succeeded, including after an early exit that discarded the failing case (`if not condition then return`, and similar)
- a checked proof or lemma may discharge an obligation the automatic liquid solver could not establish on its own
- an explicit `unsafe` claim may assume an obligation without a runtime check or checked proof; it is a real safety boundary and remains an audit obligation

A claim accompanied by a compiler-checked proof is no longer unsafe. Commentary, an unchecked certificate, or an omitted proof does not discharge the unsafe obligation. The proof language may eventually be richer than the automatic solver, but facts imported back into ordinary refinement checking must have a conclusion the liquid proposition language can represent.

The initial liquid proposition language should focus on the facts most useful to ordinary Dewy programs: Boolean combinations, equality and ordering, linear integer arithmetic, literal and type/tag tests, lengths and other trusted pure measures, and simple relationships between parameters and results. Arbitrary function calls, unrestricted quantification, effectful expressions, and general nonlinear arithmetic are outside the automatic refinement language. The exact fragment and qualifier-inference strategy remain to be specified.

> NOTE: this doesn't preclude calling functions in refinements. Suitably pure functions can be used. E.g. if the contents of a function call and any subsequent internal calls were inlined and that inlining would be a valid refinement, then that function ought to be valid.

Refinement propositions should have their own semantic representation rather than reusing unrestricted HIR expressions. Reasoning about semantic arbitrary- precision `int` must also remain distinct from reasoning about fixed-width rollover arithmetic: the latter requires bit-vector-aware rules or a separate (automated or user-provided) proof that overflow cannot occur.

Within those constraints, the refinement system shall work as follows:

- any type may receive a parameterize block (e.g. `T<p1 p2 etc...>`), including types that don't take any explicit parameters
- supported liquid propositions in the parameterize block are the refinement conditions for that type. The compiler attempts to prove them statically from inferred facts, control flow, and declared contracts

```dewy
NonEmptyArray = array<length>?0>  # retains the generic T from array, e.g. can do NonEmptyArray<int> because we didn't fill in the type

MyStruct:type = [a:int b:bool c:string]< a>?10 b=?true c not=? 'apple' >
```

- additionally assignment expressions in the conditional block can be used to directly indicate some field will always have that value. This is mostly just a convenience for a common case, e.g.

```dewy
SingleValuedArray = array<length=1>  # identical to array<length=?1>
```

- entries in the parameterize block are distinguished syntactically: an expression whose top level is a `?`-comparison (`>?`, `=?`, `not=?`, etc.), or a lambda, or an assignment is a refinement condition; every other expression is a parameter value. The expression selected as a refinement condition must still belong to the supported liquid proposition language. So a literal boolean is unambiguously a parameter, and no wrapping/escaping syntax is needed:

```dewy
trues:array<true length=5> = [true true true true true]  # element type is literal-type true, length refined to 5
```

In the rare case where a precomputed boolean should act as a condition, spell it explicitly: `cond =? true`, or use a lambda. A refinement condition that statically reduces to a constant (always true / always false) is a compile error, since it is either vacuous or unsatisfiable and almost certainly a mistake.

- inside the parameterize block, if the type is a structural type, all members on that struct are in scope to reference for conditions. Members shadow outer bindings; outer scope is otherwise visible (needed for e.g. `length =? n` against an enclosing generic parameter)
- inside the parameterize block of nominal types, there is no `self`, so you have to use a lambda to access the value

```dewy
Positive = int< i=>i>?0 >  # to refer to primitive types, use a single-argument lambda
Positive:type = [i:int]< i>?0 > # similar-ish outcome without needing the lambda
```

Note that `[i:int]< i>?0 >` is _not_ an alternate spelling of the same type: it is a structural wrapper type containing an int, which is a different type from a refined `int` (see structural splicing below for how such a wrapper could be made usable as an int).

- parameterizing a type returns another type, so parameterization may be stacked; each application only narrows (predicate intersection), so the semantics are well defined and stacking is allowed uniformly, whether through intermediate identifiers or directly (`MyStruct<c1><c2>`). Direct stacking is unidiomatic and may warrant a style lint, but not an error

```dewy
T1 = MyStruct<condition1>
T2 = T1<condition2>  # T2 requires both conditions
```

Mainly useful for e.g. letting you return a type and some consumer can further refine it if they need. In general, from an implementation point of view, applying a parameterization is much like doing a partial application on the type object: you're setting particular members, registering refinements, etc.

- refinement checking has three meaningful outcomes: proven, refuted, and unknown. Unknown is not the same as false and should not be reported as such
- when the checker cannot prove a required refinement at a use site, the programmer may: add an explicit runtime check whose success refines the value afterward, provide a compiler-checked proof or lemma, strengthen the surrounding contract, or make an explicit `unsafe` claim that takes on the proof obligation without a runtime check
- unsafe claims should be lexically explicit, scoped as locally as practical, and visible to diagnostics and tooling. If used to eliminate bounds checks, select a narrower representation, or justify other partial operations, violating the claim may produce undefined behavior
- proof-failure diagnostics should report the known facts, the required fact, and the missing relationship, and should distinguish a refuted obligation from one that is merely outside the solver's knowledge or supported fragment

### Structural splicing into the nominal type tree

Structural types may be spliced into the nominal type tree by intersecting with a nominal type. The intended idiom: the spliced type _semantically is_ the nominal type, but with a different runtime representation (and/or extra metadata):

```dewy
Posit64:type = float64 & [sign:bit regime:array<bits> exponent:array<bits> fraction:array<bits>]< regime.length + exponent.length + fraction.length =? 63 >
__as__ &= (x:Posit64):>float64 => { some algorithm to convert posits to floats }
```

Rules and semantics:

- intersecting a structural type with a nominal type requires a corresponding `__as__` overload converting to the nominal type. The absence is checked lazily at use sites (definitions may appear after the type, in any order at module level), and it is a type error to actually need the conversion when none is defined
- `x is? float64` is true for a `Posit64` instance; the spliced type genuinely is a descendant of the nominal type
- the nominal type tree itself is single inheritance, but structural (including spliced) types may have multiple parents, including multiple nominal parents (`MyType = int & float64 & [...]`), with one `__as__` overload per nominal parent
- nominal types are immutable / have no internal fields to mutate, so coercion never creates mutation-aliasing concerns; `__as__` produces a fresh value with ordinary value semantics
- `as`/`__as__` in general must be invoked explicitly; the sole implicit case is a spliced type flowing to a context requiring one of its nominal ancestors
- coercion happens at _canonical-representation boundaries_, not call boundaries. A generic bound like `<T of float64>(left:T right:T)` binds `T = Posit64` directly with no conversion; `__as__` is inserted only where the canonical machine representation is actually required (e.g. inside a builtin body), per the representation-selection rules described earlier in this document. Consequently, overload resolution prefers a representation-preserving match over one requiring `__as__`, so defining posit-native operations opts out of coercion per-operation
- conversion path resolution: an explicitly defined direct `__as__` always takes precedence over a composed path. Composed paths (chaining `__as__` up the ancestry, e.g. `Tracked -> Posit64 -> float64` for `Tracked = Posit64 & [...]`) are allowed when unambiguous. With multiple nominal parents, diamonds are possible (`X = int & float64 & [...]` at a boundary expecting a common ancestor); if multiple composed paths exist at a use site, that is a type error, resolved by defining a direct conversion. The error surfaces only at ambiguous _use_ sites — the mere existence of multiple paths is fine (opt-in lint at most) — and the diagnostic must name the competing paths and the definition sites of the `__as__` overloads involved
- a pure nominal descendant with no structural body is spelled as an ordinary expression: `UserId = type of int`

### Generativity of type expressions

- `type of T` and `T & [...]` (where `T` is nominal) are generative: each _evaluation_ mints a distinct nominal type. Type expressions are ordinary expressions and function bodies re-evaluate on every call, so a factory function containing a generative type expression returns a fresh type per call
- intersections of purely structural types are _not_ generative: structural type equality is duck typing, so two evaluations of the same structural intersection produce equal types. Generativity only enters when a nominal type is being minted. If you want a combined structural type with unique (generative) identity, splice in an anonymous nominal type: `MyUniqueStructType = type of any & [...]`
- applicative behavior (one stable type reused everywhere) is achieved with existing mechanisms: bind the result once and refer to the binding (possibly closing over it), or explicitly cache results (note: a userland memoizing type factory requires mutable state that persists across compile-time evaluations)

```dewy
Tagged = (T:type) => T & [tag:string]
TaggedInt = Tagged(int)   # bind once; every use of TaggedInt is the same type
a: TaggedInt = [...]
b: TaggedInt = [...]      # compatible with a. Writing `a: Tagged(int)` and `b: Tagged(int)` would mint two distinct types
```

- generics do not change this: genericizing an expression is sugar for making it a function taking a type parameter, so `Tagged = <T>() => T & [tag:string]` invoked as `Tagged<int>()` re-evaluates the body and mints a fresh type per instantiation, same as any other call. Generic instantiation is deliberately _not_ memoized — that would introduce a second evaluation rule for what is definitionally just a function call. (Note this only matters when the body mints a nominal type; a generic producing a purely structural result is stable across instantiations for free, per duck typing)
- type annotations (on parameters, returns, bindings) are conceptually evaluated once, at typechecking time — checking happens once even if the function is called many times. Default values, by contrast, are re-evaluated on every call (so `(a:array = []) => ...` gets a fresh array per call, avoiding the shared mutable-default trap). A generative type expression in default-value position therefore mints a fresh type per call, consistent with both rules
- builtin parameterization like `array<int>` falls on the non-generative side: `array` is a builtin structural type, and parameterizing an existing type is partial application on the type object (narrowing), not minting a descendant. The dividing line: parameterization narrows, `type of` / nominal-splicing mints

### Array type literal syntax (`T[]`)

TypeScript-style postfix `[]` is sugar for the builtin `array` type (which is the canonical representation; it is a structural type with a `length` field):

```dewy
int[]          # array<int>
int[5]         # array<int length=?5>
int[3 4]       # array<int length=?[3 4]>   multidimensional shape
int[][]        # array<array<int>>          left-associative
(bool|string)[]  # array<bool|string>
bool|string[]    # bool | array<string>     postfix [] binds much tighter than |
```

- since Dewy has no separate type-level grammar (types are ordinary expressions), this parses in the value grammar as juxtaposition of a value with an array literal — the same surface form as indexing. Juxtaposition resolves to different operations based on operand types (like `a(b)` resolving to `__mul__` vs `__call__`), so a type juxtaposed with an array literal resolves to array-type construction. Indexing a type object is otherwise meaningless, so nothing legitimate is displaced
- precedence is that of index juxtapose (high, same tier as call/index, possibly tied with type-param juxtapose)

> NOTE: these are implementation notes/tasks under the liquid refinement design above.

- [ ] Define the liquid proposition grammar, trusted pure measures, and finite qualifier vocabulary used for inference. Unsupported general Dewy expressions must not silently enter refinement checking.
- [ ] Flow-sensitive refinement typing. Track value facts through ordinary control flow: x != 0, 0 <= i < a.length, literal values, unions/intersections, exclusions like T & ~0, etc.
- [ ] Refinement-aware function contracts. Let parameter and return types express predicates and relationships between values, including overloads selected by refinements.
- [ ] Static proof before implicit partial operations. Operations like indexing, division, narrowing casts, invalid shifts, etc. compile normally only when the compiler can prove their preconditions.
- [ ] Explicit runtime validation boundary. Runtime checks should appear only when the programmer writes an explicit check or checked operation; successful checks refine the value afterward.
- [ ] Explicit unsafe escape hatch. Permit the programmer to assert an unproven invariant without a runtime check, with unsafe marking the proof obligation clearly.
- [ ] Optional checked-proof boundary. Allow a proof or lemma to discharge an obligation the automatic liquid solver reports as unknown. Checked proofs erase the corresponding unsafe obligation; unchecked evidence does not.
- [ ] Symbolic state tracking across mutation. Model operations such as push, pop, truncate, mutation, and function calls as state transitions, then propagate or invalidate refinements precisely.
- [ ] Effect and alias tracking. Know what functions can mutate, allocate, block, access shared state, change collection length, etc., so existing proofs survive calls whenever justified.
- [ ] Automatic arithmetic/range reasoning within the liquid fragment. Use a solver capable of proving common equalities, inequalities, ranges, and simple relationships without programmer-written proof terms; solver failure or an unsupported proposition produces unknown rather than false.
- [ ] Inference-first ergonomics. Ordinary imperative code should usually verify without annotations; explicit contracts/invariants should be needed mainly at abstraction boundaries and complex loops.
- [ ] Semantic types separated from machine representation. Let types such as arbitrary-precision integers describe semantics, while range analysis chooses i8/i32/i64/... representations when provably equivalent.
- [ ] Information-preserving casts by default. Normal casts must preserve value/precision; potentially lossy or fallible conversions should be explicit and typed accordingly.
- [ ] Typed failure instead of hidden traps. Allocation failure and other genuinely dynamic failures should appear as result/error values or explicit effects rather than invisible exceptional paths.
- [ ] Verifier-friendly standard library. Give core operations precise contracts—for example map preserves length, pop decrements it by one, slice has a known resulting length—so proofs compose automatically.
- [ ] Useful proof diagnostics. When verification fails, report known facts, required fact, and the missing relationship, rather than exposing solver internals.
- [ ] Optimization driven by proofs. Reuse refinement information for bounds-check elimination, integer-width selection, dead-branch elimination, specialization, and other lowering decisions.
- [ ] Idiomatic code designed to be provable. Make the language’s normal APIs and control structures naturally expose the invariants the verifier needs, rather than treating verification as an add-on.

### Dewy compilation of UDewy programs

- [ ] TBD work for ensuing dewy compiler compiles well-formed udewy programs and they produce the same visible outcomes as if compiled directly with udewy

### Proper compilation target list/representation

- [ ] redo the list of targets for compilation targets and how they are handled. Note we are not recreating LLVM's target triples because plenty of those have redundant information or need an extra field. Instead the dewy/udewy list of targets will be more about each target name having only as many fields as it needs to describe itself. The following list is not set in stone, but merely an initial stab at what the targets list might look like:
  - ## target the current machine (current machine must be compatible)
  - 'x86_64',
  - 'riscv64',
  - 'aarch64',
  - 'c',

  - ## freestanding / baremetal
  - 'x86_64-freestanding',
  - 'riscv64-freestanding',
  - 'aarch64-freestanding',
  - 'c-freestanding',

  - ## linux
  - 'x86_64-linux',
  - 'riscv64-linux',
  - 'aarch64-linux',
  - 'c-linux',

  - ## mac
  - 'x86_64-mac',
  - 'aarch64-mac',

  - ## windows
  - 'x86_64-windows',
  - 'riscv64-windows',
  - 'aarch64-windows',
  - 'c-windows',
  - ## portable-ish
  - 'c-posix',
  - 'c89',
  - 'wasm32',

  - ## Others TBD

###

### Meta stuff

- [x] remove old src and replace with cleanparse (delete intermediate cleanparse folder)
- [ ] general repo cleanup/restructuring
- [ ] web compiler demos of language
- [ ] complete docs rewrite
  - [ ] API/language reference
  - [ ] dewy book
- [ ] making generated code more human friendly

### Aspirational/Experimental/etc.

- [ ] non text-editor view over code/AST. basically render AST to look like text, but render with user set visual settings for spacing, indentation, comment positions, etc. etc. Probably requires a custom editor-esque app. Should generally feel mostly like editing regular text in a text editor, just without the pure bag-of-characters semantics
- [ ] saving/editing packed ASTs instead of bag-of-characters raw text for source code. hashing sort of like unison, though tbd the exact semantics
- [ ] python FFI (dewy as host). Semi integrated into the type system in terms of python FFI stuff e.g.:

  ```dewy
  let x: PyObject = np.array(...)

  # many function calls into python might look like this
  (...args:array<PyObject>):> (PyObject | PythonError) & PythonEffect

  PythonCallable:type = [
    __call__ = (...args:array<PyObject>):> (PyObject | PythonError) & PythonEffect
  ]
  PythonIndexable = [
    __index__ = (key:PyObject):> (PyObject|PythonError) & PythonEffect
  ]
  PythonAccessable = [
    __access__ = (fieldname:string):> (PyObject|PythonError) & PythonEffect
  ]
  ```

  Probably it wouldn't quite look like this, and there would also be a dynamic process that would actually check if the python object supported whatever operation you were trying to do to it, or returning an error. And then usage within dewy would look pretty close to normal dewy code, just the type checking safety falls away
