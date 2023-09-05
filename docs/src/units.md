# Units

Dewy was designed from day 1 to include physical units such as kilogram, meter, second. 

## A Simple Example

Using units is quite straightforward, as they are just another expression. Juxtaposing a unit with a number will multiply the number by the unit, and you can use this to build up more complex expressions.

```dewy
mass = 10kg
velocity = 30m/s
energy = 1/2 * mass * velocity^2
```

The `energy` variable now contains a value of `9000 joules`. For more complex unit expressions, sometimes it is necessary to use parentheses to group terms together. In general it is good style to do so, except for the simplest unit expressions. See [Operator Precedence](operators.md). 

Here are several more examples of unit expressions:

```dewy
7kg * 10(m/s/s)
25(N/m^2) + 15(Pa)
12(kg) + 8(kg)
3(m) * 5(s)
25(J) - 15(J)
9(N) * 6(m)
1500(W) / 10(A)
5(A) * 2(Ω)
8(m*s^-1) / 2(s)
40(N*m) * 10(rad)
200(Pa) * 3(m^2)
1000(m^3) * 2(kg/m^3)
20(J/s) * 4(s)
8(km/h) + 20(m/s)
6(N) / 2(m^2)
18(L) * 0.001(m^3/L)
1000(kg) * 9.8(m/s^2)
12(C) * 1.6 x 10^-19(C)
0.5(kg) * (10(m/s))^2
1200(W) / 240(V)
6000(s) / 3600(s/h)
7.5(mol) * 6.022e23(particles/mol)
15(kg * m^2 * s^-1 * A^-2 * K^2 * mol^-1 * cd^3) + 10(kg * m * s^-2 * A^-1 * K * mol^-2 * cd^2)

F = 5kg * 2(m/s^2) // 10 N
W = 20N * 10m * cos(45°) // 141.42 J
V = 2A * 10Ω // 20 V
P = 12V * 5A // 60 W
KE = 0.5 * 8kg * (6(m/s))^2 // 144 J
U = 75kg * 9.81(m/s^2) * 5m // 3678.75 J
F = 200(N/m) * 0.05m // 10 N
Q = 385(W/(m * K)) * 1m^2 * (100°C - 25°C) * 3600s / 0.01m // 990000 J
P = (2mol * 8.314(J/(mol * K)) * 300K) / 0.01m^3 // 498420 Pa
ρ = 50kg / 0.1m^3 // 500 kg/m^3
```

## SI Prefixes
> Note: SI prefixes only work for SI base and derived units (and a few exceptions noted below). Also the abbreviated forms of prefixes may only be combined with abbreviated units, and written out prefixes may only be combined with written out units. E.g. `kilograms` and `kg` are valid, but `kgrams` and `kilog` are invalid.

| Prefix  | Abbrev. | Scale |
| ------- | ------- | ----- |
| `yotta` |   `Y`   | 10^24 |
| `zetta` |   `Z`   | 10^21 |
| `exa`   |   `E`   | 10^18 |
| `peta`  |   `P`   | 10^15 |
| `tera`  |   `T`   | 10^12 |
| `giga`  |   `G`   | 10^9  |
| `mega`  |   `M`   | 10^6  |
| `kilo`  |   `k`   | 10^3  |
| `hecto` |   `h`   | 10^2  |
| `deca`  |   `da`  | 10^1  |
| `deci`  |   `d`   | 10^−1 |
| `centi` |   `c`   | 10^−2 |
| `milli` |   `m`   | 10^−3 |
| `micro` |   `μ`/`u` | 10^−6 |
| `nano`  |   `n`   | 10^−9 |
| `pico`  |   `p`   | 10^−12 |
| `femto` |   `f`   | 10^−15 |
| `atto`  |   `a`   | 10^−18 |
| `zepto` |   `z`   | 10^−21 |
| `yocto` |   `y`   | 10^−24 |

Non-SI units that may receive SI prefixes:
- `psi` (e.g. `kpsi` = `1000(psi)`)
- `torr` (e.g. `mTorr` = `0.001(torr)`)
- `bar` (e.g. `mbar` = `0.001(bar)`)
- `eV` (e.g. `keV` = `1000(eV)`)
- `cal` (e.g. `kcal` = `1000(cal)`)
- (TODO: probably more)


## Binary Prefixes
> Note: These prefixes are exclusively for use with units of information (e.g. `bit`/`byte`)

| Prefix  | Abbrev. | Scale |
| ------- | ------- | ----- |
| `kibi`  |   `Ki`  | 2^10  |
| `mebi`  |   `Mi`  | 2^20  |
| `gibi`  |   `Gi`  | 2^30  |
| `tebi`  |   `Ti`  | 2^40  |
| `pebi`  |   `Pi`  | 2^50  |
| `exbi`  |   `Ei`  | 2^60  |
| `zebi`  |   `Zi`  | 2^70  |
| `yobi`  |   `Yi`  | 2^80  |


## Full List of Units

