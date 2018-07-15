from unit import *

kg = Unit('k', 'g')
g = Unit(None, 'g')
km = Unit('k', 'm')
m = Unit(None, 'm')


km2 = (km*km).unit
m2 = (m*m).unit
kg2 = (kg*kg).unit
g2 = (g*g).unit


val2 = (km2*g).unit
val1 = (kg2 * m).unit


print(val1)
print(val2)

for sp, op, su, ou in zip(val1.prefix, val2.prefix, val1.unit, val2.unit):
    print((sp, op, su, ou))

print(val1 / val2 )

