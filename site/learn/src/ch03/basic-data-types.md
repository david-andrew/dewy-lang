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

Fixed-width arithmetic retains its width and rolls over according to that bit representation. `int` does not acquire overflow merely because the compiler proves that a machine integer is an efficient representation for a particular program.

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

Parameterized aliases accept compile-time type arguments:

```dewy
const Duration:type = <T of real>(T * Time)
let pause:Duration<int64> = 300ms
```

## Broader Numeric Domains

> **Provisional design:** Dewy's numeric hierarchy is intended to include exact rationals, reals, concrete floating-point representations, complex values, and quaternions. Their complete construction, promotion, rounding, exceptional-value, and literal rules are not yet specified, so this book does not invent syntax for them.

The Reference defines the settled [numeric rules](../../reference/numeric-types.html) and [type/conversion model](../../reference/types-and-conversions.html).
