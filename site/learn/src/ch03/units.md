# Units

Dewy includes physical units in the type system. Writing a number next
to a unit multiplies them. `10kg` is not the same type as `10m`, and
adding them is an error.

## A Simple Example

```dewy
mass = 10kg
velocity = 30m/s
energy = 1/2 * mass * velocity^2
```

`energy` is `4500 J`. Group the messy ones with parens. See
[operator precedence](operators.md).

```dewy
7kg * 10(m/s/s)
25(N/m^2) + 15(Pa)
12(kg) + 8(kg)
8(km/h) + 20(m/s)                   # mixed units convert
2kg + 3m                            # error: mismatched dimensions

F = 5kg * 2(m/s^2)                  # 10 N
W = 20N * 10m * cos(45°)            # 141.42 J
V = 2A * 10Ω                        # 20 V
KE = 0.5 * 8kg * (6(m/s))^2         # 144 J
U = 75kg * 9.81(m/s^2) * 5m         # 3678.75 J
P = (2mol * 8.314(J/(mol * K)) * 300K) / 0.01m^3    # 498420 Pa
```

Time works the same way. `Duration<T>` keeps the number you chose. The
unit constants carry an exact scale.

```dewy
pause = 300ms
sleep(10s)
```

## SI Prefixes

SI prefixes apply to SI base and derived units (and a few exceptions
below). Abbreviated prefixes combine only with abbreviated units, and
written-out prefixes only with written-out units. `kilograms` and `kg` are
valid; `kgrams` and `kilog` are not.

| Prefix  | Abbrev. | Scale |
| ------- | ------- | ----- |
| `yotta` | `Y` | 10^24 |
| `zetta` | `Z` | 10^21 |
| `exa` | `E` | 10^18 |
| `peta` | `P` | 10^15 |
| `tera` | `T` | 10^12 |
| `giga` | `G` | 10^9 |
| `mega` | `M` | 10^6 |
| `kilo` | `k` | 10^3 |
| `hecto` | `h` | 10^2 |
| `deca` | `da` | 10^1 |
| `deci` | `d` | 10^−1 |
| `centi` | `c` | 10^−2 |
| `milli` | `m` | 10^−3 |
| `micro` | `μ` / `u` | 10^−6 |
| `nano` | `n` | 10^−9 |
| `pico` | `p` | 10^−12 |
| `femto` | `f` | 10^−15 |
| `atto` | `a` | 10^−18 |
| `zepto` | `z` | 10^−21 |
| `yocto` | `y` | 10^−24 |

Non-SI units that may receive SI prefixes include `psi`, `torr`, `bar`,
`eV`, `cal` (for example `kpsi`, `mTorr`, `keV`, `kcal`).

## Binary Prefixes

These prefixes apply only to units of information (`bit` / `byte`).

| Prefix | Abbrev. | Scale |
| ------ | ------- | ----- |
| `kibi` | `Ki` | 2^10 |
| `mebi` | `Mi` | 2^20 |
| `gibi` | `Gi` | 2^30 |
| `tebi` | `Ti` | 2^40 |
| `pebi` | `Pi` | 2^50 |
| `exbi` | `Ei` | 2^60 |
| `zebi` | `Zi` | 2^70 |
| `yobi` | `Yi` | 2^80 |

## Base Units

Abbreviated units and prefixes are **case sensitive**. Fully written-out
units and prefixes are **case insensitive**.

In SI the mass base is `kg` / `kilograms`, not `g`. `k` / `kilo` is a
convenience so a mass base can appear without a prefix.

The plural of `kelvin` is `kelvin`.

| Quantity | Symbol | Abbrev. units | Full units |
| -------- | ------ | ------------- | ---------- |
| Mass | `[M]` | `g`, `k`, `lbm` | `gram`/`grams`, `kilo`/`kilos`, `pound-mass`/`pounds-mass`, `slug`/`slugs` |
| Length | `[L]` | `m`, `ft`, `yd`, `mi`, `AU` | `meter`/`metre`, `inch`/`inches`, `foot`/`feet`, `yard`/`yards`, `mile`/`miles`, `nautical_mile`, `astronomical_unit`, `light_year`, `parsec` |
| Time | `[T]` | `s` | `second`/`seconds`, `minute`/`minutes`, `hour`/`hours`, `day`/`days`, `week`/`weeks`, `month`/`months`, `year`/`years`, `decade`, `century`, `millennium` |
| Electric current | `[I]` | `A` | `amp`/`ampere` |
| Thermodynamic temperature | `[Θ]` | `K`, `°R`/`°Ra`, `°C`, `°F` | `kelvin`, `rankine`, `celsius`, `fahrenheit` |
| Amount of substance | `[N]` | `mol` | `mole`/`moles` |
| Luminous intensity | `[J]` | `cd` | `candela` |

Exact durations of calendar-style units, sidereal vs solar day and so on,
are not yet determined. A project-wide unit system like MKS vs CGS isn't
either.

## Named Derived Units

| Quantity | Abbrev. units | Full units |
| -------- | ------------- | ---------- |
| Plane angle | `rad`, `°` | `radian`, `degree` |
| Solid angle | `sr` | `steradian` |
| Frequency | `Hz` | `hertz` |
| Force / weight | `N`, `lb`/`lbf` | `newton`, `pound-force` |
| Pressure / stress | `Pa`, `atm`, `bar`, `psi`, `torr`, `mmHg`, `inH2O` | `pascal`, `atmosphere`, `bar`, `pounds_per_square_inch`, `torr` |
| Energy / work / heat | `J`, `cal`, `Cal`, `BTU`, `eV`, `Wh`, `erg` | `joule`, `calorie`, `kilocalorie`, `british_thermal_unit`, `electron_volt`, `watt_hour`, `erg` |
| Power | `W`, `hp` | `watt`, `horsepower` |
| Electric charge | `C` | `coulomb` |
| Voltage | `V` | `volt` |
| Capacitance | `F` | `farad` |
| Resistance | `Ω` | `ohm` |
| Electrical conductance | `S` | `siemens` |
| Magnetic flux | `Wb` | `weber` |
| Magnetic flux density | `T` | `tesla` |
| Inductance | `H` | `henry` |
| Luminous flux | `lm` | `lumen` |
| Illuminance | `lx` | `lux` |
| Radioactivity | `Bq` | `becquerel` |
| Absorbed dose | `Gy` | `gray` |
| Equivalent dose | `Sv` | `sievert` |
| Catalytic activity | `kat` | `katal` |

`Cal` is `kcal` (1000 calories).

## Other Units

| Quantity | Abbrev. units | Full units |
| -------- | ------------- | ---------- |
| Information | `b`/`bit`, `B`/`byte` | `bit`/`bits`, `byte`/`bytes` |

How unit catalogs get imported by domain, `si`, `information`, and so on,
is not yet determined. Same question for clashes like `B` meaning byte vs
bel.
