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

## Representation-Parameterized Quantities

A duration is a numeric representation multiplied by the `Time` dimension:

```dewy
const Duration:type = <T of real>(T * Time)

let pause:Duration<int64> = 300ms
sleep(pause)
```

`Duration<int64>` preserves the selected integer representation. The `Time` portion supplies meaning and static checking without requiring a wrapper object around the integer.

## Converting Scales

Units of the same dimension represent the same kind of physical value at different scales. Conversion changes the numeric scale while preserving that physical value. Mixed-unit arithmetic first establishes compatible dimensions and then applies the appropriate exact or explicitly rounded conversion.

## Unit Libraries

The standard library should organize unit catalogs by domain so programs import useful names without making every abbreviation globally ambiguous. SI, information, customary, astronomical, and domain-specific units can build on the same dimension model.

> **Provisional design:** `Time`, representation-parameterized `Duration`, exact nanosecond/millisecond/second scales, and dimension erasure establish the core model. The complete base-dimension algebra, offset units, catalog organization, calendar-relative durations, and noninteger conversion policy remain under design.

See the exact [physical quantity reference](../../reference/physical-quantities.html).
