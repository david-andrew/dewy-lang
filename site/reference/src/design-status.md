# Design Maturity and Open Questions

> [Generated coverage](/status/#ref-design-status) names related acceptance programs. This page has no examples.

This appendix says which parts of Dewy are settled, which are decided but not built yet, and which are still open. Pages in this reference describe what the current compiler does; where they show a decided design that does not compile yet, the example carries a **Design only** label that says what is missing.

## Settled Foundations

These principles organize the language. The compiler implements them today.

- Dewy is a statically checked, general-purpose language: Python-like ease, C-like speed, safe by default with danger opt-in.
- Expressions may produce values; declarations and ordinary assignments produce `void`. A file without `main` runs top to bottom; with `main`, the top level runs first and then `main` runs once.
- Rebinding, argument passing and return have value semantics. `@` selects a place (`@xs`, `@world`) or a function handle (`@f`) when reference-like behavior is intended; an explicit copy of a costly value is spelled `.copy`.
- A bare function name calls the function; zero-argument calls may omit parentheses.
- `int` is arbitrary precision. Fixed-width `intN` and `uintN` must be proven not to overflow unless their type asks for wrapping or saturation (`uint8<overflow='wrap'>`). Decimal literals and `/` on integers are exact; `float32` and `float64` are strict IEEE floating point. `%` is floored.
- Operations that raise in Python (indexing, dictionary lookup, `pop`, division by zero, narrowing conversions) must be proven safe at compile time or use a form that returns the failure as a value. `$runtime_checks` opts a program into checking at run time instead.
- Strings are immutable sequences of grapheme clusters; `length` counts what a reader sees as characters.
- Arrays are homogeneous values that may carry length or shape facts in their types. Dictionaries and sets keep insertion order; `d.keys` is a set.
- Objects are structural values; `type of Parent` is the only operation that mints a nominal type, and `&` intersects types without minting.
- Expected failures are direct union alternatives in the `error` family, not wrapped results. Postfix `or_throw` passes a failure to the caller; `??` supplies a fallback. `none` and `error` both descend from `exception`, which forwards through member access.
- Physical dimensions are part of types and are erased at run time. Every dimension has a canonical unit, other units are exact rational scales of it, and a quantity prints in a unit chosen from its dimension and magnitude.
- Time has one continuous timeline: `Instant` and `Duration` count exact nanoseconds by default, with calendars, zones and dates layered on top.
- Every value has one owner and is released deterministically. Allocation uses an implicit context allocator; running out of memory ends the process unless `$explicit_allocation_failure` asks for it as a value.
- Settings are metatags in the language (`$runtime_checks`, `$program.max_cores = 2`), not environment variables or compiler flags.
- Import cycles behave as one large file; imports splat their names unless written `as name`.

## Decided, Not Built Yet

The design is decided; the compiler does not implement all of it yet. Examples for these carry a **Design only** label.

- The rest of the time system beyond instants, durations, dates, zoned times and intervals.
- Self-length refinements, where an array's elements are constrained by that array's own length (D17).
- Some cleanup forms for resources, such as self-closing files and a fallible `$__abandon__` (D40).
- Programs that still need `$runtime_checks` because the prover cannot yet establish an ordinary fact.

## Open Questions

These areas are waiting on a design decision. The reference does not pick an answer for them; a program that depends on one is rejected or uses a provisional form that may change.

- Cancellation details: where `Canceled` can appear, cancellation helpers, `select` and cancel scopes (D4, D41, D44).
- Combining failures and tracing where each came from (D42), and who handles a failed cleanup (D40).
- Safety tag names and defaults beyond the bundles listed in [Settings and Safety Levels](settings.md) (D10).
- Game APIs: compile-time shapes, action names, audio handles and UI (D11, D28).
- Compilation target names (D46) and packages (D21).
- Command-line parsing beyond the first version of `argparse`: subcommands and cross-argument rules (D48).
- Smaller spelling questions about dates, time zones, units, `fmt` patterns, function types and nested array literals (D29–D39).
- Naming style for multi-word library names (D38) and a native database interface (D43).

Each question, with its recommended answer, is in the repository's [open decisions](https://github.com/david-andrew/dewy-lang/blob/master/docs/design/open_decisions.md); accepted answers move to [decisions](https://github.com/david-andrew/dewy-lang/blob/master/docs/design/decisions.md).

## Unspecified Behavior

When the reference calls behavior unspecified, programs must not depend on one compiler's result. The compiler diagnoses constructs for which no language behavior has been chosen rather than treating an accidental result as the specification.
