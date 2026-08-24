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
- Objects are structural values; constructors are ordinary functions.
- Defaults are per-call fallbacks and do not remove their parameters from positional binding.
- Types are compile-time values and use the ordinary expression grammar where practical.
- Physical dimensions participate in types and may erase from runtime representations.

## Provisional Designs

These areas have a clear direction, but some syntax, edge cases, or runtime contracts remain undecided:

- user-written generic functions and generic structural objects;
- first-class function handles, partial evaluation, captures, and closure identity;
- the exact liquid-refinement language, proof boundary, and `unsafe` obligations;
- the general effect vocabulary and effect-polymorphic contracts;
- multidimensional array shape syntax, broadcasting, and contiguous layout selection;
- dictionary, bidictionary, and set mutation, collision, and ordering rules;
- the complete numeric hierarchy beyond integers;
- materialized interpolation and the overloadable string-conversion protocol;
- complete physical-dimension arithmetic, units, and conversion policy;
- runtime-length aggregate ownership, returns, and escaping places;
- pattern matching, stored generators, and general unpack/collect behavior;
- compile-time evaluation and metaprogramming beyond type-valued expressions and imports.

A normative page may describe the decided portion of one of these areas, but must not silently choose an unresolved rule.

## Unspecified Behavior

When the reference calls behavior unspecified, programs must not depend on one current implementation's result. An implementation should diagnose constructs for which no valid language behavior has been selected rather than treating an accidental lowering result as specification.

Open design work is tracked in repository discussions and semantic notes. The implementation checklist may also mention a feature before its design is complete; that does not elevate the checklist wording into a language rule.
