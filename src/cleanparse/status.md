# Cleanparse implementation status

This document tracks language features in the cleanparse compiler. Checked items
are supported through parsing, semantic analysis, udewy lowering, and emission.

## Core declarations and expressions

- [x] `let` and `const` declarations, assignment, and combined assignment.
- [x] Lexical binding identities, nested scopes, and shadowing.
- [x] Boolean, fixed-width integer, `void`, `never`, and exact integer-literal
      types within the supported operations described below.
- [x] Contextual integer-literal typing for declarations, calls, returns, and
      operators. A literal can inhabit any fixed-width integer type that contains
      its value; out-of-range literals are rejected.
- [x] Type-directed operator resolution, including distinct signed and unsigned
      right-shift lowering.
- [x] `transmute` for values whose source and destination representations are
      supported by the udewy backend, including function pointers.

## Type expressions and type-valued inference

- [x] Explicit compile-time aliases using `let T:type = ...`, including a
      single type expression grouped as `<...>` in that expected type position.
- [x] Contextual value typing from annotations, function parameters and returns,
      and supported container element or field types.
- [ ] Standalone non-juxtaposed `<...>` expressions producing compile-time
      values of type `type`.
- [ ] Inferring `let T = <...>` as a compile-time type alias without requiring
      the explicit `:type` annotation.
- [ ] Runtime type values, reflection, and general compile-time evaluation of
      type expressions.

## Generics

The type system already instantiates generic function types for built-in
operator overloads, such as `<T of int>(left:T right:T):>T`. User-written
generic functions, type aliases, and explicit type arguments are not
implemented. Non-juxtaposed `<...>` as a type-valued group is tracked under
Type expressions above; here `<T>` is a type-parameter list.

- [x] Internal generic parameters, call-site inference, and instantiation used
      by built-in operator overloads.
- [x] Parameterized built-in types in annotations, including `array<T>` and
      `array<T length=N>`.
- [ ] User-written generic functions such as
      `identity = <T>(value:T):>T => value`.
- [ ] Generic bounds (`T of number`) in source, explicit type arguments at
      call sites, and named generic type aliases.
- [ ] User-defined parameterized types and generic object types.
- [ ] Monomorphization or other udewy lowering for user generic values.

## Structured control flow

- [x] Boolean `if`/`else if`/`else`, including scalar expression-valued
      conditionals.
- [x] `loop`, `break`, and `continue`.
- [x] Labeled loop exits using scope metatags. Labels have scope-wide visibility;
      duplicate declarations and shadowing an active label are errors.
- [x] Boolean short-circuiting for the operator syntax of `and`, `or`, `nand`, and
      `nor`, including their symbolic spellings. Explicit dunder calls remain
      ordinary eager calls.
- [x] Return-coverage checking through exhaustive conditional flow.

## Basic callable use

- [x] Direct calls, forward references from function bodies, recursion, and mutual
      recursion.
- [x] Structural function types with named or unnamed parameter contracts.
- [x] Function values, parameters, returns, indirect calls, and pipe calls.
- [x] Non-capturing local functions, which are hoisted with readable,
      scope-qualified names.

## Compilation-unit execution

- [x] Top-level executable statements run in source order.
- [x] A zero-argument `main`, when present, runs after top-level execution and must
      return an integer exit code or `void`.
- [x] Programs without `main` receive an empty generated entry point.
- [x] Global initialization is lowered through private startup storage while
      preserving source-order execution.
- [ ] Optional `main` argument `argv:array<string>`.
- [ ] Optional `main` environment argument. The environment structure is still TBD.

## Initialization and callable-effect analysis

- [x] Eager top-level and local expressions cannot use values before
      initialization.
- [x] Function bodies may refer to later declarations, with required
      initialization checked at each call site.
- [x] Initialization requirements propagate through direct calls, callbacks,
      callable alternatives, and statically reachable control flow.
