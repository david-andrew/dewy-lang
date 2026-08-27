# Types and Numbers

Dewy checks types when it compiles. Literals and surrounding context usually provide enough information that annotations can stay focused on interfaces and important guarantees.

```dewy
let count = 10
let enabled = true
let name:string = "Dewy"
```

## Integers

`int` is a signed integer with arbitrary-precision semantics. `uint` is nonnegative. Fixed-width types are available when width is part of an interface or representation:

```dewy
let offset:int32 = -12
let byte:uint8 = 255
let counter:uint64 = 1
```

An integer literal begins as the exact number written. Context can place it in a compatible integer type, but an out-of-range literal is rejected instead of truncated.

Fixed-width arithmetic retains its width and rolls over according to that bit representation. `int` does not acquire overflow merely because the compiler proves that a machine integer is an efficient representation for a particular program. The compiler stores an `int` as a 64-bit word when range analysis proves it fits, and as an arbitrary-precision big integer otherwise — the program's meaning does not change, only its cost. `dewy --analyze` prints a representation report listing every place a big integer was chosen and why. When you want arbitrary precision regardless of what the analysis can prove, annotate `bigint`:

<!-- dewy-example: compiler -->

```dewy
let main = ():>int64 => {
    let seed = 3000000000
    let cube = seed * seed * seed       # 2.7e28: a big integer automatically
    let factor:bigint = 2^100           # always a big integer
    printl"{cube} {factor}"
    return 0
}
```

Big values stay inside boundaries that admit them: returning one from a function whose result is `int64`, or passing it to a word-sized parameter, is a compile error until a comparison proves the range or the signature says `bigint`.

## Rationals and Fixed-Point

Dividing integers with `/` produces an exact rational, and a decimal literal is an exact rational too:

<!-- dewy-example: compiler -->

```dewy
let third = 1/3              # rational
let price = 9.8              # 49/5, exactly
let sum = third + 2/3        # 1
let ratio = (2/3)^2          # 4/9
```

Rationals print as `n/d` (or as an integer when whole). `//` remains floor division on integers. A literal zero divisor is a compile error.

`fixed` is a fixed-point number with 32 fraction bits, the representation trigonometry produces. A fixed value absorbs integers and rationals in arithmetic, and constants convert exactly:

<!-- dewy-example: compiler -->

```dewy
let x:fixed = 1/3
let y = x * 2 + 0.25
```

`^` raises integers and rationals to integer powers: constant powers fold, a negative constant exponent yields a rational (`2^(-3)` is `1/8`), and a runtime exponent must be a constant or unsigned so that an integer result is sound.

Dewy deliberately provides no floating-point arithmetic: the core targets are integer-only, and rationals and fixed-point cover exact and approximate fractions with predictable behavior. Floating-point types may return later purely for host interoperability.

## Booleans

`bool` has the values `true` and `false`:

```dewy
let ready = true
let retry = failed and attempts <? limit
```

English Boolean operators include `and`, `or`, `not`, `nand`, `nor`, `xor`, and `xnor`.

## `void`, `never`, and `undefined`

- `void` means an expression completed without producing a value.
- `never` means the path cannot complete normally.
- `undefined` is a storable value used for missing alternatives.

`T | undefined` is an optional value, covered in [Optional Values and Narrowing](optional-types.md).

## Type Values and Aliases

A type is a compile-time value of type `type`. Bind it to a name for reuse:

```dewy
const Count:type = int
const Pair:type = [left:int64 right:int64]

let total:Count = 3
let origin:Pair = [left=0 right=0]
```

`<>` groups a type expression where ordinary expression context would be ambiguous:

```dewy
const SmallPrime = <2 | 3 | 5 | 7>
const Result = <string | undefined>
```

Literal values can therefore participate in types. `|` forms a union of alternatives.

## Creating Nominal Types

`type of Parent` creates a fresh nominal child of an existing type:

<!-- dewy-example: design-only -->
```dewy
const UserId:type = type of int
const MyCustomError:type = type of error
```

Each evaluation of `type of` creates identity. Ordinary type intersection does not:

<!-- dewy-example: design-only -->
```dewy
const ContextError:type =
    (type of error) & [context:string]

const DetailedContextError:type =
    ContextError & [source:string]
```

`DetailedContextError` adds a structural requirement while retaining `ContextError`'s nominal ancestry. It is not another nominal error variant.

When an alternative belongs to the nominal `exception` family, navigation can [forward that exception value](errors-as-values.md#exception-values-forward) while applying the requested member operation to the ordinary alternatives. Both `error` and `undefined` descend from `exception`. This is a rule for exception-classified union members, not for arbitrary unions.

## Parameterized Type Aliases

A parameterized alias accepts compile-time type arguments. A bound such as `<T of real>` constrains the accepted argument; unlike the expression `type of Parent`, it does not create nominal identity:

```dewy
const Duration:type = <T of real>(T * Time)
let pause:Duration<int64> = 300ms
```

## Broader Numeric Domains

> **Provisional design:** Beyond integers, rationals, and fixed-point, Dewy's numeric hierarchy is intended to include reals, complex values, and quaternions. Their construction, promotion, rounding, and literal rules are not yet specified, so this book does not invent syntax for them.

The Reference defines the settled [numeric rules](../../reference/numeric-types.html) and [type/conversion model](../../reference/types-and-conversions.html).
