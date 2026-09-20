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

Design review: `PHASE1_DESIGN_PROPOSALS.md` contains proposed proof and effect
surfaces. David requested approval before implementation. These proposals
are not language rules and do not mark 1.2 or 1.3 complete.

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
