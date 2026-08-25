# Cleanparse implementation status

This document tracks language features in the cleanparse compiler. Checked items are supported through parsing, semantic analysis, udewy lowering, and emission.

## Current focus

The current compiler-development focus is recursive, transitive effect analysis for aggregate parameters. The analysis should distinguish reads, mutation, whole-value rebinding, and escapes; follow field and index routes; propagate effects through direct calls; and remain conservative at unresolved or indirect calls. Its first use is to make value-semantic borrowing and copying correct for nested arrays and structural objects, replacing the current array-specific boundary checks.

The intended follow-on slice is iteration over arrays of structural objects; caller-owned materialization of interpolated string results has landed (see roadmap item A1). Runtime-length array returns now use the arena tier (see roadmap item B2); whole-array place rebinding of runtime-length arrays remains deferred.

## Roadmap

The current focus above is phase 1 of this roadmap. Two named milestones anchor the sequencing: **Milestone A** — every example on the site front page compiles and runs as shown; **Milestone B** — the language is comfortable enough to write a compiler in, without the bootstrap itself being part of this roadmap. A good acceptance test for Milestone B is writing the udewy tokenizer in Dewy: it exercises files, growable arrays, dictionaries, unions with matching, strings, and error handling without committing to the full bootstrap.

### Phase 0 — hygiene

- [x] Declare `requires-python = ">=3.14"` in `pyproject.toml` and align the installer check and README, which currently claim Python 3.12. The compiler relies on 3.14 deferred annotation evaluation, so 3.12 and 3.13 fail at import.
- [x] Add a CI workflow that runs the pytest suite; only site-deploy and udewy-release workflows exist today.
- [x] Replace the stale README example table, which predates cleanparse and points at files now in `examples/old`.
- [x] Archive `dewy/todo.py` (parser-era notes superseded by this document) and remove the disabled `todo-to-gh-issue` workflow file.
- [x] Golden-stdout checks for the printing fixtures in `dewy/tests` so backend refactoring cannot silently change output. Already covered: the e2e and stage tests capture and compare program stdout with `capfd` for every fixture that prints.

### Phase 1 — effect analysis and the lowering refactor

The effect analysis described under Current focus, treated as one campaign with paying down the accumulated backend debt:

- [x] Build the recursive, transitive effect analysis as its own module. `semantic/analyze/effects.py` summarizes per-parameter reads, mutation, rebinding, and escapes by field/index route over checked HIR, propagates place-argument effects through direct calls to a fixed point, and stays conservative at indirect or unresolved calls. Value arguments propagate only a read: under value semantics each boundary decides copy-versus-borrow locally from the callee's own summary.
- [ ] Replace the array-specific call-boundary checks in `dewy/backend/udewy/lower.py` with it, unifying the near-duplicate array and object code paths. Done so far: array parameter adapter-safety is now driven by the semantic summary, which reaches the true transitive fixed point the old two-pass use-set check stopped short of — read-only parameters that return, object-store, or forward their array now borrow instead of copying (`array_borrowed_returns.dewy`). Arrays with object elements may borrow when proven read-only (`object_array_borrowed_params.dewy`); the effect analysis conservatively treats any access to a function-valued member through a parameter route as receiver mutation, since function fields capture their receiver. Plain object parameters with a read-only summary now skip the callee prologue clone and borrow the caller's storage (`object_borrowed_params.dewy`). Mixed value-plus-place arguments of one binding in a single call are now copy-forced on the value side, fixing a pre-existing bug where a borrowed value argument observed place writes mid-call (`mixed_value_place_arguments.dewy`). Still to do: boundary-analysis internals and removing the superseded use-set machinery.
- [x] Split `lower.py` (was ~11k lines) into coherent modules. `_Lowerer` is now composed from topic mixins — `lowering_strings` (strings/graphemes/unicode), `lowering_arrays` (representation analysis, boundaries, copies, results), `lowering_objects`, `lowering_places`, `lowering_optionals`, `lowering_iterators`, `lowering_flow` — with shared layout constants and data structures in `lowering_shared.py`. `lower.py` (~3.3k lines) keeps discovery, symbols, statement/expression transformation, and re-exports the public names. The split was mechanical; no behavior changed. `dewy/semantic/check.py` (~5.7k lines) still gets the same treatment opportunistically.

This phase is load-bearing: effect, escape, and ownership analysis is the prerequisite for runtime-length array returns, whole-array place rebinding, growable arrays, and representation elision.

### Milestone A — front-page examples

In dependency order; A4 and A5 are long-running and interleave with Milestone B work.

