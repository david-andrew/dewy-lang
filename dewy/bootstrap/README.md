# Bootstrap compiler

The parsing pipeline is implemented in Dewy, using the hosted
`dewy/parser/{t0,t1,t2,p0}.py` stages as its behavioral reference. Semantic
analysis and code generation are being ported in executable slices; the
whole Dewy compiler is not yet self-hosting. See
[IMPLEMENTATION.md](IMPLEMENTATION.md) for the current boundary.

## Implementation progress

- [x] t0: context-sensitive lexical tokens and delimiter pairs
- [x] t1: compound tokens, decoded strings and numbers, nested blocks
- [x] t2: operator normalization, juxtaposition, keyword and flow grouping
- [x] p0: precedence parsing and AST construction
- [x] command-line invocation and source-annotated output
- [x] parity tests, malformed inputs, bootstrap fixtures, self-parsing

`parser/t0.dewy` replaces the earlier `t0_sketch.dewy`. The historical sketch
review is retained in `parser/t0_sketch_notes.md`. `DESIGN_NOTES.md` inventories
the hosted stages' documentation and pending decisions so planned syntax and
intentional placeholders remain visible during the port.

## Running the stages

```sh
python -m dewy dewy/bootstrap/parser/parser.dewy dewy/bootstrap/tests/08_flow_and_data.dewy
python -m dewy dewy/bootstrap/parser/parser.dewy dewy/bootstrap/tests/08_flow_and_data.dewy --stage t2
python -m dewy dewy/bootstrap/parser/t0.dewy dewy/bootstrap/tests/02_numbers.dewy
python -m dewy dewy/bootstrap/parser/parser.dewy --help
```

The combined driver defaults to p0. Individual stage files default to their
own stage. t0–t2 display source annotations; t2 also displays its grouped token tree.
p0 displays an indented AST.
`--dump` selects tab-separated rows: depth, kind, start, stop, quoted payload.
In t0, `DelimiterPair` rows contain token indices in the start/stop columns.
Errors go through the Dewy reporting library and exit unsuccessfully.

## Representation choices

- t0 retains the narrowed-context probe/select/finish structure. String modes
  and quote/heredoc/EOF endings are explicit types. Only the winning probe
  constructs its token and context action.
- t1, t2, and p0 share an append-only token/AST arena. Children are `addr`
  indices; containers own arrays of those indices. This avoids recursive
  mutable token objects and lets ambiguous parses share completed nodes.
- t2 preserves the hosted rewrite ordering. Recursive collectors return both
  a result and the next input position. A juxtaposition token carries its
  remaining alternatives instead of using a subclass for every alternative.
- p0 retains the hosted binding-power reductions, flat operators, postfix
  preference, and ambiguous alternatives. It does not decide call versus
  index versus multiplication using invented parser-level type rules. The
  enumeration order of ambiguous alternatives may differ; it carries no
  preference.

The semantic port uses separate modules for type descriptions, propositions,
subtyping and joins, overload dispatch, builtin tables, HIR, bindings, and minted families.
Type references point into a compilation-owned arena. Stored descriptions
retain defaults, methods, and resolved proof bindings; structural equality
compares their separate shape keys. A recursive alias has a stable identity
and a target filled in after its declaration resolves.

The source type visitor resolves forward and generic aliases, recursive
record references, immutable field invariants, function result facts, and
record composition/minting. Deferred defaults and methods retain both their
source arena and defining lexical scope. Native source tests compare the
resolved types with the hosted checker and exercise invalid declarations.
This is one part of semantic checking, not yet the complete native compiler.

Minted families are also compilation-owned. The brand registry assigns
preorder intervals after registration, so a runtime test of a parent covers
all its descendants without tying runtime tags to source binding ids.

Spans in this implementation count graphemes, matching Dewy string indexing
and the Dewy reporting library. Hosted Python spans count code points. These
coordinates differ for combining sequences and CRLF. String chunks inside
an interpolated string have synthetic spans; hosted chunks have no spans.

## Hosted compiler support added during the port

- Preserve field bounds through common union fields, optional payload
  narrowing, array elements, and constant-offset comparisons; retain imported
  total-dictionary contracts.
- Keep nominal family storage distinct from narrowed union views, including
  calls back into a family-typed function and tests against compound groups.
- Give optional strings and aggregates independent storage, retain array
  rebindings across block lifetimes, and lower parenthesized optional results
  using the same paths as unparenthesized results.
- Lower runtime string concatenation through interpolation's grapheme
  segmentation and return-storage analysis; support string `+=` correctly.
- Implement array membership through a generic Dewy library function, sharing
  positive/negative membership dispatch. Include the helper in installed
  runtimes.
- Accept validated place arguments inside nested calls; parenthesize compound
  boolean operands in emitted code; traverse deep debug scopes iteratively.
- Correct hosted real literals at EOF and binary exponent markers, retain the
  last token of EOF strings, normalize labeled-exit payloads, accept empty
  programs, and diagnose operators without precedence instead of raising a
  Python `KeyError`.

## Array contracts and index evidence

The next compiler pass is tracked in [IMPLEMENTATION.md](IMPLEMENTATION.md).
It uses existing refinement syntax for the two approved areas below:

1. **Declared array type versus current length fact.**
   `let xs:array<int64> = [1]` keeps `array<int64>` as its store contract.
   Its current length is a fact, invalidated or updated by replacement and
   mutation. Explicit exact-length annotations remain restrictions on stores;
   immutable declarations may safely retain their initializer's exact shape.
2. **Indices tied to an arena.** `addr` establishes a position, but not that
   it belongs to a particular `nodes` array. `node_at(nodes id)` therefore
   checks `id < nodes.length`. `append_node` now promises
   `addr<i => i <? nodes.length>` about the updated arena. Direct consumers
   can use this evidence; it survives growth and value copies, but not
   truncation, replacement, or a mutable call without a preserving contract.
   Stored child lists still use `addr`, so reading arbitrary child references
   still checks their bounds. Bounds evidence alone does not prove semantic
   provenance or make an index valid for an unrelated arena.

The implementation also exposes existing optimization opportunities: reduce
copies of read-only nominal values, avoid retaining superseded rewrite nodes,
and specialize the operator metadata lookup. These affect cost, not syntax.

`DESIGN_NOTES.md` preserves the hosted documentation, including proposed
operator chains, byte escapes, unresolved operator precedence, numeric-base
choices, and juxtaposition policy. Reserved `??` and `<=>` remain reserved;
byte escapes remain unsupported, and parametric Unicode escapes remain AST
nodes for later phases to interpret.

## Validation

See [IMPLEMENTATION.md](IMPLEMENTATION.md) for the latest full-suite and
focused native verification results.
Native semantic tests compare type algebra, dispatch, bindings, minting,
parameter effects, source-order initialization, intervals, and relational
fact states, shared type queries, source type rendering, generic alias
application, HIR fact views, expression/length proofs, and index validation
with the hosted implementations.
Native parity tests cover all bootstrap fixtures, explicit ambiguous parses,
reserved operators, CLI behavior, Unicode/grapheme coordinates, and parsing
all four parser-stage source files through both t2 and p0. The native p0
self-parses took approximately 1–3 seconds per file in the development run.
Compiler regressions cover the storage, narrowing, bounds, and debug-info
issues encountered while building the parser.
