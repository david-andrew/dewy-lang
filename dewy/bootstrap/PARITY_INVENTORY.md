# Phase 0 parity inventory
The first isolated baseline completed all 201 accepted-program fixtures:
138 matched acceptance, execution, and output. The pinned hosted compiler
passed all 201 expected results; the verified eighteenth native pair rejected
59, misexecuted three, and differed only in diagnostic notes for one. Ten
separate rejection fixtures passed on both compilers. These are baseline
results, not results for the current checkout or a new native release.

Hosted packages/library were pinned to the original `18fadc66` campaign
snapshot. Native Dewy SHA-256:
`5140aa2f2bfb5b2a09656d33c59db8f631c49d14e8b1c90ca7adaa99a3243ae8`.
The machine, toolchain, isolation, and artifact provenance are in
[PHASE0_MEASUREMENTS.md](PHASE0_MEASUREMENTS.md). Detailed per-invocation
records are in `phase0-performance/parity-baseline/results.jsonl`.

A failure reports the first unsupported construct in that fixture. Fixing it
may expose another gap; it does not establish parity for the whole feature.
Keep this inventory separate from performance acceptance and fixed-point
verification. The follow-up work remains bidirectional, even though these
particular fixtures all pass on the hosted baseline.

The current runner gives expected runtime reports explicit assertions in
`tests/fixtures/compiler_parity_expectations.json`: the exit, ordinary stdout,
failure kind/location and evaluated user message must agree with expectations.
It records byte differences in stderr, but extra diagnostic notes do not fail
those cases. All other stderr remains byte-exact. Applying that policy to the
saved assertion-failure result removes its semantic parity failure; the raw
baseline counts and missing native value notes above remain recorded.

## Refreshed corpus at `49ad4c12`

The next complete, isolated run passes **152/211 cases**: 142/201 accepted
programs and all ten rejection fixtures. The frozen hosted compiler passes
all expected results. All 59 remaining native failures are compile-time
rejections; every accepted native program matches its expected execution.

The native executable is a C accelerator built from native-emitted µDewy,
SHA-256 `8d2929388f969ad20cbef62108ed1e0aa46f19163521af21310a0a9b97e59d72`.
It uses the verified `4c785f86` µDewy compiler. This is a single-generation
corpus checkpoint, not a new fixed-point certification. The hosted source is
frozen at `49ad4c12`; per-invocation records are in
`phase0-performance/parity-refreshed-labels/results.jsonl`.

Six earlier failures now pass: labeled loop exits, iterator labeled exits,
sets, integer widths, local captures, and the assertion-report expectation.
Two formerly passing fixtures regress: `array_call_adapters.dewy` and
`brand_words.dewy`. Their follow-up fixes are tracked below. These counts
include the changed diagnostic-report expectation described above; they
should not be read as six newly implemented language features.

## Refreshed corpus with reusable prelude proofs

The `a8619dab` native accelerator passes **154/211 cases**: 144/201 accepted
programs and all ten rejection fixtures. The hosted compiler passes all 211
expected outcomes. All 57 remaining native failures are compilation
rejections; every accepted native program matches the expected execution and
output. The two recovered cases are `array_call_adapters.dewy` and
`brand_words.dewy`, previously checked separately.

This run shares each implementation's checked-prelude cache across isolated
case directories and fresh compiler processes. It is a semantic inventory,
not a cold timing comparison or a refreshed fixed point. Native Dewy SHA-256:
`b38ae85e95b942db0d3aaed26d183eb17f1d4799256c22f3d19a8b34652b24c5`;
the downstream µDewy is the `d32f29e3` C accelerator. Hosted source identity,
all commands and per-case results are retained in
`phase0-performance/parity-shared-prelude-full/{metadata.json,results.jsonl}`.
The completed position-only parameter and structural-formatting changes are
later than this inventory and are not included in its pass count. Their
isolated expected-result gates and the hosted string-payload test correction
are recorded in [PHASE0_MEASUREMENTS.md](PHASE0_MEASUREMENTS.md).

