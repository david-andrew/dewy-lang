# Dewy Language Reference

This reference defines the intended syntax and semantics of the Dewy programming language. It is organized by language construct and is meant for answering exact questions rather than teaching the language in sequence.

For a guided introduction, read [Learning Dewy](../learn/).

## Normative Language and Current Implementations

The main reference describes Dewy itself. A rule does not become less normative merely because the current compiler has not implemented it yet.

Language-design maturity is recorded in [Design Maturity and Open Questions](design-status.md):

- settled behavior is documented directly;
- provisional behavior is documented only as far as decisions have been made;
- unspecified behavior is identified without inventing a default.

Current compiler coverage, target restrictions, and µDewy compatibility belong to [Implementation Compatibility](compatibility.md). Those implementation notes do not redefine the source language.

## Conventions

- Dewy source conventionally uses the `.dewy` suffix.
- µDewy source conventionally uses `.udewy`; suffixes do not select Dewy semantic rules.
- Code labelled **provisional** illustrates a design whose stated portions are decided but whose surrounding rules may change.
- `T | none` denotes an optional value.
- `exception` is the nominal parent of values forwarded by safe navigation; both `error` and `none` descend from it.
- `intN` and `uintN` denote fixed-width signed and unsigned integer families when a rule applies uniformly across widths.
- “Produces” describes the value or values expressed by a construct. `void` means that no value is produced.
- “Place” means a mutable storage location selected explicitly with `@`; it is not an accidental alias created by an optimization.

Unless a section explicitly says otherwise, evaluation proceeds from left to right within the order established by grouping and operator precedence.
