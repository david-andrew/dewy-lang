# Idiomatic facts and user-defined invariants

Recorded 2026-09-09 from a language-design discussion. This is exploratory direction, not a specification, implementation checklist, or commitment to new syntax. In particular, the library sketches below are pseudocode.

Related: [refinements and effects](../../site/reference/src/refinements-and-effects.md), [compile-time facilities](../../site/reference/src/compile-time.md), [liquid refinement direction](../status.md#liquid-refinement-system), [value semantics](value_semantics.md), [safety and concurrency](safety_and_concurrency.md), and the [numerical stress test](numerical_stress_test.md).

## Assessment and intent

Dewy's intended combination of refinements, unions, nominal identity, value semantics, effects, and compile-time programming appears suitable for the facts discussed here. This note does not propose replacing it with a different factual core. Today's incomplete propagation is not evidence of a fundamental design limitation.

The design question is what programmers naturally establish while expressing their algorithms. Prefer meaningful operations that produce reusable evidence: construction, validation, matching, iteration, partitioning, and transformation. Ordinary guards remain useful, but programmers should not have to repeatedly justify individual instructions when a reusable abstraction could carry the reason they are valid.

For example, `startswith` answers an algorithm's own question and also establishes enough input length to advance. A total dictionary establishes coverage once, making every lookup for its key type valid. A positive-denominator field invariant makes division valid wherever the value is consumed. These are existing examples of the desired style.

David's intended role for compile-time programming is substantial: libraries should be able to define reusable types and facts using ordinary Dewy computation, in the spirit of Jai/Zig-style compile-time facilities. Ideally, writing such a library is mostly writing an ordinary data type and its operations, with useful contracts, rather than implementing a separate proof framework.

## Facts that should become idiomatic

| Kind | Meaningful fact | Natural way to acquire it |
| --- | --- | --- |
| Operational validity | An index is in bounds; a divisor is nonzero; a conversion fits | Guards, refined parameters, iteration, explicit checked operations |
| Shape and correspondence | Arrays have equal lengths; matrix axes match; paired samples remain aligned | Joint construction, shape validation, shape-preserving transformations |
| Coverage and membership | Every permitted key has a value; a lookup found an entry | Total mapping construction, successful lookup, entry iteration |
| Domain invariants | Readings are ordered; durations are positive; an interval's endpoints are ordered | Validating constructors and invariant-preserving operations |
| Semantic identity | Positions use a particular coordinate frame; identifiers belong to a particular domain | Type construction and explicit conversions between domains |
| Progress and state transitions | A successful parser consumes input; a resource is in a usable state | Result alternatives and operations that explicitly establish the next state |
| Provenance and partitioning | A span belongs to this source value; pieces are disjoint and cover a region | Slicing, splitting, and scoped access operations |
| Effects and authority | A callback preserves shape; work touches only its partition; an operation has a capability | Effect contracts, scoped tasks, explicit handles |

Not every fact must enter the automatic solver. A library can enforce some through its construction and access rules. Some can be expressed directly in the liquid fragment, and some may require checked lemmas or a small explicit trusted core. General semantic correctness remains optional: trap-freedom does not establish termination, physical accuracy, or the correctness of an algorithm.

Keep fallible operations convenient too. “Try this lookup” is a legitimate intent and should not require inventing a proof that it must succeed. A success result can carry the evidence needed for subsequent work.

## Durable propagation questions

This deliberately omits individual failing cases and current special cases in the checker. Those change too quickly. The longer-lived concerns are:

- **Modular contracts.** Facts should survive helper extraction, result packaging, generic use, and calls through function slots when the declared interface promises them (or it can be inferred. Open discussion to be had on whether only unannotataed functions can infer facts, or annotations that don't contain any facts could also pass along inferred facts). Correctness should not depend on opportunistic inlining. Inferred local contracts and stable published contracts may need different policies.
- **Effects and preservation.** A call should invalidate only facts it can falsify. Length, element contents, ordering, and identity are different properties: an element write may preserve length while destroying sortedness. Higher-order operations need a way to express the relevant requirements on their callbacks.
- **Relationships and value versions.** Evidence relates particular values, not merely variable names. A span valid for yesterday's source is not automatically valid for a replacement. Copies, container storage, mutation, and result alternatives must preserve or invalidate the right relationships. Value semantics helps but does not by itself specify this entire model.
- **Loop-wide invariants.** Validating an entire collection requires summarizing what a loop established over the visited portion, then exporting the completed invariant. This is a deeper issue than retaining a scalar bound across a branch.
- **Predictable proof boundaries.** An unsupported proof should remain unknown, with the missing relationship explained. Libraries need a stable account of what contracts mean even as automatic inference improves.

These are requirements and open questions, not claims that all of them are absent today. They matter especially when facts are defined by libraries rather than recognized specially by the compiler.

## Open questions in the intended support

The existing direction leaves several interfaces provisional. None presently implies that the desired idioms are impossible, but they need explicit answers:

1. **User-defined measures and predicates.** Which pure functions can appear in facts? Inlining an expression inside the supported fragment is one route. Reusable abstract predicates need rules for identity, interpretation, and checked consequences. Purity alone does not make a predicate decidable.
2. **Construction authority.** Minting a nominal type distinguishes it from other types; it does not alone prove an invariant or prevent invalid construction. Opaque invariants need controlled construction and mutation, or obligations on every way a value can be built or changed. Structural conversion, copying, reflection, and generated constructors must respect the same boundary.
3. **The bridge to logical consequences.** “This is an OrderedReadings value” can justify using its methods without teaching the solver what ordering means. Letting arbitrary consumers derive `times[i] < times[i+1]` is stronger. The design needs a way to export such consequences with checked justification.
4. **Collection-wide properties.** Sortedness, uniqueness, and permutation are generally beyond the planned ordinary liquid fragment. A richer proof boundary could reason about them and export concrete consequences in the small fragment; unrestricted quantification need not become routine automatic inference.
5. **State and identity.** Typestate for a copied value differs from typestate for a shared external resource. Closing one copied handle must not leave another handle carrying a false “open” fact. Scoped access or ownership rules must accompany facts about identity-bearing resources.

The goal is a small understandable checking boundary, not arbitrary executable compiler plugins that may declare propositions true.

## Early compile-time library sketch

Separate three jobs: compile-time code **creates** a type and its contracts; construction or validation **establishes** its invariant; operations **expose and preserve** useful consequences. Compile-time input can be validated at compile time. Runtime input still needs runtime evidence unless its properties are already known. Generating a validator does not prove that its implementation validates the claimed predicate.

### Start with a fact already in the ordinary fragment

The following is intentionally schematic. `define_type`, `invariant`, and the construction notation are explanatory placeholders, not proposed APIs or valid Dewy syntax. There is no implied general-purpose `assume` operation.

```text
# A compile-time function returns a reusable type definition.
NonEmpty = (Element:type) => define_type {
    storage: array<Element>
    invariant: storage.length > 0

    from = (xs:array<Element>) -> Self | Empty {
        if xs.length == 0 return Empty
        return construct Self(storage=xs)
    }

    first = (self:Self) -> Element {
        return self.storage[0]
    }

    map = (self:Self, f:Element -> Other) -> NonEmpty<Other> {
        return construct NonEmpty<Other>(storage=map(self.storage, f))
    }
}

const Samples = NonEmpty(Reading)   # bind a generated nominal type once
```

The constructor's guard proves the invariant. The `first` body receives it. `map` proves its result through a length-preserving library contract. The generated declarations undergo ordinary checking, just like handwritten declarations. Unrestricted writes to `storage` cannot be allowed to silently violate the invariant. Handling errors or effects in `f` would need the usual callback contract; this sketch leaves that independent question out.

This level should not require a custom proof language. The design should also avoid accidentally minting incompatible types at separate uses of a factory; binding identity, reuse, and any explicit canonicalization must follow Dewy's generativity rules rather than an unstated cache.

### Then expose a consequence of a richer invariant

For strictly ordered readings, a possible interface is:

```text
OrderedReadings(Time, Reading):
    from(xs) -> Self | OutOfOrder
    adjacent(self, i where 0 <= i and i+1 < self.length)
        -> [earlier:Reading, later:Reading]
           with earlier.time < later.time
```

A consumer can subtract the returned times and know the mathematical duration is positive. This needs the chosen `Time` domain's ordering and subtraction contracts; fixed-width rollover or floating-point exceptional values cannot be ignored.

Possible stages of support, without selecting a final mechanism:

1. The validator establishes the invariant through a checked loop invariant or a reusable validation combinator whose implementation is checked once.
2. The invariant is carried by the resulting value. A library-defined checked lemma, or an ordinary operation with a checked postcondition, specializes it to the requested adjacent pair.
3. The caller receives an ordinary comparison fact. It need not manipulate a quantified proof or understand how the collection was validated.

An explicit `adjacent` method is a useful first interface. Automatically exposing the same consequence for arbitrary indexing is a later ergonomic possibility, not a requirement to let arbitrary library rewrite rules run without bounds. Evidence used only for checking can erase; the validator and returned data retain their ordinary runtime costs. Runtime checks remain an alternative where proving an implementation would be disproportionate, with failure represented explicitly.

If richer checked proofs are unavailable, a small explicitly trusted implementation could supply the boundary. Its trust must remain visible; generated code or a nominal brand must never silently promote an unchecked assertion into a theorem.

The ergonomic target is to write the representation, validator, operations, and contracts once. Common validation and preservation patterns should be reusable. Hard mathematical invariants may still require hard proofs; the language should not promise that arbitrary verification costs no more than ordinary programming.

## Types that stress the design

These are experiments, not a list of proposed built-ins. Each should be tried with runtime inputs and through helper functions and containers, not just literals.

| Type or abstraction | What it stresses |
| --- | --- |
| `NonEmpty<T>` | Validate once, safe first element, length-preserving map, and rejection or explicit failure for operations that may empty it |
| `TotalMap<K,V>` over finite keys | Coverage, generic reuse, value updates versus key removal, and preservation through copies |
| `Aligned<A,B>` / shape-compatible matrices | Relations between values; zipped iteration without accidental truncation; transformations that preserve or deliberately change shape |
| `OrderedReadings` | Collection-wide validation, adjacent-order consequences, positive durations, and updates that may invalidate ordering |
| `Span<Source>` / `ConsumingParser` | Source provenance, endpoint relations, a valid remainder, and strictly positive consumption on success; distinguish parsers allowed to accept empty input |
| `Sorted<T,Order>` | Comparator identity and laws, search preconditions, sortedness preservation, and the separate claim that sorting preserves the input's elements |
| `Position<Frame>` / `Transform<From,To>` | User-defined semantic identity, composable conversions, units versus coordinate frames, and generated type reuse |
| `Partitioned<T>` | Disjointness and coverage, mutable access lifetimes, parallel callbacks, and preservation at joins |
| `ValidatedUtf8` | An invariant beyond a few scalar inequalities, runtime validation, safe decoding, and mutation boundaries |
| `OpenResource` / transaction states | Postconditions about changing state, authority, aliases, and why a copied brand cannot alone guarantee a live external resource |
| `Permutation<N>` | Range plus uniqueness plus coverage; safe indexing versus a stronger whole-collection property; checked consequences without routine quantified reasoning |

Useful negative cases include a same-length but different source, a changed sort key or comparator, a copied resource that another alias closes, and an update that preserves shape while breaking a domain invariant. These distinguish real evidence from facts that happen to share a spelling.

## How to evaluate the direction

Use the tokenizer and the proposed energy report as real consumers of these abstractions. For each extra guard, annotation, or helper needed to compile, ask:

- Does it state an assumption of the problem?
- Can a reusable constructor or operation establish it once?
- Is it only compensating for missing propagation?
- Is it exposing a true limit of the supported proof fragment?

Repeat after extracting helpers, packaging results, adding a generic wrapper, and introducing unrelated mutation. Record programmer effort as well as runtime and compilation cost. Success means callers mostly express their algorithms, library authors can export useful facts through ordinary contracts, and diagnostics identify the remaining obligations without requiring knowledge of solver internals.