- [x] **A1. First-class interpolated strings** (fixes `functions.dewy`, which now runs as shown on the front page). Interpolated strings materialize into complete runtime string descriptors: part bytes are gathered (string copies, runtime integer digits, `true`/`false` selection), then shared UAX #29 segmentation — factored into `_utf8_segmentation`, also reused by the grapheme-array conversion — rebuilds boundaries over the joined buffer, so clusters spanning part joins stay correct. Functions returning materialized strings use a caller-owned result block sized by a compile-time capacity bound (constant bytes plus multiples of string-argument lengths, composed through direct calls, locals, flows, and slices); module-level results use static storage with constant capacity. `print`/`printl` keep the zero-copy streaming path, and `bool` prints and interpolates. Guarded until later: destination-ABI functions as first-class values or object methods, unbounded returned fields, defaulted string parameters in capacity formulas. Still ahead from the original scope: a user-facing `__string__`/`__as__` conversion protocol for interpolating non-builtin types, and unsigned 64-bit formatting (streaming and materialization both treat integers as signed).
- [x] **A2. Ranges as storable values** (fixes `ranges.dewy`, whose card now runs end to end). Range bindings are compile-time values: iterating or testing membership against a stored range resolves the binding back to its literal during checking, so `window = [0..10)` and `evens = 0,2..100` store, iterate, and answer stepped membership with zero runtime representation — constant-anchored memberships even fold to booleans. Range declarations are elided from lowering entirely. Guarded: reassigning a range binding is rejected (resolution would go stale), only compile-time-constant anchors resolve (inlining runtime anchors at the use site could observe later mutations), and any range value reaching lowering unresolved errors. Still ahead: a runtime range representation for runtime anchors, passing and returning ranges, and compound range arithmetic.
- [x] **A3. Iterator-target unpacking and first dictionaries** (fixes `loops.dewy`, whose card now runs end to end). Dictionary declarations (`ratings = ['star wars' -> 73 ...]`, top-level or local, `let` or implicit) desugar at check time into hidden parallel key and value arrays; the visible binding is compile-time only, like ranges. `loop [key value] in dict` unpacks by desugaring to a lockstep `and` multiiterator over the hidden arrays, reusing the existing machinery end to end. Dictionary literals outside declarations, key lookup, growth, and mutation stay pending on a runtime representation (after phase 1 ownership work); `[a b]` unpacking over plain arrays of arrays reports a clear not-implemented instead of the old mixed-condition error.
- [ ] **A4. Fractional numerics and the unit catalog** (fixes `units.dewy`). Rationals and fixed-point are the primary fraction types — `let a = 1/3` should infer a rational — and both lower naturally onto udewy's integer-only core (integer pairs and scaled integers). Floats remain available when explicitly requested but are deliberately deprioritized; no serious float implementation in this roadmap. Then: base dimensions beyond `Time`, dimension products, powers, and division, the unit catalog, `^`, and enough math library for `cos` and `°` over the chosen representations. **Rationals landed (first slice):** `rational` is the prelude object type `Rational = [numerator:int64 denominator:int64]` from `library/rational.dewy`, kept normalized (positive denominator, coprime parts) by `_rational_make`; the operations are ordinary Dewy functions there, so the compiler adds only routing — `a / b` on integers (`/` now maps to `__truediv__`; `//` stays floor division), decimal literals (`9.8` is exactly `49/5`, `1.25e2` is `125`), `+ - *` `/`, negation, and all comparisons with a rational operand call the prelude (integers promote via `_rational_from_int`), and literal operands fold to normalized parts at check time (`6/(-8)` becomes `_rational_make((-3) 4)`; a literal zero divisor is a compile-time error). `print`/interpolation render `n/d`, or `n` when whole. **Powers:** `^` (right-associative) raises integers and rationals to integer powers — constant integer powers fold (`2^10`), runtime ones call `_int_pow` (`library/math.dewy`, squaring) with the exponent required to be a constant or unsigned so the integer result type is sound, a negative constant exponent yields a rational (`2^(-3)` is `1/8`), and rational bases take any integer exponent through `_rational_pow`; narrow fixed-width operands widen to `int64`, other widths are not yet supported. Not yet: fixed-point, compile-time `RationalLiteralType` folding of whole expressions (`1/2 * mass` still runs at runtime, so rational scales cannot yet fold into quantity types), `^`, overflow beyond int64 (no bigint tier), runtime zero divisors (pending error values, B5), rationals inside materialized (returned) interpolated strings, and `rational` as a nominal type distinct from any structurally identical object.
- [ ] **A5. Liquid refinements MVP** (fixes `refinements.dewy`). Scoped to the example: parameterize-block syntax, propositions like `length>?0` and single-argument lambdas, proofs from literal initializers, and proven/refuted/unknown diagnostics. The full solver comes later per the design section below.

### Milestone B — comfortable-to-bootstrap feature set

Ordered by how much each item builds on the previous ones.

