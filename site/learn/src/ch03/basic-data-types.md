# Basic Data Types

Dewy checks types when you compile. Literals and context usually supply
enough information that you can omit annotations. When you write a type,
you are naming what the value *is*, not only how it is stored.

## Integers

An integer with no type written down has type `int`, a signed integer
that can be as big as you need. Fixed-width integers are available when
you want a specific size.

```dewy
my_int = -12                    # int
my_int32 = 42 as int32
my_uint = 15 as uint
my_uint64 = 2001 as uint64
```

A literal is exactly the number you wrote, then it has to fit wherever
you put it. `let byte:uint8 = 255` is fine. A value that does not fit is
an error.

| Type | Description | Range |
| ---- | ----------- | ----- |
| `int` | Arbitrary-precision signed | `(-inf..inf)` |
| `int8` | 8-bit signed | `[-128..127]` |
| `int16` | 16-bit signed | `[-32768..32767]` |
| `int32` | 32-bit signed | `[-2147483648..2147483647]` |
| `int64` | 64-bit signed | `[-9223372036854775808..9223372036854775807]` |
| `int128` | 128-bit signed | `[-2^127..2^127-1]` |
| `uint` | Arbitrary-precision unsigned | `[0..inf)` |
| `uint8` | 8-bit unsigned | `[0..255]` |
| `uint16` | 16-bit unsigned | `[0..65535]` |
| `uint32` | 32-bit unsigned | `[0..4294967295]` |
| `uint64` | 64-bit unsigned | `[0..18446744073709551615]` |
| `uint128` | 128-bit unsigned | `[0..2^128-1]` |

[Number Bases](number-bases.md) covers `0b`, `0x`, and friends.

### Custom-Ranged Integers

You can refine an integer type with a range:

```dewy
my_custom_number:int<range=[42..)> = 42
```

What happens if a value leaves that range (error, wrap, or `undefined`)
is not yet determined.

## Rationals and Reals

A rational is an exact ratio of integers. A real is a floating-point
number. The default real is 64-bit.

```dewy
my_rational = rational(22 7)
my_real = 3.1415
my_real32 = 54.54 as real32
my_real64 = 233.511534 as real64
```

`int of rational`. `rational of real`. `real of number`. `float32` /
`float64` are the IEEE names. `real32` / `real64` are the matching real
aliases.

### Fixed-Point

Fixed-point numbers store digits and a decimal shift. How you write a
literal is not yet determined.

## Booleans

```dewy
my_bool = true
ready = false
```

The operators are the English words `and`, `or`, `not`, and the rest. See
[Operators](operators.md).

## `void`, `never`, and `undefined`

`void` means nothing came out. Declarations, assignments, and `printl`
are `void`.

`never` means this path cannot happen. There is no value of that type.
After you have already handled every case, what is left is `never`.

`noreturn` is different. It marks a function that does not come back to
the caller, such as `exit`.

`undefined` is a real value you can store and pass around. It is not
`void`, and it is not a name you forgot to set.

Optionals are `T | undefined`. They have [their own page](optional-types.md).

## Complex Numbers and Quaternions

```dewy
my_complex0 = 2^/2 + 2i^/2
my_complex1 = complex(2^/2 2^/2)
my_complex2 = complex(1 45°)
my_complex3 = 1 ∠ 45°

q = 1 + 2i + 3j + 4k
Q = 1 + 2I + 3J + 4K
```

`i`, `j`, and `k` are the imaginary units. Uppercase forms work too.

## Other Types

Strings, ranges, arrays, objects, functions, and units each have a page.
Types themselves are expressions. You can bind an alias and use it in
annotations.

```dewy
let Pair:type = [left:int64 right:int64]
```
