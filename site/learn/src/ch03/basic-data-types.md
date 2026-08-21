# Basic Data Types

Dewy checks types when you compile. Literals and context usually supply enough information that you can omit annotations. When you write a type, you are naming what the value _is_, not only how it is stored.

## Integers

An integer with no type written down has type `int`, a signed integer that can be as big as you need. Fixed-width integers are available when you want a specific size.

```dewy
my_int = -12                    # inferred as `int`
my_int32:int32 = 42
my_uint:uint = 15
my_uint64:uint64 = 2001
```

A literal is exactly the number you wrote, then it has to fit wherever you put it. `let byte:uint8 = 255` is fine. `let byte:uint8 = 1234` is an error.

| Type | Description | Range |
| --- | --- | --- |
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

The compiler will guarantee that

## Rationals and Reals

A rational is an exact ratio of integers.

`real` is the parent type for most of the numbers you use day to day.

Floating-point work uses the concrete types `float32` and `float64`.

```dewy
my_rational = rational(22 7)
approx: float64 = 3.1415
small: float32 = 54.54
```

`int is a rational`. `rational is a real`. `real is a number`.

### Fixed-Point

Fixed-point numbers store digits and a decimal shift. Fixed-point literal syntax is not yet determined.

### Symbolics

Dewy will support symbolic values, in the same spirit as MATLAB's symbolics. You write an expression in unknowns, then substitute or differentiate later. The syntax and rules are not yet determined, but may look something like this:

```dewy
let x = sym
let y:real = sym
let W:array<real length=[5 2]> = sym

# potental way to declare many at once (needs more work)
let (a b c d) = loop true sym
```

## Booleans

```dewy
my_bool = true
ready = false
```

The operators are the English words `and`, `or`, `not`, and the rest. See [Operators](operators.md).

## `void`, `never`, and `undefined`

`void` means nothing came out. Declarations, assignments, and `printl` are `void`.

`never` means this path cannot happen. There is no value of that type. After you have already handled every case, what is left is `never`.

`undefined` is a real value you can store and pass around. It is not `void`, and it is not a name you forgot to set.

Optionals are `T | undefined`. They have [their own page](optional-types.md).

## Complex Numbers and Quaternions

```dewy
my_complex0 = 2^/2 + (2^/2)i
my_complex1 = complex(2^/2 2^/2)
my_complex2 = complex(1 45°)
my_complex3 = 1 ∠ 45°

q = 1 + 2i + 3j + 4k
Q = 1 + 2I + 3J + 4K
```

`i`, `j`, and `k` are the imaginary units. Uppercase forms work too. TBD if they need to be imported or are included in the prelude imports

## Type Declarations

A type is itself a value, and its type is `type`. Bind one to a name when you want to reuse it in annotations.

The `:type` annotation is what tells the compiler the right-hand side is a type, not a runtime value.

```dewy
let Count:type = int
let total:Count = 3
```

`const` works the same way when the name should not be rebound. A structural type gets a name the same way. That name is an alias for the structure, not a class object sitting in memory.

```dewy
let Pair:type = [left:int64 right:int64]
let origin:Pair = [left = 0 right = 0]
```

You can still write the type inline. `let count:int = 10` does not need an alias.

A parameterized alias takes type parameters before the body, such as `<T of real>(...)`. See [Time](../ch04/xx-time.md) for `Duration`, and [Objects](object-types.md) for more on structural types.

[Strings](string-types.md), [ranges](range-types.md), [arrays](container-types.md), [objects](object-types.md), [functions](function-types.md), and [units](units.md) each have their own dedicated pages.