- [ ] Reassigned callable values do not yet have resolved callable effects.
- [ ] Capturing local functions are analyzed but cannot yet be lowered as
      closures.

## Function overloads

- [x] Static overload composition with `&`, nested overload sets, and
      type-directed call selection.
- [x] Inline overloads lower to readable signature-based symbols with an ordinal
      when signatures collide.
- [ ] Runtime multifunction values cannot yet be represented or lowered.

## Function signatures and calls

- [x] Positional parameters and arguments, named parameter contracts in structural
      function types, and pipe calls.
- [x] Keyword-only parameters and defaults participate in semantic checking and
      initialization analysis.
- [ ] Keyword arguments and argument spreading do not yet lower to udewy calls.

## Integer representations and operations

- [x] Exact integer-literal types and contextual selection of all signed and
      unsigned widths from 8 through 64 bits.
- [x] udewy lowering for the fixed-width scalar operations exercised by the
      executable fixture suite.
- [ ] Abstract `int` has arbitrary-precision semantics but no bigint runtime
      representation in the udewy backend.
- [ ] Some fixed-width rollover and unsigned scalar operations still stop with
      focused backend diagnostics.

## Compile-time numeric range analysis

Unannotated integers behave as arbitrary precision. Explicit fixed-width
annotations rollover as that width. Range analysis is the pass that proves
whether a particular `int`, iterator, or arithmetic intermediate can be
represented with a concrete `intN` under the hood without changing those
semantics.

- [x] Flow-sensitive integer intervals for bindings, used to prove array-index
      bounds from comparisons, arithmetic, loops, and range iterators.
- [ ] Selecting a hidden `intN` representation for values annotated or inferred
      as `int` when every reachable value fits that width.
- [ ] Proving that a right-unbounded iterator such as `0..` never overflows a
      chosen fixed-width counter, including stepped arithmetic intermediates.
- [ ] Using the same proofs to specialize other layouts, such as optional
      niches for narrow integers.

## Homogeneous arrays

- [x] Homogeneous literals of fixed-width scalar and handle elements.
- [x] Exact length refinements, `array<T length=N>`, and `.length`.
- [x] Width-correct local and global storage for all fixed-width integer types.
- [x] Constant and flow-proven dynamic indexing, indexed assignment, and const
      mutation checks.
- [x] Bounds facts from comparisons, arithmetic, loops, and range iterators.
- [x] `bool`, string/grapheme, function, nested-array, and object-handle
      element layouts.
- [ ] Empty-array inference.
- [ ] Arrays whose exact runtime length is not known where indexing requires it.
- [ ] Returning arrays and allowing stack-allocated arrays to escape their
      defining function.

## Ranges and range iteration

- [x] Inclusive and explicitly open or closed bounds.
- [x] Static integer ranges, descending ranges, and stepped `first,second..last`
      ranges.
- [x] Right-unbounded range semantics and integer bounds in HIR.
- [x] Rejection of zero steps and iteration over ranges without a left anchor.
- [x] udewy lowering for finite ranges whose values and iteration arithmetic fit
      the supported `int64` representation.
- [x] Default one-grapheme character ranges, including descending and stepped
      forms, scalar-order iteration, and skipping the Unicode surrogate gap.
- [x] Explicit `range<uint32>` context for one-scalar string endpoints.
- [ ] Runtime-computed range anchors and steps.
- [ ] Bigint lowering for right-unbounded or finite out-of-`int64` ranges.
- [ ] Using general range values beyond the currently supported iterator
      normalization.

## `undefined`, optional values, and type narrowing

- [x] `undefined` as a value distinct from `void`.
- [x] `T | undefined` for currently lowerable single-layout payloads.
- [x] Flow-sensitive narrowing with `is?`, `isnt?`, and supported short-circuit
      conditions; assignment invalidates affected refinements.
- [x] Optional locals, globals, assignment, parameters, returns, and direct,
      indirect, or overloaded calls.
