# Numeric Types

> [Generated coverage](/status/#ref-numeric-types) names related acceptance programs. Every example on this page compiles with the current compiler unless it is marked **Design only**.

| Type | Values |
|---|---|
| `int` | mathematical integers, arbitrary precision; `bigint` names the same type |
| `int8` … `int64`, `uint8` … `uint64` | fixed-width integers: exact arithmetic, proven storage |
| `addr` | a nonnegative position below the target's address space |
| `rational` | exact fractions; decimal literals |
| `float32`, `float64` | IEEE 754 binary floating point |

## `int`

`int` is the mathematical integer. Unannotated integer literals are `int`, and arithmetic on `int` grows as needed; it never overflows. `int` has no `.min` or `.max`. The compiler keeps an `int` in a machine word when range analysis proves it fits, and switches to an arbitrary-precision representation otherwise; only the cost differs.

<!-- dewy-example: {"mode":"run","stdout":"1267650600228229401496703205376\n27000000000000000000000000000\n25000000000000000000\n"} -->
```dewy
let sq = (x:int):>int => x*x
printl(2^100)
let seed = 3000000000
printl(seed * seed * seed)
printl(sq(5000000000))
```

`bigint` is `int`'s arbitrary-precision form under another name: any integer converts to it, and an oversized literal fits it. `.divmod(other)`, `.gcd(other)`, `.abs()` and `.pow(n)` are exact; `.to_int64()` and `.to_uint64()` return an optional word and never truncate. `to_int(text)` parses decimal text of any size.

## Fixed-Width Integers

`int8`, `int16`, `int32`, `int64` and `uint8` … `uint64` describe storage. Their arithmetic is exact: plain `int64` arithmetic yields `int`, so an unannotated `let total = a + b` never overflows. Storing into a fixed-width binding, field, element, parameter or result is a *proven narrowing*: free when the facts prove the value fits, a compile error otherwise.

<!-- dewy-example: {"mode":"run","stdout":"-32 227\n255 -9223372036854775808\n"} -->
```dewy
printl"{uint64(2) - uint64(34)} {int8(127) + 100}"
printl"{uint8.max} {int64.min}"
```

<!-- dewy-example: {"mode":"reject","diagnostic":"cannot prove `sq(a) <=? 9223372036854775807` for the conversion to int64"} -->
```dewy
let sq = (x:int):>int => x*x
let a:int64 = 5000000000
let t:int64 = sq(a)
```

An unproven narrowing offers three fixes: widen the destination to `int`, state the domain as a refinement or prove it with a guard, or choose an overflow policy. Under `$runtime_checks` it becomes a check that panics when the value does not fit. A literal must fit its fixed-width context exactly (`let b:uint8 = 256` is an error).

### Overflow Policies

Wrapping and saturation are part of the type, as a keyword parameter: `uint8<overflow='wrap'>` is arithmetic modulo 2^8 (two's complement for a signed type), and `uint8<overflow='saturate'>` clamps to 0 through 255. Calling the type converts any integer, including an `int`, by that policy. A policy operand decides the arithmetic with plain integers of its width or narrower; an `int` operand keeps the result exact, and two different policies do not mix.

<!-- dewy-example: {"mode":"run","stdout":"44 255\n18446744073709551615\n4 255\n"} -->
```dewy
printl"{uint8<overflow='wrap'>(300)} {uint8<overflow='saturate'>(300)}"
printl(uint64<overflow='wrap'>(int64(-1)))
let a:uint8<overflow='wrap'> = 250
let c:uint8<overflow='saturate'> = 250
printl"{a + 10} {c + 10}"
```

## `addr`

`addr` is a position: a nonnegative integer below `2^48` on 64-bit native targets and `2^32` on `wasm32`. It is what `.length`, indices and offsets are. Two positions in one address space add and subtract without leaving it, so `i + 1` under `i <? xs.length` is an `addr` with no further proof. Storing an arbitrary integer into an `addr` is a proven conversion.

## Meeting Another Width

A value of one integer type meeting another (an `int` stored into `uint64`, an `int8` widened to `int64`, `xs.length` stored into `uint64`) is a conversion the compiler proves in range from the type's own range, a comparison, a length or a loop guard. Widening always passes. A refuted narrowing is an error naming the value; an unproven one names the missing bound. `x as T` and `T(x)` are the same proven conversion, never a reinterpretation.

<!-- dewy-example: {"mode":"run","stdout":"1\n"} -->
```dewy
first_over = (xs:array<int64> limit:int64):>uint64? => {
    loop i in 0.. and i <? xs.length {
        if xs[i] >? limit return i      # i is in [0, int64.max]: fits uint64
    }
    none
}
printl(first_over([1 5 9] 4))
```

<!-- dewy-example: {"mode":"reject","diagnostic":"w does not fit int8"} -->
```dewy
let w:int64 = 300
let b:int8 = w
```

A comparison between two widths (`i:uint64 <? s.length`) compares in the left operand's width; the right operand takes the same proven conversion. A comparison is kept as a fact about the difference of its two terms, so `xs.length - i` is at least 1 under `i <? xs.length`.

## Division and Remainder

On integers, `//` is floor division and `%` gives a remainder with the divisor's sign. `/` on integers gives an exact `rational`. `mod(a b kind='trunc')` gives C's remainder (the dividend's sign) and `kind='euclid'` a remainder that is never negative. A divisor must be proven nonzero; a constant zero divisor is a compile error.

Unary minus binds below `*`, `/`, `//` and `%`, so `-7 // 2` is `-(7 // 2)`. Parenthesize a negative operand:

<!-- dewy-example: {"mode":"run","stdout":"3 -4 -3\n1 2 -2 -1\n7/2 9223372036854775808\n"} -->
```dewy
printl"{7 // 2} {(-7) // 2} {-7 // 2}"
printl"{7 % 3} {(-7) % 3} {7 % (-3)} {mod(-7 3 kind='trunc')}"
printl"{7 / 2} {int64.min // (-1)}"
```

## Shifts

A shift count is unsigned; a negative literal count is an error. On `int`, a left shift is exact, and a right shift beyond the significant bits gives the sign continuation (`0` or `-1`). Plain `int64` shifts return `int`. Other fixed-width shifts are exact intermediates that must fit when stored; a wrapping type keeps the low bits.

<!-- dewy-example: {"mode":"run","stdout":"1180591620717411303424\n18446744073709551616 -1 0\n"} -->
```dewy
printl(1 << 70)
printl"{int64(1) << 64} {int64(-2) >> 64} {uint64<overflow='wrap'>(1) << 64}"
```

## Powers

`^` is right-associative and binds above unary minus: `2^3^2` is `2^(3^2)` and `-2^2` is `-(2^2)`. An integer power with a nonnegative exponent is an exact integer; a negative constant exponent gives a `rational`; a runtime exponent that may be negative is an obligation. Zero to the zeroth power is one. Use `xor` for bitwise exclusive-or.

<!-- dewy-example: {"mode":"run","stdout":"512 -4 1/4 27/8\n"} -->
```dewy
printl"{2^3^2} {-2^2} {2^(-2)} {(2/3)^(-3)}"
```

## Rationals

`rational` is an exact fraction, kept normalized: a positive denominator and coprime parts, each a machine word while it fits. Integer `/` and decimal literals (`9.8`, `1.25e2`) give rationals, and an integer promotes to `rational` wherever one is expected. `+`, `-`, `*`, `/`, `^`, negation and comparisons are exact; `//` gives an `int` floor quotient and `%` a rational remainder.

A value prints the way it was written: a whole number as an integer, a value made from decimals as a decimal (a repeating block in parentheses), a value made from fractions as `n/d`. How it prints never changes the value: `0.5 =? 1/2`.

<!-- dewy-example: {"mode":"run","stdout":"5/6 0.0(3) 293.15 true\n3 4 -3\n"} -->
```dewy
kelvin = (celsius:rational):>rational => celsius + 273.15
main = () => {
    printl"{1/2 + 1/3} {0.1/3} {kelvin(20)} {0.5 =? 1/2}"
    printl"{(7/2).floor} {(7/2).ceil} {int(-7/2)}"
}
```

`rational<int64>` keeps `int64` parts; its arithmetic returns `rational<int64> | Overflow` when an exact result does not fit.

## Rounding

`.floor`, `.ceil` and `.round` of a rational give an `int`; `int(q)` truncates toward zero. `round` of an exact number sends a half away from zero; `round` of a float follows IEEE 754 and sends a half to the even neighbour. `rounding=` chooses the rule: `'nearest_away'`, `'nearest_even'`, `'nearest_toward_zero'`, `'nearest_up'`, `'nearest_down'`, `'floor'`, `'ceil'`, `'toward_zero'` or `'away_from_zero'`.

<!-- dewy-example: {"mode":"run","stdout":"3 3 -3\n2.0 3.0\n"} -->
```dewy
printl"{round(5/2)} {round(2.5)} {round(-2.5)}"
let f:float64 = 2.5
printl"{round(f)} {round(f rounding='nearest_away')}"
```

## Floating Point

`float32` and `float64` are strict IEEE 754 binary32 and binary64. NaN, the infinities, signed zero and subnormals are ordinary values, not traps. Results round to nearest, ties to even, and arithmetic is never reassociated or fused, so a float expression gives the same result on every target. `float64.max`, `.min`, `.epsilon`, `.inf`, `.nan` and related constants name the limits.

A decimal literal is a float only in a float context (an annotation, a float operand or parameter). Conversions between exact and floating values are explicit: `.to_float64()` rounds a rational once; `rational(f)` is a float's exact binary value; `int(f)` truncates toward zero and requires the value to be finite and in range, proven like a narrowing.

<!-- dewy-example: {"mode":"run","stdout":"0.30000000000000004 inf true\n"} -->
```dewy
let a:float64 = 0.1
let z:float64 = 0.0
printl"{a + 0.2} {1.0/z} {-0.0 =? 0.0}"
```

Settings change a scope's float policy: `$no_nan` and `$no_inf` make producing those values an obligation, `$finite_floats` is both, and `$fast_math` permits reassociation. See [Settings](settings.md).