- [ ] **B1. General tagged unions and `match`.** A compiler is one large AST of sum types; single-payload `T | undefined` is not enough. Highest-value language feature for bootstrap ergonomics. Done so far: local union bindings with word-sized members (fixed ints, bool, strings/graphemes, `undefined`) lower as tag-and-payload cells sharing the optional layout (`undefined` is always tag 0, so the numberings coincide); initialization and reassignment tag by member, `is?`/`isnt?` compare tags (folding statically when the answer is known), flow-sensitive narrowing now splits any union — including else-branches — and fully narrowed reads load the payload. Unions now also cross call boundaries: parameters copy the incoming cell in the prologue, member-typed arguments materialize into fresh cells at the call site, results write into a caller-owned result cell, and results compose directly into further union calls. Partially narrowed subset unions work as views — tags stay physical in the storage union's numbering, so subset reads pass the cell through and tests consult the storage members. Fixed-layout aggregate members (objects whose fields are returnable, exact arrays) work too: each aggregate member owns a prepared storage tree allocated with the cell and referenced from slots after the payload word, tagging copies the value into its tree, same-union copies deep-copy the active tree by tag dispatch, and a narrower union retags into a wider one at boundaries (`Pair|string` into `Pair|int64|string`). Object and array literals now check against a union that has exactly one matching member. Still to do: recursive and runtime-sized members (arena-backed indirection per the ownership model); module-level union bindings; and exhaustiveness checking as the `match` story over `is?` chains. Narrowing now also flows past conditionals: the code after an `if` keeps the join of the refinements at the end of every non-diverging path (arm bodies that do not return/break/continue, the `else`, or the all-conditions-false fall-through), so the early-return idiom narrows the union below it even when a non-diverging `else` is present.
- [ ] **B2. Growable arrays.** Push, pop, truncate, runtime-length returns, and escapes into longer-lived storage. Depends directly on phase 1; forces the first real memory-management decision, where the descriptor's `capacity` and `owner` fields either earn their keep or get redesigned. Done so far: the first arena tier exists — `_arena_alloc` in `library/system-linux.dewy` bump-allocates from anonymous `mmap` chunks (process lifetime; scoped arenas still ahead), the prelude merge keeps backend-called runtime helpers alive, and **runtime-length array results** (`:>array<T>` with no exact length) now lower as arena-backed descriptors: the callee copies the returned array into the arena (word-scalar elements for now) and forwarded runtime-length call results pass straight through. Indexing a genuinely runtime-length array still needs the `0 <= i < a.length` refinement proofs (A5); iteration and `.length` work. **Growth syntax decided (2026-08): method-style on the value, never global functions** — `xs.push(x)`, `xs.pop(idx=end)`, `xs.insert(x idx)`, `xs.clear`, `xs.reserve(n)`, `xs.sort`, with indexing as the `__index__` dunder. Conceptually `array` is an ordinary Dewy object type with these methods and an `Index = uint< i => i <? length >` refinement, so the compiler-provided methods should behave exactly as if `array` were defined in Dewy; dunders like `__index__` are the sugar bridge to the global operator form. Container mutation is accessed exclusively through the container; free functions are reserved for genuinely global operations such as `sin`/`cos`/`sqrt`. **Growth methods landed:** `xs.push(x)`, `xs.pop`, `xs.clear`, `xs.reserve(n)` on `let` bindings declared `array<T>` (word-scalar elements for now); growth doubles capacity (minimum 8) and relocates the data into the arena, so raw stack, static, or borrowed data is never written through, and copies stay independent. A `let xs:array<T> = [...]` binding now has the declared runtime-length type with the initializer's exact length kept as a *refinement* — index proofs keep working until a length-changing method invalidates it, and loop bodies drop refinements of every binding they assign or grow before being checked (this also closed a pre-existing hole where a union narrowing established before a loop survived an assignment inside it). `const` array bindings keep their exact types. **Length facts now track growth:** an exact-length refinement steps through `push`/`pop` and resets on `clear`, and comparisons such as `xs.length >? 0` (or `2 <=? xs.length`) establish proven minimum lengths that step the same way; both are joined across conditional paths, invalidated by assignment and loop-body mutation, and reset per function. `pop` is a proven operation: it is accepted only when the exact length or a guard-proven minimum shows the array is non-empty, and `pop` on a statically empty array is an error. **Runtime-length arrays are now indexable from facts:** the bounds analysis keeps a length interval per runtime-length array (refined by `xs.length >? k`, stepped by growth methods) and `i <? xs.length` guard facts per index binding, so `loop i <? xs.length { xs[i] }` and `if xs.length >? 2 { xs[2] }` are proven; facts are dropped when the index is reassigned or the array shrinks, and joins keep only facts common to all paths. This is the first concrete slice of A5's `Index` refinements. Still ahead: `insert`, `sort`, `pop(idx)`, scoped arenas, and `truncate`. (Fixed along the way: lowering side tables keyed by `id(node)` could inherit stale analyses when CPython reused a freed node's id — an allocator-state-dependent miscompile that showed up as intermittent full-suite failures; every re-keyed node is now kept alive for the lowering's lifetime.) Reference design: the circular-deque `vector.c` from the old C implementation (`head` offset + doubling capacity, O(1) push/pop at both ends) — see the representation notes below.
- [ ] **B3. Mutable, growable dictionaries and sets.** Symbol tables, scopes, and string interning. Reference design: the compact-dict `dictionary.c` from the old C implementation — see the representation notes below. Done so far: dictionaries are runtime values on top of growable hidden parallel arrays — `let d:dict<K V> = []` or a literal, `d[k] = v` appends or replaces in place (insertion order is entry order, so iteration order is preserved by construction), `d[k]` is a `V|undefined` lookup, `k in? d` tests membership, `d.length` counts entries, and `loop [k v] in d` iterates grown dictionaries in lockstep at runtime (pure-`and` multiiterators now accept runtime-length arrays). Search is linear for now; the compact hash-index table can replace it without changing any semantics. Keys and values are word-scalar or string types; deletion, sets, and dictionaries as parameters/results are still ahead.

