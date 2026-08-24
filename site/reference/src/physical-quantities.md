# Physical Quantities

A physical quantity combines a numeric representation with a dimension. Dimensions participate in static type checking and need not survive as runtime objects.

## Type Products

Applying arithmetic to type values describes the type produced by that operation. A duration may therefore be described as a real-valued representation multiplied by the `Time` dimension:

```dewy
const Duration:type = <T of real>(T * Time)
```

`Duration<int64>` preserves `int64` as its numeric representation while requiring a time dimension.

## Unit Values

Juxtaposing a number with a unit multiplies them:

```dewy
let timeout = 300ms
let distance = 10m
```

A unit carries an exact scale and dimension. Constant expressions may fold that scale completely; for example, an implementation may lower `300ms` to an integer count in the canonical time scale while retaining no runtime unit tag.

Addition and comparison require compatible dimensions. Multiplication and division combine dimensions. Conversion between units preserves the physical value rather than reinterpreting the numeric bits.

## Time and Sleeping

`ns`, `ms`, and `s`, together with their written names, denote exact time scales. `sleep` accepts a duration, so a dimensionless number is rejected even when its machine representation would be accepted by the host system call.

## Provisional Scope

The general type-product model, representation parameterization, and erasure of compile-time dimensions are settled directions. The complete base-dimension catalog, unit import organization, offset scales such as Celsius, calendar-relative durations, noninteger runtime arithmetic, and canonical conversion policies remain provisional.
