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
  The full checker still needs to resolve source alias declarations and
  route source applications into this entry point.
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

## Verification checkpoint

The full suite passed with **1,807 passed, 10 skipped** after native
expression/length proofs and index validation. The 4,356-pair native
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
