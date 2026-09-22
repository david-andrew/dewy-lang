# Phase 1 implementation checkpoints

Started 2026-09-20 from `be7d1b1a`. The scope is all of Phase 1 in
[ROADMAP.md](ROADMAP.md), with the correctness/parity closure checkpoint
first. This ledger records implementation and validation, not new language
decisions. Fundamental new directions still need review; obvious Dewy-aligned
extensions may proceed provisionally and are recorded here for David.

## Work remaining

- Correctness/parity: `nat_types` now passes through sound finite-loop
  reasoning. Continue explicit fixture manifests and fresh paired native
  checkpoints at integration boundaries.
- 1.1: complete copy reporting and explicit-copy policy across entry points;
  explicit aggregate copies and local places/views; last-use moves in both
  implementations; deterministic lifecycle hooks and move-only resources;
  measured scoped placement and copy budgets. Keep COW as a provisional
  fallback rather than changing value semantics.
- 1.2: bounded relational proof machinery, mutation/alias-aware facts,
  loop invariants, checked proof boundaries and auditable unsafe boundaries.
  Unsettled surface forms require design review; unsupported proofs must
  remain unknown rather than silently accepted.
- 1.3: effect vocabulary and propagation, effect polymorphism and contracts;
  errors remain return alternatives, separate from effects.
- 1.4: implement and test the settled juxtaposition, reserved-name,
  unit-nominal, and uniform-container decisions. Repair the right-side
  number juxtaposition correction is implemented and paired-tested:
  `(x+1)5` multiplies and `(f)2` calls or multiplies by the type of `f`
  (ROADMAP 1.4 item 1, corrected 2026-09-21). Preserve the decisions to
  keep type brackets and conventional export privacy. Keep the explicitly
  open byte-packing and Unicode escape questions visible.

## Strict-copy cleanup

The inherited uncommitted CLI-only `$explicit_copies` implementation was
removed on 2026-09-20, with its patch and tests archived under
`../dewy-build-artifacts/phase1-2026-09-20`. It depended on incomplete copy
notes, bypassed non-CLI compilation, and prescribed remedies that did not
yet exist. This abandons that partial implementation, not the approved
directive. Reintroduce the policy with the relevant semantic/lowering API,
explicit remedies, source provenance, and acceptance-parity tests. Existing
`dewy analyze` copy reports remain available.

## Validation discipline

Checkpoint: uniform set insertion is implemented in both checkers as
`set.push(value)`, with the old `add` spelling retained as an alias. Both
spellings use the same insertion and mutation rules. Hosted tests cover
execution and rejection of const mutation; the native compiler executes
the shared fixture with its expected result 42.

Checkpoint: both bounds analyzers compose transfers for small, statically
finite loops before falling back to widening. A shared exploration budget
bounds nested work; every reachable body entry participates in validation,
and break/continue exits are retained. This closes `nat_types` without
changing its expected result. It also carries exact array growth through
small fixed loops; general symbolic loop induction remains outstanding.
Comparison narrowing now retains observed field bounds when excluding a
value, so a nonnegative field unequal to zero is positive in either operand
order. Targeted checks passed, and a second-generation native compiler passed
all 11 cases in `tests/fixtures/phase1_parity_cases.json` against the hosted
compiler. The broader corpus passed 210/211 cases and exposed a native `$prototype`
builtin-identity mismatch: registered builtin arithmetic was mistaken for a
user-defined function. The corrected native compiler runs `prototype_panic`
with the expected panic status 102 and still rejects the shadowed-intrinsic
regression. Both cases are now in the focused manifest. A fresh full paired
run remains required at the next integration checkpoint.

Each implementation batch needs acceptance/rejection and independent
execution outcomes, with hosted/native agreement. Ownership batches also
need second-generation native execution. Run complete build/fixed-point
checks at integration checkpoints, not for every small edit. Maintain
separate timing rows for C-built and direct-built executing compilers;
30 seconds is the minimum native target and 10 seconds the stretch goal.

Checkpoint: explicit `.copy()` for arrays, records, dictionaries, and sets
is represented in HIR and both lowerers, with receiver evaluation once and
independent mutation. Existing record members named `copy` take precedence.
Copied numeric, length, and membership facts belong to the destination; an
inferred record initializer now seeds its field facts in both analyzers.
Copy notes carry an explicit-intent flag for the later enforcement policy.
The operation participates in hosted representation discovery and definite
initialization; owned and discarded temporaries are released, including
array results returned through another copy. The lifetime kernel reports
zero retained bytes over 100 repeated calls in both compilers. The native
second-generation compiler built in 48.63 seconds; the C-built seed's first
generation took 21.71 seconds. This remains above the direct-route target.
Hosted copy/report gates passed 11 tests. All 14 focused parity cases
passed against the second-generation native compiler, including independent
expected panic diagnostics; the fresh full 211-case corpus also passed against that compiler.

Design review: `PHASE1_DESIGN_PROPOSALS.md` separates reviewed proof/effect
direction from outstanding proposals. David approved `$proof` with direct
statement calls, checked termination/purity and erasure; `:> <P>` is proof-
only, while ordinary functions use `:> T & <P>` (including `void`). The
unsafe boundary is `$unsafe_assume cond [, message]`. Positive effect rows
are upper bounds, omitted rows are inferred, and `no_effects` is the preferred
empty-row spelling. Negative guarantees (`no reads<resource>` and `no reads`, rejecting empty
family arguments) are also approved. Effect identity declarations and
effect-parameter syntax still have details to review. Implementation is
pending; approval does not mark 1.2 or 1.3 complete.

Checkpoint: callable/numeric unions at juxtaposition now reject with the
explicit pipe-call and multiplication forms in both compilers, without
suggesting parentheses. A numeric token on the right starts a separate
expression. Coefficient multiplication and parenthesized calls retain their
distinct precedences. Hosted parser/semantic/ownership gates passed 67 tests;
a rebuilt native compiler rejects the ambiguous-union fixture and runs the
precedence fixture with result 42.

Checkpoint: loop analysis now proposes a bounded equality vocabulary from
exact entry values of changing bindings and their field/length routes. The
ordinary loop fixed point must preserve each candidate on every backedge;
branch and early-break exits still join their actual facts. Constant scalar
shifts transform both sides of order relations, preserving negative gaps
between matching increments. This proves parallel-array length equality and
length/counter growth through unbounded trip counts. Missing pushes and
early breaks reject. Ten targeted proof tests and all 21 focused parity
cases passed. The updated compiler builds using the preceding direct native
compiler (50.12 seconds); the second-generation build also took 50.12 seconds
and passed all 21 focused parity cases. Its fresh full corpus also passed
all 211 cases against the paired hosted snapshot.
The wider symbolic range-iterator and proof-boundary work remains pending.

Checkpoint: hosted descriptor-backed array locals now use the existing
stable-route borrow proof already used by native lowering and hosted record
locals. Read-only field reads allocate zero bytes across 100 calls. A source
or destination write keeps value independence, and returning the local or
storing it in a returned record still acquires independent storage. Twenty-
one ownership gates passed, with the escape kernel checked separately on
both direct and C backends. The shared native parity fixture also passed.
Explicit local `@` demands and mutable local places are still outstanding.

Checkpoint: explicit string `.copy()` now participates in both checkers and
lowerers. Returning a copy, storing it in a record or array, copying a fresh
result, and discarding a copy all retain the normal owner-word lifetime
rules. Copy notes distinguish explicit string copies; static strings and
fresh owned results can still avoid a physical clone. Twenty-six hosted
string/ownership checks passed, followed by all eight explicit-copy tests
including the string report check. The native lifetime fixture retains zero
bytes across 100 calls, and all 22 focused parity cases passed against a
new second-generation compiler. General union copies and strict-copy
enforcement remain outstanding.

Checkpoint: both parsers canonicalize digit labels (`x_12`, `x_1_2`, and
`x₁₂`; `x‾12` and `x¹²`) and the micro-sign/mu alias at t1, preserving t0
source text and spans. Letter labels and ASCII/Greek distinctions remain.
Hosted synthesized names that round-trip through Dewy source use suffixes
stable under normalization. Hosted emission encodes non-ASCII names without
colliding with source-written ASCII names, including calls and debug metadata;
native lowering does the same for descriptive debug symbols while retaining
its ordinary binding-id symbols. No µDewy syntax changes. Twenty-one token
checks, 15 t1 parser parity cases, and 48 hosted execution/synthesis/debug
checks passed. A rebuilt native compiler passed all 23 focused parity cases
and both ordinary and debug execution of the identifier fixture (42).
The direct seed built it in 55.82 seconds. The wider Unicode repertoire and
doubled-marker escape remain open, and no rule for them was introduced.

Proof-boundary prerequisite: hosted `:> void & <P>` now checks its facts at
each explicit return and fallthrough without expecting a runtime value from
the body. Native checking already handles this form. Both type displays
retain `void &` so ordinary function contracts are not printed as proof-only
`:> <P>` syntax. The fact-bearing procedure fixture mutates an empty array
and returns 42 in the native compiler; the hosted fact suite passes 25 tests.
The separate `$proof` marker and statement-call checks are still in progress.


Checkpoint: the initial `$proof` boundary is implemented in both compilers.
Proofs have explicit HIR/binding identity, fact-only returns, direct statement
calls, pure arguments, finite bodies and an acyclic call graph. They erase
only after validation; callbacks, first-class values, mutation/effects and
`$prototype` deferral are rejected. Named and keyword-only parameters and
imported proofs retain their contracts. Native snapshot codecs preserve the
new metadata. `$unsafe_assume` and source effect rows remain pending.

The same work fixes general fact-contract rules: dependent arguments are
checked after substitution (including literals), known order relationships
can settle assertions, and mathematical affine evidence is not inferred
from possibly wrapping word arithmetic. Native empty void procedures now
check fallthrough obligations. Replacing a nominal record in a loop no
longer reinstalls the first variant's field type on exit.

Validation: 109 hosted proof/fact/call/prototype tests, two native type and
comparison harnesses, 20 direct native acceptance/rejection cases, and all
33 focused parity cases passed. A native compiler rebuilt itself in 59.94s;
a subsequent native generation with the keyword-only contract fix built in
62.50s and executed the composed proof and variant-loop fixtures (42).
These are integration timings, not a claim to meet the under-30s target.
The wider 211-case paired corpus is running at this checkpoint.
Artifacts: `../dewy-build-artifacts/phase1-proofs-stage2-2026-09-20` and
`../dewy-build-artifacts/phase1-proofs-final-2026-09-20`.


Full-corpus follow-up: 208/211 paired cases passed. The three failures
(`place_slots`, `type_values`, `length_terms`) all exposed an identifier
normalization gap in native generated dispatch helpers: parser-normalized
`__dewy_brand₀` did not find its raw `__dewy_brand_0` alias. Hidden aliases
now use the same t1 canonicalization as their generated source. A fresh
native build (59.24s) executes all three with result 42; they are also in
the focused parity manifest. This fix changes synthesis lookup, not user
identifier semantics. Artifact: `../dewy-build-artifacts/phase1-synthesis-2026-09-20`.

Checkpoint: initial `$unsafe_assume cond [, message]` support now lands in
both compilers. Pure unknown facts enter the normal mutation-aware state;
the condition is erased, messages are static, and checked proofs cannot use
unchecked assumptions. Source audits survive folded conditions, unused
checked functions and prelude caching. Ordinary, debug and test builds write
versioned `.unsafe.json` sidecars; analysis also displays them. Empty reports
replace stale ones. Consumer coverage is deliberately conservative: checks
in the same function, not exact proof-dependency provenance. That refinement
remains required for the full audit milestone. Known contradictions are
explicitly unsupported while their policy is under design review.

Validation: 43 hosted unsafe/proof tests, 30 prototype/fact regressions,
eight native acceptance/rejection and JSON-escaping checks, and all 39 focused
paired cases passed. The native seed built the updated compiler in 60.04s;
this is an integration checkpoint, still above the performance target.
Artifacts: `../dewy-build-artifacts/phase1-unsafe-2026-09-20`.

Checkpoint: explicit `.copy()` now accepts unions whose alternatives have
builtin value-copy semantics, without hiding a declared `copy` member. Only
the active payload is copied, the receiver is evaluated once, and destination
stores can consume the snapshot directly rather than copy an extra temporary.
Both general tagged unions and optional aggregates retain normal ownership.

Validation: 60 hosted ownership/copy checks passed, including C execution,
member precedence, single receiver evaluation and zero retained bytes across
repeated mixed-alternative snapshots. Native generations built in 60.64s and
60.14s, both running the lifetime fixture with zero retained bytes and exit
42. All 41 focused paired cases passed against the second generation.
Artifacts: `../dewy-build-artifacts/phase1-union-copy-stage2-2026-09-20`.

Naming review: the source form is `$unsafe_assume cond [, message]`, replacing
the intermediate `$unsafe_assert` spelling. Unknown assumptions are accepted
and audited; proven-false assumptions are rejected, including contradictions
from a guard or a declared width. The optional message and all mutation,
erasure and proof-body restrictions remain unchanged.

Validation: 47 hosted assumption/proof checks passed. A fresh native compiler
built in 60.38s, executed the assumed-index fixture (42), rejected literal,
guarded and width-derived contradictions, and rejected the superseded spelling.
Artifacts: `../dewy-build-artifacts/phase1-assume-2026-09-20`.

Checkpoint: copy inventories now include hosted local array snapshots in
both raw stack and descriptor representations; the view/ownership kernel
reports four sites in both compilers (two escapes and two independent mutable
snapshots), with no copy for the read-only local. Native summaries now count
string copies too. `tools/copy_report.py --max-copies N` provides a static
site-count gate, and `--json` saves a versioned inventory. The tool rejects
malformed, partial or summary-inconsistent output before filtering files.
This verifies report transport, not completeness of all lowering paths;
additional coverage and compiler-wide budgets remain outstanding.

Validation: 18 hosted reporting/explicit-copy checks passed. Both hosted and
native inventories passed `--only readonly_array_field_view.dewy --max-copies 4`.
The native executable was the reviewed-assumption checkpoint, which already
contains the summary correction. Runtime allocation gates remain distinct
from these static site budgets.

Checkpoint: abstract range counters can now use inductively proved word
storage in both compilers. The proof covers the initial value and every
normal/continue backedge, including step headroom and nested bounds learned
from an outer counter. Failed candidate bounds are discarded before normal
validation; neither a circular assertion nor `$prototype` can justify wrapping
an otherwise unbounded counter. The native backend now rejects an unproved
unbounded numeric iterator instead of silently using word arithmetic.

Validation: 88 hosted range/loop checks, the native bounds harness, seven
native overflow/continue/circular-proof rejection checks, and all 45 focused
paired cases passed. Native generations built in 62.99s and 59.59s; both run
the nested-counter fixture with result 42. General bigint iterator lowering
and broader liquid inference remain open.
Artifacts: `../dewy-build-artifacts/phase1-counters-stage2-2026-09-20`.

Checkpoint: both compilers now check source `no_effects` and its desugared
`Effect<>` form. Public rows live separately from internal parameter-access
summaries and participate in callable subtyping, signature substitution,
native type interning and prelude serialization. Callback parameters also
accept the reviewed `f:(args):>Result & no_effects` shape. Unknown callback
behavior cannot satisfy the empty row. Defaults and direct-call dependencies
are included; purity does not imply termination.

The initial inference subset covers scalar computation, private scalar
mutation and read-only value access. Unsupported storage operations remain
unknown; returning a runtime-length `.copy()` cannot claim purity just because
COW may defer its allocation. Named source effects, negative source guarantees,
row generics, complete inferred callable rows, and a complete allocation model
remain outstanding. The native checker skips this pass when its type arena
contains no effect contracts.

Validation: 93 focused row/contract/proof/access checks and 53 signature,
generic, runtime-key and native type-factory regressions passed. Both native
generations execute the callback/private-mutation fixture (42); 19 native
acceptance/rejection probes and all 48 paired cases passed. Integration builds
were 64.11s and 69.42s, with other checks running concurrently; these are not
isolated performance measurements or a new fixed-point certification.
Artifacts: `../dewy-build-artifacts/phase1-effects-stage2-2026-09-20`.

Checkpoint: verified the settled unit-like nominal value rule across both
backends and compilers. The execution fixture returns ordinary/error sentinels
through unions, tests their types, passes their sole values as arguments and
preserves identity through imported aliases. A separate empty mint with the
same name remains distinct. This closes the Phase 1.4 verification item without
changing the language or its runtime representation.

Validation: 12 hosted nominal checks, x86/C execution, and execution with the
second-generation effect-contract compiler returned the expected result (42).

Checkpoint: the six reviewed names (`extern`, `intrinsic`, `none`, `void`,
`end`, `new`) are now reserved in source bindings in both compilers. The
check covers declarations, parameters, fields, methods, loop/unpack targets,
generic binders and import aliases. It distinguishes binding patterns from
match type patterns, so `<none>` remains valid; synthesized last-index bindings
also retain their existing role. `untyped` remains available to users.
Compiler/library locals and fields now use ordinary names (`limit`,
`intrinsic_call`, `replacement`, etc.). This changes the string replacement
keyword argument from `new` to `replacement`; positional calls are unchanged.
It reserves `new` without implementing the later axis-insertion feature.

Validation: all 104 reserved-name checks passed, including a Dewy validator
harness over 96 binding forms and x86/C execution. The related text/source-line
and fact regressions passed (108 checks); dependent-index and brand tests also
passed. Native generations built in 62.55s and 62.79s, both running the role
fixture with result 42. All 52 focused hosted/native paired cases passed.
Artifacts: `../dewy-build-artifacts/phase1-reserved-stage2-2026-09-20`.

Effect-cache follow-up: a typed snapshot now explicitly exercises nonempty
public permissions, a parameter-route exclusion, a symbolic row binder, an
empty row and an omitted row. Decode preserves each contract and re-interns
the signature at its original id. Three cache checks passed, including x86/C
execution and regeneration freshness. This verifies the IR/cache foundation;
it does not claim source support for named rows or row generics yet.

Named-effect checkpoint: both source checkers now resolve nominal resource
identities, caller-owned place slots and stored-field routes. Positive
`reads<Resource>` / `mutates<Resource>` rows are closed upper bounds;
`no reads<Resource>` and whole-family `no reads` retain open negative
guarantees. Empty family applications diagnose the distinction. Signature
display preserves rows, including exclusions. The new `no` prefix is confined
to effect contracts; old compiler/test locals named `no` are `false_value`.

Public analysis now substitutes place routes at direct and callback calls,
checks scalar place reads/writes, and preserves shared negative guarantees
across call-graph propagation. Taking an address does not itself read its
contents. Private scalar storage disappears at a call boundary, while unknown
operations and unproved aggregate transfers remain conservative. Recursive
routes widen only positively; truncating a negative route would be unsound.
Hidden method receivers shift effect slots, and binding a receiver does not
silently erase its possible effects. Row generics and full allocation/failure
modeling are still outstanding.

Validation: 85 focused row/contract checks passed, including x86/C execution;
21 method/function-value regressions passed. Three related native-analysis
harnesses also passed. Native source gates passed all 42 initial cases and
12 additional boundary cases (position-only parameters, method-slot identity,
malformed rows, and use of `no` outside contracts). The final native generation
built in 59.49s and executed the imported-resource/place fixture with result
42. This is a correctness checkpoint, not the sub-30s performance target.
Artifacts: `../dewy-build-artifacts/phase1-named-effects-stage3-2026-09-20`.
All 55 expanded hosted/native paired parity cases passed.

Row-generic checkpoint: `<E:Effect>` is kind-checked separately from ordinary
type parameters in both compilers. Callback contracts determine row arguments;
repeated constraints join, mixed `<T E:Effect>` signatures substitute both
kinds, and instance/cache identity includes the inferred row. Effect binders
cannot enter value types or runtime expressions. Unknown callback behavior
stays unknown. Static function handles require neither an external read nor
an aggregate transfer at a higher-order call.