## Additional observations from optimization regressions

The `3bd41743` native accelerator passes nine of ten selected public CLI
cases against hosted `260c11b0`: array call adapters, printing, union
containers, token arrays, brand words, protocol tables, dynamic strings,
narrowed union copies, and position-only calls. The remaining literal-union
case rejects `flip(s:-1|1):>-1|1 => -s`: parameter and result annotations
have not received the refined-word treatment already used for record fields.
Artifact: `phase0-performance/parity-object-text`; native SHA-256
`a02fb5f3595dcb65be804f5f94252606bf3c1db3d8b7df75178bc22dc74e1454`.
This targeted run does not update the full-corpus count above.

These are outside the original corpus counts:

- `tests/fixtures/array_union_widening.dewy` now passes hosted direct/C
  execution after fixing array descriptor extraction. Native lowering passes
  its narrowed optional-array case. Native checking now preserves an exact
  matching union alternative, accepting the explicit
  `array<int64 length=2>|array<int64>` return without choosing a different
  representation merely because the fixed array also fits the wider member.
  Unique-array contextual construction and rejection checks pass. The full
  `32a1570e` integration executable compiles and runs the expanded case with
  expected result 42 (`runtime-caches-integration/gates.log`).
- Comparing two separately constructed arrays of equal records with `=?`
  currently returns false in both compilers. The numbering regression exposed
  this while comparing independent snapshots; checking each field confirms
  that their contents match. Agreement here is not evidence of correct value
  comparison. Clarify the array comparison contract, including its relation
  to planned vectorized comparisons, before expanding this behavior. The
  isolated reproducer and both executions are retained in
  `phase0-performance/array-equality-probe.{dewy,log}`.
- The hosted compiler rejects an optional array as a container element,
  including the value of `dict<addr (array<addr>|none)>`, despite supporting
  arrays and optionals separately. The native lowering query cache uses an
  empty member list for a non-cell type; an actual cell always has members.
  This internal encoding does not close the general optional-array container
  gap.
- Native compound shifts now let overload selection determine a literal
  count's unsigned type, matching ordinary shifts. The original reproducer
  `let value:int64=84; value >>= 1` is accepted; an explicitly signed count
  still fails. `test_bootstrap_compound_refinements.py` compares nine accepted
  cases (including both shifts, a record field, int8 and existing refinement
  cases) and two signed-count rejections with the hosted checker. The library
  retains ordinary assignment. Original evidence remains in
  `phase0-performance/compound-shift-gap.dewy` and
  `compound-shift-{hosted,native}.log`; the passing gate is
  `compound-shift-gates.log`.
- Hosted dictionary/set flow results now use the ordinary record temporary
  representation. Both branches, literal and binding results, and independent
  mutation after selection execute on direct x86-64 and C in
  `test_container_flow_values.py`. This closes the lowering restriction found
  while sharing the native borrowing analysis graph.

- Both proof implementations now retain a named prefix's numeric minimum
  alongside its symbolic remainder when applying a predicate to a string
  slice. Constant delimiter advancement can therefore preserve the source
  bound. Hosted scanner acceptance and rejection checks plus a compiled
  native call-fact test cover the change (`named-prefix-fact-gates.log`).
  The native full `type_facts.dewy` fixture still has the earlier type-test
  predicate gap listed below.

- A focused global-effects case also exposed an operator lookup difference:
  after a user declaration of `__add__`, `__add__(1 2)` uses that binding in
  both checkers, but `1+2` still uses a builtin in the hosted checker while
  native checking resolves the lexical binding. The global-effects rejection
  deliberately uses the explicit call; operator desugaring parity remains
  separate follow-up work.

- Snapshot codec development found a hosted lowering gap when a binding
  narrowed to `none` crosses an ordinary call boundary. The absent member
  has no payload to load; it now uses the established unit word. Explicit
  optional/union/record-field checks pass hosted direct/C output and native
  direct output in `native_none_forwarding.dewy`.

