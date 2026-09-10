# Native compiler work

This records verified progress, not a claim that the Dewy compiler is already
self-hosting. The Python compiler remains the seed and behavioral reference.

## Order of work

1. Restore inline parser explanations and use module namespaces. Fix any
   hosted bugs exposed by ordinary module-local type names.
2. Separate explicitly declared array contracts from current length facts.
   Express arena index relationships using checked refinements, preserving
   invalidation on replacement and truncation.
3. Port types, binding/scope resolution, checked HIR, and semantic analysis in
   executable slices. Carry over hosted placeholders and pending designs next
   to their implementations. Unsupported inputs must be diagnosed honestly.
4. Port representation analysis and µDewy lowering/emission, followed by the
   compiler invocation, analysis, test, and debug interfaces.
5. Build the µDewy compiler from its own sources; build Dewy with the hosted
   seed, then use native Dewy and native µDewy to rebuild both compilers. Test
   subsequent generations and the language regression corpus.
6. Package verified native compilers and libraries, wire release artifacts and
   installation to that package, and test installation without Python.
7. Continue clearly settled language features; update reference material and
   stress-test with libraries and examples.

## Current state

- Native module validation now precedes executable emission: it checks
  proofs and integer representation, removes discharged witnesses, and
  validates startup against the entry module's actual `main` binding.
  Function signatures preserve mathematical `int` until bounds analysis;
  the integration suite rejects an otherwise silently wrapping overflow.

- Native dictionary/set lowering covers hashing, probing, insertion,
  replacement, growth, tombstones, compaction, views and container algebra.
  Place arguments cover bindings, fields, indexed elements, forwarding,
  and whole aggregate replacement. The expanded driver executes **156
  programs**, plus invalid calls and unresolved-proof rejection cases.
  Native allocations still use process-lifetime storage; native ownership
  cleanup, closures and full runtime string/reporting support remain needed.

- Container membership records literal evidence at expression evaluation,
  preserving an earlier operand's value across a later mutation. Six native
  cases cover unions, intersections and rejection of unavailable keys.
  An abstract integer can explicitly convert to a fixed width while keeping
  the conversion for the bounds visitor to prove.

- The native checker successfully checks the complete tokenizer source and
  all 17 prelude modules (625 seconds in the latest measured run). This checks
  source types; the paired native rebuild is still pending. Reflexive subtype
  queries now bypass normalization, with the type-algebra differential suite
  passing after that change.

- The native bounds visitor now connects evaluation snapshots, refinements,
  indexing, slices, array mutations, branches, function bodies, and loop fixed
  points. Thirty source programs agree with hosted validation. Separate tests
  cover 432 slice cases and index diagnostics, including saved indices whose
  source binding changed later. Scoped breaks and continues discard local
  facts. Module validation and representation selection are being connected
  before executable emission; prototype check insertion remains pending.

- Native union-field legalization passes the complete lowering test driver,
  including exception forwarding, different record offsets, mixed result
  types, and evaluating a receiver once. The driver executes 124 programs.

- Hosted retained string reads now copy narrowed cell payloads before their
  owner leaves scope. Dictionary lookup temporaries release their independent
  payloads; fixed-length arrays release optional/union elements in both raw
  and descriptor storage. Repeated-call memory regressions pass. The latest
  non-bootstrap checkpoint passes **1,723 tests, with 10 skipped**.

- The native checker now retains string methods after literal exclusions,
  accepts literal-string enums in interpolation, and emits common-field
  access for record unions, forwarding exception alternatives unchanged.
  Focused native checks include missing-field rejection and optional results.
  Checking the tokenizer's own source with the complete prelude is in progress;
  this is a source-checking milestone, not a self-rebuild claim.

- Hosted dictionary compaction releases dead entries and moves surviving
  handles without releasing their old slots a second time. Fresh `.values`
  arrays use the same temporary/ownership transfer as returned arrays.
  Record, string, and optional-record dictionaries retain independent copies
  through removals and reuse memory across repeated compactions; 57 focused
  ownership, array-release, union-container, and dictionary-proof tests pass.
  The full native prelude check now passes in 238 seconds with about 3 GB
  peak RSS, down from roughly 32 GB before the preceding ownership fixes.

- Native comparison transfer connects interval bounds with stable value and
  length routes, including affine offsets, index propagation, nonzero facts,
  and strictness recovered from excluded equality. A compiled test covers
  all feasible pairs in 432 bounded numeric cases plus relational routes.
  Traversal must still invalidate historical predicates after writes before
  feeding this transfer; the complete bounds controller remains in progress.
  The short-circuit path kernel now carries that invalidation through `and`,
  `or`, `nand`, and `nor`, joins alternative states, and revisits conjunctions
  without resurrecting predicates invalidated by later writes. Its compiled
  tests cover both outcomes of each operator, impossible paths, and a later
  assignment that invalidates an earlier operand. Atomic proof transfer is
  supplied as a typed function argument.
  Expression interval transfer now consumes evaluated child snapshots for
  scalar reads, arithmetic, casts, field contracts, lengths, and slices.
  Mutation removes symbolic identities while preserving already evaluated
  values; 128 numeric/length queries match the hosted evaluator, with added
  tests for arguments read before a later write. Selected function-result
  contracts transfer argument intervals, order/index facts, and slice-window
  bounds, and return compound boolean promises to the predicate traversal.
  Compiled tests cover conditional/unconditional promises, impossible paths,
  and invalidation of historical argument values. These kernels still need
  the complete effect-ordered bounds traversal before native compilation.
  Short-circuit transfer is now generic over its callback's analysis data,
  passed by place. The hosted compiler preserves explicitly callable generic
  parameters instead of converting their arguments to signature strings;
  recursive callbacks and positional/keyword calls execute successfully.
  The native atomic predicate driver connects those paths to comparisons,
  boolean bindings, negation, selected call promises, and narrowed result
  members. Its compiled integration test covers chained length bounds and
  historical-value invalidation. The current hosted non-bootstrap regression
  checkpoint passes **1705 tests, with 23 skipped**, after the lifetime and
  generic-callback changes.

