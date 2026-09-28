# Phase 1 finite fact domain

This records the fragment implemented by the hosted and native analyzers. It is
an implementation boundary, not a replacement for the broader liquid-refinement
design in `status.md`. A missing proof stays unknown; the compiler must not turn
an inference budget or an unsupported expression into evidence.

## Sources of evidence

A checked parameter contract supplies facts at function entry. A guard supplies
facts only on its corresponding path. Every normal exit checks a written result
contract; callers then substitute stable actual arguments into that contract.
By-value arguments are snapshots: a call that changes an argument's source does
not establish a result fact about that source's new value. Place postconditions
refer to the caller's value after the call.

`$assert` requires an existing proof. `$runtime_assert` supplies its condition on
the success path. `$unsafe_assume` accepts and audits unknown assumptions but
rejects conditions already refuted. An assertion inside a loop may select a
candidate relation; its desired conclusion is never evidence for that candidate.
Checked `$proof` functions have their separate, erased statement-call boundary.

The compact source contract grammar accepts integer/literal bounds and named
value or length bounds, comparisons, conjunctions and ordered comparison chains,
field projections, type/tag facts, and true/false result arms. Dependent `not=?`
uses the same syntax as dependent order comparisons. Arbitrary arithmetic
expressions in a type's bound are not a general symbolic contract language yet.
Ordinary conditions and assertions have wider expression syntax: interval
arithmetic and checked affine recognition can prove some of them, while an
unrecognized expression contributes no symbolic theorem. A pure call contributes
its checked contract, not a guessed meaning from its source name. This also
applies to lexical operator declarations: a user function named `__lt__` is not
an intrinsic comparison. Builtin recognition requires its binding identity (or
an explicitly lowered integer operation tag). Guard and storage affine transfer
both require the mathematical result to fit its machine representation.

## Identities and stored facts

Facts name declaration identities and registered field/element routes, not source
spellings. A term is a scalar value or a sequence length. Current facts include:

- a numeric interval, with target-address-cap provenance;
- nonzero evidence and an index bound against a named sequence;
- an ordered difference, `larger - smaller >= gap`;
- a remainder bound, `upper - offset >= subject + gap`;
- a symmetric disequality between two terms;
- separately maintained literal/type alternatives and callable predicate facts.

An immutable sibling-field contract can establish a relation whenever its field
is read. Mutable numeric selections can be named while their selectors stay
unchanged. A changed selector, overlapping field/index write, length-changing
operation, or possibly aliasing call invalidates the affected identities. Numeric
selection tracking does not make arbitrary mutable indexed type narrowing safe.

Private constructor field bindings live through default evaluation and value
installation, then expire with their temporary routes. Destination field facts
and independently stored snapshots survive that expiration. Lexical scope
exits also retire local routes and selections whose indices have expired.
Normal, break and continue edges use the same cleanup; destination snapshots
are installed before their source locals expire. Native cleanup batches the
retired identities into one state scan.

A scalar or length snapshot receives the source facts that still describe its
observed value. Later replacement of the source discards relations involving that
source, while relations between the snapshot and other unchanged terms survive.
For example, `let size = xs.length` creates a scalar term; it does not create a
new sequence to which index facts may refer.

Uniform array-element summaries retain numeric intervals, both endpoints of
order facts, index/remainder facts, nonzero facts and disequalities about stable
external terms. Transfer renames every occurrence of the stored value's identity,
including its length and sequence/upper/offset positions in relations. Scalar and
length identities remain distinct. Static length evidence joins through this
same summary, rather than a separate length-only path. Source identities must still describe the evaluated argument;
later constructor fields or call arguments that change them prevent symbolic
transfer. Record field initialization consumes captured values, never replays
initializers. A stored foreign
element removes unsupported summaries; clearing or popping to empty makes old
summaries vacuous, so the first replacement discards them before deriving new
facts. Reading or copying the array transfers the surviving summaries. This is
not a complete aggregate relational domain yet.

