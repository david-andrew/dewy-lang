# No traps

Dewy is a trap-free language. This note is the design rule the compiler and
the library follow; the user-facing statement is in the reference
(`site/reference/src/refinements-and-effects.md`, "No Traps").

**The rule.** A compiled program never aborts, panics, or crashes on a path
the programmer did not write. The only exits are the ones spelled in the
source: `return`, an explicit exit call, a failed `$runtime_assert` (the
user's own check). Every operation that could fail is handled in exactly one
of two ways:

1. **Compile-time proof.** Preconditions (index in bounds, nonzero divisor,
   refinement obligations, word-size fits) are proven by the checker and the
   bounds analysis from facts the program states — guards, refined types,
   `$assert`. Unproven is a compile error whose fix is more facts, never a
   compiler-inserted runtime check.
2. **A value.** What is genuinely undecidable at compile time (overflow of
   fixed-width parts, `tan` where `cos` is exactly zero, I/O that may fail)
   is in the result type — `T | Overflow`, `T | DivisionByZero`, `T | undefined`
   — and the caller handles the branch (`is?`, `or_throw`, defaults).

**Consequences for the compiler.**
- Never emit a fallback that changes an operation's meaning (no wrap-to-zero,
  no clamping, no "unreachable" abort). An operation with an unproven
  precondition does not lower; it is reported.
- Analyses may only change *cost*, never validity: a program the analysis
  cannot optimize still compiles and still has no hidden exit.
- Representation choices that avoid the value branch are the preferred way
  to keep the default types ergonomic: `int` becomes `bigint` where a word
  fit is unproven; the default `rational` (decision 2026-08-28) is the
  abstract one, choosing int64 or big-integer parts the same way, so the
  default type has no `Overflow` member. The explicit fixed-width forms
  (`int64`, `rational<int64>`) keep the value branch.

**Consequences for the library — and for every library.** It is unidiomatic
for library code to exit the process: an exit is a whole-program decision that
belongs to the application's author, at points they chose. No `_trap`-style helpers. A library
function that cannot prove its precondition either moves the proof to its
caller (a refined parameter: `_rational_div(a b:Rational<numerator not=? 0>)`)
or returns the failure (`_rational_over(...):>Rational|Overflow`). Invariants
are declared on the types (`Rational`'s positive denominator) so reads assume
them and constructions prove them.

**Why.** Proofs-over-exceptions only pays off if a compiled program is
believed not to crash; a trap is a crash with a nicer message, and it hides
the failure from the type. Errors as values keep every possible failure
visible where it can be handled. History: the first refined-parameter slice
(2026-08-27) briefly introduced `_trap` fallbacks in the rational and fixed
libraries; David rejected them on sight and they were replaced the next day
(see `dewy/status.md`, "No runtime traps").