- Hosted cleanup now releases owned aggregate payloads in record fields and
  array union cells, including recursive aliases. Brace-less return, break,
  and continue arms run scope cleanup. `clear` and `truncate` release their
  discarded elements; optional string-array copies own independent strings.
  Thirty focused union/string tests and a further 61 ownership/object/binary
  checks pass. Repeated record and union-array copies reuse released arena
  storage after warmup. Local union cleanup distinguishes prepared frame roots
  from owned handles; replacements compute their value before releasing the
  old payload. Optional record elements use the existing owned-cell layout.
  String returns use the union copy rule without a second copy/transfer path.
  A further 148 container/string regressions and 27 focused local/recursive
  checks pass (including the updated return-copy assertion). The full prelude
  still checks in 240 seconds after the first cleanup changes; larger memory
  measurements are being repeated with local-cell cleanup included.
  Field and whole-object replacement now share copy-before-release behavior,
  including implicit receivers and checkpoint restoration. Fourteen lifetime
  cases verify repeated restoration and self-assignment without arena growth;
  35 place/string and 85 numeric/container regressions pass. Native rebuilding
  exposed a returned match-string alias freed with its cell; string escape
  classification now follows that owner and copies the returned payload.
  The isolated non-bootstrap suite passed 1,695 tests with 23 skips; its four
  failures were two field-temporary name assertions and two UTF-8 return/debug
  lifetimes. All four pass in the subsequent 32-test focused run. Union string
  copies now account for owner zero also describing frame storage. A moved
  array result empties its source length before statement cleanup, preserving
  transferred element handles; 21 ownership/move checks and the native
  signature reconstruction probe pass.

- Native module assembly retains dependency initialization order and binding
  identities, emits each loaded module once, and selects only the entry
  module's `main`. Reachability keeps callbacks and recursive functions while
  omitting unused function bodies. Four compiled graph cases cover shared
  dependencies, same-spelled functions, imported `main`, and unused bodies;
  an unsupported imported body reports its own source path. This remains a
  legalization kernel until the complete proof driver is connected.

- The function-region/checkpoint regression suite passes 1,954 tests, with
  23 skipped. Two code-shape assertions now expect region-backed dynamic
  copies; the remaining quota-interrupted tests passed on disk-backed storage.
  Later hosted enum fixes pass 66 focused numeric and ownership regressions.
  Array-field mutation retains its declared store contract after `clear`,
  including implicit method receivers and subsequent pushes in a loop.

- Native legalization executes 121 source programs through native checking,
  lowering, emission, and µDewy. Beyond scalar functions/control flow, it now
  handles scalar arrays with independent declaration/assignment copies,
  keyword-ordered argument copies, callee defaults, arena-backed returns and
  globals, and push/pop/insert/reserve/truncate/clear. The allocator is the
  existing prelude implementation, selected by binding identity. A separate
  stress case verifies growth through 100 byte elements. Arrays also own record,
  nested-array, and callable elements. Cached monomorphic copy helpers handle
  recursive minted record hierarchies without expanding the compiler stack.
  Immutable strings retain UTF-8 bytes and grapheme boundaries through
  indexing, half-open/nested slices, comparisons, arrays, fields, and returns;
  converting to a byte array makes an independent mutable value.
  Optional/general union cells retain stable member tags through narrowing,
  fields, arrays, arguments, and returns. Projected field facts survive sibling
  writes and are invalidated by field/parent replacement; three stale-read
  programs are rejected. Narrowing changes reads, never the physical write
  representation. Field writes evaluate their source once before copying it.
  Range, array, record-element, and Unicode-grapheme iterators now execute,
  including empty inputs, continue/break, filtered captures, and nested
  captures. Iterator setup remains local to the reached arm and advancement
  precedes each condition; exhausting an array never reads past its end.
  Conjunctive multi-iterators advance their participating sequences before
  evaluating the combined condition. Literal enums preserve tags across
  variables, fields, arrays, calls, casts, and arithmetic; numeric operations
  decode their values first. String alternatives sharing a union tag compare
  their payload for literal tests. Constant scalar promises discharge only
  when proven, preserving effects and every unresolved obligation. Two such
  unresolved/refuted programs still stop before unchecked legalization.
  The Dewy Unicode library now validates UTF-8 and streams extended grapheme
  boundaries using generated Unicode 16 tables. Its compiled library test
  matches all 1,093 conformance rows, seven additional strings, and twelve
  malformed UTF-8 inputs. Wiring this helper into native concatenation and
  decoding remains subsequent backend work.
  Frame/arena lifetime optimization and release insertion remain pending.
  These tests enter below the full proof driver; they are not a public
  unchecked compilation route.