The initial inference intentionally leaves underdetermined decompositions,
effect-polymorphic type aliases, negative row arguments, and callback-relative
place subjects pending. The last case needs subject scope preserved rather
than interpreting a callback's slot number as the enclosing function's slot.
These are conservative rejections/lost precision, not new source semantics.

Validation: 111 focused hosted row/contract/generic regressions passed,
including x86/C execution of mixed type/row generics. Nine native source
acceptance/rejection probes passed. Two cache checks passed (108.63s), verifying
row binder kinds/identities, binding values and instantiated row arguments
survive an x86/C snapshot round trip, plus generated-code freshness. Native
generations built in 60.74s and 60.09s and both executed the row-generic fixture
with result 42. All 58 expanded hosted/native paired parity cases passed.
Artifacts: `../dewy-build-artifacts/phase1-row-generics-stage2-2026-09-20`.

Copy-inventory follow-up: hosted same-union snapshots and union conversions
now report the copy that lowering emits; an explicit union `.copy()` does not
also become an implicit-copy note at the same site. Native ownership copies
of strings, including copies selected through the shared copy-kind helper,
now appear in the inventory. Recursive fields remain covered by their enclosing
aggregate-copy decision rather than counting each generated helper separately.
This closes specific reporting gaps; it does not claim the whole inventory
or `$explicit_copies` implementation is complete.

Validation: 24 hosted copy/report/source-provenance regressions passed. Native
generations built in 60.39s and 60.20s and executed the coverage fixture with
result 42. Native `analyze` reports both cell and string sites in that fixture.
Artifacts: `../dewy-build-artifacts/phase1-copy-coverage-stage2-2026-09-20`.

Copy-budget tooling now supports exact file/directory scopes and static
sites per thousand physical Dewy source lines. Zero-copy files contribute
to the denominator; malformed, partial, or source-unresolvable inventories
cannot pass a scoped gate. Both hosted and native summary formats are
validated before filtering. Nine tool regressions passed, and the real
hosted/native ownership kernel each reports four sites in 39 lines. Its
stable regression budget remains four sites; density (102.564 sites/kloc)
is supplementary and says nothing about runtime bytes or frequency.

Hosted string-move checkpoint: a single-use local holding an explicit string
snapshot or an owned call result can transfer into a binding, record, array
literal, push, or element/field store. Earlier views and loop backedges stay
conservative; frame descriptors never enter this path. The source slot is
cleared before normal cleanup, including for source-const bindings. Returned
views still retain independent bytes, with a conditional copy note. Move
collection also records returns during its first traversal instead of
rescanning the function for every transfer candidate.

Validation: 32 hosted move/copy/report regressions passed, including x86/C
execution, const storage, earlier views, repeated loop uses and zero retained
bytes over 100 calls. A measured element replacement allocates zero bytes;
disabling moves provides a positive allocating control. The existing second-
generation native compiler also executes the shared fixture with result 42.
No native lowering changed in this batch, so no new self-build was needed.

Borrow/move correctness checkpoint: an inferred local view now extends its
owner's liveness through that view's reads, transitively through further
views. Native borrowed getter results use the same dependency rule. Previously,
moving an array after its last spelled read could allow a destination write to
change a live snapshot of one of its records (99 instead of the required 42).
Both move planners now retain the owner when a later dependent read needs it.
Once the borrowed read is finished, the move remains available; direct whole-
value returns still transfer at function exit.

Validation: 69 ownership/borrow/native-lowering regressions passed, including
x86/C execution; two focused hosted borrow tests also passed. The native
expired-borrow kernel confirms zero allocation for the later transfer on both
backends. Native generations built in 63.80s and 62.84s; both execute the live
borrow and string-move fixtures with result 42. All 60 expanded paired cases
passed against the second generation. These are correctness integration
builds, still above the under-30s native target. A fresh broader corpus run is
starting against this fixed snapshot.
Artifacts: `../dewy-build-artifacts/phase1-move-borrows-stage2-2026-09-20`.

Hosted array-binding checkpoint: descriptor-backed locals can now take a
last-use array value, including an explicit `.copy()` result. Live borrowed
views, later named reads, loop backedges and exposed raw/unknown aliases keep
copies conservative. A heap descriptor transfers directly (including its
existing COW reference), with the source slot cleared; moving it no longer
allocates a second descriptor. Frame-backed storage retains the checked
adopt-or-copy path. Cleanup now releases an arena descriptor independently of
whether it still owns the buffer, fixing a 64-byte-per-iteration leak exposed
by the new transfer kernel.

Validation: 82 move, explicit-copy, sharing, ownership, provenance and lifetime
checks passed, including x86/C execution. The new binding kernel retains zero
bytes over 100 calls and executes with result 42 in the existing second native
generation. A COW-backed local transfer allocates zero bytes on both hosted
backends; disabling moves gives an allocating positive control. This batch
changes hosted lowering only; the native implementation already moves these
bindings. The broader paired run remains pinned to the preceding snapshot.

The full paired corpus at the borrow/move snapshot passed all 211 cases.
This broader run used the fixed second-generation snapshot above, before the
later hosted array-binding and module-provenance work.

Module-provenance checkpoint: assembled hosted HIR now keeps each top-level
item's defining source in `hir.Program` metadata, mirroring the native module
graph's source map. Source attribution survives ordinary HIR rebuilding and
proof erasure. Global startup copy notes now point to the imported module's
initializer rather than to an unrelated span in the entry file. This metadata
also travels through direct checking/code-generation APIs; no CLI scan is used.

Validation: 21 initial provenance/traversal/copy tests, 66 cache/proof/generic/
native-effect-analysis regressions, and four final provenance checks passed.
The direct API test covers both global initialization and a bare top-level
copy with an imported erased proof. Hosted and native CLI inventories both
attribute the global snapshot to dependency.dewy, and the scoped hosted gate
counts its one copy. Strict-copy enforcement remains pending.

Explicit-view checkpoint: both compilers recognize `const name = @route`
for local record and array storage. The declaration retains a view demand
through HIR rewriting and native snapshot serialization; a failed borrow
proof reports the conflicting write where available, rather than falling
back to a copy. Whole-binding views participate in the same transitive owner
liveness used by inferred field/element views. Returning or storing a view's
value still creates an independent value. Mutable local places, other value
kinds, and more precise lifetime intervals remain pending; this first subset
requires function-wide owner stability.

Validation: 83 initial ownership regressions passed, as did 20 local-view,
HIR traversal and native snapshot checks (including x86/C round trips).
The view kernel allocates zero bytes across 100 reads, and its escaped values
remain independent. Eight native acceptance/rejection probes passed. Native
generations built in 61.79s and 63.42s, with the latter executing both the
explicit-view and index-evaluation kernels (42). These remain correctness
integration timings above the native performance target.
Artifacts: `../dewy-build-artifacts/phase1-local-views-stage2-2026-09-20`.

The index-evaluation kernel exposed a hosted lowering bug predating local
views: a singleton index fact erased evaluation of an effectful expression.
Array reads/stores, nested places and string indexing now evaluate it once
before subsequent operands. Literal and scalar-name reads can still use the
proven value directly, including the contextual `end` binding. A first paired
run passed 63/64 cases and caught that `end` regression; it was fixed rather
than changing the fixture's expected result. All 64 cases passed on the final focused rerun. Hosted follow-up gates
passed 94 and 74 checks, covering the changed
diagnostics, width-aware addressing, effectful indices and local views.

The full paired corpus at the local-view/index checkpoint passed 211/211
cases. This run preceded the following union and lazy-string changes.

Union-view checkpoint: required local views now support tagged unions,
optionals, strings and string-literal enums. They retain the source owner
through dependent views and allocate neither replacement cells nor string
handles. Pure inspection of ordinary by-value input can declare
`no_effects`; a view does not hide a place parameter's external read.
Native `.length` also accepts closed string-literal unions by decoding the
active enum before reading its descriptor.

A cold native string length or grapheme-type query now counts without
allocating a boundary table. The shared Unicode scanner has a count-only
sink, with a scalar invalid-input result; existing public segmentation
wrappers preserve their optional results. Compiler-created frame views call
that scanner directly through an imported binding, avoiding a by-value
wrapper's conservative copy. Length and boundary-table caches are separate.
Index/slice comparisons now explicitly request offsets instead of depending
on an earlier length read to have materialized them. General runtime
refinement-predicate tests remain pending; the shape kernel uses `grapheme`.

Validation: the union batch passed 103 hosted effect/row/view checks and
65/65 paired cases at its earlier snapshot. The completed string batch
passed 16 hosted checks, including count-only Unicode conformance and all
ASCII pairs on x86 and C. Native descriptor/lifetime/scratch/Unicode/string
comparison regressions passed on both targets. Cold ASCII and Unicode
length/shape queries allocate zero bytes and later indexing remains valid.
Two generations execute all three new kernels with result 42. Their builds
took 62.89s and 67.40s (the latter shared the machine with another integration
job), above the native target. The expanded paired run passed all 67 cases.
Artifacts: `../dewy-build-artifacts/phase1-string-count-stage3-2026-09-20`.


Scalar-view checkpoint: the frontend now recognizes a view demand by its
stored route rather than an aggregate-kind whitelist. Both lowerers retain
word width and signedness; native storage matching ignores proven array
lengths and fact qualifiers that leave the representation unchanged.
Dictionary/set reads and array joins no longer incorrectly require an
owning local slot solely for read-side cache maintenance. Stores, removals,
place exposure and source instability still reject a required view. Native
rejections now report relevant binding/storage proof failures.

Validation: 31 initial hosted local/union/scalar checks passed; all 12
expanded scalar/container checks also passed, including x86/C execution.
The final native compiler built in 63.25s and runs the scalar/container,
union, string-union and cold-length kernels with result 42. Four additional
native probes passed: prelude-free scalar views and rejection of scalar,
dictionary and set owner mutations. This remains above the native build
target. Artifacts: `../dewy-build-artifacts/phase1-scalar-views-stage6-2026-09-20`.


Explicit-copy policy checkpoint: the approved module directive is carried
through hosted checked-HIR assembly (including direct API use) and native
module options/snapshots. Both lowering boundaries reject recorded implicit
runtime-sized copies in marked modules, preserve unmarked dependency policy,
and allow explicit copies and proven views/moves. Fixed outer layouts are
checked transitively, including concrete child fields; grapheme counts do
not bound string bytes. No COW deferral is treated as a proof of no copy.
The classifier is memoized within the closed compilation. Hosted reporting
now also records array argument/assignment copies, fixed-array field copies,
and owned optional/union parameter cells.

This replaces the removed CLI-only implementation, but does not close the
report-completeness or ownership-parity work. Native mutating by-value
parameters can still receive a conservative entry copy after the caller has
prepared owned storage. A function that explicitly copies a read-only input
into its working local passes both implementations; eliminating redundant
entry copies remains an ownership optimization, not grounds to suppress a
copy note.

Validation: 48 copy/view/provenance/native-cache regressions passed, followed
by 28 hosted policy/classification/provenance checks, 15 copy-bound tests
(including execution of the native classifier on x86/C), and 38 follow-up
report/policy checks. Six native policy/import probes and both explicit/fixed
copy kernels on C passed. The native snapshot kernel preserves an enabled
directive through serialization, and the native bound classifier includes
runtime-sized fields carried through a parent or structural type. Two native
generations built in 66.48s and 64.81s; the latter executes all six view/string/
copy kernels with result 42. These are correctness timings above target.
All 71 paired cases passed at that snapshot. The focused five-case follow-up
also passed against the final hosted report-site changes; the shared manifest
now has 73 cases.
Artifacts: `../dewy-build-artifacts/phase1-strict-copy-stage4-2026-09-20`.


Allocation-contract checkpoint: David approved bare `allocates` and
`no allocates`. Both parsers/kind checkers represent them as the ordinary
subjectless allocation atom and reject resource arguments, including empty
`<>`. Public checking now distinguishes logical copies, aggregate
construction and implicit value boundaries from entirely unknown behavior.
Permission does not authorize external reads/writes, and propagates through
calls, defaults, recursion and row-parameter substitution. COW deferral is
not evidence of no allocation. Storage boundaries remain conservative until
backend placement/move evidence is available; failure policy remains open.

Native lowering now places proven nonescaping scalar places in one frame
slot per local/parameter, reused across loops. This removes a hidden arena
allocation on private scalar mutation paths accepted as effect-free. The
public check uses the same escape summaries: a private place sent through an
unresolved callback or forwarding helper conservatively requires allocation
permission. Captured/escaping slots retain their existing storage protocol.

Validation: 97 existing hosted public-row/generic checks passed, as did 80
allocation/place/row regressions and the final 36 allocation checks. All 33
native acceptance/rejection probes passed, including private places through
callbacks, and both new kernels execute on x86 and C. The native generation
built with the frame-slot change executes the allocation, scalar-place and
strict-copy kernels (42); the final generation built in 65.03s. All 77 paired
Phase 1 cases passed. The build timing remains above target.
Artifacts: `../dewy-build-artifacts/phase1-allocation-effects-stage4-2026-09-20`.

Direct array ownership checkpoint: native direct-only functions can own a
caller-prepared mutable array when escape summaries prove it cannot be kept.
The caller transfers a fresh/moved/copied value; the callee releases it on
normal and early exits, including replacement and forwarding through a place.
This is separate from single-use consumption: reading the parameter does not
consume it. First-class functions, defaults, captures and runtime entrypoints
retain the ordinary ABI. Callback target analysis now includes only observed
function values (and still treats raw callable ingress as unknown), rather
than every function with a compatible signature. Shared HIR nodes are checked
by parent-child use, so a direct call cannot hide a value use of the same node.

Hosted lowering now retains and releases caller-prepared nonescaping argument
snapshots. Rebound parameters own their replacement storage separately from
the caller's incoming descriptor. Mutable array parameters of functions used
as values isolate their contents on entry; callback forwarding cannot mutate
the caller's ordinary by-value input. Fresh nested literal elements transfer
into lasting replacement buffers instead of leaking their initial owners.
Strict-copy accounting uses the source's known outer extent at a runtime-length
parameter boundary, while retaining the destination's child-storage costs.
True unbounded implicit argument copies remain errors under `$explicit_copies`.

Validation so far: the direct native second generation built in 64.26 seconds
and passed the three ownership kernels on x86 and C. The broad paired corpus
passed 211/211. The final hosted ownership/strict-copy group passed 19 tests,
and 35 array/lifetime regressions passed. Native timing remains above target;
this checkpoint does not certify a new fixed point or complete Phase 1.
Artifacts: `../dewy-build-artifacts/phase1-owned-parameters-stage3-2026-09-20`.

A proof gap exposed by the nested-array lifetime kernel remains: checking
`rows[0].length` does not currently establish a stable fact route for a later
`rows[0][0]`. A named local row view does carry that fact, but the general
indexed-route proof and its mutation invalidation are still required; the
fixture's local views do not constitute a fix for that proof gap.
Final integration check: all 82 paired Phase 1 cases passed, including the
nested-array lifetime kernel and both bounded/unbounded strict-copy argument
cases. Results: `../dewy-build-artifacts/phase1-owned-parameters-final-parity-2026-09-20`.

Indexed-fact checkpoint: field routes now also admit constant index selectors.
A guard on `rows[0].length` can justify `rows[0][0]` without a named local
view, including records containing rows, string elements and deeper nesting.
An index expression is still evaluated normally; known index values do not
erase its effects. A component write conservatively drops indexed evidence
for the root, including writes through places and element relocation. Recursive
invalidation removes element evidence rooted at the projected sequence too.
Dynamic index identities and finer disjoint-index preservation remain pending.

Validation: 31 hosted index/container/order tests, 64 proof/loop/refinement
regressions, and two native registry/fact-transfer unit tests passed. The native
compiler built in 66.26 seconds, executes the indexed-read kernel on x86 and C (42), and
passes all 14 acceptance/rejection probes. All seven paired index cases passed,
including invalidation by replacement, shifting and effectful index evaluation.
Artifacts: `../dewy-build-artifacts/phase1-indexed-routes-stage1-2026-09-20`
and `../dewy-build-artifacts/phase1-indexed-routes-parity-2026-09-20`.

Iterator allocation contracts now consume the existing bounds proof. Public
effect validation runs after bounds checking, and accepts private numeric
range counters when their finite extent fits a word or every advancing edge
is proved to fit. Unbounded continue paths cannot borrow the parser's guard
hint as evidence. Counter reads and direct scalar arguments use that same
proof; loop-body allocation, external reads/writes and unknown behavior keep
their ordinary effects. This permits natural counted loops under `no_effects`
and `no allocates` without requiring a hand-written scalar while loop.

Validation: 13 iterator checks and the 36 allocation checks passed, alongside
144 existing effect/proof/unsafe tests. A native generation built in 66.62s,
executes the iterator allocation-counter kernel on x86 and C (42, no arena
allocations), and passes all 12 acceptance/rejection probes. All 16 paired
effect cases passed, including an unbounded continue-edge rejection.
Artifacts: `../dewy-build-artifacts/phase1-iterator-effects-stage1-2026-09-20`
and `../dewy-build-artifacts/phase1-iterator-effects-parity-2026-09-20`.

Fresh replacement report correction: hosted assignment of a fresh nested
array literal to lasting runtime-length storage already transfers its element
owners. It now reports that operation as a move, instead of an unproven
independent copy. This keeps `$explicit_copies` acceptance aligned with native
for nested string/array replacements and preserves the report entry describing
why lifetime promotion is needed. Actual snapshot sites retain their copy notes.
Validation: 23 strict-copy, ownership and array-release tests and all eight
paired strict-copy cases passed. The new fixture executes on x86 and C through
hosted lowering and through the existing native compiler.
Artifacts: `../dewy-build-artifacts/phase1-fresh-replacement-parity-2026-09-20`.

Required views now have a lexical-scope proof as well as the original
whole-function proof. A private owner may change before and after the view's
containing block, but any overlapping write, mutable place or unresolved call
within that block prevents the view. Captured or addressed owners stay on the
conservative path. Derived local views remain within that block; ordinary
values leaving it retain independent-value semantics. Diagnostics search the
relevant block rather than blaming a harmless earlier write. This first
shorter lifetime is explicit-demand-only; ordinary inference and last-use
intervals within a block remain separate work.

The additional scope scan runs only for functions containing required views;
the bootstrap's ordinary borrow analysis keeps its existing path. Native
bookkeeping uses numeric scope keys, since optional numeric keys still lack a
native hash implementation (an implementation gap, not a new design rule).

Validation: 41 hosted view tests initially passed; the expanded scope tests
and ownership/copy-report regressions passed 29 checks. Native passed all ten
focused probes, including printing through a view, copying a value out and
rejecting an addressed owner. The allocation/lifetime kernel passes on x86
and C, with zero view allocations and no retained storage over 100 calls. A
second native generation built in 67.16 seconds and executes both the scope
and iterator-effect kernels (42). These remain correctness timings above target.
Artifacts: `../dewy-build-artifacts/phase1-scoped-views-stage2-2026-09-20`.


Dictionary-key parity correction: hosted lowering no longer hashes the address
of an unsupported tagged cell or aggregate as if it were the key's value.
Such a lookup could silently miss a separately owned equal value. It now
rejects the same unsupported representations as native; fixed-width words,
bools, strings and word enums retain their existing value hashes. This does
not settle a user-defined hashing protocol or implement aggregate key equality.
Validation: 16 hosted dictionary/set tests passed; native rejects all five
unsupported representation probes and executes the supported-key kernel (42).
The hosted kernel executes on x86 and C. The change was prepared in an isolated
checkout while the preceding full integration runs used unchanged sources.