(TODO->maybe like solidworks, allow user to set unit system, e.g. meters-kilograms-seconds, centimeters-grams-seconds, etc. See: https://en.wikipedia.org/wiki/MKS_system_of_units https://en.wikipedia.org/wiki/Metre%E2%80%93tonne%E2%80%93second_system_of_units https://en.wikipedia.org/wiki/Foot%E2%80%93pound%E2%80%93second_system https://en.wikipedia.org/wiki/Centimetre%E2%80%93gram%E2%80%93second_system_of_units )

## Base Units

> Note: abbreviated units and prefixes are **case sensitive**, while fully written out units and prefixes are **case insensitive**

| Quantity | Symbol | Abbrev. Units | Full Units |
| -------- | ------ | ------------- | ---------- |
| Mass* | `[M]` | `g`<br>`k`<br>`lbm`<br>- | `gram`/`grams`<br>`kilo`/`kilos`<br>`pound-mass`/`pounds-mass`<br>`slug`/`slugs` |
| Length | `[L]` | `m`<br>-<br>`ft`<br>`yd`<br>`mi`<br>-<br>`AU`<br>-<br>- | `meter`/`meters`/`metre`/`metres`<br>`inch`/`inches`<br>`foot`/`feet`<br>`yard`/`yards`<br>`mile`/`miles`<br>`nautical_mile`/`nautical_miles`<br>`astronomical_unit`/`astronomical_units`<br>`light_year`/`light_years`<br>`parsec`/`parsecs` |
| Time | `[T]` | `s`<br>-<br>-<br>-<br>-<br>-<br>-<br>-<br>-<br>- | `second`/`seconds`<br>`minute`/`minutes`<br>`hour`/`hours`<br>`day`/`days`<br>`week`/`weeks`<br>`month`/`months`<br>`year`/`years`<br>`decade`/`decades`<br>`century`/`centuries`<br>`millennium`/`millennia` |
| Electric Current | `[I]` | `A` | `amp`/`amps`/`ampere`/`amperes` |
| Thermodynamic Temperature | `[Θ]` | `K`<br>`°R`/`°Ra`<br>`°C`<br>`°F` | `kelvin`<br>`rankine`/`degrees_rankine`<br>`celsius`/`degrees_celsius`<br>`fahrenheit`/`degrees_fahrenheit` |
| Amount of Substance | `[N]` | `mol` | `mole`/`moles` |
| Luminous Intensity | `[J]` | `cd` | `candela`/`candelas` |


(TODO: metric vs us vs etc. tons)

> Note: in SI, the base unit for mass is `kg`/`kilograms`, not `g`/`grams`. `k`/`kilo` is provided as a convenience to allow for a mass base unit without a prefix. e.g. `kilokilo` would be equivalent to `1000(kilograms)`. 

(TODO: exact durations of longer units. e.g. sidereal day vs solar day, etc.)

> Note: the plural of `kelvin` is `kelvin`, not `kelvins`

## Named Derived Units

| Quantity  | Abbrev. Units | Full Units |
| --------  | ------------- | ---------- |
| Plane Angle | `rad`<br>`°` | `radian`/`radians`<br>`degree`/`degrees` |
| Solid Angle | `sr` | `steradian`/`steradians` |
| Frequency | `Hz` | `hertz` |
| Force / Weight | `N`<br>`lb`/`lbf` | `newton`/`newtons`<br>`pound`/`pounds`/`pound-force`/`pounds-force` |
| Pressure / Stress | `Pa`<br>`atm`<br>`bar`<br>`psi`<br>`torr`<br>`mmHg`<br>`inH2O` | `pascal`/`pascals`<br>`atmosphere`/`atmospheres`<br>`bar`<br>`pounds_per_square_inch`<br>`torr`<br>`millimeters_of_mercury`<br>`inches_of_water` |
| Energy / Work / Heat | `J`<br>`cal`<br>`Cal`*<br>`BTU`<br>`eV`<br>`Wh`<br>`erg` | `joule`/`joules`<br>`calorie`/`calories`<br>`kilocalorie`/`kilocalories`<br>`british_thermal_unit`/`british_thermal_units`<br>`electron_volt`/`electron_volts`<br>`watt_hour`/`watt_hours`<br>`erg`/`ergs` |
| Power / Radiant Flux | `W`<br>`hp` | `watt`/`watts`<br>`horsepower` |
| Electric Charge / Quantity of Electricity | `C` | `coulomb`/`coulombs` |
| Voltage / Electrical Potential / EMF | `V` | `volt`/`volts` |
| Capacitance | `F` | `farad`/`farads` |
| Reistance / Impedance / Reactance | `Ω` | `ohm`/`ohms` |
| Electrical Conductance | `S` | `siemens` |
| Magnetic Flux | `Wb` | `weber`/`webers` |
| Magnetic Flux Density | `T` | `tesla`/`teslas` |
| Inductance | `H` | `henry`/`henries` |
| Luminous Flux | `lm` | `lumen`/`lumens` |
| Illuminance | `lx` | `lux`/`luxes` |
| Radioactivity (Decays per unit time) | `Bq` | `becquerel`/`becquerels` |
| Absorbed Dose (of Ionizing Radiation) | `Gy` | `gray`/`grays` |
| Equivalent Dose (of Ionising Radiation) | `Sv` | `sievert`/`sieverts` |
| Catalytic Activity | `kat` | `katal`/`katals` |

> Note: `Cal` is equivalent to `kcal` or `kilocalorie` (i.e. `1000(calories)`). 

## Weird Units

(TODO->all other units + weird units. e.g. drops)

## Other Units

| Quantity | Abbrev. Units | Full Units |
| -------- | ------------- | ---------- |
| Information | `b`/`bit`<br>`B`/`byte` | `bit`/`bits`<br>`byte`/`bytes` |

(TODO: where do decibels go? `B` is already taken by `byte`... perhaps the user can select what units get imported by importing units from different domains, e.g. `import units from si` or `import units from information`) 