- Ambiguous-expression transactions checkpoint mutable checking state while
  retaining the session's read-only source forests. All 156 valid and 86
  rejected source comparisons pass, including slice-bound metadata. The
  hosted seed also moves runtime-sized compiler copies into its existing
  function region, including parameter-copy prologues. This fixes stack
  exhaustion from multi-megabyte value copies without changing explicit
  source `__alloca__` calls. Thirty-one ownership/region regressions pass,
  including large arrays and records under a 1 MiB native stack limit.
  Ambiguity trials now skip restoring the untouched first candidate and
  retain a final successful candidate directly; all 242 source comparisons
  pass. String clones copy established grapheme boundaries instead of
  re-segmenting their bytes, with 42 focused string regressions passing.
  Exact constant quantity arithmetic now preserves and composes dimensions;
  seven valid and five invalid source/HIR comparisons pass. All 17 ordered
  prelude modules check natively in 240 seconds. Peak memory was about 36 GB,
  so copy lifetimes remain a practical concern before larger bootstrap inputs.

- Native layout queries match the hosted layouts for primitive and nested
  fields, scalar/handle array strides, inline union cells, and brand storage
  through parent and structural views. Descriptors use typed byte offsets.
  Record lowering now executes nested fields, independent scalar-array
  members, callable fields, parent/child type tests and copies, and record
  parameters/results. Dynamic copies use the selected brand's field schema,
  preserving child fields without reading the reserved size of a larger sibling.

- Contextual function expectations now supply unannotated lambda parameter
  types before checking their bodies, including array sort keys. Explicit
  annotations retain their meaning. Five accepted and two rejected native
  cases agree with the hosted checker. Inherited bare record defaults retain
  the earlier field contract while preserving literal identity for the
  compatibility check; scalar field predicates are still checked at use.
  Physical type products and rational part types also resolve natively.

- Profiling found whole-source token copies in declaration and member reads.
  Scoped read helpers removed those copies from the expression/type visitors;
  the source type comparison passes, and the same full-prelude diagnostic
  went from approximately 499 seconds to 297 seconds. Concrete type tests now
  select generic branches with the existing DecidedBool HIR; five accepted
  and two rejected native cases pass. Selected blocks keep their lexical
  scope, and an effectful operand is never discarded by this optimization.
  Full-prelude checking is progressing through reporting and I/O; expression
  conversion parity and the complete proof driver remain in progress.

- BigInt aliases and annotated numeric boundaries use the prelude's own type.
  Exact constants materialize into canonical base-2^32 limbs; signed and
  unsigned words call the ordinary prelude conversion helpers. Oversized
  unannotated integers retain their abstract type for representation analysis.
  The native constant and boundary comparisons pass. Runtime arithmetic
  dispatch and integration with the complete proof driver remain pending.
  The native representation pass now promotes oversized literals and flagged
  arithmetic, propagates abstract local storage through accumulators, retains
  word parameter/result boundaries, and reports refuted narrowing. A native
  HIR fixture agrees with hosted binding propagation and checks these errors
  and preservation of effectful singleton expressions. Generic re-instantiation
  is carried over through the checker's cache and still needs execution coverage.

- Literal-member equality now uses ordinary union tag narrowing, so an early
  `if value =? 0 return 0` excludes BigInt's zero alternative afterward.
  Source readers borrow the token arena for a single query rather than copying
  a whole source forest. Three native source comparison groups pass together.
  Contextual record construction selects a union member before checking its
  fields. Four record cases and two rejections pass, and the full numeric
  prelude through BigRational now checks natively. Remaining portable
  libraries and target services are under investigation.

- The full regression suite at the type-product checkpoint passed with
  **1,948 passed and 23 skipped**. Subsequent array/record lowering and source
  checker changes have the focused verification above. The earlier retained
  container-slice lifetime bug and outdated code-generation expectations are
  fixed and included in that full run.

- Native µDewy emission accepts lowered HIR expressions, statements, function
  units, globals, ordered startup, and an entry wrapper. Twenty-two expression
  forms match hosted spelling; emitted direct/startup/empty programs compile
  and execute. The command-line wrapper accepts a lowered argument prologue;
  argument construction and debug metadata still need their lowering passes.
  This is an emission boundary, not yet a source-to-executable compiler.
  Its binary-literal test exposed a hosted lifetime bug: views of static text
  still have temporary descriptors. Retained views now get independent storage;
  character and slice regressions execute through reused loop regions.

- Native bindings retain literal string types unless explicitly widened by a
  storage contract, matching hosted reassignment behavior. Fixed and rational
  zero comparisons expose payload field facts. The numeric prelude checks
  through fixed-point operations; arbitrary-precision library checking is the
  next frontier. Numeric contracts, text, and source checks pass together.

- Native decimal reals and decimal exponents retain arbitrary-precision exact
  fractions. Arithmetic and comparisons fold those constants, including exact
  integer division; division has no obsolete same-type result signature.
  Runtime rational materialization remains pending. Source intersections such
  as `int64 & ~0` become value refinements, while excluding literal union
  members selects the remaining alternatives. Numeric constants/contracts,
  existing source values, and matches pass in a four-group native run; the
  source-type comparison passes separately with the new exclusion forms.

- Native based strings pack power-of-two radixes into exact bytes, retaining
  the hosted reserved radixes and padding rules. Byte materialization, indices,
  lengths, compile-time path constructor views, and `$include_bytes` now check
  through HIR. Literal path views reuse their declaring type's method bindings.
  The native module loader checks the ordered prelude through strings, arrays,
  paths, Unicode's embedded case-folding table, and math. Callable intersections
  retain ordered overload alternatives and their selected methods.