## Entailment and joins

Intervals answer constant range questions. The finite ordered graph answers
transitive difference questions without a fixed two-edge cutoff; search is
bounded by its existing edge count. Affine updates retain relations only when
the arithmetic and its destination cannot wrap. A cheap one-edge interval
reduction handles ordinary counters; when it is insufficient, forward and
reverse paths through the established graph tighten upper and lower bounds.
Each endpoint carries its path evidence, including address-cap provenance.
The edge-count relaxation limit never supplies a convergence assumption. The remainder form connects
checked sums, offsets and slices without inventing general nonlinear rules.

Linear comparison queries can combine these established difference paths with
integer coefficients: `a<=c` and `b<=d` prove `2*a+3*b<=2*c+3*d` when every
intermediate operation fits. Normalization accepts addition, subtraction and
multiplication by a known constant, with cancellation of equal identities.
It uses at most 128 expression visits and 32 distinct terms per query. Opposite
coefficients consume concrete order paths; unmatched terms use ordinary
interval endpoints. Pair selection is deliberately incomplete, so a different
matching could prove a query this implementation leaves unknown. No new facts
are assumed by normalization, and nonlinear expressions, invalidated identities,
opaque calls, potentially wrapping intermediates and exhausted budgets stay
unknown. The query itself never installs new evidence. Separately, bounded linear
source syntax can select difference candidates for ordinary loop validation.

Disequality does not choose an ordering. It can sharpen a known non-strict integer
order. A join retains facts supported on every reachable incoming path. For an
already selected disequality, a peer path can supply the same fact, a direct
strict order in either direction, or disjoint intervals. This does not enumerate
all term pairs or run graph closure at each join. Other unsupported combinations
remain unknown, even when a stronger solver could establish them.

## Loop candidates and budgets

Before invariant search, a memoized control summary checks whether a while body
can advance to its condition. A body with neither fallthrough nor a local
`continue` is validated once from its incoming state. Nested loops consume their
local continues and propagate outward targets, so `continue $outer` prevents
this optimization on the targeted loop. Value facts never supply this structural
termination evidence. Abstract transfers preserve outward break/continue states
across while, finite-iterator and general iterator boundaries.

Candidate selection is bounded separately from proof:

- exact entry values select at most 64 changing terms and a linear-size set of
  difference relations through representative anchors;
- source predicates and subtraction select at most 64 deduplicated term pairs;
  while guards precede bodies in this shared pair budget. Names under addition,
  subtraction and literal scaling also select cross-operand pairs, with at most
  128 expression visits and 32 terms per operand. These still propose only
  ordinary differences, not general coefficient-weighted invariant facts;
- entry intervals must establish each offered difference;
- the loop condition's effects and every advancing edge participate in transfer,
  including `continue` paths;
- a loop nest shares 4,096 speculative widening/narrowing steps. Exhaustion
  drops an unstable head to unknown; final condition/body validation still runs.
  A separate top-level loop receives a fresh budget;
- widening has eight passes. Exhaustion discards the unstable head and starts
  from unknown; it is not a convergence certificate;
- while loops may perform three sound narrowing passes from that overapproximation;
- known finite iterator loops of at most eight iterations can use a shared
  64-iteration budget. Exhaustion falls back to ordinary loop analysis;
- a proposed machine-word iterator representation must hold on every advancing
  edge. Failure discards the speculative facts and retries abstract arithmetic.

These are precision/performance limits of the current implementation, not
language-level maximum loop sizes. The delayed-dependency, zero-trip,
condition-write, iterator and candidate-budget regressions check that exhausted
or unproved candidates cannot justify an obligation.

## Remaining closure work

General coefficient-weighted loop invariants, measurements of nested-loop state size
and qualifier discovery, correlations among multiple aggregate components, and
consuming-obligation provenance for unsafe audits still need work.
The roadmap remains open for these items; this inventory does not certify all
of Phase 1 merely because the current finite domain reaches a fixed point.