- [x] A correct tag-and-payload udewy ABI with value semantics.
- [ ] General heterogeneous runtime unions such as
      `int64 | string | undefined`.
- [ ] Compact niche layouts and scalar-replaced optional calling conventions.

## Multiiterators

- [x] Arbitrarily many static range iterators combined by `and`, `or`, `xor`,
      `nand`, `nor`, or `xnor`, including symbolic spellings and grouped formulas.
- [x] Eager left-to-right iterator advancement.
- [x] Exhausted targets become `undefined`, with optional target types inferred
      from statically known iterator lengths and the complete logical formula.
- [x] Literal post-exhaustion truth-table behavior and labeled exits.
- [x] Grapheme iteration over strings.
- [ ] Multiiterator sources other than normalized integer ranges.
- [ ] Conditions that mix iterator clauses with ordinary Boolean predicates.
- [ ] Iterator fusion and scalar replacement of the baseline per-leaf state.

## Objects

- [x] Anonymous object literals with named fields in source order.
- [x] Structural object types and named compile-time `type` aliases used in
      annotations.
- [x] Field read and write, nested objects, and exact name/type/order matching.
- [x] Object parameters, returns, and constructors (functions that return
      literals), with value-semantics copies.
- [x] Function fields, including parenthesis-free zero-argument calls on member
      access, and object-local reads of sibling fields.
- [x] Sequential udewy layout for `bool`, fixed-width integers, function
      pointers, string/array handles, and nested objects of those types.
- [ ] Dictionary and bidictionary `[]` forms.
- [ ] sets `set[1 2 3 4]`
- [ ] Extracting an object method as a naked function value.
- [ ] Packing, field reordering, dunder methods, and width subtyping.

## Strings

- [x] Exact string-literal types with contextual materialization as immutable
      grapheme strings, `array<uint8>`, `array<uint32>`, or
      `array<grapheme>`. `char` is the one-grapheme string refinement.
- [x] Unicode 16.0.0 UAX #29 extended-grapheme segmentation from checked-in
      generated property tables, including combining marks, Hangul, emoji ZWJ
      sequences, regional indicators, modifiers, and Indic conjuncts.
- [x] One-word udewy string descriptors over immutable UTF-8 plus byte-offset
      grapheme boundaries. Literals, calls, returns, globals, objects,
      optionals, and handle-element arrays use the descriptor ABI.
- [x] Grapheme `.length`, indexing, slicing with all bound forms, iteration,
      exact byte equality, and supported character ranges.
- [x] `string as array<uint8>` borrowing with copy-on-write mutation,
      materialized `array<uint32>` scalar views, string-to-grapheme arrays, and
      grapheme-array-to-string conversion with UAX #29 re-segmentation.
- [x] `as` performs representation-changing conversions; `transmute` remains
      bit-preserving and rejects string/array layout reinterpretation.
- [x] Runtime re-segmentation uses current grapheme-array values, including
      mutations that cause adjacent clusters to merge.
- [ ] `array<uint8>` or `array<uint32>` to string. These conversions require
      future refinement proofs for valid UTF-8 or Unicode scalar contents.
- [ ] Normalization APIs and normalization-aware comparisons. String equality
      currently preserves and compares the exact scalar spelling.

## Conditional values

- [x] Exhaustive conditionals can produce one scalar value and lower through a
      typed temporary.
- [x] Non-exhaustive conditionals are statement-valued `void`.
- [ ] Multi-value conditional results.

## Completely unimplemented

- [ ] Imports and modules
- [ ] Floating-point, rational, and real numbers
- [ ] Physical units
- [ ] Dictionaries, bidirectional maps, and sets
- [ ] Pattern matching (`match`)
- [ ] String interpolation
- [ ] Partial application (`@`)
- [ ] Implicit declaration (`:=`) and compile-time assignment (`::`)
- [ ] Juxtaposition multiplication and broadcasting
- [ ] Linear algebra, multidimensional array sysntax, etc.
- [ ] Generators (`yield`)
- [ ] Unpack and collect
- [ ] Host intrinsics and foreign-function interop
- [ ] Effects and error values
- [ ] Compile-time evaluation and meta-programming
    - [ ] metatags for things historically passed as compiler flags