- Hosted call lowering completes earlier operands before executing a later
  argument's preparation. Copy barriers account for direct place arguments and
  later nested mutations; already completed calls do not force new snapshots.
  Primitive compound updates use ordinary operator lowering, preserving bitwise
  spellings, unsigned division, and fixed-width wrapping. The native match suite
  passes again after its full-suite regression exposed the operand-order bug.

- Native module graphs accept an ordered prelude, retaining library binding
  identities while allowing module declarations to shadow inherited names.
  Target queries select platform branches and prepare their imports; ordinary
  literal booleans keep ordinary flow semantics. File directives retain
  no-prelude/prototype policy and enforce target restrictions. Prototype policy
  still awaits the complete proof/representation driver. The graph comparison
  checks exported declaration contracts, not the hosted registry's separately
  retained singleton initializer types. The filesystem and process foundations
  now both check through this loader. The complete prelude remains in progress.

- Array membership and set conversions call their ordinary lexical library
  helpers. Range membership shares exact step/open-bound normalization with
  iteration, folds exact queries, and retains runtime membership HIR. Generic
  instances precede the module statements that call them. Five native source
  comparison groups pass together (targets, library calls, ranges, existing
  source forms, and inference); the prelude and module checks pass in a separate
  three-test run. These are HIR comparisons, not a native executable compiler.

- Native text materialization tracks UTF-8 byte, scalar, and grapheme lengths;
  checked byte decoding, word-shape transmutes, fixed integer limits, and
  lexical string methods now reach checked HIR. Error mints denote singleton
  values; contextual unit-like records use their ordinary constructor defaults.
  Blocks apply result expectations to their expressed result, preserving void
  statements and explicit returns. The text comparison covers 20 accepted and
  eight rejected programs, including complete string and array library sources;
  the unit comparison covers 13 accepted and four rejected programs, including
  the Linux filesystem foundation. Native lowering remains separate work.

- The hosted seed borrows array fields at proven read-only call boundaries.
  Storage-root tracking preserves value isolation when another argument, or a
  nested call while evaluating arguments, exposes that root as a place. Five
  execution regressions cover direct/indexed/named field arguments and aliasing;
  the repeated-read cases run under a 128 MiB memory limit. Related regressions
  pass in focused batches of 31 and 143 tests. This avoids unnecessary copies
  using the existing ownership model; it introduces no allocator design.
  A subsequent fix distinguishes disjoint record fields for both array and
  object value arguments. Unknown indices remain conservative; a place into
  the same array field still forces a snapshot. Eight execution regressions
  and related place checks pass in a 31-test batch, with 146 further array,
  object, effect, method-barrier, and string-retention checks passing separately.

- Native record methods now compile into hidden functions with lexical member
  bindings, static/instance receivers, direct mutation barriers, and inherited
  method ownership. Constructor overloads participate in ordinary argument
  dispatch alongside field-wise construction. Function-typed protocol slots
  supply expected return contracts, renamed by parameter position and then
  attached to binding identities. Record names retain carried brands through
  family and structural views. Focused comparisons cover 25 method programs
  and 12 rejections, nine constructor programs and five rejections, ten name
  queries, and seven slot implementations with two rejections. Those groups,
  function inference, matches, and the existing source comparison pass together
  through a reusable native file-driven checker. Generic record methods and
  extracting a receiver-bound function retain explicit pending diagnostics.

- Native match checking now resolves typed, catch-all, record, and sequence
  signatures into ordinary conditional HIR, evaluates non-name scrutinees
  once, and scopes pattern bindings to their arms. Thirty-five valid and
  twenty-two invalid programs agree with the hosted checker, including
  integer guards and holes, late minted descendants, and correlated tuple
  patterns. Both implementations now keep each tuple arm's product separate;
  the hosted fix also executes mixed-pair fallbacks in its native regression.
  A shared flow-result rule handles literal/block results and rejects mixed
  void/value branches. Positional record arguments use their expected shape,
  and excluding a descendant preserves its family's readable structure.

- Native assertion checking covers `$assert`, `$runtime_assert`, `$expect`,
  and `$fail`, with compile obligations, failure-only messages, continuation
  facts, and collected warnings. Nineteen accepted and fourteen rejected
  programs agree with the hosted checker. Runtime reporting remains deferred
  HIR for the native lowering stage. Nested membership tests retain the key
  proof without assuming their search-position temporary escapes the test.

- Function result inference now collects explicit return sites independently
  for each function. It rejects mixed bare/valued returns, valued returns
  with reachable fallthrough, and unused expressed values before returns.
  Single boolean predicates retain parameter type, numeric, and length facts
  on their inferred signatures; callers recover their branch implications.
  Call expressions shed call-specific result refinements while signatures
  retain their proof contracts, using the shared result-type view. Unannotated
  functions remain order-dependent; complete signatures allow forward reads.
  The focused comparison includes inferred and explicit refined results,
  nested functions, predicate calls, and defining-scope parameter defaults.

- `semantic/value_sets.dewy` supplies exact integer coverage for match arms.
  Sorted disjoint intervals retain holes, unlike the convex bounds used by
  flow analysis. Forty native comparisons exercise union, intersection,
  exclusion, coverage, and counterexamples with unbounded and bigint endpoints.