**Runtime representation notes for dictionaries, sets, and deque arrays.** The intended full representations are based on the old C implementations on the `C_Clustered_Nonterminal_Parser` branch (`src/dictionary.c`, `src/vector.c`):

- Dictionaries (and sets) use the compact two-structure layout: a sparse `indices` probe table mapping hash slots to entry positions, plus a dense `entries` array of `(hash, key, value)` in insertion order; iteration walks the dense entries array. The two structures resize independently (indices rehash at ~2/3 load; entries double). **Probing decision (2026-08):** do *not* copy the C implementation's PRNG/LFSR step for collision resolution; use CPython's scheme instead — open addressing with `i = (5*i + perturb + 1) mod size` and `perturb >>= 5`, where `perturb` starts as the full hash. The first probes stay near the initial slot (cache-friendly), the high hash bits still break up clustering, and once `perturb` reaches zero the recurrence is a full-period permutation of a power-of-two table, so every slot is visited. Also worth taking from CPython: a power-of-two index table sized so load stays under 2/3, index entries narrowed to 1/2/4/8 bytes by entry count, and hashes stored in the entries so rehashing never recomputes them. **Current state:** only the dense-entries half exists (parallel key/value arrays with linear search); adding the index table changes no semantics. For the remaining open questions (deletion via index-table tombstones, resize policy, hash mixing) the default is to pattern after CPython's dictionary wherever its choices fit Dewy.
- **Semantic guarantee to preserve from day one: dictionaries and sets iterate in insertion order.** The current compile-time dictionaries (hidden parallel arrays in literal order) already satisfy this; nothing may regress it when the runtime representation lands. Deletion semantics in the C code were unfinished (a `DELETED` sentinel existed but was unused), so deletion behavior is an open design point, not something to copy.
- Vectors are circular deques: `head` offset + `size` + `capacity` with modular indexing, capacity doubling (power-of-2), giving O(1) push/pop at both ends. This is a candidate representation for growable arrays where front-insertion matters; the known middle-insertion off-by-one in the C code is a bug, not a spec.
- [ ] **B4. Closure lowering.** Capture analysis exists; lowering does not.
- [ ] **B5. Error handling.** Effects and error values per the design, or at minimum a workable result-type idiom.
- [ ] **B6. File I/O and `main(argv)`.** Done so far: `main = (args:array<string>)` receives the command line — the entry wrapper walks the C `argc`/`argv`, copies each argument into the arena as a segmented string, and pushes it onto a growable `array<string>`; `library/linux/system.dewy` (the Linux system module, moved from `system-linux.dewy` as the first step of the per-OS library layout, with the stale `core-*` files parked in `library/old/`) provides `read_bytes(path):>array<uint8>`, `write_bytes(path bytes):>bool`, `write_text(path text):>bool`, and `file_exists(path):>bool` over raw syscalls. Still ahead: decoding file bytes into strings (`array<uint8> as string` needs a validating UTF-8 decode), error values instead of empty results, and directory/stream operations.
- [ ] **B7. User-written generic functions and parameterized types.** The internal machinery exists for builtins; exposing it makes containers writable in the standard library instead of as compiler magic.
- [ ] **B8. String building.** Concatenation, join, and a builder on top of A1's materialized interpolation.
- [ ] **B9. Self-hosted test harness**, written in Dewy, as the dogfooding proof.

### Library housekeeping

