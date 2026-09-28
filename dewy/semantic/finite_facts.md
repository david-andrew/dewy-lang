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
its checked contract, not a guessed meaning from its source name.

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

A scalar or length snapshot receives the source facts that still describe its
observed value. Later replacement of the source discards relations involving that
source, while relations between the snapshot and other unchanged terms survive.
For example, `let size = xs.length` creates a scalar term; it does not create a
new sequence to which index facts may refer.

## Entailment and joins

Intervals answer constant range questions. The finite ordered graph answers
transitive difference questions without a fixed two-edge cutoff; search is
bounded by its existing edge count. Affine updates retain relations only when
the arithmetic and its destination cannot wrap. The remainder form connects
checked sums, offsets and slices without inventing general nonlinear rules.

Disequality does not choose an ordering. It can sharpen a known non-strict integer
order. A join retains facts supported on every reachable incoming path. For an
already selected disequality, a peer path can supply the same fact, a direct
strict order in either direction, or disjoint intervals. This does not enumerate
all term pairs or run graph closure at each join. Other unsupported combinations
remain unknown, even when a stronger solver could establish them.

## Loop candidates and budgets

Candidate selection is bounded separately from proof:

- exact entry values select at most 64 changing terms and a linear-size set of
  difference relations through representative anchors;
- source predicates and subtraction select at most 64 deduplicated term pairs;
  while guards precede bodies in this shared pair budget;
- entry intervals must establish each offered difference;
- the loop condition's effects and every advancing edge participate in transfer,
  including `continue` paths;
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

Broader linear-combination inference, the depth/scaling behavior of nested loop
exploration, complete transfer of every fact kind through aggregate element
summaries, and consuming-obligation provenance for unsafe audits still need work.
The roadmap remains open for these items; this inventory does not certify all
of Phase 1 merely because the current finite domain reaches a fixed point.
