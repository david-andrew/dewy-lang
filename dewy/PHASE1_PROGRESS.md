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
  unit-nominal, and uniform-container decisions. Preserve the decisions to
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
The expanded 55-case paired parity run is in progress.