The library is now split into a portable layer and per-target layers: `library/linux/io.dewy` (`_write_stdout`/`_write_stderr` over the `write` syscall) and `library/linux/system.dewy` (arena, `sleep`, file access) are the Linux target layer; `library/io.dewy` (`print`/`printl`, integer and boolean printing, interpolation streaming), `path.dewy`, and `units.dewy` are portable and build only on the target primitives. Target gating is native and mirrors udewy exactly (udewy is meant to be valid Dewy): `$target` is the backend name (`x86_64`, `riscv`, `arm`, `c`, `wasm32`) as a compile-time string, `$target =? "..."` folds during checking (Dewy adds the conveniences `$target in? ["x86_64" "riscv" ...]`, `not =?`/`not in?`, prefix `not`, and `and`/`or` over such conditions), and an `if` on such a condition skips its dead arms entirely (unchecked, so they may import files that only exist for other targets) while splicing the live `{}` body into the enclosing scope; plain literal conditions (`if true`) keep ordinary flow semantics with every arm checked. `library/io.dewy` imports its own primitives with `if $target in? ["x86_64" "riscv" "arm" "c"] { from p"linux/io.dewy" import (_write_stdout _write_stderr) }` (udewy's `host.udewy` spells the same thing as one `if $target =? ...` per target). `$supported_targets = ["x86_64" ...]` (backend names, as in udewy) rejects compilation for other targets. Open design point for later: the target list in `dewy/targets.py` is slated for an overhaul into fuller triples (`x86_64-linux-musl`, `c-posix`, `wasm32-wasi`, ...); per-target gating then gets cumbersome (`$target in? [...]`), so the likely shape is a structured target (`$target.os =? "linux"`, `$target.arch`, ...) — to be settled in a dedicated discussion, not now. `dewy/semantic/prelude.py` now lists only the portable files plus the OS *services* layer (`linux/system.dewy`, which needs portable types such as `Duration`), selected from the target passed down from the CLI (`dewy -t`). The stale `core-*.dewy` files are parked in `library/old/`. A new target provides its own `io.dewy`/`system.dewy` with the same bindings.

### Tangents (after the current roadmap)

- **A test framework written in Dewy.** A general-purpose library — assertions, test discovery and grouping, expected-failure and skip markers, and readable reporting — usable by any Dewy project. Distinct from B9, which is the compiler's own fixture harness; B9 would become the first consumer of this framework once it exists. Not to be started until the current roadmap is complete.

### Ownership and storage model (design decision, 2026-08)

Growable arrays (B2), runtime dictionaries and sets (B3), runtime-sized union members, recursive sum types such as an AST, and runtime-length returns all wait on one backend decision: where dynamically sized storage lives, when it is released, and when a copy may become a move. The language-level rule is already fixed by `semantic/value_semantics.md`: every binding uniquely owns its value; assignment has value behavior but must be realized through moves, ownership transfer, sharing of provably immutable storage, or explicit copies; copy-on-write is never the universal mechanism. The backend model that realizes it:

1. **Static sizing first.** Storage whose size is fixed at compile time stays where it is today: frame `__alloca__` for locals, `__static_alloca__` for module lifetime, caller-owned result trees across calls. This includes structures that are *dynamic in shape but static in inputs*: if a program builds a growable structure only from values present in the source, with no path for input-dependent size (as established by the effect analysis — no reads of arguments, files, or other external inputs feeding the size), the compiler should eventually compute the required size at compile time and allocate it statically. That full analysis comes later; the model must leave room for it, so no representation may assume a heap.
2. **Arenas as the first dynamic mechanism.** When a size genuinely depends on runtime input, storage comes from an arena: a bump allocator over `mmap`ed regions, with a lifetime tied to a scope (function frame, loop, or an explicitly named region). Arenas give predictable cost with no per-object bookkeeping, no refcount traffic, and no latency spikes, which matches the systems-programming goal; they fit compiler-shaped workloads where whole phases of allocations die together. Release is arena release at scope exit — there is no per-value free in this tier.
3. **Heap as last resort.** Individually owned heap objects with per-value release (via `__malloc__`/`__free__`, which are currently empty placeholders in `library/core-all.dewy`) are reserved for lifetimes that neither static sizing nor a scoped arena can express. They must be explicit or provably necessary, never the default path a growable structure falls into.
4. **The move rule.** Value copies of dynamically sized storage are elided by analysis, not by runtime tricks: a copy becomes a move when the source binding is provably dead afterward (last use, from a liveness pass built on the effect summaries), a borrow when the consumer is provably read-only (already implemented for parameters), and an explicit copy otherwise. Sharing is allowed only for storage proven immutable for its whole lifetime.

Consequences for pending items: the array descriptor's unused `capacity` and `owner` fields become the arena/ownership metadata (or are removed if the tier design does not need them); growable arrays and dictionaries take their storage from the current arena; recursive union members (`Node = Leaf | Pair`) use arena-allocated indirection; fixed-layout union members need none of this and can be implemented now as inline maximum-size payload trees. Open details to settle during B2: arena granularity (per function versus explicit regions), how a value escapes an arena into a longer-lived one (copy into the outer arena at the boundary, guided by escape analysis), and the concrete liveness analysis for moves.

An additional, opt-in systems escape hatch is now outlined in [`semantic/user_managed_storage.md`](semantic/user_managed_storage.md). A library-defined `Rc<T>` should be an ordinary explicit handle value, not an escaping `@` place and not Dewy's default storage strategy. Making that implementable in user code eventually requires deterministic copy/transfer/release hooks, typed unsafe allocation and layout capabilities, lifetime-bounded places into managed payloads, and atomics only for a later cross-thread `Arc<T>`. This is design work after the current arena and ownership slice, not a reason to introduce universal reference counting.

### Sequencing

Phase 0 → phase 1 → A1 → A2 → A3 → B1 → B2 → B3 → B4, with A4 and A5 interleaved as parallel long-poles (they touch different compiler layers than the ownership work) → B5–B8 → B9 → the tokenizer-in-Dewy checkpoint.

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
- [x] Optional `main` argument `args:array<string>` (see roadmap item B6).
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
- [x] Explicit non-escaping place parameters and arguments use `@` on both sides. Named mutable fixed-width scalar, Boolean, array, and structural-object bindings can be updated or replaced through direct and nested calls; place types are invariant.
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
- [x] `bool`, string/grapheme, function, nested-array, and structural-object element layouts.
- [x] Arrays of recursively fixed structural objects preserve value semantics across literals, copies, element replacement, calls, and returns.
- [x] Non-escaping function-local `let` and `const` bindings initialized by an exact-length array literal use only a fresh stack element buffer when every use is `.length`, an indexed read, or an indexed write.
- [x] Ordinary binding, rebinding, element storage, object-field storage, and argument passing recursively copy exact nested arrays. Read-only calls may borrow the source invisibly; calls that might mutate receive fresh element storage.
- [x] Non-escaping runtime-length array copies allocate from the source length and use a counted, width-correct element loop.
- [x] Recursively fixed array and structural-object return values use caller-owned storage, including exact nested arrays and exact array-valued object fields. Direct literals, returned locals, forwarding calls, and indirect or method calls all fill storage prepared by the caller.
- [x] Non-escaping `@` places for named mutable array bindings. Both the parameter and call site must use `@`; element writes and recursively fixed whole-array rebinding propagate to the caller through nested calls. Place types are invariant, `const` places and overlapping arguments are rejected.
- [x] Place projection through object fields and individual array elements, including nested mixed routes and whole-value replacement of array-valued elements. `@root.field[i]` follows ordinary prefix and selector precedence; `@(root.field[i])` is equivalent.
- [x] Left-to-right iteration over arrays of settled scalar, function, and immutable string-like elements. Dynamic-length arrays work as single iterators, and exact-length arrays compose with other multiiterator leaves.
- [ ] Empty-array inference.
- [ ] Arrays whose exact runtime length is not known where indexing requires it.
- [ ] Returning arrays whose storage requirement is not known at the call site, return elements with unresolved backing-storage lifetimes, and other escapes into longer-lived storage.

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
- [x] General heterogeneous runtime unions such as `int64 | string | undefined` for local bindings with word-sized members: tag-and-payload cells, member-indexed tags (`undefined` always tag 0), tag-comparing `is?`/`isnt?`, and payload loads after full narrowing. Union parameters, results, module-level bindings, aggregate members, and partially narrowed subset unions remain pending (see roadmap item B1).
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
- [x] Object bindings, assignments, parameters, and constructors recursively copy exact array-valued fields as well as directly stored and nested-object fields.
- [x] Caller-owned object returns recursively prepare exact array-valued fields and nested structural fields in the caller before the callee fills them.
- [x] Non-escaping `@` places for named mutable structural-object bindings. Field mutation and whole-object replacement operate directly on the caller's recursively fixed storage and can be forwarded through nested calls.
- [x] Explicit `@` place routes through mutable structural-object fields, including routes that continue into array fields or nested objects.
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

Language-level assignment, passing, and return are copies; `@` is the spelled place. See [`semantic/value_semantics.md`](semantic/value_semantics.md). Sharing a pointer for `let b = a` is an elided copy, not the user-visible rule.

The source-level type of a value describes its semantics, not a mandatory machine layout. Lowering should retain only information that can affect the program at runtime. Facts already established by typing, refinement, control-flow, or effect analysis should normally become constants in the emitted program rather than fields stored beside every value.

The current backend still uses a canonical pointer to a 48-byte descriptor containing `data`, `length`, `capacity`, `stride`, `flags`, and `owner` for most arrays. Two proven cases omit it:

- Module-scope `const` arrays whose binding-identity use set contains only `.length`, indexed reads, and proven-safe direct-call boundaries can use raw static storage. Compatible one-word literals and function references use udewy's internal `__static_words__`, while exact based bytes use their static data pointer.
- A function-local `let` or `const` binding initialized directly by an exact-length `ArrayLiteral` uses a fresh `__alloca__` element buffer when all uses are `.length`, indexed reads or writes, ordinary same-function copies, or analyzed call boundaries. Each downstream binding gets independent element storage when either value could be mutated. Length is folded from the exact type, element stride is compiled into address arithmetic, and width-correct loads and stores address the buffer directly. Semantic checking still rejects indexed writes through a `const` binding.

For a statically resolved direct or selected-overload call, a parameter that only observes length, indexed reads, or other read-only calls is adapter-safe. Lowering wraps raw local/static data in a temporary canonical descriptor in the call prelude without copying elements; the callee ABI and indexing remain descriptor-based. When the callee may write or the call cannot be analyzed, arrays are copied into fresh descriptor-backed element storage first. Exact copies are unrolled; runtime-length copies use a counted loop over the descriptor length. Read-only exact static bytes use borrowed-static flags.

Recursively fixed array and structural-object returns use a hidden destination supplied by the caller. The caller allocates the complete mutable storage tree in its own frame, including exact nested array descriptors and buffers or exact array-valued object fields. The callee initializes or recursively copies into that storage before returning, and a directly returned call forwards the same destination through wrapper functions. No callee-local mutable result storage escapes. Local binding, assignment, element storage, object-field storage, and argument passing use the same recursive value-copy rule. Runtime-length arrays can be copied while the destination remains in the current frame. Results with runtime-dependent storage, unresolved backing-storage lifetimes, and other escapes remain pending. Control-flow representation joins, general or transitive effect analysis, indirect/method read-only adapters, and descriptor-free specialized direct-call ABIs also remain pending. At present arrays cannot change length; `capacity`, `stride`, and `owner` are not read by generated programs.

A named scalar or array passed as `@name` uses non-escaping addressable storage for the duration of the call. Scalar cells use width-correct loads and stores. An array place exposes the caller's descriptor, so direct element writes reach the selected storage; replacing a recursively fixed array writes into the complete storage tree already owned by the caller rather than publishing callee-local pointers. The caller reloads its binding after the call, including when one place parameter forwards the place to another. Structural objects already have stable recursively fixed storage, so an object place passes that address directly without another cell; field writes and whole-object copying both update the caller's storage. Field and index selectors project the root place to the final storage address, evaluating computed indices once. Disjoint constant indices or object fields may be passed together; dynamic indices and prefix routes are conservatively treated as potentially overlapping. This ABI deliberately requires exact source/parameter type equality and does not allow a place to be stored or returned. Whole-value rebinding of a runtime-length array place remains pending because the destination storage size may change.

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
- [x] Give simple same-function exact-array bindings independent raw stack buffers; materialize borrowed canonical descriptors without copying at proven read-only direct and selected-overload call boundaries.
- [x] Copy exact arrays into fresh element storage for ordinary whole-array rebinding and calls that may mutate or cannot yet be proven read-only.
- [x] Recursively copy nested exact arrays and array-valued object fields for local binding, assignment, element storage, and parameter passing.
- [x] Recursively copy structural-object array elements at literals, bindings, assignments, call boundaries, and caller-owned returns; conservatively disable borrowing when nested object mutation could otherwise be hidden.
- [x] Copy descriptor-backed runtime-length arrays in non-escaping contexts with a counted element loop.
- [x] Return recursively fixed arrays and structural objects through caller-owned result storage, copying direct literals or existing values and forwarding destinations through wrapper calls without exposing callee-local mutable allocations.
- [x] Pass named mutable scalars and arrays to explicitly marked non-escaping `@` parameters through width-aware temporary storage, writing rebinding back after the call while direct array-element mutation intentionally shares the selected storage.
- [x] Pass named mutable structural objects as `@` places using their existing caller-owned storage, avoiding an extra pointer cell while preserving both field mutation and whole-object replacement.
- [x] Project non-escaping places through nested object fields and individual array indices, passing the final width-correct cell or structural storage address and conservatively rejecting routes that may overlap.
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

- [ ] Fractional numbers. Rationals and fixed-point are the primary fraction types (`1/3` infers a rational); floats exist only when explicitly requested and are deprioritized for now. Real numbers remain further out.
- [ ] Dictionaries, bidirectional maps, and sets
- [ ] Pattern matching (`match`)
- [ ] Partial application and function handles with `@`, escaping places, and place targets beyond mutable named roots with field/index projection. See [`semantic/value_semantics.md`](semantic/value_semantics.md).
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

Structural requirements may be combined with a fresh nominal descendant. `type of Parent` is the operation that mints the nominal identity; `&` only intersects the resulting type with the structural requirements:

```dewy
Posit64:type = (type of float64) & [sign:bit regime:array<bits> exponent:array<bits> fraction:array<bits>]< regime.length + exponent.length + fraction.length =? 63 >
__as__ &= (x:Posit64):>float64 => { some algorithm to convert posits to floats }
```

Rules and semantics:

- `type of Parent` creates one fresh nominal child of `Parent`. Intersecting that child with a structure does not mint a second type or add another edge to the nominal tree
- `A & B` is always non-generative type intersection. A hybrid retains any nominal ancestry already present in its operands, and otherwise follows structural/duck-typed equality
- a structural type with a representation different from a representation-bearing nominal ancestor requires a corresponding `__as__` overload when a use reaches that ancestor's canonical representation. The absence is checked lazily at use sites (definitions may appear after the type, in any order at module level), and it is a type error to actually need the conversion when none is defined. Marker ancestry with no canonical representation, such as `exception` and `error`, introduces no conversion by itself
- `x is? float64` is true for a `Posit64` instance; the spliced type genuinely is a descendant of the nominal type
- the nominal type tree itself is single inheritance, but structural intersections may require membership in multiple nominal families (`MyType = int & float64 & [...]`), with one `__as__` overload per representation-bearing nominal parent
- nominal types are immutable / have no internal fields to mutate, so coercion never creates mutation-aliasing concerns; `__as__` produces a fresh value with ordinary value semantics
- `as`/`__as__` in general must be invoked explicitly; the sole implicit case is a spliced type flowing to a context requiring one of its nominal ancestors
- coercion happens at _canonical-representation boundaries_, not call boundaries. A generic bound like `<T of float64>(left:T right:T)` binds `T = Posit64` directly with no conversion; `__as__` is inserted only where the canonical machine representation is actually required (e.g. inside a builtin body), per the representation-selection rules described earlier in this document. Consequently, overload resolution prefers a representation-preserving match over one requiring `__as__`, so defining posit-native operations opts out of coercion per-operation
- conversion path resolution: an explicitly defined direct `__as__` always takes precedence over a composed path. Composed paths (chaining `__as__` up the ancestry, e.g. `Tracked -> Posit64 -> float64` for `Tracked = Posit64 & [...]`) are allowed when unambiguous. With multiple nominal parents, diamonds are possible (`X = int & float64 & [...]` at a boundary expecting a common ancestor); if multiple composed paths exist at a use site, that is a type error, resolved by defining a direct conversion. The error surfaces only at ambiguous _use_ sites — the mere existence of multiple paths is fine (opt-in lint at most) — and the diagnostic must name the competing paths and the definition sites of the `__as__` overloads involved
- a pure nominal descendant with no structural body is spelled as an ordinary expression: `UserId = type of int`
- extending an existing hybrid structurally does not need or create another nominal type: `DetailedPosit = Posit64 & [source:string]`. It remains nominally a `Posit64` while requiring the added field

Structural object intersections merge requirements by field name. A field present on only one side is retained. For a field on both sides, the required type is the intersection of the two field types. The mutability declarations must agree; mutable and const requirements for the same field are incompatible rather than silently selecting one. If a required field type normalizes to `never`, the entire object intersection is uninhabited and a declaration that presents it as a constructible type is rejected.

### Generativity of type expressions

- `type of T` is the sole generative type expression. Each evaluation mints a distinct nominal child. Type expressions are ordinary expressions and function bodies re-evaluate on every call, so a factory containing `type of` returns a fresh type per call
- `A & B` never mints identity. Purely structural intersections use duck-typed equality; intersections carrying a nominal component retain that existing nominal identity. If a combined structural type needs unique identity, write `(type of any) & [...]`
- binding a generative result once gives it stable identity; aliasing or structurally strengthening that binding does not mint again

```dewy
Tagged = (T:type) => T & [tag:string]
TaggedInt1 = Tagged(int)
TaggedInt2 = Tagged(int)  # equal to TaggedInt1: the body contains no generative expression

FreshTagged = (T:type) => (type of T) & [tag:string]
Fresh1 = FreshTagged(int)
Fresh2 = FreshTagged(int) # distinct nominal types
```

- generics do not change this: genericizing an expression is sugar for making it a function taking a type parameter. Re-evaluating a body containing only intersections produces an equal structural type; re-evaluating a body containing `type of` mints a fresh type. Generic instantiation is not implicitly memoized
- type annotations (on parameters, returns, bindings) are conceptually evaluated once, at typechecking time — checking happens once even if the function is called many times. Default values, by contrast, are re-evaluated on every call (so `(a:array = []) => ...` gets a fresh array per call, avoiding the shared mutable-default trap). A generative type expression in default-value position therefore mints a fresh type per call, consistent with both rules
- builtin parameterization like `array<int>` is non-generative: parameterizing an existing type is partial application on the type object (narrowing), not minting a descendant. The dividing line is simple: only `type of` mints

### Constructing nominal and hybrid values

- a unit-like nominal type has one canonical inhabitant, written with the type's own name. `MyCustomError = type of error` can therefore be returned as `return MyCustomError`; an explicit `MyCustomError()` spelling is not currently part of the design
- it remains open whether the type value and this canonical inhabitant are literally the same semantic object or share only the spelling selected by type/value context
- a hybrid nominal/structural value is constructed by applying the type to its object portion: `MyComplexError[extra='context' fields=42]`. The object literal must provide every required field with a compatible type, and the result carries the hybrid's nominal ancestry
- structurally strengthened aliases use the same construction form and require the combined fields. They are not separate nominal variants: `Base | (Base & Extra)` normalizes to `Base`
- a pure nominal descendant is not automatically unit-like merely because it declares no object fields. A representation-bearing parent may require a payload; for example, `UserId = type of int` describes an integer-like nominal descendant rather than a singleton

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
