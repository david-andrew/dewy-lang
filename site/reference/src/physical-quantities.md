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

A unit carries an exact scale and dimension. Constant expressions fold that scale completely; a quantity that reaches runtime carries only its number in the canonical scale and no unit tag.

## Dimensions and Canonical Scales

The base dimensions are `Time`, `Length`, `Mass`, `Current`, `Temperature`, `Amount`, `Luminosity`, and `Angle`. Their canonical units are the second, metre, kilogram, ampere, kelvin, mole, candela, and the whole turn. Every other unit is a rational scale of a canonical unit, so prefixes and derived units are exact: `ms` is `1/1000 s`, `N` is `kg * m / s^2` with scale one, `°` is `1/360 turn`. The radian's scale is irrational and is represented in fixed point.

Addition, subtraction, and comparison require identical dimensions and are otherwise compile errors. Multiplication and division combine dimensions; `^` with a constant integer exponent raises them. Dividing a quantity by a unit of the same dimension yields the dimensionless count in that unit. A quantity's number is an integer, rational, or fixed-point value, promoted by the same rules as dimensionless arithmetic.

## Trigonometry

`cos`, `sin`, and `tan` accept a rational or fixed-point angle quantity and return `fixed`. Range reduction happens exactly on the turn count before evaluation.

## Time and Sleeping

`s`, `ms`, `us`, and `ns`, together with their written names and `minute`/`hour`, denote exact time scales. `sleep` accepts a rational time quantity and converts it to whole nanoseconds at the system boundary; a dimensionless number is rejected.

## Provisional Scope

The type-product model, representation parameterization, the base-dimension algebra with canonical scales, and erasure are settled. Provisional: a quantity's display unit (printing `4500 J` rather than the canonical number) and `x as km` to select one, declaring base dimensions in library code, offset scales such as Celsius and their point/delta semantics, calendar-relative durations, and catalog organization.
