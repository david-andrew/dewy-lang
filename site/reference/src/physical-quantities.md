# Physical Quantities

> [Generated coverage](/status/#ref-physical-quantities) names related acceptance programs. Every example on this page compiles with the current compiler unless it is marked **Design only**.

A physical quantity is a number with a dimension. The dimension is part of the static type and is erased at run time: a quantity is stored as its plain number in canonical units.

## Unit Values

A unit is written against its number: `20m`, `300ms`, `9.81m/s^2`. `9.81 m` is two expressions, and a unit written apart from the number before it is an error. Writing a number against a unit multiplies them.

The time units `s`, `ms`, `us`, `ns`, their written names, `minute` and `hour` are in the prelude. Every other unit is imported from the library module `units`. Units are ordinary bindings, so a local `m` hides the metre.

After `0`, a letter is a unit (`0g`, `0s`, `0deg`). Only `0x` and `0z` always begin a base prefix; `0b`, `0t`, `0q`, `0s`, `0o`, `0d`, `0u` and `0g` begin one only before a digit, `_` or quote (`0b101`).

<!-- dewy-example: {"mode":"run","stdout":"6.0\n"} -->
```dewy
from units import m
Speed:type = float64 * Length / Time
Duration:type = <T>(T * Time)
travel = (speed:Speed elapsed:Duration<float64>):>(float64 * Length) => speed*elapsed
let distance = travel(20m/s 300ms)
printl"{distance/m}"
```

A type is a number type times a dimension (`float64 * Length`); `<T>(T * Time)` is a type constructor that keeps the number type as a parameter.

## Dimensions and Scales

The base dimensions are `Time`, `Length`, `Mass`, `Current`, `Temperature`, `Amount`, `Luminosity` and `Angle`. Their canonical units are the second, metre, kilogram, ampere, kelvin, mole, candela and the whole turn.

Every unit is an exact multiple of a canonical unit. `units` defines, among others, `m`, `km`, `cm`, `mm`, `L`, `mL`, `kg`, `g`, `mg`, `A`, `K`, `mol`, `cd`, `turn`, `°` (also `deg`), `rad`, `Hz`, `N`, `Pa`, `J`, `W`, `V`, `kJ`, `kW`, `kWh`, `inch`, `ft`, `yd`, `mile`, `BTU`, `°C`, `°F`, `R` and `RSI`.

<!-- dewy-example: {"mode":"run","stdout":"true true true true\n"} -->
```dewy
from units import m, km, deg, turn, L, mL
printl(3km =? 3000m  300ms =? 3s/10  90deg =? turn/4  1000mL =? 1L)
```

A quantity's number is a machine integer, a checked `int`, a `rational`, `float32` or `float64`, following the same rules as a plain number. A whole number with a unit holds whole numbers; a decimal point makes it hold fractions (`let t = 0.0m`, then `t = t + 1.5m`). A floating annotation rounds an exact scale to that representation.

## Arithmetic

- Addition, subtraction and comparison need identical dimensions. Anything else is a compile error.
- Multiplication and division combine dimensions.
- `^` takes a constant exponent. Exponents may be fractions, and `sqrt` halves the powers, so a noise density is `V/sqrt(Hz)`. Types can say `Time^(1/2)`.
- Dividing by a unit gives the dimensionless count in that unit: `d/m`, `t/1s`.
- Annotations, generic functions, overloads, arrays, records and conversions keep dimensions. Ordinary conversions cannot add or remove one; `x transmute (float64 * Time)` changes it explicitly and keeps the number.

<!-- dewy-example: {"mode":"run","stdout":"3.0V/Hz^(1/2)\n"} -->
```dewy
from units import V, Hz
let noise = 3V/sqrt(1Hz)
printl(noise)
```

<!-- dewy-example: {"mode":"reject","diagnostic":"dimension mismatch: Length and Time"} -->
```dewy
from units import m
let x = 3m + 2s
```

## Display

A quantity prints with a unit chosen from its dimension and magnitude. `string(x)` gives the same text.

<!-- dewy-example: {"mode":"run","stdout":"1500m 3km 300ms 4500J 20m/s 2N*s\n1.5km 1.5m\n1/3m 2500mm 0s\n"} -->
```dewy
from units import m, kg, J
printl"{1500m} {3000m} {300ms} {4500J} {20m/s} {2kg*m/s}"
let d:float64 * Length = 1500m
printl"{d} {d/1000}"
printl"{m/3} {2.5m} {0s}"
```

- Each kind has candidate units: time `ns µs ms s min h`; length `nm µm mm m km`; mass `mg g kg`; SI prefixes `n` to `G` for amperes, moles and the named units `Hz N Pa J W C V Ω`. Temperatures print in `K`, angles in `°`, luminosity in `cd`.
- A float prints in the largest candidate not above its magnitude.
- An exact value prints in the largest candidate that keeps a whole count (`2.5m` is `2500mm`); failing that, in the candidate with the simplest fraction (`m/3` is `1/3m`).
- Zero prints in the kind's own unit (`0s`).
- Other dimensions print in canonical units, using one named unit where that needs fewer factors (`m/s^2`, `N*s`, `V/Hz^(1/2)`).

`fmt` formats plain numbers. To format a quantity, divide by a unit first: `fmt'.1f'(1500m/1km)` is `1.5`.

### `as` a unit

`x as unit` selects the unit a quantity prints in. The unit must be a constant of the same dimension. It changes only the display: comparisons and counts are unaffected. The unit stays through scaling and sums, but not through products of quantities.

<!-- dewy-example: {"mode":"run","stdout":"1500/127inches 90km/hour 400cm\n"} -->
```dewy
from units import m, cm, inches, km
let l = 2m
printl"{30cm as inches} {25m/s as km/hour} {(l as cm)*2}"
```

## Temperatures with an Offset

`°C` and `°F` count from an offset zero. A temperature in one of them is either a *point* (a reading) or a *difference*, and which one is part of its type.

<!-- dewy-example: {"mode":"run","stdout":"27°F 95°F 55/2°C 68\n68°F 36°F 300K\ntrue\n"} -->
```dewy
from units import K, °C, °F
let start = 20°C
let later = start + 15°C     # a literal next to a point is a difference
let rise = later - start     # point - point: a difference
printl"{rise as °F} {later as °F} {mean[start later]} {start/°F}"
printl"{20°C as °F} {(25°C - 5°C) as °F} {300K}"
printl(start <? later)       # comparing with a point makes start a point
```

<!-- dewy-example: {"mode":"reject","diagnostic":"cannot add two temperatures"} -->
```dewy
from units import °C
let a = 20°C
let b = 30°C
printl(a <? b)
printl(a + b)
```

- Computed and input values are points: a reading, a parsed value, `c*°C`, a sum with a point. Subtracting two points gives a difference. Plain kelvin (`20K`) has no offset and stands for either.
- A literal written as an operand next to a point is a difference: `start + 20°C`, `t += 5°C`.
- A binding that holds only temperature literals in one unit takes its kind from all of its uses. A use that needs a difference (`t + rise`, `rise*2`, `-rise`) makes it a difference; a use that needs a point (`rise <? t`, `rise - t`) makes it a point. Uses that allow either (`t - rise`, printing, `as`) decide nothing, and an undecided binding is a point. When `t - rise` is the only deciding use, or the uses disagree, the compiler warns. Write the difference in kelvin or as `25°C - 5°C` to settle it.
- A point moves by a difference; differences add, subtract and scale. Adding two points, comparing a point with a difference, and scaling a point are errors with fix-its. For an average write `mean[t1 t2]`, which is a point.
- Dividing by a temperature unit gives the reading in that unit (`t/°C`). In a compound unit the offset unit counts one degree (`4J/(g*°C)`).
- A plain `float64 * Temperature` annotation holds kelvins and drops the offset.

## Angles and Trigonometry

`sin`, `cos` and `tan` take an angle and reduce it exactly in whole turns. A plain number is rejected. A float angle gives a `float64`; an exact one gives a `float64` rounded to 32 fraction bits. Radians are `x*rad`, where `rad` is a fraction within 1e-31 of 1/2π turn.

<!-- dewy-example: {"mode":"run","stdout":"0.5 1.0\n0.4794\n"} -->
```dewy
from units import °, deg, rad
printl(cos(60°) sin(90deg))
printl(fmt'.4f'(sin(0.5*rad)))
```

In shader code a quantity is its plain canonical number (an angle counts turns).

## Sleeping

`sleep` takes a length of time, `sleep(300ms)`, and waits whole nanoseconds, counting time the machine is suspended. A plain number is rejected. A day, week, month or year is a calendar period, not a length of time (see [Time and Dates](time-and-dates.md#calendar-periods)).

<!-- dewy-example: {"mode":"reject","diagnostic":"a day or week is a calendar period"} -->
```dewy
sleep(1day)
```