Integration closure for these checkpoints: the scoped-view second-generation
compiler passed all 211 broad corpus cases and all 91 then-current Phase 1
cases. The subsequent hosted-only dictionary-key correction passed both new
paired cases, bringing the focused manifest to 93. Artifacts:
`../dewy-build-artifacts/phase1-scoped-views-full-parity-2026-09-20`,
`../dewy-build-artifacts/phase1-scoped-views-parity-2026-09-20`, and
`../dewy-build-artifacts/phase1-key-validation-parity-2026-09-20`.

Lifecycle design review: David approved the zero-argument compiler-only
member shape, internal borrowed receiver, return types and automatic field
cleanup order. Observable effects are allowed under ordinary effect
contracts; implicit copy/move and temporary drop counts may change through
elision. The proposal and storage design notes now reflect that decision.
Hook implementation, raw-resource ownership contracts and remaining failure
behavior are still outstanding. Phase 1 is not complete.

Lifecycle declaration foundation: both checkers retain the metatag's role
separately from the ordinary method name, require one zero-argument member
per role on a nominal owner, check drop's void result and copy/move's exact
nominal result, and reject manual calls or function values. Even a field-free
body receives the original object through an internal place. Copy receivers
are read-only through projections, forwarded places and nested functions.
Ordinary effect contracts still check hook bodies; observable unannotated
hooks are allowed. Result inference continues to work. Native cache codecs
preserve the new member metadata.

This is declaration support, not automatic resource lifetime support. Both
code-generation routes reject runtime hooks explicitly. The native guard
runs before reachability pruning, which would otherwise erase a hidden hook
and silently compile its object with ordinary memberwise semantics. Inherited
hooks were explicitly pending at this checkpoint; the parent-portion direction
has since been approved. Next, implicit ownership operations must be visible to effect/fact
analysis and reachability as well as to cleanup and copy lowering.

Validation: the initial hosted declaration/method suites passed 39 tests;
the effect/declaration suite passed 122, and the expanded declaration suite
passed 28. Native passed all 16 focused acceptance/rejection probes (including
the explicit lowering limitation), the existing scoped-view and iterator
execution kernels, and all four new paired rejection fixtures. The native
build took 65.66 seconds, still above target. The focused manifest has 97
cases; no new full-corpus result is claimed for this batch. Artifacts:
`../dewy-build-artifacts/phase1-lifecycle-declarations-stage1-2026-09-20` and
`../dewy-build-artifacts/phase1-lifecycle-declarations-parity-2026-09-20`.

Lifecycle call checking and cleanup foundation: explicit custom `.copy()`
operations now resolve to checked calls with an internal read-only receiver,
including const sources. Their effects and returned facts come from the hook,
not from a memberwise copy of the source. Drop-only explicit copies are
rejected. Lifecycle members cannot escape through inherited callable fields.
HIR and native snapshot codecs retain each function's lifecycle role.

The internal receiver is private to the lifecycle operation for public effect
contracts; ordinary alias analysis still sees its place accesses. Both effect
checkers now include projected member/index writes, including possible storage
detachment and independent by-value parameter storage. Cleanup releases nested
scopes and record fields in reverse order. Runtime lifecycle invocation remains
explicitly gated until automatic ownership operations have correct checking
and lowering; these declaration/call checks alone do not enable resources.

Validation: all 101 Phase 1 paired cases passed, including seven lifecycle
rejections whose expected diagnostic fragments are now checked. Hosted checks
passed 142 effect/allocation/declaration tests, 37 final declaration tests,
35 copy/method/report regressions and 26 ownership/cleanup tests. Native passed
26 focused probes and three execution kernels; the projected-store kernel also
passed hosted x86 and C. The final native generation built in 64.35 seconds,
still above the performance target. Artifacts:
`../dewy-build-artifacts/phase1-lifecycle-calls-stage3-2026-09-20` and
`../dewy-build-artifacts/phase1-lifecycle-calls-parity-2026-09-20`.

David approved parent-portion lifecycle inheritance and clarified the review
policy: proceed provisionally with obvious choices consistent with Dewy and
report them; seek advance review for fundamental new language directions.

Inherited lifecycle checking now composes through the immediate parent in
both implementations. Each hidden helper borrows its child source once,
invokes the parent operation once, and reconstructs the complete child from
the returned parent portion and the added fields. The ordinary constructor
checker rejects parent results that cannot establish a strengthened child
contract. Added custom-copy effects remain visible. Inherited drop bodies
delegate to the parent body; complete-child field cleanup remains the
responsibility of the pending ownership lowering. Runtime hooks are still
explicitly rejected, so this is not a resource-lifetime completion claim.

The provisional override rule follows the role rather than the member name:
an explicitly tagged child operation replaces that inherited role, while an
ordinary same-named method cannot silently remove it. A child override
supplies the complete operation; it does not also run the overridden body.

Validation: 121 hosted lifecycle/method/effect checks and the final expanded
47 lifecycle checks passed. Native passed the previous 26 focused probes
and six additional inheritance probes, including multi-level copy, move,
override and strengthened-contract checking. The build took 64.30 seconds
and executed all three existing view/ownership/projected-store kernels (42).
All 11 lifecycle parity cases passed with required diagnostic fragments;
the focused manifest now has 105 cases. Artifacts:
`../dewy-build-artifacts/phase1-lifecycle-inheritance-stage1-2026-09-20` and
`../dewy-build-artifacts/phase1-lifecycle-inheritance-parity-2026-09-20`.

Required local views now use statement intervals through the last use of
their derived aliases in both lowerers. Owners may change earlier and later
in the same block. The dependency closure includes aggregate forwarding and
explicit derived scalar views; an explicit `.copy()` creates an independent
snapshot. Loops and conditional statements remain indivisible, preventing
a later iteration or branch from reading invalidated storage. Captured,
exposed and outward-stored aliases retain the containing-block proof, and
addressed owners still need stronger evidence. Ordinary inferred views keep
their existing fast path. Conflict diagnostics search the selected interval,
so an earlier unrelated write no longer receives the blame.

Validation: 50 hosted view/copy checks passed initially; one old rejection
expected an unused view to block a later write and was updated to read the
view after that write. The corrected local-view and ownership/report suites
passed 34 checks. Native passed all 14 last-use acceptance/rejection probes
and all ten paired view fixtures. The new allocation kernel executes on
hosted x86/C and native, allocates nothing for the views and retains no
storage over 100 repetitions. The native generation built in 63.41 seconds
and also executes the previous three kernels (42), still above target.
The focused manifest now has 108 cases. Artifacts:
`../dewy-build-artifacts/phase1-view-last-use-stage1-2026-09-20` and
`../dewy-build-artifacts/phase1-view-last-use-parity-2026-09-20`.

Lifecycle follow-up: structural extension of an existing nominal identity is
not a new child mint. Its hook adaptation previously attempted to look up a
nonexistent nominal parent and could fail internally. Both checkers now
diagnose this unsupported composition explicitly. Hosted passed 48 lifecycle
checks; the new paired fixture passed with the expected diagnostic. A fresh
native generation built in 67.19 seconds while integration tests were also
running, then executed the three existing kernels (42). Artifacts:
`../dewy-build-artifacts/phase1-lifecycle-structural-guard-2026-09-20` and
`../dewy-build-artifacts/phase1-lifecycle-structural-guard-parity-2026-09-20`.

Integration closure: the last-use-view compiler passed all 211 broad corpus
cases and all 108 then-current Phase 1 cases. The structural-composition
diagnostic follow-up passed its additional paired case, bringing the focused
manifest to 109. The broad runs used unchanged sources while the follow-up
was prepared in an isolated checkout. Artifacts:
`../dewy-build-artifacts/phase1-view-last-use-full-parity-2026-09-20` and
`../dewy-build-artifacts/phase1-view-last-use-full-phase1-parity-2026-09-20`.

Nominal writable-prefix correction: an inherited mutating method could write
a wider parent value into a child's strengthened field while checking still
trusted the child invariant. Both checkers now require matching writable
field types, refinements and mutability across that prefix. Read-only value
methods retain ordinary subtyping. The compiler-only copy receiver has a
separate read-only compatibility check that preserves field representation;
this also permits inherited copies of const children without granting source
code a mutable alias. Constructor checking still owes the child's result
invariants. This correction does not yet settle whole-value replacement or
escape through a parent place; those need the existing effect summaries to
prove that the complete child's identity and additional invariants survive.

Validation: 90 hosted declaration/place/method checks and 15 final method
barrier checks passed, including execution on x86 and C. Native passed six
focused probes and both new paired fixtures. A fresh generation built in
63.57 seconds and executed the three existing kernels (42). Artifacts:
`../dewy-build-artifacts/phase1-nominal-place-contracts-2026-09-20` and
`../dewy-build-artifacts/phase1-nominal-place-contract-parity-2026-09-20`.

Parent-place identity proof: both compilers now use transitive parameter
access summaries to reject whole-parent replacement or escape through a
child's wider nominal view. Field-only updates and independent value reads
remain valid, including through imported helpers. Unknown callbacks cannot
supply that proof. The pass sees all loaded source functions before runtime
pruning, so an unused invalid function cannot disappear before checking.
The native effect collector now accepts several module roots without
repeating collection. Existing overload dispatch still rejects a mismatched
place type before this proof is reached. Sibling-field invariants remain
restricted to immutable records under the existing type rules.

Validation: 112 hosted place/lifecycle/effect checks passed. The fresh native
generation built in 64.90 seconds, executed the three ownership kernels (42),
and passed all five paired nominal-place cases. The focused manifest now
has 114 cases. Artifacts:
`../dewy-build-artifacts/phase1-parent-place-effects-2026-09-20` and
`../dewy-build-artifacts/phase1-parent-place-effects-parity-2026-09-20`.

Inferred const projection views now reuse the last-use interval proof when
their owner is not stable for the whole function. Alias dependencies are
collected once per containing block and shared by its candidate views;
already-proven whole-function borrows keep their existing fast path.
Conflicting writes still select independent copies, or the existing
`$explicit_copies` diagnostic. No new source form was introduced.

Validation: the hosted ownership/view/report/strict-copy batch passed 109
checks, with one new test initially expecting the wrong diagnostic text;
after correcting that expectation, all nine new inferred-view tests passed.
The fresh native generation built in 63.90 seconds and passed the three
ownership kernels plus all eleven paired view fixtures. The inferred-view
kernel allocates nothing for the views and retains no storage across 100
repetitions on hosted x86/C and native. The focused manifest has 115 cases.
Artifacts: `../dewy-build-artifacts/phase1-inferred-view-last-use-2026-09-20`
and `../dewy-build-artifacts/phase1-inferred-view-last-use-parity-2026-09-20`.

Public effect checking now runs over the complete checked module graph,
after bounds validation has certified iterator storage and before runtime
pruning. Direct imported helpers, including transitive imports, participate
in the same fixed point as local functions. An omitted row no longer turns
a known imported helper into an unknown operation. Unused imported contracts
are still checked, and unknown operations/allocations remain conservative.
Native effect collection is shared with its access-summary solve rather than
traversing the graph twice. This does not yet infer rows into callback types.

Validation: 164 hosted public-effect, allocation and lifecycle checks passed.
The fresh native generation built in 63.66 seconds, executed the three
ownership kernels (42), and passed all 24 paired effect fixtures. The focused
manifest now has 118 cases. Artifacts:
`../dewy-build-artifacts/phase1-imported-effects-2026-09-20` and
`../dewy-build-artifacts/phase1-imported-effects-parity-2026-09-20`.

Integration checkpoint: the imported-effect generation passed all 118 Phase 1
parity cases on unchanged sources. Follow-up work was prepared in a separate
checkout while that run completed. Artifact:
`../dewy-build-artifacts/phase1-imported-effects-full-phase1-2026-09-20`.

Synthesized explicit copies now propagate move-only capability through
record fields, array elements, dictionary storage and union alternatives.
A nested drop-only resource cannot acquire a copy operation merely by being
wrapped in a container. Diagnostics identify the component path. A custom
copy hook remains responsible for constructing its own complete result and
may acquire fresh move-only members. Recursive capability queries terminate
without treating a cycle itself as evidence of move-only storage. These are
capability checks, not runtime lifecycle implementation: automatic copy/move
and cleanup remain gated. This follows the existing resource rule and adds
no syntax or ownership annotation.

Validation: 72 hosted lifecycle/copy checks passed. A fresh native generation
built in 68.32 seconds while the integration run was active, executed the
three ownership kernels (42), and passed all six nested-resource probes plus
the paired diagnostic fixture. The focused manifest now has 119 cases.
Artifacts: `../dewy-build-artifacts/phase1-lifecycle-components-2026-09-20`
and `../dewy-build-artifacts/phase1-lifecycle-components-parity-2026-09-20`.

Imported lifecycle declarations now remain in the hosted runtime dependency
graph until ownership operations have explicit call edges. Otherwise pruning
could remove a hidden hook and bypass the runtime implementation gate for
an imported resource. Native validation already rejects before pruning.
Both used and unused imported hook declarations are covered. Validation:
51 hosted lifecycle checks and the new paired imported-resource diagnostic
passed. The focused manifest has 120 cases. Artifact:
`../dewy-build-artifacts/phase1-lifecycle-import-gate-parity-2026-09-20`.

Broad integration: the lifecycle-component generation passed all 211 broad
compiler/parser corpus cases on fixed sources. Together with the preceding
118-case Phase 1 run and the two new paired lifecycle cases, this closes the
current integration checkpoint; it does not complete Phase 1. Artifact:
`../dewy-build-artifacts/phase1-lifecycle-components-full-parity-2026-09-20`.

Runtime drop now supports fresh local nominal owners with word fields in both
compilers, including inherited and imported drops, reverse lexical order,
early returns and loop exits. Return values are captured before cleanup;
backing storage is released after the hook. Calls are explicit checked HIR,
so hook writes invalidate later facts and enter public effect contracts.
Unsupported ownership shapes still receive source fact/effect diagnostics
before the implementation-gap diagnostic. Copy/move hooks, aggregate fields,
owning transfers, escaping resources and implicit value returns with local
owners remain explicitly gated. No new source form was introduced.

Validation: the hosted lifecycle/place/effect batch passed 92 checks, followed
by all 14 final runtime tests on x86 and C. The fresh native generation built
in 67.16 seconds and passed the three ownership kernels (42). All 18 paired
lifecycle cases passed, including the new cleanup, no-retained-storage,
effect and stale-fact fixtures. The focused manifest now has 124 cases.
Artifacts: `../dewy-build-artifacts/phase1-lifecycle-drop-runtime-2026-09-20`
and `../dewy-build-artifacts/phase1-lifecycle-drop-parity-final-2026-09-20`.

Tight right-hand numeric adjacency now retains both call and multiply
readings in both parsers. Whitespace remains a separator. The hosted checker
now preserves call-target context through single grouping parentheses,
matching native; `(f)2` no longer auto-calls `f` before seeing its argument.
Callable-or-number unions still require explicit call pipes or multiplication.
Validation: 40 hosted adjacency/function-value/keyword-call tests passed.
A fresh native generation built in 66.31 seconds, passed three ownership
kernels and the extended paired precedence fixture (including `g(1)2` and
both call/multiply exponentiation). Artifacts:
`../dewy-build-artifacts/phase1-tight-numeric-adjacency-2026-09-21` and
`../dewy-build-artifacts/phase1-tight-numeric-adjacency-parity-2026-09-21`.

