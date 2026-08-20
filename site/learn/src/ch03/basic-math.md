# Basic Math

Arithmetic is ordinary Dewy. There is no separate formula language.

## Operators

The usual operators work on numbers. `+` `-` `*` `/` `//` `%` `^`. Prefix
`/x` is `1/x`. Composite chains keep the first operator's precedence, so
`n^/2` is a square root.

```dewy
quadratic = (a b c x) => a(x^2) + b(x) + c
root1 = (-b + (b^2 - (4a)c)^/2) / 2a
root2 = (-b - (b^2 - (4a)c)^/2) / 2a
```

Juxtaposition multiplies when both sides are numeric, and calls when the
left side is a function:

```dewy
identity = sin(x)^2 + cos(x)^2
2(x + 1)
```

See [Operators](operators.md) for the full table, including shifts and
elementwise `.`.

## Constants and Functions

`pi` and `inf` are language constants. `sin`, `cos`, `sqrt`, and the rest
of the usual real functions are ordinary functions. Complex and
quaternion literals are in [Basic Data Types](basic-data-types.md).

```dewy
my_expression = 'string with the expression {sqrt(64) + 9 * cos(pi)}'
```

## Broadcasting

Prefix `.` on an operator applies it per element:

```dewy
primes = [2 3 5 7 11 13 17 19]
mods = 20 .% primes
is_factor = mods .=? 0
p_factors = primes[is_factor]
```

## Units

Numbers can carry dimensions. `10kg * (30m/s)^2` is energy. See
[Units](units.md).
