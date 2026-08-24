# Everyday Mathematics (Draft)

> **Unpublished design draft:** This page is retained as source material for a future practical mathematics guide. It will return to the Learn navigation after fractional numerics, ordinary juxtaposition multiplication, the core math library, and vectorized operations have settled contracts.

Integer arithmetic uses Dewy's ordinary typed operators. Prefix `/x` is intended to express a reciprocal, and a composite chain such as `n^/2` is intended to express a square root while retaining the first operator's precedence.

The more compact formula notation depends on general numeric juxtaposition multiplication, which is still provisional:

<!-- dewy-example: design-only -->
```dewy
let quadratic = (a:real b:real c:real x:real) => a(x^2) + b(x) + c
let root1 = (-b + (b^2 - (4a)c)^/2) / 2a
let root2 = (-b - (b^2 - (4a)c)^/2) / 2a
```

## Mathematical Library

Constants such as `pi` and functions such as `sin`, `cos`, and `sqrt` belong in the ordinary library namespace rather than requiring a separate formula language. Their precise types depend on the still-provisional rational, real, and floating-point hierarchy.

<!-- dewy-example: design-only -->
```dewy
let identity = sin(x)^2 + cos(x)^2
let message = "result: {sqrt(64) + 9 * cos(pi)}"
```

Complex numbers and quaternions are intended numeric domains, but their construction, literal, promotion, and exceptional-value rules have not been selected. This draft therefore does not invent literal syntax for them.

## Vectorized Operations

A leading `.` on an operator is intended to apply it elementwise. Broadcasting and Boolean array selection must be specified with the multidimensional shape model before these examples become normative:

<!-- dewy-example: design-only -->
```dewy
let primes = [2 3 5 7 11 13 17 19]
let remainders = 20 .% primes
let factors = primes[remainders .=? 0]
```

Physical quantities compose with the same numeric model; see [Physical Quantities and Units](units.md).