## Regressions found by the refresh

The `49ad4c12` refresh rejects `array_call_adapters.dewy`, which passed in
the original baseline: a function body loses an annotated constant array's
initializer length. The capture-boundary fix is now refined so immutable
bindings retain their initialization-derived read type, while their written
store contract remains separate. The complete fixture, constant/default/local
capture cases, and the earlier mutable capture regressions pass isolated
hosted/native x86-64/C gates. The refreshed `f1345e78` CLI also passes the
fixture; the completed `49ad4c12` corpus refresh records the older rejection.

`brand_words.dewy` loses its stack-length evidence across the read-only
`describe` call. Both bounds checkers now use transitive global-write
summaries instead of blanket invalidation. Function entry still discards
mutable-global flow facts; a possibly mutating call clears scalar, length,
and member-route evidence. The hosted checker previously cleared only scalar
facts, leaving stale array bounds. Predicate paths now also account for
callee writes in later short-circuit operands. Eleven explicit acceptance and
rejection cases cover reads, direct/transitive/recursive writes, defaults,
unknown callbacks, unrelated globals, nested literals, and predicate history.
The native/hosted bounds comparison, predicate-effect comparison, and existing
parameter-effect suite pass (16 gates, `global-effects-bounds.log`). A subsequent native-source gate also checks those eleven cases plus the
complete `brand_words.dewy` graph. It exposed and fixed the native builtin
identity difference: arithmetic intrinsics carry bindings explicitly marked
`builtin`; user bindings with the same names keep ordinary effects. All
12 native-source cases pass using the compiled validation driver, including
a user-defined mutating `__add__`. The refreshed `f1345e78` public CLI passes
`brand_words.dewy`, `array_call_adapters.dewy`, and `local_captures.dewy`, with
matching expected results and output (`parity-prelude-cache/results.jsonl`).

## Execution and output differences

| Fixture | Baseline result | Follow-up |
| --- | --- | --- |
| [sets.dewy](../tests/sets.dewy) | Native process crashed after successful compilation. | The optional `set.pop` result-cell fix passes isolated direct/C regressions and the full native CLI fixture at `1fa828cc` (expected exit 92 and output). |
| [integer_widths.dewy](../tests/integer_widths.dewy) | Native exit 39 differs from the expected result. | Isolated to a finite range's 2^64 cardinality wrapping into an empty signed-word length. Native lowering now uses the last cursor index and sticky exhaustion for wide counts. Guarded prefixes, continue and break pass direct/C checks in both compilers. The full native CLI fixture at `1fa828cc` returns the expected 42. |
| [local_captures.dewy](../tests/local_captures.dewy) | Native exit 26 differs from the expected result. | Fixed caller flow narrowing leaking into deferred function bodies. The complete fixture and lazy-default capture regression pass both lowerers on direct/C backends. Defaults also now contribute captures to the hosted callee. The full native CLI fixture at `1fa828cc` returns the expected 42. |
| [assertions_runtime_fail.dewy](../tests/assertions_runtime_fail.dewy) | Both exit 101 and print the same ordinary output; hosted diagnostics include extra value notes. | Diagnostic richness difference; exact wording is not a semantic parity requirement. |

## Native acceptance gaps

