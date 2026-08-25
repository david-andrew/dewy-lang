# Design Maturity and Open Questions

This appendix records where Dewy's intended semantics are settled, provisional, or open. It is about language design, not compiler progress.

## Settled Foundations

The following principles organize the language and should be treated as normative:

- Dewy is a statically checked, general-purpose language centered on everyday ease of use.
- Expressions may produce values; declarations and ordinary assignments produce `void`.
- Ordinary rebinding, argument passing, and return have value semantics.
- `@` explicitly selects a place or function binding when reference-like behavior is intended.
- Strings are immutable grapheme-cluster sequences with explicit lower-level views.
- Arrays are homogeneous values and may carry length or shape facts in their types.
- Objects are structural values. User-defined constructors are ordinary functions, while a structural or hybrid type may directly contextualize an object literal.
- Defaults are per-call fallbacks and do not remove their parameters from positional binding.
- Types are compile-time values and use the ordinary expression grammar where practical.
- Physical dimensions participate in types and may erase from runtime representations.
- Expected failures are direct union alternatives belonging to a nominal `error` family rather than values wrapped in a `Result` container.
- Any alternative descended from nominal `exception` forwards through receiver navigation. Both `error` and `undefined` descend from it, while all ordinary alternatives remain subject to member checking; call arguments never forward implicitly.
- Returned errors and evaluation effects occupy separate parts of a function contract.
- `type of Parent` is the sole generative type operation. It creates a fresh nominal child; `&` is non-generative intersection and preserves nominal ancestry already present in its operands.
- A unit-like nominal type has one canonical inhabitant written with the type's name. Hybrid nominal/structural values use `Type[field=value ...]` construction.
- Structural object intersections merge matching fields by intersecting their types. A mutability disagreement is invalid rather than selecting one declaration.

## Provisional Designs

These areas have a clear direction, but some syntax, edge cases, or runtime contracts remain undecided:

- user-written generic functions and generic structural objects;
- inference for unannotated function parameters when the body requires overloaded operations;
- first-class function handles, partial evaluation, captures, and closure identity;
- the exact liquid-refinement language, proof boundary, and `unsafe` obligations;
- the general effect vocabulary and effect-polymorphic contracts;
- multidimensional array shape syntax, broadcasting, and contiguous layout selection;
- dictionary, bidictionary, and set mutation, collision, deletion, and equality rules;
- the complete numeric hierarchy beyond integers;
- the overloadable string-conversion protocol beyond built-in conversions;
- transformed exception propagation, recovery helpers, and whether pipes join automatic exception forwarding;
- complete physical-dimension arithmetic, units, and conversion policy;
- runtime-length aggregate ownership, returns, and escaping places;
- user-defined managed handles, including lifecycle hooks, typed allocation capabilities, and lifetime-bounded payload places;
- pattern matching, stored generators, and general unpack/collect behavior;
- compile-time evaluation and metaprogramming beyond type-valued expressions and imports;
- the final Unicode identifier repertoire and source-normalization policy.

Whether a unit-like nominal type value and its canonical inhabitant are literally the same semantic object remains open; the shared spelling is settled independently of that representation question.

A normative page may describe the decided portion of one of these areas, but must not silently choose an unresolved rule.

## Unspecified Behavior

When the reference calls behavior unspecified, programs must not depend on one current implementation's result. An implementation should diagnose constructs for which no valid language behavior has been selected rather than treating an accidental lowering result as specification.

Open design work is tracked in repository discussions and semantic notes. The implementation checklist may also mention a feature before its design is complete; that does not elevate the checklist wording into a language rule.
