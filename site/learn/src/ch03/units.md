# Physical Quantities and Units

Dewy places physical dimensions in the type system. A length is not interchangeable with a duration merely because both happen to use the same machine number.

```dewy
let distance = 120m
let elapsed = 10s
let speed = distance / elapsed
```

Adding incompatible dimensions is an error:

```dewy
2kg + 3m
```

## Units Are Ordinary Values and Types

Writing a number next to a unit multiplies them. Group compound units when that makes the intended precedence clearer:

```dewy
let acceleration = 9.8(m/s^2)
let force = 5kg * acceleration
```

Unit scales can fold at compile time. The unit portion may disappear entirely from the runtime representation once it has guaranteed that operations are dimensionally valid.

The base dimensions are `Time`, `Length`, `Mass`, `Current`, `Temperature`, `Amount`, `Luminosity`, and `Angle`. Multiplying, dividing, and raising quantities combines their dimensions; adding, subtracting, and comparing require the same dimension.

## Canonical Scales

Every dimension has a canonical unit — the SI base unit, and the whole turn for angles — and every other unit is an exact rational scale of it. `1/2 * mass * velocity^2`, `30m/s`, and `9.8(m/s^2)` therefore fold to exact constants, and a quantity that survives to runtime carries only its number in the canonical scale:

<!-- dewy-example: compiler -->

```dewy
const mass = 10kg
const velocity = 30m/s
let energy = 1/2 * mass * velocity^2       # 4500 J
let joules:rational = energy / J            # dividing by a unit yields the count
```

(`const` keeps the quantities compile-time so the arithmetic folds; runtime rational arithmetic on 64-bit parts yields `rational | Overflow` for the caller to handle — the abstract `rational` that picks big-integer parts where a fit cannot be proven is the planned default.)

Angles use the turn so that degrees are exact (`45°` is `1/8 turn`) and trigonometry reduces exactly before computing. `cos`, `sin`, and `tan` accept an angle and return a [fixed-point](basic-data-types.md#rationals-and-fixed-point) value:

<!-- dewy-example: compiler -->

```dewy
let work = 20N * 10m * cos(45°)            # about 141.42 J
```

The catalog covers the SI base units, the usual prefixes (`km`, `cm`, `mm`, `g`, `mg`, `ms`, `us`, `ns`, `minute`, `hour`), the derived units `Hz N Pa J W`, `turn`, `°`/`deg`, and `rad`.

## Representation-Parameterized Quantities

A duration is a numeric representation multiplied by the `Time` dimension:

```dewy
const Duration:type = <T of real>(T * Time)
```

`Duration<int64>` preserves the selected integer representation. The `Time` portion supplies meaning and static checking without requiring a wrapper object around the integer. `sleep` takes a time quantity — `sleep(300ms)` — and converts to whole nanoseconds at the system boundary; a dimensionless number is rejected.

## Converting Scales

Units of the same dimension represent the same kind of physical value at different scales. Dividing by a unit yields the count in that unit, as in `distance / km`. Mixed-unit arithmetic first establishes compatible dimensions and then applies the exact scales.

## Unit Libraries

The standard library should organize unit catalogs by domain so programs import useful names without making every abbreviation globally ambiguous. SI, information, customary, astronomical, and domain-specific units can build on the same dimension model.

> **Provisional design:** The base-dimension algebra, canonical scales, the rational/fixed representations, and dimension erasure are settled. Still under design: printing a quantity in the unit it was written in (and `x as km` to choose one), declaring new base dimensions in library code, offset units such as Celsius (points versus deltas), calendar-relative durations, and catalog organization.

See the exact [physical quantity reference](../../reference/physical-quantities.html).