| Fixture | First reported obstacle |
| --- | --- |
| [labeled_loop_exits.dewy](../tests/labeled_loop_exits.dewy) | Baseline: Metatag value. Native scope resolution and exit legalization now pass isolated x86-64/C execution, rejection, and cleanup gates. The full CLI fixture also passes at `49ad4c12`, as does `iterator_labeled_exits.dewy`; the other two labeled fixtures now reach the separate non-conjunctive iterator gap. |
| [rationals.dewy](../tests/rationals.dewy) | runtime rational materialization |
| [powers.dewy](../tests/powers.dewy) | no declaration of this name is in scope |
| [units_algebra.dewy](../tests/units_algebra.dewy) | no declaration of this name is in scope |
| [trig.dewy](../tests/trig.dewy) | no declaration of this name is in scope |
| [refinements.dewy](../tests/refinements.dewy) | BinOp expression |
| [abstract_int.dewy](../tests/abstract_int.dewy) | no overload takes (int64, uint8) |
| [bigint.dewy](../tests/bigint.dewy) | no declaration of this name is in scope |
| [bigint_auto.dewy](../tests/bigint_auto.dewy) | its range is [123456789012345678901234567890, 123456789012345678901234567890]; annotate a fixed width, prove its range, or use bigint |
| [bigint_division.dewy](../tests/bigint_division.dewy) | runtime exact division materialization |
| [literal_unions.dewy](../tests/literal_unions.dewy) | int64 does not fit -1 &#124; 1 |
| [bigint_zero_or_nonzero.dewy](../tests/bigint_zero_or_nonzero.dewy) | runtime exact division materialization |
| [refined_nested_fields.dewy](../tests/refined_nested_fields.dewy) | runtime exact division materialization |
| [match_chains.dewy](../tests/match_chains.dewy) | its range is unknown; annotate a fixed width, prove its range, or use bigint |
| [place_slots.dewy](../tests/place_slots.dewy) | these type arguments |
| [conditional_value_facts.dewy](../tests/conditional_value_facts.dewy) | effective endpoint intervals are 0..0 and -1..281474976710654 |
| [length_preserving_calls.dewy](../tests/length_preserving_calls.dewy) | effective endpoint intervals are 0..0 and -1..281474976710654 |
| [nat_types.dewy](../tests/nat_types.dewy) | BinOp expression |
| [addr_types.dewy](../tests/addr_types.dewy) | no declaration of this name is in scope |
| [printing.dewy](../tests/printing.dewy) | structural and union string conversion |
| [union_containers.dewy](../tests/union_containers.dewy) | structural string interpolation |
| [token_arrays.dewy](../tests/token_arrays.dewy) | structural string interpolation |
| [abstract_int_containers.dewy](../tests/abstract_int_containers.dewy) | a runtime test within one union payload alternative |
| [precedence.dewy](../tests/precedence.dewy) | Postfix expression |
| [refinement_chains.dewy](../tests/refinement_chains.dewy) | no type of this name is in scope |
| [tokenizer_gaps.dewy](../tests/tokenizer_gaps.dewy) | BinOp expression |
| [prototype_mode.dewy](../tests/prototype_mode.dewy) | the index interval here is 0..0 |
| [prototype_panic.dewy](../tests/prototype_panic.dewy) | the index interval here is 0..0 |
| [flow_body_lowering.dewy](../tests/flow_body_lowering.dewy) | Block expression |
| [error_fields.dewy](../tests/error_fields.dewy) | earlier arms already cover these values |
| [protocol_tables.dewy](../tests/protocol_tables.dewy) | structural string interpolation |
| [dynamic_strings.dewy](../tests/dynamic_strings.dewy) | structural string interpolation |
| [narrowed_union_copies.dewy](../tests/narrowed_union_copies.dewy) | structural string interpolation |
| [covariant_slots.dewy](../tests/covariant_slots.dewy) | earlier arms already cover every value |
| [type_values.dewy](../tests/type_values.dewy) | these type arguments |
| [recursive_mints.dewy](../tests/recursive_mints.dewy) | these type arguments |
| [unpacking.dewy](../tests/unpacking.dewy) | no declaration of this name is in scope |
| [length_terms.dewy](../tests/length_terms.dewy) | these type arguments |
| [type_facts.dewy](../tests/type_facts.dewy) | @tok is? 0 is required when the result is true |
| [string_join_decode.dewy](../tests/string_join_decode.dewy) | No implemented token starts here |
| [error_values.dewy](../tests/error_values.dewy) | Postfix expression |
| [spread.dewy](../tests/spread.dewy) | each record field needs a named value |
| [refined_results_fields.dewy](../tests/refined_results_fields.dewy) | 1/3 does not fit [numerator:int64 denominator:int64<i => i >? 0>] |
| [loop_temporaries.dewy](../tests/loop_temporaries.dewy) | 0/1 does not fit [numerator:int64 denominator:int64<i => i >? 0>] |
| [array_iteration.dewy](../tests/array_iteration.dewy) | its range is [0, ∞]; annotate a fixed width, prove its range, or use bigint |
| [range_values.dewy](../tests/range_values.dewy) | range |
| [iterator_labeled_exits.dewy](../tests/iterator_labeled_exits.dewy) | Metatag value |
| [multi_iterator_or.dewy](../tests/multi_iterator_or.dewy) | non-conjunctive iterator formula |
| [multi_iterator_formula.dewy](../tests/multi_iterator_formula.dewy) | non-conjunctive iterator formula |
| [multi_iterator_exhausted_truth.dewy](../tests/multi_iterator_exhausted_truth.dewy) | non-conjunctive iterator formula |
| [multi_iterator_labeled_exits.dewy](../tests/multi_iterator_labeled_exits.dewy) | Metatag value |
| [multi_iterator_operators.dewy](../tests/multi_iterator_operators.dewy) | non-conjunctive iterator formula |
| [range_stepped_labeled_exits.dewy](../tests/range_stepped_labeled_exits.dewy) | Metatag value |
| [range_stepped_multi_optional.dewy](../tests/range_stepped_multi_optional.dewy) | non-conjunctive iterator formula |
| [object_methods.dewy](../tests/object_methods.dewy) | a is initialized here; a may be accessed here before it is initialized |
| [string_ranges.dewy](../tests/string_ranges.dewy) | character range ordinal conversion |
| [runtime_grapheme_strings.dewy](../tests/runtime_grapheme_strings.dewy) | No implemented token starts here |
| [keyword_default_calls.dewy](../tests/keyword_default_calls.dewy) | BinOp expression |
| [position_only_calls.dewy](../tests/position_only_calls.dewy) | write this parameter as name:type |

