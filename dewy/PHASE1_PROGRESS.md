# Phase 1 implementation checkpoints

Started 2026-09-20 from `be7d1b1a`. The scope is all of Phase 1 in
[ROADMAP.md](ROADMAP.md), with the correctness/parity closure checkpoint
first. This ledger records implementation and validation, not new language
decisions. Open design questions stay open until resolved with David.

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
  number juxtaposition: `(x+1)5` and `(y)3.14159` multiply and `(f)2`
  calls or multiplies by the type of `f` (ROADMAP 1.4 item 1, corrected
  2026-09-21); the four 2026-09-20 blacklist entries in both parsers and
  the tight-spelling tests pin the wrong behavior. Preserve the decisions to
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
