# Dewy Language Reference

> [Generated coverage](/status/#ref-index) names related acceptance programs. Every example in this reference compiles with the current compiler unless it is marked **Design only**.

This reference defines the syntax and semantics of the Dewy programming language, organized by construct. It is for answering exact questions; for a guided introduction, read [Learning Dewy](../learn/).

## What the Examples Mean

The site build compiles every example in this reference with the current compiler:

- An example with an **Output** block was built and run, and printed exactly that text.
- An example without one compiles. Where the text says a program is rejected, the build checks that the compiler rejects it with the diagnostic described.
- An example labelled **Design only** shows a decided design that the compiler does not implement yet. The label says what is missing. [Design Maturity and Open Questions](design-status.md) lists these areas and the questions still open.

Examples compile under the default rules, in which nothing is checked at run time behind your back: a possible failure is proven impossible or handled as a value. An example that relies on `$runtime_checks` says so in its first line.

## Conventions

- Dewy source uses the `.dewy` suffix.
- `T | none` denotes an optional value; `T?` is the same type.
- `exception` is the parent of every value forwarded by safe member access; both `error` and `none` descend from it.
- `intN` and `uintN` denote the fixed-width signed and unsigned integer families when a rule applies to every width.
- “Produces” describes the value or values expressed by a construct. `void` means that no value is produced.
- “Place” means a mutable storage location selected explicitly with `@`; it is never an accidental alias created by an optimization.

Unless a section says otherwise, evaluation proceeds from left to right within the order established by grouping and operator precedence.