- `semantic/check.dewy` begins the source value visitor: stable runtime
  bindings, literals/arrays, builtin dispatch, contextual conversions and
  refinement obligations, typed and forward-declared functions, returns,
  conditional expressions, and type-test narrowing. Branch read alternatives
  are separate from declared store contracts. Its first comparison covers
  154 source programs and 86 invalid programs. Short-circuit boolean HIR,
  record construction and lexical defaults, member reads/stores, function
  defaults, and enclosing-scope assignments now share this visitor. Known
  sequence lengths remain singleton types. Place arguments preserve storage
  contracts and reject overlapping routes; array methods share their signature
  table and update exact length views. Inferred arrays become growable on use,
  while explicitly fixed arrays keep their contract. Bare function names call
  the function, and `@fn` retains its value. Compound assignments and contextual
  call-result obligations preserve their selected operations and conversions.
  While-style loops, static integer ranges, array/string iterators, guarded
  counters, and conjunctive iterator groups now enter HIR with scoped targets.
  Loop exits respect function boundaries. The visitor drops facts the next
  iteration can invalidate and keeps borrowed record elements read-only.
  Comparison checks include iterator bounds, target types, and exit levels,
  rather than only the module's result type. Advanced iterator formulas,
  unpacking, runtime range ends, and scope-metatag exits remain to be added.
  Shared binding/flow shapes sink parser ambiguity to the competing values.
  Each candidate checks in an isolated compilation snapshot; exactly one
  successful candidate commits its bindings, types, HIR, and facts. Computed
  fields now work in declarations, defaults, constructors, and iterators.
  Dictionary literals, constant set literals, entry stores/lookups, membership
  guards, `get`/`pop`/`clear`/`add`, and fresh container views now enter the
  shared HIR. Literal and copied membership facts have stable key identities;
  branches intersect them and writes expire affected binding/member routes.
  Total dictionaries prove finite key coverage at their conversion boundary.
  Concrete call signatures contextualize literal arguments, including finite
  dictionary key types. Homogeneous array inference uses the same entry checker.
  The comparison checks lookup proof/slot metadata and removal optionality too.
  Dictionary unpacking and set iteration share the ordinary iterator HIR.
  Iteration proves the current key, drops positions that compaction may move,
  and rejects mutation of the iterated container. Unpacked records obey the
  same read-only borrow rule as array elements. Set algebra, dictionary union,
  and string equality/concatenation retain their specialized HIR operations
  and literal folding. Membership survives view compaction while cached entry
  positions expire, including across short-circuit guards and const captures.
  Generic functions share the type-alias parameter scope and ordinary call
  inference. Concrete bodies resolve in their defining source, cache by full
  type identity (including defaults/methods), and register before body checking
  so recursion reuses the same instance. Hoisted bodies remain with the module
  that first requested them; native namespaces export source declarations.
  Sequence indexing binds `end` locally, records constant positions, and
  rejects known invalid indices. String slices retain their ranges and known
  lengths; exact array slices expand to element reads, matching the hosted
  shape. Dynamic array slicing and stepped slices retain the hosted pending
  work. Array element stores preserve lengths and follow the complete storage
  route when checking const bindings and iterator borrows. Compound indexed
  stores remain pending until their read and write share one evaluated route.
  Primitive type spellings do not implicitly introduce runtime value bindings.
  Comparisons include instance counts/signatures, bounds, recursion, nested
  instantiation, lexical shadowing, and invariant refined array elements.
  Runtime set conversion and automatic library installation remain separate work. `key_facts.dewy`, `container_state.dewy`, `container_values.dewy`,
  and `container_methods.dewy` keep those transfers outside the source visitor.
  This is an intermediate HIR entry point, not yet a
  compiler driver: the remaining value forms, proof validation,
  representation selection, and native emission are still required.
- `semantic/modules.dewy` loads file-relative module graphs into that shared
  session. Namespace and selective imports retain original declaration ids;
  qualified type names and constructors use lexical namespace bindings, so
  parameters can shadow an imported namespace. Native tests cover normalized
  path aliases, single initialization, missing exports, and import cycles.
  Target-selected imports, automatic prelude installation, dynamic path
  evaluation, and filesystem symlink identity remain driver work.
- Hosted and native initialization analysis follow callback origins only for
  values that may themselves be callable. Scalar and aggregate arguments,
  including their non-callable unions, no longer expand every path through
  recursive record producers. Callable fields and optional callbacks retain
  their initialization checks. The focused hosted checks pass (34 existing
  and graph tests plus two callback regressions), as does the 17-case native
  initialization comparison.
- Hosted union destinations preserve machine-integer to bigint payload
  conversion, including optional values evaluated once. Bigint's existing
  decimal formatter now participates in interpolation and `as string`,
  including optional members and container elements. Dedicated execution
  tests cover unsigned maximum, zero, absence, large decimal text, and retained
  string lifetime; the conversion also passes 63 numeric/union regressions,
  and string formatting passes 44 related regressions.
- Hosted short-circuit continuations join mutations from the evaluated and
  skipped paths. Bounds evaluation composes value blocks and conditional
  expressions without replaying effects; scoped expression blocks share the
  existing conditional-result lowering. Named argument/field classification
  retains ambiguities inside their values, and synthesized assertion helpers
  resolve their original prelude binding rather than a shadowing local name.

- `semantic/context.dewy` owns source modules, syntax references, lexical
  scopes, types, HIR, and mint registries for one compilation. Deferred
  defaults and methods retain their defining source and scope.
- `semantic/type_check.dewy` now visits parsed source types: primitive and
  literal types, containers, immutable records, field contracts, function
  signatures and boolean/void result facts, generic/forward/recursive aliases,
  structural record intersections, and named object/error mints. Record
  composition shares its field replacement rule in `record_types.dewy`.
  Method bodies remain source references for later expression checking.
  Native source comparisons cover successful forms and rejection of invalid
  contracts, aliases, fields, and mints. Arbitrary default inference, module
  type imports, numeric library representation roles, and protocol method
  slot synthesis still require the full expression/module checker.
