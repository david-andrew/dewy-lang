# Juxtaposition multiplication

Decided 2026-10-23. This restricted, type-directed rule replaces the reference's
fully general juxtaposition design (operators-and-precedence.md:24-35). It came
from a brainstorm with Astra and Sol, reviewed by David.

## Eligible forms

The parts are written with no whitespace between them:

- a numeric literal followed by a name or member term (including its postfix
  calls) or a parenthesized group: `2x`, `2sin(x)`, `3(a+b)`, `2x^2`;
- a named numeric value or field route followed by a parenthesized group:
  `a(x)`, `material.k(T)`, `n(n+1)/2`;
- an explicitly parenthesized scalar expression followed by a parenthesized
  group, a name or a number: `(a+1)(a-1)`, `(a+b)(c+d)^2`, `(5)x`, `(x)2`,
  `(a+1)x^2` (corrected 2026-10-23).

The left side must be a statically known, non-callable numeric scalar or
quantity. Having `__mul__` alone does not qualify.

In this multiplication context, the parenthesized group must supply exactly one
value expression: no named arguments, spreads or multiple items. For a number
`a`, `a(x y)` is an error ("write `a * (x * y)`"). Everywhere else, parentheses
keep holding multi-expressions wherever the receiving context accepts them; the
restriction applies only to juxtaposition multiplication.

## Resolution

At `head(...)`, the head is classified once, before any implicit zero-argument
call:

- a callable is a call, at call precedence;
- an eligible number is a multiplication, at coefficient precedence;
- a union of callable and numeric, an unresolved category, or an object that is
  both requires narrowing or an explicit operator.

A failed call never falls back to multiplication. A numeric or array value
named like a function (`let sin=0.5` then `sin(x)^2`) warns that it hides the
function (decided 2026-10-23).

Calls (corrected 2026-10-23):

- any expression immediately followed by an empty `()` is a call: `(5)()` and
  `2()` call a number, which is an error;
- a parenthesized callable followed by a delimited argument is a call:
  `(f)(x)`, `(f)[1 2]`, `(p)"..."`, `(p)r"..."`, like `f[1 2]` and `printl'...'`;
- a parenthesized callable followed by a name or number is an error ("write
  `f(x)`"), as is a parenthesized non-number (`(s)x` for a string `s`);
- a member or index right after a call's parentheses (`a(x).abs()`, `a(x)[i]`)
  is rejected only when `a` is a number, where it would bind to the group, not
  the product (idiomatic: `abs(a(x))`). With a callable `a` it is an ordinary
  call chain.

## Precedence

From highest to lowest:

1. member, call, index;
2. `^` (right-associative);
3. juxtaposition multiplication (left-associative);
4. `* / // %`;
5. unary `+ -`;
6. binary `+ -`;
7. comparisons.

| Expression | Means |
|---|---|
| `sin(x)^2` | `(sin x)^2` |
| numeric `a(x)^2` | `a*(x^2)` |
| `2sin(x)^2` | `2*(sin(x)^2)` |
| `-a(x)^2` | `-(a*x^2)` |
| `2^3x` | `(2^3)*x` |
| numeric `a(x)(y)^2` | `a*x*y^2` |
| `1/2m` | `1/(2m)` (correct by precedence; no lint) |

## Excluded, with diagnostics

| Written | Diagnostic |
|---|---|
| `a b`, `ρ g h` (whitespace products) | "write `*`"; whitespace always separates expressions |
| `f(x)g(x)` (a call result as coefficient) | "write `f(x) * g(x)`" |
| `xs[i](j)`, `xs[i]y` (an indexed element as coefficient) | "write `xs[i] * j`"; `]x` stays a parse error |
| `A x`, `A(x)` (tensors) | "write `A*x` (or `A[x]` to index)" |
| numeric `@a(x)` | partial application requires a callable |
| `printl"hi"` | string-literal calls stay call-only |

## Units

There are no spaced units anywhere. A unit must be juxtaposed: `9.81m/s^2`,
`20m`. `9.81 m` is two expressions. This is one rule across the whole language.
Unit names resolve through ordinary bindings, so a local `m` shadows the meter.

## Implementation

One local typed pass over marked adjacency spans. There are no alternative
trees and no speculative rechecking. It is O(n) with cached category lookups,
and its cost on the flagship panel is shown before landing.