Hosted lowering no longer erases refinements in place on the shared checked
graph. The cached prelude retained some of those nodes, so a later compilation
could lose parameter facts (observed in `Report.point`'s `addr` parameters).
Erasure now rebuilds changed DAG paths before lowering constructs its identity
indexes. A regression reuses one checked program twice and verifies that its
parameter facts survive and its generated program remains identical.
Validation: 28 lowering/physical-unit/union-refinement checks passed.

Local drop now also handles ordinary aggregate fields, including strings and
arrays: the hook runs while those fields are live and automatic storage
cleanup follows. Scalar implicit results are captured before drop, just like
explicit returns. Lifecycle-bearing nested fields, resource transfers and
copy/move hooks remain pending. Validation: 69 hosted lifecycle checks passed,
including x86/C execution, and all 20 paired lifecycle fixtures passed. The
new aggregate fixture checks inherited cleanup, a snapshot across array
mutation, field mutation inside drop, and zero retained bytes over 100 calls.
The fresh native generation built in 65.81 seconds and passed three ownership
kernels. The focused manifest has 126 cases. Artifacts:
`../dewy-build-artifacts/phase1-lifecycle-aggregate-drop-2026-09-21` and
`../dewy-build-artifacts/phase1-lifecycle-aggregate-drop-parity-2026-09-21`.

Integration checkpoint: the combined drop/adjacency generation built in
65.21 seconds, passed the three ownership kernels, and passed all 126 Phase 1
parity cases against fixed sources. Nested-field follow-up work stayed in an
isolated checkout during this run. This is an integration checkpoint, not
completion of Phase 1; native self-build time remains above the 30-second
target. Artifacts: `../dewy-build-artifacts/phase1-drop-integration-2026-09-21`
and `../dewy-build-artifacts/phase1-drop-full-parity-2026-09-21`.

Nested record ownership now materializes containing hooks before reverse
field cleanup, recursively, including wrappers with no hook of their own.
Fresh constructor trees are supported; transferring an existing resource
into a field, replacing a resource field, resource arrays/unions, and general
owning arguments/results remain explicitly unsupported. The native pass
resolves operations through the checked nominal-owner inventory, since
method descriptors can precede binding resolution. Hosted fact revalidation
now uses each function's original source for diagnostics across imports.

Validation: 72 hosted lifecycle checks passed, followed by 34 runtime and
refinement checks after adding the imported-diagnostic regression. Native
built in 70.71 seconds during the independent integration run, passed the
three ownership kernels, all seven paired drop-runtime cases, and both new
nested effect/fact rejection cases. The nested fixture checks hook/field
order and zero retained bytes across 100 calls. The focused manifest has
129 cases. Artifacts:
`../dewy-build-artifacts/phase1-lifecycle-nested-drop-2026-09-21`,
`../dewy-build-artifacts/phase1-lifecycle-nested-drop-parity-final-2026-09-21`
and `../dewy-build-artifacts/phase1-lifecycle-nested-drop-facts-2026-09-21`.

Explicit custom copy hooks now execute when they construct a fresh result,
including a fresh wrapper whose fields call their own copy hooks. Internal
receivers stay borrowed and read-only; the result becomes a separate local
owner and is dropped independently. Hook effects and return facts remain
ordinary checked calls. This does not yet support inferred moves/copies,
inherited copies consuming an intermediate parent result, general owning
arguments/results, or containers of resources. Those forms still diagnose
the missing ownership operation rather than falling back to memberwise copy.

Validation: 84 hosted lifecycle/capability checks passed, followed by four
runtime fixture checks after extending the copy fixture with nested hooks.
The fresh native generation built in 67.26 seconds, passed three ownership
kernels and all 24 paired lifecycle cases. The copy fixture checks independent
mutation, exercised hook/drop counts, and zero retained bytes across 100
iterations on hosted x86/C and native. The focused manifest has 130 cases.
Artifacts: `../dewy-build-artifacts/phase1-lifecycle-copy-runtime-2026-09-21`
and `../dewy-build-artifacts/phase1-lifecycle-copy-runtime-parity-2026-09-21`.

## Test repair and ownership continuation (2026-09-21)

The original failing local suite is repaired: the fixed baseline passed
3,347 tests with 14 skips, and CI run 35565972436 passed. The recovery release
published `native-8406363e1299` after three byte-identical generations and
execution checks on both backends. Test drivers are cached within a pytest
worker; each source case still executes in its own process and cache.

Resource factories and callbacks now return fresh owners. Result evaluation
precedes cleanup, including aggregate field snapshots and copy hooks with
scratch owners. Ordinary `@` parameters lend resource records without
transferring ownership; nested fields and callback forwarding are covered.
Explicit returns transfer local owners along the exiting path, including
branches and loops, and release the remaining owners. Hosted record binding
moves now reuse storage at proven last use, matching the native behavior.
Their allocation regression has a positive control with moves disabled.

The expanded full suite passed 3,368 cases and exposed two regressions:
construction-time move bookkeeping was missing, and optional widening was
misclassified in the copy inventory. Both are fixed; all 11 targeted
copy-inventory, binding-identity and record-move checks passed afterward.
The full suite must still be rerun on the combined follow-up changes.

Inherited copy wrappers now consume the intermediate parent's fields into
the complete child instead of dropping those resources prematurely. Explicit
HIR metadata identifies the checked composition; snapshot codecs preserve
it. Native parent-place contracts compare proposition identities rather than
array storage addresses. All 95 lifecycle, identity and snapshot checks passed.

Explicit owner returns now invoke custom move hooks. The consumed owner's
own drop hook is skipped; remaining nested resources still receive automatic
cleanup. Inherited hooks compose the parent operation with ordinary added
fields. Hook effects invalidate caller facts and participate in effect
contracts; a returned fact must hold for the hook's result. All 96 targeted
checks passed, including hosted x86/C and native execution, inheritance,
effect rejection, and no retained storage across repeated calls.

These checkpoints do not complete Phase 1. General local resource transfers,
resource containers, owning parameters, mutable local places, shared storage
proofs for allocation contracts, and inferred callable effect rows remain
work to finish. Existing rejection gates remain explicit until their
ownership operations are implemented. New integration and second-generation
checks are required before certifying the combined changes.

Implicit resource results now follow the explicit-return ownership path.
Conditional results and nested scopes preserve cleanup order; a value before
trailing statements is saved before those statements and transferred after
them. This also fixes a premature return in that resource-result case.
All 42 hosted/native lifecycle checks passed. The combined committed snapshot
then built three native generations; the last two are byte-identical and the
bootstrap execution checks passed on both output backends. The final generation
took 110 seconds under concurrent test load; this is an integration result,
not a performance-target claim. Artifacts:
`../dewy-build-artifacts/phase1-ownership-integration-2026-09-21`.

Same-scope local resource bindings now transfer an owner at proven last use,
invoking a custom move hook where declared and retaining nested cleanup for
fields left behind. Captures, later uses and outer-owner conditional transfers
do not acquire this proof. Lexical ownership is established before cleanup
introduces artificial reads. All 102 lifecycle/declaration checks passed,
including ordinary and custom moves, loops and branches, hook effect/fact
rejection, and repeated-call storage accounting on hosted x86/C and native.
Outer-owner conditional consumption, inferred resource views/copies and field
transfers remain outstanding; this is not the complete ownership model.

The fixed-point generation passed 135/136 original Phase 1 manifest entries;
the sole failure was an obsolete rejection expectation for importing a
move-hook declaration without moving it. Both compilers accepted that already
supported program. Renamed it to `lifecycle_imported_owner`, required exit 42,
and reran the case against the same native generation: passed. All 136
integration cases therefore have checked expected outcomes. Artifacts:
`../dewy-build-artifacts/phase1-ownership-parity-2026-09-21` and
`../dewy-build-artifacts/phase1-imported-owner-parity-2026-09-21`.

Fresh arrays now own their resource elements, including nested arrays, empty
arrays, record array fields and factory results. Cleanup borrows each array
through a checked helper, runs element hooks in reverse order, then leaves
backing storage release to normal lowering. Helper reuse avoids duplicating
nested loops at every exit and gives each receiver a stable proof identity.
Generated bindings and module provenance remain explicit in HIR. Aggregate
mutation, resource union/dictionary handling and inferred element copies are
not covered by this batch.

Validation: the hosted lifetime fixture passed on x86 and C; 27 hosted
lifecycle checks passed before native compilation found an incorrect internal
binding-kind spelling. After correcting it, all eight native lifecycle cases
passed. Three final hosted lifetime/effect checks and two native rejection
cases passed, including propagation of implicit element-drop effects and
invalidation of caller facts. No storage remains after 100 repeated calls.

Ordinary by-value resource parameters now receive ownership from fresh
arguments, factory results and explicit custom copies, including callbacks
and default arguments. Parameters drop in reverse order after later locals;
returning a parameter transfers it to the caller. Scalar and aggregate field
results are captured before parameter cleanup. Existing `@` parameters retain
their borrowed lifetime. Named-owner argument transfers and implicit copies
still need the general ownership plan.

Validation: all 100 lifecycle/declaration checks passed, including the shared
owning-parameter fixture on hosted x86/C and native. Two additional hosted and
two native effect/fact rejection cases passed. Repeated calls retain no storage.

Remaining correctness issue found while extending the fixture: preliminary
source bounds validation runs before lifecycle operations are inserted. It
can retain a counter fact across a call whose implicit drop will change that
counter, then incorrectly consider a combined counter/length guard impossible.
For example, a later `if drops not=?6 or values.length not=?2 return 7` can
lose the length proof when earlier checks established `drops=?3`. Ownership
materialization and proof validation need an ordered shared pipeline; the
final post-materialization validation is necessary but cannot undo an earlier
false rejection. Keep this as a Phase 1 correctness task, not a source-style
requirement to split such guards.

Full-suite checkpoint: commit `744f25d7` passed 3,379 tests with 14 skips
(1,985 seconds). The test inputs stayed fixed while later work proceeded in
separate checkouts. The combined local-move/array/parameter tree then passed
100 hosted checks and built two byte-identical native generations with both
backend execution checks. The final generation took 60 seconds under load.
Artifacts: `../dewy-build-artifacts/phase1-resource-ownership-integration-2026-09-21`.
Targeted second-generation lifecycle parity passed all 33 cases; the full-suite
checkpoint is green on CI (run 35572685303).

Ownership/proof ordering follow-up: both file and in-memory hosted modules
now materialize lifecycle operations before their first bounds and effect
validation, matching native ordering. A module-local pass uses a cached hook
inventory and marks the finished program so backend entry points cannot
insert cleanup twice. The combined counter/array-length guard now compiles
unchanged. Contradictory assertions and effect contracts are rejected by the
semantic entry point as well as code generation.

Custom copy receivers can now be factory and constructor temporaries,
including nested copies and inherited hooks. Each receiver is evaluated once;
the copy result is captured before dropping its temporary receiver. A shared
fixture checks hook counts, independent storage and repeated-call reclamation.

The prior combined ownership generation passed all 33 lifecycle manifest
cases against the hosted compiler. The 744f25d7 full-suite checkpoint passed
3,379 tests (14 skipped), and its CI run 35572685303 is green.

Validation for this follow-up: 65 hosted/native lifecycle checks passed,
including both output backends; all 53 module, prelude-cache, imported-effect,
prototype and representation checks passed. The earlier hosted lifecycle
coverage passed 108 cases before the temporary-receiver additions.


Expression exits now carry their enclosing ownership context through blocks,
conditions and selectors. Hosted `or_throw` is expanded to the same checked
binding/test/return structure used natively before ownership validation.
Propagated optional and record-error results release locals and owning
parameters in reverse order; ordinary successful results keep their usual
path. Rewritten selector expressions are retained in hosted HIR.

A captured `none` return previously lost its unit tag during lowering; unit
absence now needs no capture before cleanup. A literal-valued conditional
also emitted its literal type as a micro-Dewy variable annotation: the flow
temporary now uses its already-selected runtime type.

Validation: 60 lifecycle checks passed on the initial hosted/native batch,
including both output backends. All 12 hosted propagation/error checks
passed. The extended selector-propagation fixture then passed hosted and
native execution on both backends; the three hosted ownership-order and
temporary-copy integration checks also passed. Full integration follows the
next ownership batch; this does not complete Phase 1.


Read-only local resource aliases now retain one logical owner. Same-scope
bindings whose source and destination are never written or captured can
share the original owner, including chains and explicit const views. Last-use
owner transfers still take precedence. Writes, escaping owners, field moves
and general cross-scope resource aliases need further ownership analysis.

The common view lifetime proof now works backward through blocks and return
edges. Cleanup after a captured return value is outside that view's live
interval, while loop backedges retain aliases read on later iterations.
Captured/outward aliases keep their conservative lexical lifetime. A known
nonescaping place call before or after a view no longer disqualifies its owner
for the entire function; overlapping writes during the view still fail.
Unknown or retaining place calls keep their exclusion.

Validation: the initial resource-view/lifetime batch passed 50 tests, including
native execution. After integration with expression exits and preserving the
lexical fallback, all 56 combined hosted/native checks passed. Two obsolete
rejections now test nonescaping calls outside the live interval and a genuine
conflict inside it. Shared fixtures check one drop and no retained storage.


The resource-view and expression-exit integration (`4deadf4e`) built two
byte-identical native generations. Both generated backend execution checks
passed, followed by all 36 lifecycle parity cases against the second-generation
compiler. Generation times were 85 and 80 seconds while the full test suite
was running; these are integration results, not isolated performance claims.

Resource unions and optional owners now clean up only their active alternative,
including union elements in resource arrays. A union transfer dispatches a
custom move only for the alternatives that declare one; remaining fields of
that consumed alternative drop, while intact alternatives transfer their
nested owners. Drop calls still participate in effect and fact checking.

Narrowed array elements retain their declared storage layout when loading or
taking a place. Optional projections bind an already-evaluated cell rather
than copying and reevaluating their selector. Fresh safe-navigation receivers
and frame-rooted record results packed into unions release their temporary
owned storage after the statement. Shared fixtures exercise custom moves,
optional absence, selector evaluation once, and repeated calls without retained
storage.

The immutable `4deadf4e` integration passed the full local suite: **3,401
passed, 14 skipped** in 1,870.74 seconds. The subsequent union changes have
separate focused coverage. GitHub API rate limiting prevented a fresh CI status
query at this checkpoint; the prior `744f25d7` CI run was successful.

Validation: all six focused union/forward-reference checks passed, including
native execution on both output backends. The preceding run also passed all
21 adjacent hosted optional/union checks. Resource-union fixtures retain zero
storage over 100 iterations; cleanup effects reject empty contracts and stale
assertions in both compilers.


Ordinary implicit function results now preserve their evaluation position even
when statements follow them. Hosted lowering previously returned immediately;
native block cleanup treated the last statement as the result. Both now save
the expressed value and run trailing statements before returning/releasing the
scope. The shared regression covers scalar, string, array, record, optional
and conditional results, mutation after evaluation, and zero retained storage.
All eight focused result-order and lifecycle integration checks passed,
including hosted/native execution on both output backends. Mixed explicit
and implicit returns retain their existing source-checking rules.


Independent resource values now invoke a declared `$__copy__` hook when a
surviving source cannot move or share a read-only view. This covers local
bindings, projected resources and ordinary owning arguments. Calls enter HIR
before fact/effect validation; refinements must hold for the hook's result,
not merely its source. The HIR call retains implicit-copy intent for copy
reports and `$explicit_copies`; native snapshot serialization preserves it.
Proven local moves and views still take precedence. Synthesized copies of
containers/records containing custom-copy components remain outstanding.

All 12 focused inferred-copy, resource-union and resource-view checks passed,
including hosted/native execution on both backends. The shared fixture checks
independent mutation, hook effects/counts and zero retained storage over 100
iterations; rejection cases cover effect contracts, strict-copy policy and
stale facts. Snapshot-codec validation follows regeneration for the new HIR
metadata.

The regenerated native snapshot codec passed all three snapshot/schema checks,
including round-tripping an implicit-copy call and effect contracts on both
output backends. The four hosted inferred-copy checks also passed after
integration with the implicit-result ordering fix (seven checks total).


Resource arrays now accept fresh/copied owners through `push` and `insert`,
transfer ownership through `pop` (including indexed removal), and change
capacity through `reserve`. Discarded resource-valued expressions capture and
drop their result once, including discarded pops and factory calls. Their
cleanup remains checked HIR, so its effects and invalidated facts reach callers.
Element overwrite, `clear`/`truncate`, field transfers and transfers from
existing move-only bindings still require further lifetime handling.

Validation: all nine focused array-method, union and implicit-result-order
checks passed, including hosted/native execution on both backends. After
integration with inferred custom copies, all seven hosted array/copy checks
passed; the existing native driver also rejected both discarded-element
fact/effect violations. The fixture retains zero storage across 100 calls.
The preceding inferred-copy revision additionally passed all 134 broader
hosted lifecycle, explicit-copy, copy-source and prelude-cache checks.


The `c277e5d8` integration reached a native fixed point: generations 2 and 3
were byte-identical for both compilers, and paired execution checks passed
with both output backends. The seed predates the lowering changes, so its
first generation differed as expected and a third generation was required.
The final two generations took 63 and 71 seconds under concurrent test load.
All 41 lifecycle/result-order/receiver-lifetime cases then passed against that
native pair. This is an integration checkpoint, not a performance claim.

Replacing a local or owning parameter now evaluates the new value before
running the old owner's drop, then stores the replacement. The binding keeps
one current owner on branch and scope exits. Ownership follows the declared
storage even when an optional is currently `none`; a narrowed read type does
not erase that storage's lifetime. Borrowed owners still cannot be replaced.

Validation: three focused replacement checks passed in both compilers; the
expanded shared fixture also passed hosted/native execution on both backends.
It covers initializer reads from the old owner, optional absence/reentry,
owning parameters, conditional replacement, invalidated facts and zero retained
storage across 100 calls. The preceding integration also passed 11 adjacent
array/inferred-copy checks. Field replacement and conditional consumption of
outer owners remain pending.


Clearing a resource array now drops its elements in reverse order before the
normal storage release. One checked helper borrows the receiver, so an indexed
route is evaluated once. Its ordinary `void & <items.length =? 0>` return
contract preserves the builtin's length guarantee; no special proof assumption
or caller guard is introduced. Hosted array methods now accept indexed stored
arrays through the same root/immutability checks as fields, matching native
checking. Const roots and explicitly fixed-length storage still reject mutation.

Validation: all eight focused clear/narrowed-array checks passed, including
hosted/native execution on both backends. The shared fixture checks empty and
nonempty arrays, reinsertion, nested arrays, an effectful selector evaluated
once, the static post-call length fact and zero retained storage. Additional
paired checks reject const and fixed-length indexed mutation. Truncation,
element overwrite and general field transfers remain outstanding.

After integration with replacement, all eight hosted clear/replacement/narrowed
array checks passed, including the const and fixed-length diagnostic assertions.

Truncation now transfers the relation `new_length = min(old_length, count)`:
it retains the count upper bound, proves equality when the count fits, and
preserves existing index facts when no elements can be removed. These rules
use pre-mutation named terms and intervals, without reevaluating arguments.
A count proven at least the length is also nonnegative through that relation.

The regression exposed premature place invalidation in both analyzers. Taking
an address now evaluates its route without applying the callee's writes;
argument preconditions can still refer to that endpoint. Contracts are checked
again against evidence common to the argument snapshot and call-entry state,
so later arguments cannot invalidate them silently. Endpoint writes are then
applied before result facts. Fifteen focused hosted checks and the native
acceptance/rejection harness passed, including execution on both backends.

Full-suite checkpoint `40586e70`: 3,424 passed and 14 skipped in 1,855.84s.
The subsequent truncation/call-entry change also passed all 76 adjacent hosted
array, dependent-index, projected-place and length/order-fact checks.

CI follow-up: the release job at `40586e70` reached packaging after verifying
three native generations, but packaging still compared stages 1 and 2. It
now compares the last two stages recorded in the checked manifest and verifies
the distributed binaries against the final stage. Unrecorded stale stage files
do not change that choice. Eight packaging checks passed, including valid-hash
mismatches and three-generation builds with different stage-1 output. The
updated script also packaged the actual verified `c277e5d8` three-generation
pair successfully. The remote pytest workflow was still running at this check.

Synthesized record and union copies now construct independent resource
components through their declared hooks, including nested wrappers, optional
absence and fresh temporary receivers. A helper borrows the receiver once;
component calls and result obligations remain ordinary checked HIR. Types
containing move-only components cannot acquire an independent copied owner.
The copy report labels implicit operations as resource copies, classifying
union storage separately from records. Array/container copies remain pending.

Validation: all 132 hosted lifecycle checks passed. The component-copy and
existing inferred-copy harnesses passed hosted/native execution on both output
backends and their rejection cases. The shared fixture checks hook results,
independent mutation, effect checking and zero retained storage over 100 calls.
A test-harness adjustment retains the existing unsupported-lifetime diagnostic
category for an inferred move-only conflict; it still requires native rejection.

Bounds checking now reuses the transitive parameter-effect proof to preserve
facts across read-only, nonescaping place calls. Unknown callees, ambiguous
pairings, writes and escaping storage remain conservative; implicit global
writes still invalidate their own roots. Argument evaluation and call-entry
preconditions retain the ordering established in the preceding fix.
Relational result contracts also retain their current numeric consequence,
so a returned array with the source's known length carries that exact length.
The source's ordinary copy loop proves this contract through its loop invariant.

Validation: eight focused hosted cases and the native acceptance/rejection
harness passed on both output backends. All 83 adjacent hosted effect,
truncation, dependent-index and projected/length-fact checks passed. This does
not yet preserve untouched subfields of a parameter that the callee mutates
elsewhere; that needs finer route-specific invalidation.

Imported read-only calls now use the loaded declaration graph in both
compilers. Previously the source module's isolated effect scan could not
resolve an imported body, so a safe borrow lost its facts. Native validation
shares one transitive summary across the loaded modules, including generated
lifecycle helpers placed in a different module. Standalone bounds-analysis
clients retain the single-root default. Unknown calls and imported mutators
still invalidate borrowed endpoints.

Validation: nine hosted call-fact checks passed. The imported reader/mutator
harness passed native/hosted acceptance, rejection and execution on both
backends using the current integration driver. A new fixed-point integration
is still required; this local comparison alone does not certify it.

Synthesized array copies now build each resource element through checked copy
operations, including nested arrays, optional elements and fixed-length arrays.
The helper proves its result length against the borrowed source; inferred
copies retain an implicit-cost note, while explicit copies work under
`$explicit_copies`. Component hooks may change values, so their output is
constructed rather than treated as a physical snapshot of the source.

Generated clear helpers now contain an explicit return proof obligation.
Their earlier signature declared the zero-length fact but did not itself
cause the body to be checked. Tests remove the clear operation, or the append
from a generated copy loop, and require bounds validation to reject the broken
helper. This corrects that validation gap rather than trusting generated HIR.

Array element facts now retain common static lengths from literal elements,
copy them to independent arrays, and widen or forget them on insertion and
mutation. Evidence comes from evaluated values' static types, not reevaluating
an argument or reading a binding after another argument changed it. Mutating
an indexed child invalidates the parent's common element facts.

The hosted result ABI now supports exact outer arrays containing dynamic rows,
strings and optional cells. Nested rows own their storage; result writes retain
owned elements rather than leaving handles into a released source. Optional
array places lend the selected cell, matching the parameter ABI.

Validation: 78 focused checks passed, including three native comparison groups,
strict explicit-copy acceptance and implicit-copy rejection, generated-contract
corruption checks, and existing fixed-array lowering. The shared resource-copy
fixture checks seven copies, twelve drops, independent mutation and zero retained
storage over 100 repetitions on both output backends. Imported-effect integration
and broader ownership regressions are checked separately before the native
fixed-point checkpoint.

After importing the module-effect fix, all 181 adjacent hosted lifecycle, array
storage, projected-place, borrowed-call and generated-contract checks passed.
The remote pytest checkpoint at `40586e70` and the post-packaging-fix native
release at `d858cf4e` both completed successfully.

Checkpoint: indexed array and record-field routes now retain length facts
when their selector is an immutable local. Re-entering that declaration in
a loop invalidates the old selection; writes through other indices still
invalidate potentially aliased routes. Receiver mutations preserve their
newly established length while dropping dependent element evidence. The
hosted resident-prelude rollback also removes selector dependencies for
discarded routes, and the native cache schema includes this metadata.
This prepares ordinary fact tracking for mutable local places; it does not
yet implement those places or establish disjointness between indices.
Validation: 39 hosted cache/bounds checks passed; the immutable-selector
acceptance/rejection corpus, including record fields, executes through both
compilers and both output backends.

Checkpoint: warm-prelude differential execution caught three lifecycle
fixtures failing in a self-built compiler despite byte-identical generations.
A flow join from a record union to its parent retained the child payload
without converting its storage: cleanup then used the parent's allocator
size class, and the union wrapper was abandoned. Native joins now consume
their already-evaluated owner through the same conversion used for checked
casts. Retagged cell results transfer directly; unchanged cells need no copy.
The hosted counterpart now retains the destination record type when lowering
a flow binding and extracts/copies a union payload into that layout, instead
of treating its cell address as a record. The regression exercises both
branches, differently sized descendants, independent mutation and zero
retained bytes. Validation: 80 focused ownership/copy checks passed; the new
join regression and four adjacent union/lifecycle fixtures run through both
compilers and both output backends, using a freshly native-built driver.
An earlier version of the native conversion also produced byte-identical
second and third generations and passed the three warm-cache regressions.

Follow-up from the reduced case: explicit stored `(Base & ~Child) | Child`
reached an unhandled `TypeAnd` in hosted union-storage selection. The record-
family checkpoint below closes that storage gap; the concrete child-union
reproducer above independently covers the earlier flow ownership fix.

Full-suite checkpoint at `b23ff134`: 3,481 passed, 14 skipped, two failures
in stale harness interfaces. The query-cache spy now forwards the shared
effect context; the length-transfer kernel comparison passes its caller's
truncate decisions and excludes caller-installed named-count relations.
Those relations retain independent source-level acceptance/rejection tests.
All 20 affected and adjacent checks pass after repair. The later flow-join
fix was validated separately as recorded above.

Integration checkpoint at `a91af1f9`: the direct native compiler pair reached
byte-identical second and third generations, with no hosted compiler or C
backend in the loop. Those generations took 62 s and 74 s respectively;
these are integration measurements, not a performance-target claim. All
152 Phase 1 parity cases passed against the final pair, including the
warm-cache lifecycle cases. The release job at `47fbc9cd` also passed.
Artifacts: `../dewy-build-artifacts/phase1-flow-join-final-2026-09-21` and
`../dewy-build-artifacts/phase1-flow-join-parity-2026-09-21`.

Checkpoint: scalar snapshots retain equality in the ordinary mutable fact
state. Changing either endpoint invalidates or transfers that relationship;
no special trusted rule is used for compiler-generated temporaries. Hosted
result contracts also retain the numeric consequences of symbolic bounds,
matching native comparison refinement. Parameter annotations now constrain
hosted assignment storage consistently with annotated locals and native
parameters. Previously a private parameter could be assigned an out-of-
contract value while its old facts were reinstalled by analysis.
Validation: 72 adjacent hosted checks passed. The scalar snapshot and
parameter-store corpus passes both compilers and both output backends using
a freshly native-built driver. Indexed scalar selections remain separate
work; snapshot equality does not equate every element of an array.

Checkpoint: resource-array `truncate` drops its suffix in reverse order before
releasing element storage. Counts above the current length are a no-op;
negative counts still require a proof failure. Selectors and the count are
captured once. The suffix helper proves that it preserves array length,
then the existing builtin transfer computes `min(old_length, count)`. This
uses an ordinary checked pre/postcondition, not a trusted generated fact.
May-write summaries reject selector/count expressions which replace or
relocate the selected receiver; proven read-only borrowed calls remain
usable. Hosted summaries include imported bodies as well as local hooks.

Validation: the final candidate passed 32 hosted/native checks, including
both x86-64 and C execution, symbolic length contracts, selector/count
side effects, imported counts, invalidation, and an intentionally damaged
helper whose length claim must be rejected. Repeated nested resource
truncation retains zero bytes. The preceding paired batch also passed the
clear, const-index, and ordinary truncation corpora (49 passing checks;
its two failures were repaired in this final batch). Seventy-two adjacent
hosted annotation/bounds/place checks passed. The native driver was built
by the verified native pair, not by the hosted compiler. Whole-compiler
integration and the updated full suite are separate subsequent gates.

Checkpoint: scalar facts now follow indexed elements selected by a literal or
immutable binding, alongside the existing field and sequence-length routes.
A guard can establish a selected denominator is nonzero, and a store can
establish its new value. Writes through potentially aliased indices, owner
mutation, and loop re-entry invalidate the evidence; mutable selectors do
not acquire persistent element identities. Assignment analysis evaluates
its operands once and records the result only when its target stayed stable.
Validation: eight hosted acceptance/rejection cases pass. The bounds-only
native visitor agrees with hosted analysis, and a freshly native-built
program driver passes the cases through both compilers and both backends.
These are ordinary array facts, not a special rule for generated helpers or
permission to assume distinct indices are disjoint.

Checkpoint: resource field and element replacement now uses the same lifetime
order as local-owner replacement. Selectors and the new value are evaluated
once, the old value's drop and component cleanup run, and the replacement is
stored through the rooted mutable place. Optional absence, nested arrays and
borrowed receivers follow the same path. A shared selector helper also serves
truncation; may-write summaries fence side effects that invalidate a selected
receiver. Drop calls remain ordinary checked operations, so their fact and
effect consequences are visible before lowering.
Validation: 28 focused checks passed using a freshly native-built program
driver, covering both compilers and both x86-64/C backends, adjacent clear and
truncate behavior, imported effects, optional/nested replacement, single
selector evaluation and zero retained bytes over repeated replacements.

Integration checkpoint at `61a044bd`: the direct native pair reached a
byte-identical generation 2/3 fixed point and passed its execution checks.
All 155 Phase 1 parity cases passed with shared prelude caching against the
final pair. Generations 2 and 3 took 131 s and 164 s while the full suite and
other checks ran concurrently; these timings are not performance baselines.
Artifacts: `../dewy-build-artifacts/phase1-truncate-integration-2026-09-21`
and `../dewy-build-artifacts/phase1-truncate-parity-2026-09-21`.

Full-suite checkpoint at `61a044bd`: 3,514 passed, 14 skipped, one bounds-
visitor mismatch. Native retained the identity of a block's saved scalar
result while hosted analysis retained only its numeric interval. Hosted
blocks now expose that identity only when trailing statements cannot change
it; assignments and mutable calls invalidate it. All 65 cases now agree
with the native bounds visitor produced by the full run.

The new result-order regression also exposed hosted conditional-return
lowering using a branch's last statement as its result. It now saves the
unique expressed value before trailing statements and returns it afterward,
matching the native implementation and the existing function-body rule.
Validation: 17 adjacent hosted checks pass. Positive/negative result-fact
cases and string/array snapshot cases pass both compilers and both backends.
No µDewy semantics changed. The full-suite count above records the original
run; it is not a claim that the entire suite was rerun after this repair.

Integration checkpoint at `1ef6c8d1`: the direct native pair again reached a
byte-identical generation 2/3 fixed point and passed execution checks. All
eight selected integration cases passed, including indexed scalar facts,
resource slots and block-result repair. Generations 2/3 took 64/73 s; this
remains above the native latency target. Artifacts are under
`../dewy-build-artifacts/phase1-resource-slots-integration-2026-09-21`
and `phase1-resource-slots-parity-2026-09-21`.

Checkpoint: mutable local places now select rooted bindings, record fields
and array elements. Selectors are captured once; ordinary checked assertions
prove valid selection at declaration, including an unused place. The same
structured lifetime analysis as required views includes derived aliases and
rejects owner replacement/resizing before their last use, captures and raw
exposure. Normal place lowering retains COW snapshot independence and const
barriers; no raw pointer survives between uses.

Storage contracts remain invariant, including declared refinements. Alias
writes invalidate source-checker owner facts and vice versa. Before ordinary
fact/effect/lifecycle checking, rooted selections replace alias reads/writes
and rebind dependent fact identities, including projected terms and nested
types. Native type factories preserve arena keys; only functions containing
aliases are rewritten. Speculation and hosted prelude rollback retain the new
metadata correctly. Debuggers currently expose the rooted owner instead of a
separately stored alias variable. Dictionary-entry and captured/exposed-owner
places still need further lifetime work.

Validation: 60 adjacent hosted view/cache checks passed. The final 37
acceptance/rejection cases and integration fixture pass both compilers and
both x86-64/C backends through a fresh native-built program driver. Coverage
includes generic instances, loop selectors, dependent refinements, alias
invalidation, resource replacement/drop, effects and explicit-copy policy.
The former test requiring mutable places to be unsupported was removed;
rejections for unstable selections and const storage remain.

CI checkpoint at `1ef6c8d1`: 3,517 passed, 32 skipped, one failure. The
remaining failure was an obsolete test expecting resource-field replacement
to be unsupported, after that operation had landed. It now executes the
replacement and checks the exact `42` then `1` drop trace; all 51 adjacent
hosted lifecycle checks pass. This updates the expected supported behavior,
not the compiler's acceptance rules. CI's release workflow passed separately.


Checkpoint: the same last-use proof now supplies existing owners to function
arguments, forwarded owning parameters, record/array construction, insertion
and field/element replacement. These are ownership inputs with one rule,
not separate syntax-specific move permissions. A first if condition is an
unconditional input site; branch bodies, repeated loop conditions and later
arms cannot consume an outer owner through this same-block proof.

Dependent read-only aliases extend the source lifetime, accounting for when
those aliases are created. The destination of the current transfer is not
an already-live alias. Custom move hooks run as checked calls, their remaining
nested fields are released, and the consumed owner does not drop twice.
Surviving sources requiring independent ownership still need a copy hook;
that rejection is now an ordinary ownership diagnostic. This does not yet
implement conditional outer-owner joins or field ownership transfers.

Validation: all 70 adjacent hosted lifecycle checks pass. Twelve new execution
cases, six adjacent/integration kernels and six rejection cases pass both
compilers and x86-64/C backends through a freshly native-built program driver.
The kernel checks exact hook/drop counts and zero retained arena bytes over
100 repetitions. Existing local-transfer, move-effect, resource-view and union
fixtures remain covered. Tests that formerly required array/record transfers
to be unsupported now check their single-drop execution behavior.


Integration checkpoint at `c2cc99a7`: the direct native pair reached another
byte-identical generation 2/3 fixed point, and all 160 parity cases passed.
The interrupted full pytest run found 17 failures (2,791 passed, 14 skipped),
mostly sharing a hosted build failure in the native program driver. This is
not a full-suite pass: native fixed points did not detect a hosted/source
parity gap in a bare `capture` declaration shadowing the prelude function.

The declaration now explicitly shadows with `let`; native function
predeclaration and imported-binding assignment enforce the existing rule.
A local-view diagnostic now supplies its required pointer message. The shared
source-checker tests no longer expect mutable local places to be unimplemented:
local usage is supported, while a module-level escaping selection is rejected.
37 adjacent checks passed; an initially malformed new execution case was
corrected to suppress its discarded call result. All corrected foreign-name,
import mutation, explicit-shadow and local-view cases pass both compilers and
both backends through a freshly hosted-built native program driver.


Loop-entry repair: source checking now distinguishes one-time iterator inputs
from repeated Boolean predicates and loop bodies. Both checkers retain entry
facts for iterable evaluation, then invalidate facts about backedge writes
before checking repeated code. This fixes a guarded pop nested inside an
iterator expression without requiring a split source expression.

The negative regression exposed an older native gap: unindexed pop had no
final non-empty obligation, so a two-iteration loop could pop a one-element
array twice. Both bounds visitors now prove positive length at each reachable
pop. The hosted source visitor defers dynamic proofs to this stage, permitting
valid finite-loop pops and retaining immediate empty-array diagnostics. Its
bounds visitor also evaluates an array-method receiver before the arguments.

Validation: 68 hosted iterator/array checks passed; four positive and four
negative cases pass both compilers and both backends using a fresh native
program driver. The old native pair accepted the over-pop counterexample;
the repaired driver rejects it. Finite two-element/two-pop iteration and the
nested guarded worklist loop execute with result 42. Repeated predicates and
an unguarded parameter pop reject. The integration manifest now includes the
worklist and over-pop cases.


Placement checkpoint: both allocation-effect checkers and lowerers now use
one bounded proof for fixed scalar local arrays. Only length/element accesses
are permitted: descriptor escapes, captures, address-taking, replacement and
resizing exclude this route. A conservative 4 KiB budget per function bounds
frame storage. Each slot is allocated in the prologue and reused when its
declaration executes again. Native descriptors mark the frame as owner;
ordinary release does not free it and writes need no COW detach.

This permits `no allocates`/`no_effects` for proven local array computation,
including inferred calls and defaults, while retaining allocation permission
for unproved aggregate storage. It is an implementation proof budget, not a
source array-size limit. General placement, scoped arenas, escaping aggregates
and placement through nonescaping calls remain further work.

Validation: 119 adjacent hosted allocation/effect checks passed. Five runtime
cases and eight rejection cases passed both compilers and x86-64/C backends
through a freshly native-built driver. The kernel repeats 10,000 times with
zero arena bytes allocated, covering mutable words, bools, narrow integers and
empty arrays. Capture/escape, resize/rebinding and per-function budget limits
reject. The hosted compiler also successfully emitted the updated native
program driver. Additional iterator rejection probes exposed a pre-existing
native unindexed-pop proof gap, repaired separately; they are not counted as
passes here.


Recursive ownership checkpoint: cleanup now closes recursive type expansion
with checked borrowed helper calls, publishing each helper identity before
building its body. Runtime recursion follows the active, finite stored values.
Hooks still run before fields, and fields/array elements retain reverse cleanup
order. Transparent casts naming a fresh value through a recursive alias retain
its ownership; they do not create an implicit copy. Arrays containing recursive
optional-link records work. The separate language gap for recursion *through*
`array<Self>` remains unimplemented, as does general recursive field transfer.

Validation: 66 hosted lifecycle checks passed. Five execution cases and two
rejections pass both compilers and both backends through a fresh native-built
program driver. Coverage includes linked and branching records, reverse array
cleanup, recursive factories, exact hook order/counts, effect contracts and
move-only independence. A 100-call kernel drops all 300 nodes and retains zero
arena bytes. No new source syntax or lifecycle semantics were introduced.


Integration checkpoint at `386475fb`: native generations 2/3 are byte
identical and execution checks pass on the direct and C backends. Generation
2/3 took 92/97 s with other tests running; these are not isolated performance
measurements and remain above the latency target. Artifacts are under
`../dewy-build-artifacts/phase1-placement-integration-2026-09-21`.

The next interrupted full run at `fc9030f4` recorded 3,425 passes, 14 skips and
two failures. One was the newly exposed unindexed-pop gap repaired above;
the other was an outdated generated snapshot codec omitting `local_place_roots`.
The codec is regenerated, its outer format is bumped to 7, and the snapshot
fixture now checks that nonempty owner-map data survives. The generator
freshness test passes. A new full run includes these fixes and recursive cleanup;
these interrupted counts must not be represented as a full-suite success.

Native execution-test groups now share only their checked prelude cache within
a worker and compiler binary. Each input still starts a fresh process and
Session. Explicit cold-cache tests retain an opt-out. A paired two-group
probe took 33.82 s cold and 4.38 s warm, with acceptance/rejection and both
backends checked. This removes repeated setup rather than reducing coverage.

Recursive-copy checkpoint (2026-09-21): hosted method hoisting now publishes
a fully annotated signature before checking its body, matching native method
predeclaration. A copy hook can therefore recursively copy its optional tail.
Both ownership passes also accept fresh conditional/block initializers,
capturing each branch's expressed value before releasing its local owners.
Trailing statements retain their original evaluation order. Synthesized
recursive wrapper copies use the same component-hook rules. This does not
introduce first-class lifecycle hooks or conditional consumption of outer
owners. Read-only receivers, move-only restrictions and effects remain checked.

Validation: 92 hosted adjacent lifecycle cases passed; four positive and three
negative cases passed on both compilers, with each positive executed through
x86-64 and C. Cases cover custom and synthesized recursive copies, branch
cleanup, trailing statements, receiver writes and empty effect contracts.

Branch-local result checkpoint (2026-09-21): an expressed value in a resource
block is now an owning input to the existing bounded last-use analysis.
Move-only locals can leave either branch without a synthesized copy; later
reads/writes and dependent aliases still prevent transfer. Statements after
the value retain their evaluation point. Outer-owner joins remain separate.
Validation: ten hosted checks and six positive/four negative paired cases
passed, with all positives executed through x86-64 and C.

Affine-loop checkpoint (2026-09-21): the bounded qualifier vocabulary now
connects exact entry-value groups with constant differences, while retaining
separate equality groups when another counter advances at a different rate.
Every advancing edge must preserve a candidate. At most 64 entry terms are
considered, with linear-size stars rather than all pairs. A one-hop reduction
combines interval and difference evidence when proving an update fits its
word. Rollover invalidates affine facts, including a narrow operation widened
into a wider destination; mathematical order cannot survive modular wrap.

Validation: 32 adjacent hosted loop/proof checks passed. Five positive and six
negative cases passed both compilers and x86-64/C; the new native driver also
successfully checked and emitted its own complete source. The manifest adds
nonzero parallel-array differences and narrow-operation rollover rejection.
This extends the bounded proof machinery without adding source syntax.

Completed full-suite checkpoint at `c2cc5330`: 3,628 passed, 14 skipped, two
failed in 2,341.73 s. Both failures were outdated expectations: a guarded pop
retains a weaker nonnegative difference, and fixed nonescaping scalar arrays
now satisfy `no allocates` through frame placement. The revised tests retain
strict-positivity/index rejection and runtime-length escaping-array rejection;
all 21 adjacent tests passed. The website's unchecked `nat64` sum now checks
fixed-width overflow, and all 329 published examples validate. These repairs,
recursive copies, branch-local transfers and affine qualifiers are integrated
at `bd17c8c5`; 43 focused integrated checks pass. The previous CI run at
`fc9030f4` completed with 3,585 passes, 32 skips and only the two already-fixed
pop/snapshot failures. Website CI is green at `bd17c8c5`; full CI remains a
separate gate, not a claimed pass.

A fresh native inventory of `c2cc5330`, using the verified `386475fb` native
pair, records 4,919 bootstrap-only static copy sites across 45,661 physical
Dewy lines (107.729 sites/KLOC): 1,185 records, 667 arrays, 479 cells and 2,588
strings. This is a scoped inventory, not a comparison with the earlier
whole-program baseline, nor a count of runtime allocations/bytes. Detailed
output is `/tmp/dewy-phase1-copy-inventory.json`. The reporting path rescanned source prefixes and rendered thousands of
source excerpts that the inventory tool then discarded. Concise reporting
and shared source geometry address that avoidable work.

Copy-inventory gate checkpoint: `dewy analyze --brief` preserves every copy
entry/count without rich excerpts; hosted move, representation and cap notes
remain available in concise form, and unsafe auditing is not suppressed.
Native reporting reuses immutable source-line indexes, and lowering memoizes
copy type names. The inventory tool defaults to concise mode, with
`--legacy-analyze` retained for historical compiler seeds. The existing native
command test now gates the bootstrap at 5,000 static sites and 110 sites/KLOC.

Validation: 14 hosted report/CLI checks and 11 options/tool checks passed.
Native rich/concise inventories agree with CRLF and Unicode source offsets.
A padded-source warm probe took 3.199 s rich versus 1.520/1.473 s concise,
with identical entries; this measures reporting overhead, not compiler build
latency. The full own-source gate records 4,932 sites over 45,710 Dewy lines
(107.898/KLOC), taking 62.98 s and 2,694,940 KiB peak RSS. Artifacts are
`/tmp/dewy-phase1-copy-budget.{json,log}`. These budgets are static reporting
ratchets, not permission to hide copies or substitutes for byte-level kernels.

Integration checkpoint at `bd17c8c5`: direct native generations 2/3 are byte
identical; generation times were 64/74 s with other work running, still above
the latency target. Direct and C execution checks pass, and all 168 expanded
hosted/native parity cases pass. The pair and parity outputs are under
`../dewy-build-artifacts/phase1-affine-{integration,parity}-2026-09-21`.
The concise-report change is subsequent to this fixed-point certification.

## Unwritten local view lifetimes (2026-09-21)

An unwritten `let` projection now uses the same shorter lifetime proof as a
`const` projection in both compilers. The source must remain stable through
the last use of the view and its derived aliases; captured, exposed, written
or escaping bindings still need independent values. This introduces no new
aliasing semantics. Early source eligibility checks avoid scanning scopes
whose owners cannot satisfy the private-storage proof.

Validation: 71 adjacent hosted checks passed. A freshly built native program
driver passed 12 positive and one negative case against the hosted compiler,
with accepted programs executed through both direct and C backends. The
strict-copy fixture checks zero allocation during reads and zero retained
storage after repeated calls; writes through scalar and array fields, owner
mutation, and a captured local retain independent values.

## Shared forwarding storage proof (2026-09-21)

Allocation contracts and both lowerers now share a read-only array-parameter
forwarding proof. A whole-caller access summary rules out later-argument
writes; a closed call graph excludes nonlocal storage, raw operations and
unresolved callbacks. Parameter and representation agreement are required.
Default expressions participate in the graph. Native operator purity uses
the binding registry, so a user function named like an intrinsic cannot
acquire its guarantees. Recursive and named forwarding can satisfy
`no allocates` or `no_effects` without treating COW deferral as proof.

Validation: 73 adjacent hosted checks passed. A fresh native driver passed
the zero-allocation fixture and six rejection cases against hosted checking;
the fixture executes through direct x86-64 and C. That driver also checked
and emitted its own complete source successfully (20 MB of emitted µDewy).
This is the first shared argument-storage slice; other projection borrows,
moves and placement still need to feed allocation checking.

Full CI checkpoint at `bd17c8c5`: **3,636 passed, 32 skipped**, in 2,618.68 s.
The website and native release checks are also green. Subsequent concise
reporting, unwritten-let views and forwarding proofs have their own targeted
validation and await the next full integration run.

## Excluded record-family storage (2026-09-21)

Hosted checking and lowering now share the native compiler's structural-base
query: exclusions restrict values while comparable positive record types
determine layout. Logical alternatives retain their own tags and predicates.
Union packing selects among descendant/exclusion alternatives by dynamic
brand when the source fits the union collectively. Native checking now permits
that already-proven case to reach its existing dynamic packing path.

Field reads/writes, copies, release and lifecycle capability queries use the
positive storage view. Nested descendant tests no longer treat every excluded
record family as disjoint from all other records. Splitting a stored parent
alternative into several descendants preserves the correct child field offsets.

Validation: 58 adjacent hosted checks passed, followed by all 12 final focused
cases. Nine positive and three negative programs pass both compilers, with
positives executed through x86-64 and C. They cover parent/child/grandchild
values, sibling narrowing, independent fixed-array copies, frame-only storage,
move-only resources and rejected copies, logical fact retention and zero
retained allocation after repeated calls. The hosted compiler also checked
and emitted the complete native test driver (49,897,821 bytes).

The preceding forwarding-proof snapshot's native own-source inventory passes
the unchanged 5,000-site / 110-per-KLOC gate at **4,865 sites / 45,841 lines =
106.128 per KLOC** (67.85 s; 2,712,860 KiB peak RSS). This is a static inventory,
not a runtime byte count or a full native build latency measurement.

## Inherited resource moves (2026-09-21)

Compiler-generated inherited move wrappers now adopt added resource fields,
including arrays and multiple inheritance levels. The original user hook still
operates on its parent portion. Cleanup follows the composition chain and drops
only that hook's leftover fields; transferred child fields belong to the result.
This privilege applies only to checked compiler-generated composition, not to
ordinary borrowed receivers. Inherited copy hooks still require copyable added
fields. No surface syntax or hook invocation guarantees change.

Validation: 44 adjacent hosted checks passed. A fresh native driver passes the
fixture and two rejection cases against hosted checking; accepted programs run
on x86-64 and C. Exact drop traces distinguish the consumed parent fields from
transferred children, and arena counters check complete storage reclamation.

## Storage integration checkpoint (2026-09-21)

At `38b8cec8`, generations 2/3 of both native compilers are byte identical
through the direct x86-64 route. Direct and C execution checks pass, as do
all **173** explicit parity cases. Artifacts are under
`../dewy-build-artifacts/phase1-storage-{integration,parity}-2026-09-21`.
Generation times were 68/78 seconds with concurrent work, not isolated
performance baselines; the direct-route latency target remains outstanding.

## Conditional resource consumption (2026-09-21)

A backwards liveness pass joins the possible future reads of each branch.
An owning input at last use may consume an outer owner on that path. Aliases,
captures, overlapping sibling arguments and later uses retain ownership; loop
backedges remain conservative. Existing same-block transfers remain available.
The compiler inserts an ordinary boolean only for owners needing conditional
cleanup. This tracks logical resource ownership; the storage lowerer retains
its separate borrow/copy/move decisions. No source annotation is needed.

Flags are initialized beside the owner's declaration, or at entry for owning
parameters. Transferred owners remain in lexical cleanup lists, preserving
scope and loop boundaries. Custom moves still clean their leftover fields
before deactivation. Native lowering now treats unscoped void statement groups
as part of their enclosing storage lifetime, while selected arms retain their
own scope; generated transfer declarations are not released before later uses.

Validation: all 207 selected hosted lifecycle checks passed, plus the repeated
conditional kernel. A fresh native driver passes ten positive and six negative
conditional cases against hosted checking, running accepted cases through both
x86-64 and C. Adjacent consumption, recursive copies, inherited moves, resource
array operations and ordinary container text cases pass on the same routes.
The driver checked and emitted its own complete source (20,910,854 bytes;
70.83 seconds, 3,016,084 KiB peak RSS). This batch follows the fixed-point
checkpoint above and is not yet a new fixed-point certification.

## Iteration-local ownership (2026-09-21)

The branch liveness proof now distinguishes owners created during an iteration
from owners that must survive its backedge. Iteration-local owners may transfer
inside conditional branches, including break/continue paths and nested loops.
A return ends the function rather than advancing the loop, so an owning input
on that exit may also consume an outer owner. Other repeated consumption of
outer owners remains rejected. No loop-count heuristic or source annotation
is involved; the distinction comes from birth scopes and control-flow exits.

Validation: 23 focused and 68 adjacent hosted checks passed. Four positive and
three negative cases pass a freshly built native driver against hosted checking,
with all accepted cases executed through x86-64 and C. They check immediate
versus end-of-iteration drop timing, break/continue cleanup, function returns,
nested loops, rejected repeated consumption, and complete storage reclamation.

## Resource iterator source lifetimes (2026-09-21)

Resource arrays and dictionaries now use ordinary lexical owners for iterator
sources. Existing move, copy and read-only-view proofs choose how to keep each
source alive. Read-only loop bindings borrow their elements; an owning value
boundary in the body invokes the usual checked copy. Fresh factory results
receive logical cleanup on returns, breaks, continues and normal completion.
Dictionary key/value leaves share one evaluated receiver. Multi-iterator setup
preserves source evaluation order, including ordinary sources before resources.
The existing restriction on dictionary mutation during iteration is unchanged.

The hosted borrow planner now recognizes stable single-place parameters when
no ambient call or alias can change their storage. Native lowering no longer
rejects an addressed source after the borrow planner has proven its lifetime.
The hosted padded-iterator path stores a borrowed element word into its cell;
it must not treat an already-lowered record load as an owning function call.

Validation: 21 focused hosted checks and 59 adjacent borrow/view checks pass.
Resource iteration and place-view programs run through hosted/native checking
and x86-64/C execution, including zero retained bytes over 100 early-return
loops. The final source-order/dictionary-source/view bundle passes five
positive and seven negative cases. The rebuilt native driver checks and emits
its own source (21,229,873 bytes). The preceding `5e4281cb` direct-route fixed
point also completed all 184 explicit hosted/native parity cases; this newer
batch is not yet a fresh fixed-point certification. These changes do not
complete Phase 1: entry places, broader field transfers and placement, full
strict-copy acceptance, effect-row inference and proof provenance still need
work.

## Dictionary fallback lifetime correction (2026-09-21)

The first executable effect-row inference kernel exposed a hosted `.get`
lifetime bug. A read-only record binding borrowed the dictionary's storage,
but a missing key selected a newly constructed fallback. Statement cleanup
released that fallback's nested strings before the next statement used them.
Both lowerers now require an independently owned result when an unproven
lookup can select a fallback; stability of the dictionary alone is not a
lifetime proof for the fallback. Proven entry borrows retain their usual path.

The reduced fixture fails before the hosted fix and passes afterwards on
x86-64 and C, including zero retained bytes across 100 calls. The newly built
native driver passes the same fixture and the effect solver kernel against
the hosted compiler on both backends. Nine focused and 34 adjacent hosted
checks passed. Source-level inference is still being connected to the solver.

Integration checkpoint: `f7e5c1ec` closes the direct native bootstrap with
byte-identical generations 2/3, direct/C execution checks, and all **186**
explicit hosted/native parity cases. Generation times were 68/79 seconds
with concurrent work, not isolated latency baselines. Artifacts are under
`../dewy-build-artifacts/phase1-iteration-f7e5c1ec-*`. CI also completed at
`5e4281cb`: **3,803 passed, 32 skipped** in 55m24s. Neither result certifies the
newer fallback correction as a new fixed point.

## Public effect-row inference machinery (in progress, 2026-09-21)

Both implementations now have an independent monotone row solver. Function
bodies seed possible behavior; selected assignment constraints widen inferred
destination rows. Unknown operations and unresolved user row parameters remain
unknown or symbolic. Explicit permissions are removed before inferring a row's
residual; negative contracts are checked against the result and never erase
possible effects. Reverse dependency worklists handle recursion and long chains.
The public-effect body inventory is now callable without a written contract;
ordinary validation reuses it. Connecting inferred rows to source callable
types and recording selected-boundary obligations is still outstanding.

Validation: 33 focused/adjacent hosted checks pass. The Dewy solver executes
through both hosted and native checking on x86-64 and C. Three written-effect
programs and five rejection cases also agree across the two compilers after
the inventory refactor. This is an internal foundation checkpoint, not a
claim that callable-type inference is complete.

## Reassigned callback call targets (2026-09-21)

The inferred-callable tests exposed an independent native lowering bug: a
callback variable reassigned from one function to another could still call
its initial function. Call-target discovery now invalidates initializer-only
resolution after assignment or writable exposure. Saved function handles
retain their value semantics. The focused regression passes hosted/native
checking and x86-64/C execution, including repeated assignment and a saved
handle. Function-handle place parameters remain separately unsupported.

## Inferred callable rows (2026-09-21)

Omitted function-literal rows now receive compiler identities shared by
prebinding, body checking and generic specialization. Ordinary callback type
annotations with no row remain open. The fixed point combines body behavior
and selected value-boundary constraints; speculative subtype/overload probes
do not contribute assignments. Deferred checks preserve the actual value
type, survive lifecycle insertion and erase before runtime lowering. Native
cache codecs retain the new metadata. Internal identities are not displayed
as source syntax.

A copied callback handle gets an independent inference variable: reassigning
it cannot widen its source function's own row. Compatible conditional callable
shapes join possible behavior instead of introducing distinct runtime variants
solely because their inferred rows differ. Recursive and generic callbacks
retain their body effects, and unknown operations stay unknown. Union and
overload boundary checks are conservative when several alternatives compete.

Scoped polymorphic place rows still need a retained substitution environment.
Until that exists, moving an unresolved inference variable to a different
place scope contributes unknown behavior rather than reusing an unrelated
parameter index. Preserving open negative guarantees through inferred wrappers
also remains pending; the positive-row solver does not infer such exclusions.

Validation so far: 142 adjacent hosted effect/lifecycle/proof checks and 44
focused row/callable checks pass. The preceding native build passed seven
positive and six negative callback cases on x86-64/C against hosted checking,
and checked/emitted its own source (21,670,022 bytes; 61.95 seconds and
3,101,360 KiB peak RSS under concurrent work). The final batch passes eight positive and eight negative cases on both
compilers/backends, including lifecycle cleanup. After the unannotated-program
fast path and literal-reassignment correction, another 104 hosted checks and
the final two positive/three negative native cases pass. Twelve hosted cache
checks preserve cold/resident/on-disk behavior. These are bounded development checks, not
a new native fixed-point or latency certification.

The rebuilt native CLI reports **4,992** bootstrap copy sites over 47,049
source lines (**106.102/KLOC**), within the unchanged 5,000/110 gates. Inventory:
`../dewy-build-artifacts/phase1-inferred-effects-copies.json`. The absolute
budget is close; subsequent batches must keep reducing unproved copies.

## Immediate dictionary key borrows (2026-09-21)

Native membership and default-free lookups now borrow a string binding until
probing finishes. The probe runs no user code, so a later assignment to the
binding does not require an independent handle. Longer intervals still use
the existing stability proof; in particular, an eager lookup default can
change the key and retains the earlier snapshot. This is a lowering proof,
with no new surface syntax. Hosted probes already read these keys directly.

Validation: the key-lifetime fixture passes both compilers on x86-64 and C,
including an eager default that changes a global key. Native analysis removes
five unnecessary key-copy sites in that fixture while retaining the default's
snapshot. The command test checks this inventory distinction; the runtime
fixture also checks that a warmed membership probe allocates no storage.


## Negative guarantees through inferred wrappers (2026-09-21)

Possible effects still grow from bodies and selected assignments. Alongside
that least fixed point, exclusions shrink over a finite vocabulary gathered
from bodies and obligations. Requirements only nominate candidates; every
body and incoming assignment must establish each surviving guarantee. An
unknown operation removes unsupported candidates even in a recursive cycle.
Written permissions are removed before checking an inferred residual.

Both implementations preserve open guarantees through inferred callable
wrappers without pretending those wrappers are pure. Generic row substitution
still carries positive rows, so negative guarantees across a user `E` remain
separate work, as do scoped place substitutions and competing callable
alternatives.

Validation: 22 hosted callable/guarantee checks pass. The native solver kernel,
positive source wrapper and unknown-callback rejection agree with hosted
checking on x86-64 and C. A rebuilt CLI checked the compiler's own source.
The batch initially exceeded the copy gate (5,031 sites); immediate dictionary
key borrowing removes 50 sites in the combined-source inventory, bringing it
to 4,981 (105.642/KLOC), under the unchanged 5,000/110 limits. This preliminary
combined inventory uses the key-borrow CLI; the integrated source remains due
for its own fixed-point check.

The preceding callable-inference revision, `69b8eb8d`, separately completed
191/191 hosted/native parity cases and a byte-identical direct native fixed
point. Its generation timings were 65 and 77 seconds under concurrent work;
these are not isolated latency benchmarks and do not meet the 30-second goal.

## Generic negative effect guarantees (2026-09-21)

Generic row arguments now carry complete contracts, including negative
promises. Inference combines permissions and retains only guarantees shared
by every contributing callback. An unknown callback removes unsupported
exclusions; adding a permission can invalidate an inherited exclusion.
Explicitly written exclusions remain obligations on the complete row.

Binding metadata, signature substitution, instance cache identity and native
prelude serialization preserve these contracts. The ordinary inferred-row
solver shares the same substitution helper. Callback-relative place exclusions
remain rejected as generic row arguments until their scope can be represented;
they must not accidentally name a slot in the enclosing signature.

Validation: 60 hosted effect checks and 12 hosted prelude-cache checks pass.
Two positive programs and one rejection case agree on both compilers and
x86-64/C. A native cached prelude containing two distinct negative-only generic
instances produces identical output before and after restoration, and both
outputs execute correctly on both backends. The rebuilt native CLI reports
4,985 bootstrap copy sites over 47,170 source lines (105.682/KLOC), within the
unchanged 5,000/110 gates. Inventory:
`../dewy-build-artifacts/phase1-generic-guarantees-copies.json`.

The preceding integrated revision, `181db533`, reached another byte-identical
direct fixed point, with native execution checks on both backends. Its own
rebuilt pair confirms 4,981 sites over 47,154 lines (105.633/KLOC). Generation
2/3 took 70/80 seconds during concurrent work; the latency target remains open.

## Full-suite regression repairs (2026-09-21)

The user's failure report was reproducible in CI: revision `80a83728` had
15 failures, 3,866 passes and 32 skips. Earlier selected parity checks did
not establish that the full suite passed. Roadmap work paused for these
repairs:

- Callable arrays and loop captures join the effect rows of otherwise
  identical signatures. Distinct inferred rows no longer cause a misleading
  homogeneous-element error, and the join retains every possible effect.
- Deferred effect checks preserve callable binding, receiver and default
  metadata. This repairs method/default-argument errors and runtime crashes
  without dropping the effect obligations carried by those checks.
- Native method-body inference uses the complete parameter scope, including
  the hidden receiver. Only written contracts need their source parameter
  indices shifted. Prebound signatures retain their inference identity.
- Generic-signature expectations now account for per-instance inferred rows.
  The snapshot regression uses complete generic effect contracts, including
  negative guarantees, rather than the superseded positive-row representation.

The complete local run collected 3,923 tests and finished with **3,904 passed,
14 skipped and five failures** in 76m54s. It started before the final snapshot
fixture and native method repairs landed. The snapshot failure passes its
focused pytest rerun; both method/ordered-call failures pass their original
test functions against the rebuilt native checker. The other two failures
were filesystem fixtures affected by this development session's `/tmp` quota;
both pass their focused pytest rerun after old development artifacts were
moved to disk-backed storage. There were no other failures. This is full-suite
coverage followed by targeted repairs, **not a claim that one final full-suite
invocation was all green**. Local evidence lives in
`../dewy-build-artifacts/pytest-repairs-full.{log,xml}` and the focused repair
logs alongside it.

The first ten new callable regression tests passed in that full run. The final
method repair adds five passing hosted cases and a native harness covering
three valid programs and two rejected contracts, checked against hosted
execution on x86-64 and C. Existing native move-hook and inferred-callback
checks also pass with the rebuilt driver. These checks preserve rejection of
unknown/effectful callbacks under pure contracts and of methods whose written
mutation permission names the wrong argument.

The final compiler repair (`3794df8b`, built in its isolated worktree as
`c5095e30`) closes a three-generation C-backed native bootstrap of both Dewy
and µDewy, with byte-identical final compiler generations and runtime checks
on x86-64/C. The resulting pair is
`../dewy-build-artifacts/pytest-repairs-native-pair`. Its own copy inventory is
**4,985 sites over 47,211 lines (105.590/KLOC)**, within the unchanged 5,000/110
gates (`pytest-repairs-final-copies.json`). Generation 2/3 took 199/201 seconds
while the full suite was running; these are not isolated latency measurements.
Phase 1 and the performance target remain unfinished.

## Effect validation activation (2026-09-21)

The native type table now distinguishes inferred body metadata from contracts
that impose obligations. Omitted rows and private inference variables alone
no longer trigger whole-program public-effect validation and erasure scans.
Explicit permissions, empty rows, exclusions and user row parameters activate
the existing complete validation path. Activation is monotone and remains
part of the cached type table; importing a constrained callable cannot disable
it. Proof functions retain their independent validation/erasure trigger.

Validation: 123 hosted effect/proof checks pass. A freshly built native driver
passes the activation kernel and generic negative-guarantee fixture on x86-64
and C against hosted execution, and rejects both lifecycle and generic
guarantee violations. This removes unnecessary work without changing effect
semantics; no isolated latency improvement has been measured yet.

## Projection stability and forwarded place storage (2026-09-21)

The storage evidence shared with allocation checking now asks whether writes,
rebindings or escapes overlap the particular projection being forwarded.
An untouched sibling field can remain borrowed; replacing an ancestor or
mutating a descendant cannot. Array selectors still use the conservative
shared index step. Ordinary whole-parameter read-only cases take the existing
fast path without constructing a route. Raw exposure, unknown callees and
lifecycle-bearing values retain their restrictions.

The tests also exposed an accounting gap: forwarding a scalar field/element
to a mutating helper could omit the storage obligation imposed on a direct
projected write. Both public-effect analyzers now use the same projected-store
rule for these calls. A disjoint borrow does not establish that mutating the
other field is allocation-free. Known read-only element calls and proven
scalar frame places still satisfy empty rows.

Validation: 16 new hosted cases pass, with eight valid programs and eight
rejections checked by a second-generation native driver against hosted
checking/execution on x86-64 and C. The adjacent aggregate-borrow/access and
public-allocation/effect checks pass (29 and 106 existing hosted cases).
These are bounded checks, not another complete pytest or fixed-point run.

## Frame storage through nonescaping place calls (2026-09-21)

Fixed scalar arrays and scalar records may now lend element/field addresses
to known nonescaping callees while remaining in reusable frame storage. The
public allocation checker and lowering consume the solved parameter escape
summaries. Every possible target and argument position must establish the
lifetime; unknown callbacks, captured owners, whole-container uses, resizing
and the existing frame-size limit retain their restrictions. Forwarding,
recursion and keyword argument pairing need no new source annotations.

The effect collector retains call sites for the new proof, avoiding another
whole-HIR traversal. The native borrow planner also exposes its already
validated place sites to placement. Projection stability shares the route
overlap query instead of constructing concatenated mutation/escape arrays.
The new native escape proof updates its sets rather than rebuilding them at
each call; this removes accidental repeated copying of the growing result.

Validation: the new hosted cases and adjacent frame/projection checks passed
(40 in the first run, with one additional rejection case corrected to avoid
an unrelated bounds error; the corrected six new cases and 52 adjacent
allocation/access checks pass). A second-generation native driver agrees with
hosted checking on five execution kernels and 14 rejections on x86-64/C.
The new 10,000-iteration kernel observes zero arena allocation while passing
array-element and record-field addresses through helpers. Initial compiler
inventory was 4,995 sites over 47,295 lines (105.614/KLOC), within the unchanged
gates. That inventory precedes the final set-update cleanup; a fresh native
fixed point and final inventory are the next integration check.

Integration follow-up: `23a0d7a6` completed the three-generation C-backed
native bootstrap with byte-identical final Dewy and µDewy generations. The
resulting pair passes all **211/211** cases in the hosted/native parity
corpus on the direct x86-64 backend. Its final inventory is **4,986 sites over
47,300 lines (105.412/KLOC)**, within the unchanged 5,000/110 gates. Artifacts:
`../dewy-build-artifacts/phase1-frame-placement-23a0d7a6`,
`phase1-frame-places-parity`, and `phase1-frame-places-final-copies.json`.
Generation 2/3 took 190/198 seconds including C compilation and concurrent
development work; these are not isolated latency measurements.

## Nested getter projections (2026-09-21)

Both lowerers extend the existing direct-getter specialization from one field
to a checked field path, such as `node_at(nodes id).position.start`. They keep
the original arguments, default evaluation, guards, prefix effects and cleanup.
The complete source owner stays alive while the path is read; only the leaf
needs an independent lifetime. Integers/bools pass directly, while selected
strings and runtime-length arrays are retained before temporary-owner cleanup.
Constructors and unsupported control-flow results keep the ordinary route.
Variant identity includes the full path, so different nested fields with the
same final name cannot share the wrong implementation.

Validation: six existing hosted projection tests and four new hosted tests
pass. The nested scalar kernel allocates/copies/retains zero arena bytes; its
hosted positive control with specialization disabled allocates over 100 KB.
The second-generation native driver agrees on this kernel, effects/defaults,
temporary string/array lifetimes, and the failing runtime guard on x86-64/C.
Its rebuilt native CLI reports **4,987 sites over 47,324 source lines
(105.380/KLOC)** in the isolated checkout, within the unchanged gates.
Artifacts use the `../dewy-build-artifacts/phase1-nested-projections-` prefix.
Integration follow-up: the three-generation direct x86-64 bootstrap also
completed, with byte-identical final Dewy and µDewy generations and passing
runtime checks on x86-64/C. Generation 2/3 took 67/77 seconds during concurrent
development; these are integration timings, not isolated latency measurements.
The 211-case corpus certification above belongs to the preceding placement
checkpoint. Phase 1 remains in progress.


## Whole-owner frame loans (2026-09-21)

The shared placement proof now distinguishes call-only addresses from whole
owners whose storage remains fixed. Known nonescaping helpers may read whole
fixed scalar arrays or update fields of scalar records in reusable frame
storage. Every resolved target and argument position must establish the
relevant guarantee; owner replacement, array mutation/resizing, raw exposure,
captures, unknown callbacks and by-value whole-owner uses remain conservative.
This extends the existing place protocol without a new source annotation.

Hosted raw arrays receive a borrowed call descriptor and slot. Native frame
arrays also keep the addressable handle slot in the frame, with no arena cleanup
for either block. The storage budget includes that slot. A 10,000-iteration
kernel observes zero arena allocation through forwarding, recursion and keyword
calls, including whole-array reads and whole-record field mutation.

Validation: 62 focused hosted allocation/access checks pass; the frame groups
also passed (29 initial checks and 20 corrected checks after the hosted call
adapter). A second-generation native driver agrees with hosted checking and
execution on 15 kernels and 18 rejections across x86-64/C. The compiler inventory
is 4,988 sites over 47,364 lines (105.312/KLOC), within the unchanged gates.
Artifacts use `../dewy-build-artifacts/phase1-whole-frame-` prefixes. This slice
has bounded second-generation validation; the preceding nested-getter checkpoint
is the most recent full native fixed point.


## Conditional callable access summaries (2026-09-21)

Access/effect analysis now retains all known targets of a conditional callable
value, including stable aliases and checked value wrappers. Dispatch selection
is applied inside each possible overload value rather than selecting one
runtime branch. Every alternative must justify a loan; unresolved arms,
reassigned handles and alias cycles remain unknown. Public effects also check
the selector expression, while constructing an overload set only evaluates its
operands. Native borrowing reuses this target resolution and the already
collected access graph.

Shared choices use a bounded graph walk rather than enumerating paths; ordinary
direct calls keep their fast path and unresolved ingress/intrinsics create no
search state. A shared graph with 65,536 paths and an unresolved cycle have
explicit regressions. Choosing either of two known read-only array helpers now
retains frame placement and zero arena allocation across repeated calls.

Validation: 94 adjacent hosted effect/placement tests passed initially; 38
hosted callback/projection cases pass after the overload-evaluation correction.
The final focused run passes 11 tests, including native/hosted effect-summary
parity on the shared graph. A second-generation native driver passes 11 runtime
kernels and 16 rejections against hosted checking on x86-64/C. The inventory is
4,991 sites over 47,432 lines (105.224/KLOC), within the unchanged gates.
Artifacts use `../dewy-build-artifacts/phase1-conditional-place-` prefixes.
These are focused checks, not a new complete pytest run or fixed point.


## Default-argument assumption audit coverage (2026-09-21)

The audit collector now enters a function through all of its executable HIR
children, including parameter defaults, while keeping nested function scopes
separate. Previously a default's assumption could disappear from the sidecar
when the collector skipped straight to the body. Unused functions and explicitly
overridden defaults still retain their source assumptions. This is inventory
coverage; consumer lists remain the documented conservative function-scope
candidates, not exact proof dependencies.

Validation: all 18 hosted assumption checks pass, plus the two parameterized
resident/persistent prelude-cache cases. The fresh native CLI retains the named
default audit for unused, used and overridden defaults on x86-64/C; all six
executables return 42. It rejects a proven-false unused default and replaces a
stale sidecar after removal. Repeated native invocations also retain an unused
imported default with its original source path. The native command regression
now covers these cases alongside its existing invocation checks. Artifacts use
the `../dewy-build-artifacts/phase1-default-audit-` prefix.


Integration checkpoint: `3e30f72a` completed the three-generation direct x86-64
bootstrap with byte-identical final Dewy and µDewy binaries and passing runtime
checks. Generation 2/3 took 66/76 seconds during concurrent development; these
are integration timings, not isolated latency measurements. The certified pair
reports 4,991 copy sites over 47,440 lines (105.207/KLOC). Artifacts:
`../dewy-build-artifacts/phase1-loans-audit-3e30f72a` and
`phase1-loans-audit-copies.json`. Native cache invalidation after removing the
imported default also replaces its audit with an empty report.

## Stable local values at ordinary call boundaries (2026-09-21)

The shared storage proof now lends fresh local array/record owners to known
read-only by-value callees. Local owners must remain unwritten and unexposed
throughout the containing function, including defaults; call-graph checks still
exclude nonlocal/raw access and unresolved callbacks. Incoming parameter loans
retain their existing route proofs. Fixed outer array lengths may erase at the
boundary when the element representation stays identical. Lifecycle values and
alias initializers retain their independent ownership requirements.

Frame placement consumes the same per-call evidence, including keyword calls,
so small scalar owners no longer need an explicit `@` to avoid allocation.
Occurrence counting still rejects a separate escaping use of the same HIR node.
The shared 4 KiB budget is unchanged. The direct-write query was extracted from
predicate effects and reused over the existing unique function inventory rather
than adding another recursive traversal.

Validation: 34 initial hosted storage checks, 44 adjacent effect/borrow checks,
and the final 11 local-value checks pass. Native/hosted predicate dependency
parity passes. A second-generation native driver passes ten runtime kernels and
14 rejections against hosted checking on x86-64/C, including snapshots across
later argument mutation, captured-write rejection, keyword calls and the storage
budget. The 10,000-iteration kernel observes no arena allocation. The measured
compiler inventory is 4,992 sites over 47,474 lines (105.152/KLOC), within the
unchanged gates; subsequent edits only clarify comments/tests. Artifacts use
`../dewy-build-artifacts/phase1-frame-values-`. These are bounded checks, not a
new full-suite or fixed-point certification.

## Dictionary array views and hosted parity (2026-09-22)

Proven dictionary array entries now lend their stored descriptors through the
existing local-view lifetime proof. Read-only inferred bindings use the same
route; explicit demands reject conflicting writes and temporary fallbacks.
Returning a view or explicitly copying it still creates an independent value.
Hosted checking now follows dictionary storage to its named owner, matching
native checking for both record and array entry views.

The compiler's storage analysis uses checked views for retained function bodies,
local-owner maps, reverse call edges and parameter summaries. Function body
inventories move into their table after the final local read. The native
inventory falls from 4,992 to 4,986 sites over 47,487 lines (104.997/KLOC), with
unchanged budgets. Ten hosted view cases and 61 adjacent lifetime checks pass;
six runtime kernels and five rejections agree across hosted/native checking and
x86-64/C execution. The eager-default case explicitly checks receiver mutation.

The full hosted compiler build also exposed two parity gaps. Optional numeric
calls and conditional `none` arms now retain common payload bounds without
proving presence or preserving facts across assignment. Four execution cases
and three rejections agree on both compiler/backend routes; 36 adjacent bounds
checks pass. Read-only defaulted record parameters now borrow supplied values
in hosted lowering. Cleanup uses the existing ABI presence bit, so only omitted
defaults are owned locally. Mutable/escaping/resource parameters retain their
existing ownership requirements. Ten selected parameter/default tests pass,
and two repeated lifetime kernels agree on both compilers and backends.

Checkpoint `eea60209` closes another three-generation direct bootstrap: the final
Dewy and µDewy generations are byte-identical and runtime checks pass. Generation
2/3 took 69/82 seconds with concurrent development, not isolated latency samples.
The subsequent hosted-only default fix emits and links the complete compiler
(54,290,861 bytes of µDewy); its executable reports the expected version and compiles the frame-value
fixture, which exits with the expected 42. Full corpus parity passed all
211 explicit cases against the certified pair and hosted checkpoint `1e3eefa6`. Artifacts use the
`../dewy-build-artifacts/phase1-dictionary-views-`, `phase1-dictionary-array-views-`,
`phase1-optional-conditional-bounds-` and `phase1-readonly-defaults-` prefixes.
These checkpoints do not complete Phase 1 or certify a new full pytest run.


## Stable string comparison roots (2026-09-22)

Native whole-string and slice/index comparisons borrow roots whose existing
storage proof establishes stability. Other roots retain an owning snapshot
through evaluation of the right operand. Nested spans retain the same owner,
selectors execute once in source order, and only owned roots are released.
The hosted comparison path now snapshots a left value when the right operand
may replace its source, including transitive calls, module initializers,
defaults and early returns. String-valued flow temporaries use their runtime
handle representation even when the semantic type is a string literal.

The native compiler inventory drops by 596 sites to **4,390 over 47,488 lines
(92.444/KLOC)**. CI budgets ratchet to **4,500 sites and 100/KLOC**. This measures
static copy sites, not elapsed time or runtime copied bytes. The Unicode
comparison kernel runs 1,000 iterations without arena allocation under
`$explicit_copies`. Eight hosted snapshot cases pass; paired x86-64/C runs
also cover the allocation kernel, eleven existing descriptor/lifetime kernels,
four text cases and three rejections.

Checkpoint `a708b511` closes the three-generation direct x86-64 bootstrap with
byte-identical final Dewy and µDewy generations and passing runtime checks.
The certified pair reports the same 4,390 sites over 47,501 source lines
(92.419/KLOC) in the integrated checkout and passes the tighter gates.
Generation 2/3 took 64/82 seconds during concurrent work, not isolated latency
measurements. Artifacts use `../dewy-build-artifacts/phase1-string-comparison-views-`
and `phase1-string-views-` prefixes. These are focused checks and a fixed point,
not a new complete pytest or corpus certification of this checkpoint.


## Scoped inferred call rows (2026-09-22)

Public effect analysis now retains a call's subject mapping as a solver
projection. It resolves the callee row before translating parameter slots and
field routes, including reassigned callbacks, keyword calls and nested wrappers.
Private arguments erase only their own storage effects; unknown behavior stays
unknown. Body equations and selected callable-boundary constraints use one
solver rather than a separate body-call fixed point followed by row inference.
These equations are transient analysis data, not new type syntax or cache data.

Negative guarantees translate without broadening their routes. Written
exclusions nominate candidates; inverse call mappings propagate those demands
to source scopes by removing prefixes and renaming slots. The finite vocabulary
therefore remains route suffixes even with recursion. Every candidate still
needs evidence from all defining rules. Deep positive paths retain the existing
widening, while deep exclusions drop. General user-written polymorphic `E` rows
with callback-relative place subjects remain conservative: this checkpoint
retains environments for inferred call equations, not those generic binders.
Function-handle assignment also no longer implies allocation by itself;
projected storage writes still retain their separate storage obligation.

The solver kernel exposed a hosted iterator bug: optional record elements in a
composite iterator were wrapped as present records instead of preserving their
stored tags. Optional scalar/string and general union cells now use the same
borrowed tag/payload transfer. Dictionary entries, nested record storage and
padded array iteration preserve absence and execute correctly.

Validation: 125 hosted effect checks passed before the negative-demand
extension; 95 adjacent proof/allocation/cache/iterator checks pass after the
final correction. The solver kernel, six scoped-call programs and three
optional-iterator programs pass hosted/native checking and x86-64/C execution;
five wrong-scope/forbidden-effect cases are rejected by both compilers. The
native inventory is **4,408 sites over 47,545 lines (92.712/KLOC)** in the isolated
checkout, within the tighter 4,500/100 gates. Artifacts use
`../dewy-build-artifacts/phase1-scoped-inferred-` prefixes. The latest certified
full fixed point remains the preceding string-view checkpoint; this slice has
second-generation execution checks. Phase 1 remains in progress.


Integration checkpoint: `e145a7f2` completed the three-generation direct x86-64
bootstrap with byte-identical final Dewy and µDewy binaries and passing runtime
checks. Generation 2/3 took 66/81 seconds during concurrent work, not isolated
latency samples. The certified pair is
`../dewy-build-artifacts/phase1-scoped-effects-e145a7f2`; the preceding 211-case
corpus result belongs to the dictionary-view checkpoint.


## Ownership at loop exits (2026-09-22)

Logical ownership liveness now follows the selected loop continuation for
`break` and `continue`, including labeled exits. Repeating paths retain outer
owners; a break path may transfer one at its last use when nothing after the
selected loop needs it. Nested loops retain the enclosing continuation, so
breaking only the inner loop cannot consume an owner needed on the next outer
iteration. Existing alias/capture checks and conditional cleanup flags remain
authoritative. Custom move hooks and owning parameters use the same path proof.
No new move syntax or resource representation is introduced.

Validation: 36 focused hosted loop/branch checks pass. A second-generation
native driver passes 19 runtime kernels and 16 rejection cases against hosted
checking on x86-64/C, including labeled exits, live aliases, continued paths,
custom moves, drop counts and repeated-call retained-memory checks. The native
inventory is **4,411 sites over 47,551 lines (92.764/KLOC)** in the isolated
checkout, within the 4,500/100 gates. The reference now describes scoped effect
inference and the supported conditional resource transfers. Artifacts use
`../dewy-build-artifacts/phase1-loop-exit-` prefixes. The latest complete native
fixed point remains `e145a7f2`; this is a bounded second-generation ownership
checkpoint, not completion of Phase 1.


Broader hosted validation after `21fe9314`: `pytest -q -k 'not bootstrap and
not native'` completed with 3,400 passed, 14 skipped and one failure in 446 s.
The failure expected a stable known read-only function alias to require an
array copy, predating the local-value loan proof. That expectation now accepts
the proved loan; a new incoming-unknown-callback case still requires a copy.
All 58 static-array tests pass after this test correction. This is the broader
hosted selection plus a focused repair, not a complete all-route pytest run.
The log is `../dewy-build-artifacts/phase1-effects-exits-hosted-suite.log`.


## Mutable dictionary entry places (2026-09-22)

Both compilers now accept local mutable places selecting proven dictionary
entries. The shared lifetime rule retains the stored owner through the last
use of all dependent aliases; other dictionary mutations in that interval
remain conservatively conflicting. Keys and enclosing array selectors are
captured once. The rewritten route probes the saved key instead of keeping a
physical position that compaction can invalidate. Missing entries, const
ancestors, captures and changed owners remain errors.

Entry fact identities distinguish dictionary keys from array indices and
retain const-selector reentry dependencies. Alias-dependent contracts rebind
to those same identities. Payload writes invalidate value facts while keeping
ancestor dictionary membership, without retaining cached entry positions.
Native mutable routes now detach shared dictionary/value-array storage before
selecting payload storage, and record/array payload detachment writes the new
handle back into the entry slot. Optional record payloads retain their stored
union layout. Resource replacement uses ordinary drop-before-store cleanup.

Validation: 106 adjacent hosted checks passed, followed by 31 focused checks
after correcting the optional-value fixture and adding a repeated-call kernel.
Two additional strict-copy/dependent-contract cases passed paired execution.
Together the fresh second-generation native driver agrees with hosted checking
on 21 runtime kernels and 12 rejection cases, with execution on x86-64 and C.
The repeated-call kernel preserves earlier snapshots and retains no arena
bytes over 100 calls, including a dictionary with tombstones. The native
snapshot tests initially caught shared record/array mutation and pass after
routing detachment back through the entry slot. Logs/artifacts use
`../dewy-build-artifacts/phase1-entry-` prefixes. This is a bounded checkpoint;
the latest full fixed point is still `e145a7f2`.

Additional probes identified existing gaps outside this slice: ordinary
membership is forgotten at loop entry; unnamed `totaldict` receivers need
better totality propagation; hosted array layout does not yet erase a nested
`totaldict` refinement. These probes are not counted as passing coverage.
Phase 1 remains in progress.


Integration checkpoint: `a240f952` completed the three-generation direct x86-64
bootstrap with byte-identical final Dewy and µDewy binaries and passing native
runtime checks. Generation 2/3 took 66/74 seconds during concurrent work;
these are not isolated latency measurements. The pair is
`../dewy-build-artifacts/phase1-entry-places-a240f952`. Its inventory is
**4,414 sites over 47,648 lines (92.638/KLOC)**, within the 4,500/100 gates.
The full corpus checkpoint remains the earlier 211-case dictionary-view run.


## Public container storage effects (2026-09-22)

Public inference now gives built-in array growth/removal/reservation/joining,
dictionary/set operations and array iteration bounded read/mutation/allocation
rows instead of making the whole operation unknown. Storage permission remains
conservative: even lookup may construct/compact a hash index, and mutation can
detach shared backing storage. These are permissions, not claims that every
execution allocates. Selector, argument and eager-default effects propagate;
unknown callees still cannot satisfy a closed row. Lifecycle hook calls remain
subject to the ordinary validation after ownership rewriting.

A dictionary entry selection uses its containing dictionary as its public
subject, not an internal values-array path. Address formation itself reads the
keys, so a write-only callee cannot silently justify `no reads<table>`. Array
addresses retain their existing selector-only rule. Sort callbacks remain
unknown until their implicit call equations are represented.

Validation: 20 initial hosted container checks and 140 adjacent
allocation/effect/lifecycle checks pass. A fresh second-generation native driver
agrees with hosted execution on 16 container/scoped-effect kernels and 16
rejections across x86-64/C, including eager defaults, effectful selectors,
transitive wrappers, missing permissions and resource drop hooks. This includes
the added dictionary-address read exclusion regression. Artifacts use
`../dewy-build-artifacts/phase1-container-effects-` prefixes. The preceding
dictionary-place commit is the latest complete native fixed point; Phase 1
remains in progress.

## Sort callback effects and option evaluation (2026-09-22)

Sort keys now contribute their invoked bodies or callback contracts to the
public effect equations. Function-handle selection contributes its own effects;
known conditional/reassigned targets join, unconstrained callbacks stay unknown,
and generic row arguments retain their guarantees. Sort still needs storage
permission. Global-write summaries also follow the implicit key call through
wrappers, preserving snapshots across callback writes. String-to-string
widening retains the operand's effects without inventing unknown behavior.

Hosted lowering now evaluates sort options once in source order, including on
empty arrays, and saves indirect key-call results before numeric normalization.
The native lowerer already used these evaluation rules. No µDewy evaluation
semantics changed.

Validation: 32 focused hosted tests passed. A fresh native driver passed 26
runtime kernels and 22 rejection cases against hosted checking, with x86-64/C
execution, including the adjacent container/scoped-effect groups. Artifacts:
`../dewy-build-artifacts/phase1-sort-effects-*`. The preceding broad hosted run
at `82d73625` passed 3,456 tests with 14 skipped in 522.18 seconds using
`-k 'not bootstrap and not native'`; that is not a complete all-route pytest run.
The latest complete native fixed point remains `a240f952`. Phase 1 continues.

## Total dictionaries as value guarantees (2026-09-22)

`totaldict` now retains its named guarantee through factory results, optional
narrowing, record-field reads and array storage. Unnamed receivers can use the
same totality proof as bindings. Contextual storage wrappers retain already
proved totality rather than losing it at a second argument/element check.
Literal key evidence survives conversion to the storage key type. Hosted array
layout now erases element refinements through the shared representation query.

The same bounds remain enforced at construction, replacement and removal:
a partial result cannot stand in for a total dictionary, and clear/pop cannot
remove a required key. Proved value refinements preserve their operand effects;
accessing a computed owned container still accounts for producing that value.

Validation: 76 hosted object/entry-place checks passed before the final effect
classification; 107 hosted total-dictionary/public/container-effect checks
passed afterward. A fresh native driver passes seven runtime kernels and nine
rejections against hosted checking on x86-64/C. A repeated temporary lookup
calls its factory once per iteration and retains no arena bytes over 100 calls.
Artifacts use `../dewy-build-artifacts/phase1-totaldict-` prefixes. Full integration
checks are running separately; these focused checks do not complete Phase 1.

## Sort storage lifetimes (2026-09-22)

Both checkers now reject sort keys and option expressions that can invalidate
selected receiver storage. The shared call graph follows wrappers and known
callback targets. Private owning values remain independent of unrelated
callbacks; captured/exposed owners and borrowed receivers require a stable
call graph or a contract proving no mutation. Borrowed receivers conservatively
include externally reachable owners because their caller may supply an alias.
This does not add closure mutation support: writes to enclosing function locals
remain a separate unsupported case.

Validation: the fresh native driver agrees with hosted checking on 15 runtime
kernels and 13 rejections (including the preceding sort effect group), executing
on both x86-64 and C. Cases include by-value snapshots, mutable record key
arguments, captured receivers, transitive writes, effect-qualified keys and
option evaluation. Artifacts use `phase1-sort-lifetimes-*` under
`../dewy-build-artifacts`. Phase 1 remains in progress.


Integration checkpoint: `f729d465` completed the three-generation direct x86-64
bootstrap with byte-identical final Dewy and µDewy binaries and passing x86-64/C
runtime checks. Generation 1/2/3 took 162/124/78 seconds under concurrent load;
these are not isolated latency measurements. The pair is
`../dewy-build-artifacts/phase1-totaldict-f729d465`. Copy inventory: **4,418 sites
over 47,770 lines (92.485/KLOC)**, within the 4,500/100 gates. The broad hosted
selection (`-k 'not bootstrap and not native'`) passed **3,488 tests with 14
skipped** in 569.44 seconds. These integration results precede the sort storage
lifetime change; its fresh paired checks are recorded separately above.


## Owning field returns (2026-09-22)

Returning a resource field from a local owning record or by-value parameter now
transfers that field and drops the remaining fields in reverse order. Nested
synthesized wrappers, optional fields, arrays of resources, conditional exits
and custom moves on the selected field share the rule. A custom move still
cleans up the consumed component's remaining fields and must establish the
return facts. Wrappers with their own lifecycle hooks conservatively retain
the complete-receiver requirement; borrowed parameters/views cannot donate
ownership. Native last-use rewriting no longer promotes an explicit resource
view to an owning transfer, fixing a paired acceptance mismatch.

Validation: 278 adjacent hosted lifecycle tests passed before the final explicit
view guard; the final focused hosted selection passed 13 tests. A fresh native
driver agrees on eight runtime kernels and five rejections, with x86-64/C
execution. The array-field kernel checks 100 calls with no retained arena bytes.
Artifacts: `../dewy-build-artifacts/phase1-field-return-*`. General partial
transfers and array-element returns remain pending; Phase 1 is not complete.


## Returning owned array components (2026-09-22)

An exiting array owner can now transfer a selected element, including mixed
field/index paths, nested arrays, optional results and custom moves. Selectors
are saved once before the result is evaluated; conflicting receiver writes
remain errors. Reverse cleanup skips the transferred component and drops its
siblings. Nested array traversal uses a checked borrowed helper so each loop
has a stable array identity. This extends the existing exit-transfer rule;
there is no new source syntax or partially initialized value available to user
code. Non-exiting partial transfers still require further lifetime work.

These tests also found and fixed a shared-HIR constant-index bug. Both bounds
analyzers now retain a constant only when all checked occurrences agree;
disagreement with another constant or a dynamic occurrence removes it. Native
discharge clears stale annotations on revalidation. Hosted graph-level tests
cover arrays and strings; the paired nested-record cleanup test would otherwise
drop the wrong indexed record.

Validation: 23 hosted field/element tests passed before the final reduction in
helper generation; the final ten element tests passed afterward. There are 34
passing adjacent bounds/index/generated-contract checks, plus the two added
string graph checks. A fresh native driver passes 15 execution kernels and
eight rejection cases against hosted checking on x86-64 and C. Dynamic selection
is evaluated once; the repeated-call kernel retains no arena bytes over 100
calls. Artifacts use `../dewy-build-artifacts/phase1-element-return-*` and
`phase1-index-adjacent.log`. Phase 1 remains in progress.


Integration checkpoint: `7f040b71` completed the three-generation direct x86-64
bootstrap with byte-identical final Dewy and µDewy binaries and passing native
runtime checks, including x86-64/C execution. Generation 1/2/3 took 154/141/104
seconds under concurrent test load; these are not isolated latency results.
The pair is `../dewy-build-artifacts/phase1-component-returns-7f040b71`.
Copy inventory is **4,452 sites over 48,103 lines (92.551/KLOC)**, within the
4,500/100 gates. The broad hosted selection (`-k 'not bootstrap and not native'`)
passed **3,527 tests with 14 skipped** in 590.13 seconds. This is not a complete
all-route pytest run; fresh paired checks for this batch are recorded above.

## Nested scalar record placement (2026-09-22)

The shared nonescaping frame proof now includes records containing nested scalar
records, under the existing 4 KiB per-function budget. Repeated field shapes
count separately; recursive, dynamic-storage and lifecycle-managed shapes do
not qualify. Native lowering initializes compatible nested record literals
directly in their parent's frame storage, preserving field order and earlier
field bindings used by defaults. Nominal adaptation retains its existing
storage obligations. Public allocation inference uses the same literal-tree
proof, including ordinary read-only forwarding and known nonescaping places.

Validation: 38 hosted adjacent placement/loan tests passed, followed by ten
final nested-record checks. A fresh driver agrees with hosted checking on 14
runtime kernels and 14 rejections on x86-64/C. The kernels verify zero arena
allocation, including 100,000 loop iterations, nested nominal records, scalar
field mutation, defaults and read-only/by-place calls. Copies that need an
independent value, escapes, dynamic fields and oversized shapes remain
conservative. Artifacts: `../dewy-build-artifacts/phase1-nested-frame-*`.
Phase 1 continues.

## Explicit fixed-record copies in frame storage (2026-09-22)

The same placement proof now supplies independent frame storage for explicit
copies of scalar records, including nested records and copies into inline
fields. Fresh literal/copy chains can initialize that destination directly;
a copy of an existing value writes its scalar fields into independent storage.
Source evaluation and nested field defaults keep their original order. The
source owner may itself remain in frame storage because `.copy()` does not
expose its address. Escaping results and dynamic/resource storage retain their
allocation obligations; COW is not used to justify the exclusion.

Validation: seven focused hosted tests pass. A fresh native driver agrees on
11 runtime kernels and five rejections (including nested-record placement),
with x86-64/C execution. Kernels check value independence, by-value parameters,
fresh-copy chains, inline-field copies and zero arena allocation over 100,000
iterations. Artifacts use `../dewy-build-artifacts/phase1-frame-copy-*`.


## Explicit fixed-array copies in frame storage (2026-09-22)

Fixed scalar arrays now use the shared 4 KiB frame budget for explicit copies
as well as literals. Copies of existing arrays write independent data; fresh
literal/copy chains initialize the destination directly. Native descriptors
mark frame ownership so writes need no COW detachment and cleanup cannot free
the frame. Dynamic, resizing and escaping arrays keep allocation obligations.

The paired tests exposed proof witnesses hiding an explicitly typed initializer
from native placement. Both analyses now look through representation-preserving
obligations and their discharged one-value blocks. Ordinary proof validation
still rejects a false length; placement does not assert it.

Validation: 25 adjacent hosted tests passed before adding two refinement cases.
The final fresh native driver agrees with hosted checking on 17 runtime kernels
and nine rejection cases on both x86-64 and C. This includes the added refinement
cases, independent narrow-word/boolean copies, fresh chains and zero arena
allocation over 100,000 iterations. Artifacts: `phase1-frame-array-copy-*`.


## Frame-copy integration checkpoint (2026-09-22)

Source `113146f1` closes the three-generation direct x86-64 bootstrap. Both
compiler binaries in generations two and three are byte-identical, and the
pair's x86-64/C execution checks pass. Artifacts are in
`../dewy-build-artifacts/phase1-frame-copies-113146f1`. Generations took 163,
191 and 131 seconds under concurrent test/build load; these are validation
runs, not isolated performance measurements.

The broad `tests/python_misc -k 'not bootstrap and not native'` selection passed
3,554 tests with 14 skips in 771 seconds. This is not the all-route pytest suite;
a few selected import tests also exercise native drivers. The new pair reports
4,457 bootstrap copy sites across 48,220 source lines (92.431/KLOC), within
unchanged 4,500-site and 100/KLOC gates. Logs and JSON use the
`phase1-frame-copies-*` artifact prefix. Phase 1 remains in progress.

## Last-use component inputs (2026-09-22)

Owning bindings, calls, record construction and array construction now transfer
a field or element when its containing local/by-value owner has no later use.
The proof is shared with whole-owner input transfers: it excludes captures,
borrowed owners, surviving aliases and conditional/repeated parent-scope uses.
Custom wrapper hooks still require complete receivers. Selectors are saved
once, and receiver-changing selector effects remain rejected.

The wrapper keeps its lexical cleanup. Cleanup skips the transferred component,
or cleans only its remaining fields after a custom move, and drops siblings in
reverse order. The selected owner cleans up independently, including after
returns and loop exits. This does not yet allow transferring one component
while subsequent code continues to use siblings of the same owner.

Sixteen focused hosted cases passed, including dynamic selections over 100
calls without retained arena growth. The adjacent lifecycle selection passed
304 tests; a fresh native driver agrees with hosted checking on 26 runtime
kernels and 13 rejections on x86-64/C, including field/element returns.
Artifacts use `phase1-component-moves-*`. This feature is newer than the
`113146f1` integration certificate.


## Re-established ownership across loop backedges (2026-09-22)

Resource liveness now solves a finite backward fixed point at loop conditions.
Whole-value assignment kills the previous value's future liveness; `continue`
(including labeled exits) contributes to the selected loop's backedge, and
`break` retains the continuation after that loop. A consuming input may move
when every advancing path supplies a replacement before the next use. This
also handles owning inputs in loop conditions. Captures, overlapping arguments
and live aliases retain their existing exclusions.

Replacement evaluates the new value first, conditionally cleans up the previous
owner, stores the replacement, and re-enables its cleanup flag. A move does not
leave that binding permanently exempt from cleanup. Custom move hooks and
nested storage use the same protocol.

Validation: 52 adjacent hosted checks passed. Fresh native/hosted comparisons
passed 20 runtime kernels on x86-64/C and 16 rejection cases across renewal,
iteration-local ownership and loop exits. The nested-array move kernel runs
100 renewals with no retained arena growth. One initially selected explicit-view
negative hit a pre-existing unsupported-lifetime diagnostic rather than the
intended move rejection; the final case uses an inferred alias and reaches
that rejection on both routes. Runtime cases were not rerun unnecessarily;
rejection checks and the two final storage kernels ran separately.
Artifacts use `phase1-renewed-owners-*`. Broader partial ownership and the
remaining Phase 1 proof/effect work are still in progress.


## Disjoint record component ownership (2026-09-22)

Same-block component liveness now compares member paths. A move of `pair.first`
no longer conflicts with a later read, write or transfer of `pair.second`.
Whole-owner uses and ancestor/descendant routes overlap; captures and surviving
whole-owner aliases still block the proof. Indexed transfers retain the earlier
whole-root last-use rule until index disjointness joins this analysis.

Cleanup retains all transferred paths, not just one. It recursively skips each
moved component, cleans custom-move remnants, and releases untouched siblings
in reverse order. Returned components combine with prior transfers. Union
alternatives preserve this metadata, and recursive cleanup follows a finite
selected path before using its ordinary per-shape helper; previously those two
routes could forget a selection and repeat its drop.

Validation: 71 hosted adjacent cases passed. Fresh hosted/native comparisons
passed 28 runtime kernels on x86-64/C and 15 rejections, including recursive
and optional owners, multiple transfers, sibling replacement, custom move
remnants, and 100 array-field transfers without retained arena growth.
Artifacts use `phase1-partial-records-*`. Field reinitialization, conditional
partial ownership and broader indexed disjointness remain conservative.


## Partial-record integration checkpoint (2026-09-22)

At `e8d2a2da`, the direct x86-64 three-generation bootstrap completed with
byte-identical second/third generations of both compilers and passing x86-64/C
execution checks. Generation times were 165/152/130 seconds under concurrent
load, not isolated performance measurements. The broad
`tests/python_misc -k "not bootstrap and not native"` selection passed 3,603
tests with 14 skips; this selection is not the complete all-route suite.

The fresh native copy inventory contains 4,479 sites over 48,324 source lines
(92.687/KLOC), within the unchanged 4,500-site and 100/KLOC gates. Artifacts
are `phase1-partial-records-e8d2a2da/`, `phase1-partial-records-bootstrap.log`,
`phase1-partial-records-broad.log`, and `phase1-partial-records-inventory.json`.
Full corpus certification remains a separate gate.


## Effect-parameterized type aliases (2026-09-22)

Generic type aliases now accept the existing separately kind-checked `E:Effect`
parameters in both compilers. Applications resolve argument kinds before
substitution: `Action<no_effects>` supplies a row and `Action<E>` forwards one.
The row table is keyed by lexical binder identity, separate from value-type
arguments. Positive bounds, open negative guarantees and nested callable
binders retain ordinary substitution behavior. Mixed type/row aliases,
composition and imports use the same mechanism. Native checking now resolves
applied generic aliases through module namespaces as well.

Validation: 18 final focused hosted checks pass; 41 adjacent generic/row checks
passed before correcting one fixture that exercised unsupported non-literal
callable field storage. The final fixture uses an ordinary function literal.
A fresh native driver agrees on eight runtime kernels and ten rejections,
with x86-64/C execution. Cold/restored prelude snapshots retain alias row kinds,
emit byte-identical output, execute correctly and reject a value type supplied
as a row. Artifacts use `phase1-effect-aliases-*`. Callback-relative place rows
and other remaining Phase 1 work are still in progress.


## Reinitializing transferred record fields (2026-09-22)

A direct same-block assignment to a field, its containing record, or the whole
owner now starts a new lifetime after a component transfer. The liveness proof
checks every RHS read before that renewal; the target occurrence alone is not
a read of the old value. Conditional replacements, live aliases and borrowed
owners remain conservative.

Cleanup drops the still-owned old descendants and custom-move remnants, then
forgets only the replaced route's extraction metadata. The new value receives
normal cleanup. Returning before replacement retains the earlier partial
cleanup plan; returning the complete record after replacement transfers all
its renewed fields.

Validation: 62 adjacent hosted cases passed before adding two final exit/multi-
field fixtures; the final focused selection passed 15. A freshly built native
driver and the hosted compiler agree on 20 runtime kernels and 12 rejections,
with x86-64/C execution. Repeated array-field replacement retained no arena
allocation across 100 calls. Artifacts use `phase1-field-renewal-*`.


## Full corpus checkpoint (2026-09-22)

All 211 default corpus cases passed acceptance/rejection and expected runtime
comparisons using native pair `phase1-partial-records-e8d2a2da` and frozen hosted
source `28dbe7db`, through direct x86-64 output with shared checked-prelude
caches. The report is `phase1-partial-records-corpus.json` and its log is
`phase1-partial-records-corpus.log`. This certifies the corpus at those inputs;
field renewal and subsequent source changes retain their separate focused
validation until the next integration checkpoint.