- Supporting hosted fixes preserve lexical record-default scopes through
  imports and generic syntax copies; keep nested place stores alive beyond
  the storing frame; distinguish lowered physical cell addresses from semantic
  narrowed bindings; and allocate optional cells for contextual flow arguments.
  Early prelude generics can use numeric helpers installed later in the same
  compilation. Function type signatures use the same fact-only result rule
  as function literals.
- Hosted big-integer calls retain their mathematical operator in HIR, so
  range guards and arithmetic evidence survive library lowering. Proven
  `bigint` values now cross fixed-width boundaries (implicit or `as`) through
  Dewy word-extraction helpers; unproven conversions remain errors. Unsigned
  widening preserves all 64 bits. Component writes invalidate the numeric
  facts of their containing value. Native HIR and constant/term analysis
  carry the same metadata, including floor division for big integers.
- The four parser phases were executable and parity-tested before this work.
- Parser namespace/comment cleanup passes all 152 parser parity tests. Type
  minting now distinguishes same-spelling declarations across modules, and
  module-qualified constructors use the ordinary type-construction path.
- `semantic/ty.dewy` and `semantic/subtyping.dewy` implement the initial
  type-expression algebra, DNF normalization, and subtyping for primitives,
  arrays, strings, exact literals, dimensions/quantities, callables, objects,
  paths, modules, metatypes, refinements, and recursive aliases. The native
  comparison covers 4,356 subtype pairs. Separate assertions exercise
  metadata preservation, recursive resolution, and minted inheritance.
  Library numeric representation roles still need registering with the
  checker before their additional materialization rules can be ported.
- Type descriptions retain defaults, methods, and proof binding identities
  separately from structural equality; interning does not discard them.
  `semantic/propositions.dewy` carries the hosted predicate descriptions.
- Generic aliases are separate compile-time constructor values, carried by
  module exports, bindings, and HIR type values without entering the subtype
  hierarchy as atoms. `semantic/type_aliases.dewy` checks application arity
  and parameter bounds in order, then substitutes the body; its comparison
  covers dependent bounds and shadowing by nested callable type parameters.
  The source type visitor now resolves alias declarations and routes their
  applications into this entry point.
  The supporting hosted union check preserves predicates already carried by
  a member when alternatives are added, while still requiring missing facts
  and retaining resolved identities of dependent terms.
- `semantic/brands.dewy` owns each compilation's minting order and runtime
  preorder intervals; its native numbering agrees with the hosted registry.
- `semantic/hir.dewy` carries the hosted HIR variants, including placeholders
  and the original call/default/partial-evaluation design notes inline.
  The native binding test exercises its node arena alongside
  `semantic/bindings.dewy`: shadowing, lexical lookup, stable member routes,
  and the distinction between a storage path and a fact-preserving view.
- `semantic/dispatch.dewy` ports call-shape matching, generic inference,
  substitution, indexed overload selection, and numeric promotion. The
  hosted comparison covers 23 dispatch cases; object/refinement/binary
  inference now uses the same representation boundary. Numeric-object
  materialization and the associated rational/fixed dispatch preferences
  still need their checker context.
- `semantic/builtins.dewy` carries all active builtin signatures, operator
  maps, intrinsic arities, dimension aliases, and promotion rules. A native
  comparison checks each against the hosted tables; pending operator and
  iterator designs remain inline comments.
- `semantic/type_queries.dewy` shares container shapes, named refinement
  handling, optional payloads, enum/general-union classification, and integer
  layouts. Native tags use structural keys rather than Python repr; their
  exact numbering is internal, and every ordering of the same alternatives
  produces the same tags (`none` first).
- `semantic/type_display.dewy` renders the current type algebra as Dewy
  syntax, including callable names/place parameters, boolean proof arms,
  field invariants, named refinements, containers, dimensions, and aliases.
  Recursive aliases remain named instead of unfolding during diagnostics.
  Its native comparison also exposed and now covers frame-backed string
  results mistakenly treated as movable owned values, conditional returns
  losing their storage requirement when the result size is unknown, and
  unsigned boolean array loads disagreeing with the signed all-ones
  representation of true. Optional result cells retain their payload moves.
  Source strings use Dewy-compatible Unicode escapes and escape interpolation
  openers, including openers sharing a grapheme with a combining mark.
- Value joins distinguish applicability from proof: accepting a refined
  target's base does not grant its predicates to a merged value. Recursive
  comparisons track visited pairs; complex variance cases retain the hosted
  conservative union behavior.
- `semantic/analyze/effects.dewy` computes transitive parameter effects over
  the HIR arena. Its native fixed point agrees with the hosted pass on value
  and place calls, recursion, overloaded and unknown callees, projected
  storage, dictionary mutation, and escaping views. Shared HIR traversal
  excludes type indices and binding metadata from expression children.
- `semantic/analyze/initialization.dewy` passes a native comparison on 17
  source programs. It retains callback tracking, recursive-call assumptions,
  dependency caching, and main's invocation rules. Diagnostics remain values
  for the caller to render.
- The bounds-analysis kernel is executable: `intervals.dewy` covers interval
  joins, widening, comparison constraints, arithmetic, and representation
  limits using bigint endpoints. `fact_state.dewy` uses explicit value/length
  terms and relational fact kinds instead of packed integer ids. Native
  comparisons cover state joins, narrowing, widening, affine preservation,
  invalidation, and vacuous predicates on empty arrays. The HIR transfer and
  proof-diagnostic parts of the bounds pass are still to be ported.
