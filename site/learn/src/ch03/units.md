# Physical Quantities and Units

A number can carry a unit. The compiler tracks the dimension (length, time, mass and so on) as part of the type, so adding metres to seconds is an error and mixing up units is caught before the program runs. At run time a quantity is just its number.

## Writing a quantity

Write the unit right against the number: `20m`, `300ms`, `9.81m/s^2`. `9.81 m` with a space is two separate expressions.

The time units `s`, `ms`, `us`, `ns`, `minute` and `hour` are in the prelude, so they need no import. Every other unit comes from the library module `units`.

<!-- dewy-example: {"mode": "run", "stdout": "42\n"} -->
```dewy
from units import m
let distance = 42m
printl(distance/m)
```

Dividing a quantity by a unit gives a plain number: how many of that unit it holds. That is how you get a quantity back out as a number for formatting or for a calculation that has no units.

## Arithmetic keeps dimensions

Multiplying and dividing combine dimensions. Adding, subtracting and comparing need the same dimension.

<!-- dewy-example: {"mode": "run", "stdout": "6\n"} -->
```dewy
from units import m
let speed = 20m/s
let elapsed = 300ms
let travelled = speed * elapsed
printl(travelled/m)
```

Units of the same kind convert exactly. `3km =? 3000m` is true because every unit is an exact multiple of a base unit:

<!-- dewy-example: {"mode": "run", "stdout": "true true true true\n"} -->
```dewy
from units import m, km, deg, turn, L, mL
printl(3km =? 3000m  300ms =? 3s/10  90deg =? turn/4  1000mL =? 1L)
```

## Dimension errors

Mixing dimensions is a compile error that names both:

<!-- dewy-example: {"mode": "reject", "diagnostic": "dimension mismatch: Length and Time"} -->
```dewy
from units import m
let x = 3m + 2s
```

## Display

A quantity prints in a sensible unit for its size, with no work on your part. `1500m` prints as it is and `3000m` as `3km`:

<!-- dewy-example: {"mode": "run", "stdout": "1500m 3km 300ms 4500J 20m/s\n1/3m 2500mm 0s\n"} -->
```dewy
from units import m, J
printl"{1500m} {3000m} {300ms} {4500J} {20m/s}"
printl"{m/3} {2.5m} {0s}"
```

Whole counts stay whole where they can (`2.5m` shows as `2500mm`), and a value that is not a whole number of any unit shows as a fraction.

### Choosing the unit with `as`

To print in a particular unit, convert with `as`. It changes only how the value prints. Comparisons and arithmetic see the same quantity.

<!-- dewy-example: {"mode": "run", "stdout": "1500/127inches 90km/hour 400cm\n"} -->
```dewy
from units import m, cm, inches, km
let l = 2m
printl"{30cm as inches} {25m/s as km/hour} {(l as cm)*2}"
```

To format the number inside a quantity, divide by a unit first: `fmt'.1f'(1500m/1km)` gives `1.5`.

## Temperature: points and differences

`°C` and `°F` start counting from an offset zero, so 20°C plus 20°C is not 40°C of anything meaningful. The compiler separates a temperature *point* (a reading) from a *difference* (a change), and tells you when you mix them badly.

<!-- dewy-example: {"mode": "run", "stdout": "27°F 95°F 55/2°C 68\n"} -->
```dewy
from units import °C, °F
let start = 20°C
let later = start + 15°C     # a point moved by a difference
let rise = later - start     # point minus point: a difference
printl"{rise as °F} {later as °F} {mean[start later]} {start/°F}"
```

Two points do not add, so for an average use `mean`, which gives a point back. Adding two points is an error:

<!-- dewy-example: {"mode": "reject", "diagnostic": "cannot add two temperatures"} -->
```dewy
from units import °C
let a = 20°C
let b = 30°C
printl(a <? b)
printl(a + b)
```

## Angles and time

`sin`, `cos` and `tan` take an angle, so `cos(60°)` works and a bare number is rejected. Radians are written `x*rad`. In the same way `sleep(300ms)` takes a time, never a bare number.

<!-- dewy-example: {"mode": "run", "stdout": "0.5 1.0\n"} -->
```dewy
from units import °, deg
printl(cos(60°) sin(90deg))
```

The [reference](/reference/physical-quantities.html) has the complete rules, including the unit list and every display rule.
