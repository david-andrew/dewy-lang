# Basic Data Types

## Numeric

Numeric data is what it sounds like, values that represent a number

### Numbers

Numbers are the base case for numerical values, with each subsequent type being a more specific / restricted version of the number class.

```dewy
my_number = 10
```

### Integers

Integers are numbers that do not contain any decimal component. By default, integers can be arbitrarily large, but fixed width integers are also possible

```dewy
my_int = -12 as int
my_int32 = 42 as int32

my_uint = 15 as uint
my_uint64 = 2001 as uint64
```

The full list of integer types includes
 - **int**: Arbitrary precision signed integer
 - **int8**: 8-bit signed integer. range = [-128:127]
 - **int16**: 16-bit signed integer. range = []
 - **int32**: 32-bit signed integer. range = []
 - **int64**: 64-bit signed integer. range = []
 - **(maybe) int128**: 128-bit signed integer. range = []
 - **uint**: arbitrary precision unsigned integer
 - **uint8**: 8-bit unsigned integer. range = [0:255]
 - **uint16**: 16-bit unsigned integer. range = []
 - **uint32**: 32-bit unsigned integer. range = []
 - **uint64**: 64-bit unsigned integer. range = []
 - **(maybe) uint128**: 128-bit unsigned integer. range = []

### Fixed Point
Fixed point will be stored as two integers, `digits` and `shift` where the value is `digits * 10^shift`

TBD on the syntax for declaring a fixed point number. likely to be a function call e.g. 

```dewy
my_fixed_point = fixed_point(3141592, -6)
```


### Rational
Rational numbers are stored as two integers, the `numerator` and the `denominator`, where the value is `numerator / denominator`

TBD on the syntax for declaring a rational number. likely to be a function call e.g.

```dewy
my_rational = rational(22, 7) //rational approximation of pi
```


### Real

Real numbers are positive and negative numbers that can have a decimal component to them. The default real will be stored as a `float64` i.e. a 64-bit floating point number, but other widths (and potentially arbitrary precision) are possible

```dewy
my_real = 3.1415
my_real32 = 54.54 as real32
my_real64 = 233.511534 as real64
```

### Boolean

Standard true/false type

```dewy
my_bool = true
```

### Complex

complex numbers

```dewy
my_complex0 = 2^/2 + 2i^/2
my_complex1 = complex(2^/2, 2^/2)
my_complex2 = complex(1, 45°)
```

### Quaternions

Quaternions

## MISC.
Other datatypes (probably include on this page)
- strings
- symbolics
- units
- types
- enums or tokens