- `semantic/analyze/hir_facts.dewy` compares successfully with the hosted
  views of selected call contracts, argument binding, common and enclosing
  field invariants, loop-counter guards, and mutation targets. These are
  support for HIR transfer, not a completed bounds validator.
- `semantic/analyze/value_bounds.dewy` supplies declared storage intervals,
  constant-expression evaluation, immutable-container element bounds, and
  iterator/counter intervals. Its native comparison includes optional and
  mixed-width iterator targets, oversized constants, and place contracts.
- `semantic/analyze/relations.dewy` proves bounded chains of order facts and
  transfers relational evidence between copied values and sequence lengths.
  Its hosted comparison covers 384 proof queries, cycles, remainder/index
  evidence, fact copies, and normalization of element subjects.
- `semantic/analyze/term_facts.dewy` substitutes call-result contracts into
  named values, sequence lengths, member routes, and slice windows. Its 361
  native comparison cases cover comparison directions, value/length result
  projections, named arguments, selected overloads, and symbolic result
  seeding. End-relative subtraction chains retain the hosted restrictions.
  Affine assignment recognition, stored sums, and differences also preserve
  justified gaps; the comparison includes obligation-wrapped assignments and
  subtraction of a bounded suffix length.
- `semantic/analyze/element_facts.dewy` transfers universal element evidence
  through record stores, element reads, and array copies. Its native test
  checks weakening, missing guarantees, empty arrays, scalar nonzero/index
  facts, and projected routes. Declared element refinements are returned to
  the caller for the ordinary binding-refinement rule to seed.
- `semantic/analyze/refinement_facts.dewy` seeds proven scalar, nonzero,
  length, dependent-term, field, and parameter contracts. Immutable sibling
  relationships become route facts and field intervals; mutable records do
  not recover those relationships merely from their type's field metadata.
  The native comparison includes nested fields and address-space contracts.
- `semantic/analyze/length_facts.dewy` computes post-operation intervals and
  relational changes for push, insert, pop, truncate, and clear. Its native
  comparison exercises exact, ranged, and unknown lengths/counts against the
  hosted HIR evaluator; validation and element transfer stay separate.
- `semantic/analyze/length_proofs.dewy` connects relational evidence to
  expression bounds, in both directions. Its native comparison agrees with
  the hosted pass on 10,800 queries covering arithmetic offsets, end-relative
  indices, transmutation, remainder facts, and contracts on slice results.
  The evaluator supplies an interval snapshot at the query site; proof
  search does not evaluate effectful expressions again. These snapshots must
  not survive a change to the flow state. The full evaluator remains pending.
- `semantic/analyze/index_checks.dewy` uses these proofs to validate array
  and string subscripts and the indices of pop/insert calls. Its 224 native
  comparisons check success, constant-index hints for lowering, and failure
  titles, pointer messages, notes, and help text. They include empty/fixed/runtime
  sequences, grapheme lengths, end-relative indices, and index facts whose
  subject may still be negative. Results and diagnostics are values for the
  future validator driver, including its `$prototype` handling.
- The supporting hosted fixes include dictionary field stores, field-valued
  key facts with invalidation, runtime set literals, and optional array
  returns through the existing aggregate ownership path. Loop conditions
  discard incoming facts that the body can invalidate; raw-array lengths
  come from allocation analysis rather than an assumed descriptor layout.
- Declared index facts track current values and expire on mutation. Place
  parameters retain their scalar store contracts through recursive calls.
  Equality between unions with the same alternatives compares tags and
  payloads, evaluating both operands once in source order.
- Negation propagates predicate facts to the opposite branch, and key
  identity survives a refinement obligation. An unconditional loop with no
  break targeting it has no fallthrough. Runtime-length arrays can be
  replaced through places using existing owned arena storage; replacement
  copies before releasing the old value and updates the caller's cell.
  Runtime erasure normalizes unions when refinements merge alternatives.
- Numeric literals materialize into a union's unique compatible numeric
  object alternative, including `bigint | none`. Division bounds include
  zero when the positive divisor has no known upper bound.
- Prelude-cache restoration rebuilds Python syntax-address indices from
  restored objects. Unary operations update singleton facts through
  parentheses and literal-preserving casts, so later numeric materialization
  cannot recover the operand's old value. Both hosted and native µDewy count
  call-opening tokens when scanning condition parentheses; grouped guards
  retain short-circuit behavior even around nested calls and dereferences.
- String results depending on defaulted parameters use the existing caller
  region. The caller neither reads an absent argument to size a result nor
  repeats the default to discover its size. This also protects a default's
  newly constructed string when the callee returns the parameter directly.
- Dictionary lookup broadens union-valued elements into the result's tagged
  union, including `bigint | none`, and copies owned payloads before the
  dictionary can be cleared or replaced.
- Result contracts substitute known argument lengths using the ordinary
  comparison constraint rule. A lower-bound promise no longer incorrectly
  seeds an upper bound, and inequality promises do not imply equality.
- Length-changing array methods preserve declared maximum lengths as well
  as minima, including contracts on member routes. Assignments retain both
  endpoints for subsequent analysis. Guarded growth and shrinking are checked
  against the resulting length, not just against valid element indices.
  Relative length contracts are seeded and validated too. A shared transfer
  adjusts order and remainder gaps by the possible length change; shrinking
  drops coarse index facts but can retain stronger order evidence. Unknown
  replacement invalidates remainder subjects as well as their upper terms.
  Runtime truncation counts require a nonnegative proof. Mutation obligations
  without a supported `$prototype` check remain compile errors, not internal
  assertions or unchecked operations.