- [ ] bootstrap compiler implementation in dewy
- [ ] full end to end self-hosted compiler via dewy->udewy frontend, udewy->asm backend
- [ ] standard library
    - [ ] OS agnostic interfaces on top of OS-dependent implementations per supported OS/environment
- [ ] implementation of hello world examples from the different domains
- [ ] test harness system. 
    - [ ] self hosted unit tests with automation for running on all updates

### Full Refinement System
- [ ] Flow-sensitive refinement typing. Track value facts through ordinary control flow: x != 0, 0 <= i < a.length, literal values, unions/intersections, exclusions like T & ~0, etc.
- [ ] Refinement-aware function contracts. Let parameter and return types express predicates and relationships between values, including overloads selected by refinements.
- [ ] Static proof before implicit partial operations. Operations like indexing, division, narrowing casts, invalid shifts, etc. compile normally only when the compiler can prove their preconditions.
- [ ] Explicit runtime validation boundary. Runtime checks should appear only when the programmer writes an explicit check or checked operation; successful checks refine the value afterward.
- [ ] Explicit unsafe escape hatch. Permit the programmer to assert an unproven invariant without a runtime check, with unsafe marking the proof obligation clearly.
- [ ] Symbolic state tracking across mutation. Model operations such as push, pop, truncate, mutation, and function calls as state transitions, then propagate or invalidate refinements precisely.
- [ ] Effect and alias tracking. Know what functions can mutate, allocate, block, access shared state, change collection length, etc., so existing proofs survive calls whenever justified.
- [ ] Automatic arithmetic/range reasoning. Use a solver capable of proving common equalities, inequalities, ranges, and simple relationships without programmer-written proof terms.
- [ ] Inference-first ergonomics. Ordinary imperative code should usually verify without annotations; explicit contracts/invariants should be needed mainly at abstraction boundaries and complex loops.
- [ ] Semantic types separated from machine representation. Let types such as arbitrary-precision integers describe semantics, while range analysis chooses i8/i32/i64/... representations when provably equivalent.
- [ ] Information-preserving casts by default. Normal casts must preserve value/precision; potentially lossy or fallible conversions should be explicit and typed accordingly.
- [ ] Typed failure instead of hidden traps. Allocation failure and other genuinely dynamic failures should appear as result/error values or explicit effects rather than invisible exceptional paths.
- [ ] Verifier-friendly standard library. Give core operations precise contracts—for example map preserves length, pop decrements it by one, slice has a known resulting length—so proofs compose automatically.
- [ ] Useful proof diagnostics. When verification fails, report known facts, required fact, and the missing relationship, rather than exposing solver internals.
- [ ] Optimization driven by proofs. Reuse refinement information for bounds-check elimination, integer-width selection, dead-branch elimination, specialization, and other lowering decisions.
- [ ] Idiomatic code designed to be provable. Make the language’s normal APIs and control structures naturally expose the invariants the verifier needs, rather than treating verification as an add-on.

### Meta stuff
- [ ] remove old src and replace with cleanparse (delete intermediate cleanparse folder)
- [ ] general repo cleanup/restructuring
- [ ] web compiler demos of language
- [ ] complete docs rewrite
    - [ ] API/language reference
    - [ ] dewy book

### Aspirational/Experimental/etc.
- [ ] non text-editor view over code/AST. basically render AST to look like text, but render with user set visual settings for spacing, indentation, comment positions, etc. etc. Probably requires a custom editor-esque app. Should generally feel mostly like editing regular text in a text editor, just without the pure bag-of-characters semantics
- [ ] saving/editing packed ASTs instead of bag-of-characters raw text for source code. hashing sort of like unison, though tbd the exact semantics