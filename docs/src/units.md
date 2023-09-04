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

## (TODO->rest of units features + examples)

## Full List of Units

(TODO->maybe like solidworks, allow user to set unit system, e.g. meters-kilograms-seconds, centimeters-grams-seconds, etc. See: https://en.wikipedia.org/wiki/MKS_system_of_units https://en.wikipedia.org/wiki/Metre%E2%80%93tonne%E2%80%93second_system_of_units https://en.wikipedia.org/wiki/Foot%E2%80%93pound%E2%80%93second_system https://en.wikipedia.org/wiki/Centimetre%E2%80%93gram%E2%80%93second_system_of_units )

### Base Units
Abbreviations are written inside of brackes `[]`. 

> Note: abbreviated units and prefixes are **case sensitive**, while fully written out units and prefixes are **case insensitive**

#### Mass [M]
`[g]`, `gram`, `grams` 
`[k]`, `kilo`, `kilos`
`[lbm]`, `pound-mass`, `pounds-mass`  
`slug`, `slugs`
(TODO: metric vs us vs etc. tons)

> Note: the base unit is `kg`/`kilograms`, not `g`/`grams`. `k`/`kilo` is provided as a convenience to allow for a mass base unit without a prefix. e.g. `kilokilo` would be equivalent to `1000(kilograms)`. 

#### Length [L]
`[m]`, `meter`, `meters`, `metre`, `metres`

#### Time [T]
`[s]`, `second`, `seconds`
`minute`, `minutes`
`hour`, `hours`
(TODO: exact durations of longer units. e.g. sidereal day vs solar day, etc.)
`day`, `days`
`week`, `weeks`
`month`, `months`
`year`, `years`
`decade`, `decades`
`century`, `centuries`
`millennium`, `millennia`

#### Electric Current [I]
`[A]`, `amp`, `amps`, `ampere`, `amperes`

#### Thermodynamic Temperature [Θ]
`[K]`, `kelvin` 
> Note: the plural of `kelvin` is `kelvin`, not `kelvins`

#### Amount of Substance [N]
`[mol]`, `mole`, `moles`

#### Luminous Intensity [J]
`[cd]`, `candela`, `candelas`

### Named Derived Units

#### Plane Angle
`[rad]`, `radian`, `radians`
`[deg]`, `°`, `degree`, `degrees`

#### Solid Angle
`[sr]`, `steradian`, `steradian`, `steradians`

#### Frequency
`[Hz]`, `hertz`

#### Force / Weight
`[N]`, `newton`, `newtons`
`[lb]`, `[lbf]`, `pound`, `pounds`, `pound-force`, `pounds-force`

#### Pressure / Stress
`[Pa]`, `pascal`, `pascals`

#### Energy / Work / Heat
`[J]`, `joule`, `joules`
`[cal]`, `calorie`, `calories`
`[Cal]` 
`[BTU]`, `british_thermal_unit`, `british_thermal_units`
`[eV]`, `electron_volt`, `electron_volts`
`[Wh]`, `watt_hour`, `watt_hours`
> Note: `Cal` is equivalent to `kcal` or `kilocalorie` (i.e. `1000(calories)`). 

#### Power / Radiant Flux
`[W]`, `watt`, `watts`
`[hp]`, `horsepower`

#### Electric Charge / Quantity of Electricity
`[C]`, `coulomb`, `coulombs`

#### Voltage / Electrical Potential / EMF
`[V]`, `volt`, `volts`

#### Capacitance
`[F]`, `farad`, `farads`

#### Reistance / Impedance / Reactance
`[Ω]`, `ohm`, `ohms`

#### Electrical Conductance
`[S]`, `siemens`

#### Magnetic Flux
`[Wb]`, `weber`, `webers`

#### Magnetic Flux Density
`[T]`, `tesla`, `teslas`

#### Inductance
`[H]`, `henry`, `henries`

#### Relative Temperature
`[°C]`, `celsius`, `degrees_celsius`
`[°F]`, `fahrenheit`, `degrees_fahrenheit`

#### Luminous Flux
`[lm]`, `lumen`, `lumens`

#### Illuminance
`[lx]`, `lux`, `luxes`

#### Radioactivity (Decays per unit time)
`[Bq]`, `becquerel`, `becquerels`

#### Absorbed Dose (of Ionizing Radiation)
`[Gy]`, `gray`, `grays`

#### Equivalent Dose (of Ionising Radiation)
`[Sv]`, `sievert`, `sieverts`

#### catalytic activity
`[kat]`, `katal`, `katals`

(TODO->all other units + weird units. e.g. drops)

### SI Prefixes
> Note: SI prefixes only work for SI base and derived units (and a few exceptions noted below). Also the abbreviated forms of prefixes may only be combined with abbreviated units, and written out prefixes may only be combined with written out units. E.g. `kilograms` and `kg` are valid, but `kgrams` and `kilog` are invalid.

10^24 = `[Y]`, `yotta`  
10^21 = `[Z]`, `zetta`  
10^18 = `[E]`, `exa`   
10^15 = `[P]`, `peta`  
10^12 = `[T]`, `tera`  
10^9 = `[G]`, `giga`  
10^6 = `[M]`, `mega`  
10^3 = `[k]`, `kilo`  
10^2 = `[h]`, `hecto`  
10^1 = `[da]`, `deca`  
10^−1 = `[d]`, `deci`   
10^−2 = `[c]`, `centi`  
10^−3 = `[m]`, `milli`  
10^−6 = `[μ]`, `[u]`, `micro`  
10^−9 = `[n]`, `nano`  
10^−12 = `[p]`, `pico`  
10^−15 = `[f]`, `femto`  
10^−18 = `[a]`, `atto`  
10^−21 = `[z]`, `zepto`  
10^−24 = `[y]`, `yocto`  