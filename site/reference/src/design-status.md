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
- Loop capture is collecting a loop's non-`void` expressed values in a surrounding collector such as `[]`.
- Sequences combine through their construction syntax: interpolation joins strings, and `...` spreads an array into a surrounding `[]` literal.
- Objects are structural values. User-defined constructors are ordinary functions, while a structural or hybrid type may directly contextualize an object literal.
- Defaults are per-call fallbacks and do not remove their parameters from positional binding.
- Types are compile-time values and use the ordinary expression grammar where practical.
- Physical dimensions participate in types and may erase from runtime representations; every dimension has a canonical unit and other units are exact rational scales of it.
- Integers are arbitrary precision (words when proven to fit, big integers otherwise, `bigint` on request), `/` yields exact rationals, `fixed` is the fixed-point domain, and there is no floating-point arithmetic.
- Operations that would raise an exception in Python — indexing, dictionary lookup, `pop`, division by a literal zero — must be proven safe at compile time or use an explicit alternative (`get`, `default=`); non-failing behavior stays Python-shaped, and shared names (`length`, `pop`) mean the same thing on every container.
- Dictionaries and sets are values with insertion-ordered iteration, proven-key lookups, and hash-table representations; a container may not be mutated by a loop that iterates it.
- Every value has one owner and storage is released deterministically; placement (stack, static, arena) is a proof-gated optimization and never changes whether a program is valid.
- Expected failures are direct union alternatives belonging to a nominal `error` family rather than values wrapped in a `Result` container.
- Any alternative descended from nominal `exception` forwards through receiver navigation. Both `error` and `none` descend from it, while all ordinary alternatives remain subject to member checking; call arguments never forward implicitly.
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
- bidictionaries, container equality and ordering, compound container operators, and keys beyond words and strings;
- the numeric hierarchy beyond integers, rationals, and fixed-point (reals, complex, quaternions);
- the overloadable string-conversion protocol beyond built-in conversions;
- transformed exception propagation, recovery helpers, and whether pipes join automatic exception forwarding;
- display units for printing quantities, `as unit`, offset units, and declaring base dimensions in library code;
- runtime-length aggregate ownership, returns, and escaping places;
- user-defined managed handles, including lifecycle hooks, typed allocation capabilities, and lifetime-bounded payload places;
- pattern matching, stored generators, and general unpack/collect behavior;
- compile-time evaluation and metaprogramming beyond type-valued expressions and imports;
- the final Unicode identifier repertoire and source-normalization policy;
- three proposed precedence adjustments (`not` vs `~`, comparison
  associativity, `or_throw` below `as`) in `dewy/semantic/precedence.md`;
  `type of` should be a prefix tighter than `&`, not the same `of` as `<T of Bound>`.

Whether a unit-like nominal type value and its canonical inhabitant are literally the same semantic object remains open; the shared spelling is settled independently of that representation question.

A normative page may describe the decided portion of one of these areas, but must not silently choose an unresolved rule.

## Unspecified Behavior

When the reference calls behavior unspecified, programs must not depend on one current implementation's result. An implementation should diagnose constructs for which no valid language behavior has been selected rather than treating an accidental lowering result as specification.

Open design work is tracked in repository discussions and semantic notes. The implementation checklist may also mention a feature before its design is complete; that does not elevate the checklist wording into a language rule.