- Narrowed optional/general-union arrays keep their selected array
  alternative through content mutation and loop iteration. Whole-binding
  stores and place arguments still discard that selection. Mutating methods
  use the selected array's declared storage shape and retain its length
  obligations. Overlapping array alternatives with different predicates are
  currently checked conservatively against all of those predicates; choosing
  a union tag alone does not prove which predicate alternative held.
  The focused mutation/length/loop regression batch passes 27 tests.
- Iterator recognition uses the existing ambiguity normalization before
  binding loop targets, including `loop x in make().values` and guarded
  forms. Logical conditions can share either operand; binding targets retain
  their complete alternative readings. The iterable is evaluated once.
- Hosted lowering shares generated aggregate copy/cleanup helpers. Frame
  allocations stay in their owning frame; prepared-result and arena copies
  can call shared helpers. The expanded type test's emitted source fell
  from 43 MB to approximately 10 MB without changing ownership semantics.
- µDewy has an existing bootstrap with native backends and parity tests. Its
  release workflow currently builds with Python. `tools/bootstrap_udewy.sh`
  now builds two native generations from a supplied seed and compares them.
  Both native generations were verified byte-identical on Linux x86_64,
  including after the condition-parser fix.
- The installer still installs the hosted compiler. Switch only once the
  native package can fulfill that interface.

## Design boundaries

Array contracts and dependent index facts have been approved for development.
Use the existing refinement language where possible. A proof about an arena's
old contents must not become proof about a replacement just because the
binding name is unchanged. Append-only stability and element provenance are
different from merely proving an integer lies below a current length.

The exploratory `semantic/idiomatic_facts.md` is design direction, not a list
of settled new constructs. Any necessary provisional design (including
allocation) will be recorded here with examples and implementation limits.

No provisional language syntax or allocator design has been introduced yet.
The new [resource-exhaustion discussion](../semantic/resource_exhaustion.md)
remains an open design problem. Existing borrow/copy optimizations do not claim
to establish resource availability or a new failure policy.

## Verification checkpoint

The committed method/conversion checkpoint (`a297da0f`) passed **1,899 tests,
23 skipped** in a fresh checkout. Thirteen skips were SDL tests whose generated
artifacts were absent from that checkout; all thirteen passed separately in
the main workspace, leaving the usual ten unavailable-toolchain skips.
The record-method checkpoint passes seven native comparison groups
in 482.61 seconds. Its hosted seed also copies retained string reads out of
array/record storage before replacement can release that storage; six native
execution regressions cover direct, aliased, sliced, block, conditional, and
field reads. Related ownership checks pass in two focused batches (20 and 29
tests). The full-suite count includes those changes and the hosted conversion
overload fixes: three execution cases retain separate string/integer bodies
through structural declarations, minting, and inheritance. The subsequent
lexer diagnostic change passes 22 focused tests, including an unfinished
quote after 4,096 ordinary statements; its context reports stay concise.
The generic source visitor also matches the 126-program comparison; its 64
rejection cases pass through the native module loader. Imported generic
instances preserve their original lexical bindings. The subsequent sequence
comparison passes all **154 valid and 86 invalid programs**, including full
instance and index/slice metadata. The subsequent indexed
store borrow fix passes 33 focused tests, including native execution showing
that an explicit copy can change its array without changing the borrowed one.


The full suite passed with **1,837 passed, 10 skipped** after the source type
visitor, numeric helper instantiation, and optional-flow argument fixes.
The source comparison covers 49 valid forms and 13 rejected declarations.
The 4,356-pair native
type-algebra comparison allows 90 seconds under parallel load (its executable
takes about 24 seconds alone). Both native µDewy generations also match.
The call-term comparison's table-driven harness retains all 361 cases while
avoiding hundreds of separately emitted checks. The element-fact comparison
and loop-iterable regression are included in this full run.
The native refinement-fact comparison also passes, including
unknown sibling bounds that must remain unknown rather than imply a range.
The affine assignment/sum/difference comparison passes as well.
The native array-length transfer and source type-rendering comparisons are
also included in this full run. The focused storage/rendering batch passed
275 tests before the type-rendering checkpoint. Generic alias comparisons
now include application diagnostics, dependent bounds, nested binder
shadowing, and transport through module exports, bindings, and HIR. The
union-copy regressions also check stronger contracts and resolved term ids.
Temporary logs are not required to resume: the comparison programs are
generated by `tests/python_misc/test_bootstrap_*.py`.

## Correctness questions retained from the hosted implementation

Field predicates are excluded from record structural equality. For example,
two immutable records with the field `x:int64` compare equal in the type
algebra even when one field metadata entry requires `x >? 0` and the other
requires `x <=? 0`. The hosted `join` first constructs a syntactic union,
which discards the second equal shape before its proof-aware coverage test.
The surviving description therefore retains the first predicate. This is
verified at the hosted type-algebra API; source-level consequences still
need investigation. The bootstrap currently preserves that behavior, with
an inline TODO. Reconciling field proof metadata at joins is correctness
work, not evidence that one alternative's predicate holds of both values.

The hosted word bounds pass models `//` as truncating division, whereas the
bigint library implements floor division and the numeric reference describes
`//` as floor division. The bootstrap kernel currently explicitly reproduces
the word analysis's truncation; it must not accidentally inherit bigint
division semantics just because its endpoints are bigints. This existing
representation inconsistency needs a focused end-to-end follow-up.