## Position-only parameters

Native function literals now accept the hosted `(<name:Type>)` form, including
defaults, generic parameters, inferred callable values and place parameters.
A shared source-parameter reader retains the lexical name while the callable
slot omits its public keyword name. Signature reservation, default checking,
contextual inference and body binding use that same interpretation. Named
calls to these slots, malformed angle blocks, duplicate names and place
defaults are rejected. Position-only parameters in explicit function-type
annotations remain unsupported in both compilers; this change adds no spelling
for that separate gap.

The rejection tests also exposed hosted duplicate lexical parameters being
silently overwritten in the body scope. Hosted checking now rejects duplicates
across positional, keyword-only and rest parameters. Nineteen signature and
ordered-call checks pass, alongside direct/C execution for positional defaults,
indirect calls and place updates. Artifacts: `position-only-checking-gates.log`
and the passing execution case in `position-only-final-gates.log`. These are
isolated gates; the 154/211 complete inventory above predates this change.

## Integer singleton value contracts

Both compilers now interpret integer singleton sets consistently in binding,
inline record field, parameter and named function signature annotations.
Assignments and compound assignments retain those declared contracts after a
narrowed read. Positive intersections keep the predicates when their underlying
shape becomes narrower, rather than incorrectly declaring the overlap empty.

Runtime integer-set tests compare the value, including payloads of tagged
unions, filter literals outside the operand's fixed width, and evaluate an
effectful operand once. Native narrowed integer views convert values to enum
tags when that representation is required. The complete `literal_unions.dewy`
fixture and ten isolated programs return their explicit expected result through
both compilers and both backends (44 executions); six invalid contracts are
rejected by both. The compound-refinement kernel also passes. Artifacts:
`integer-set-integration-gates.log` (2 tests, 166.43 seconds) and
`integer-set-hosted-final-gates.log` (56 hosted regressions). This is an isolated
integration gate, not a refreshed whole-corpus count or native fixed point.
