# Structural Objects

An object groups named fields. You write one with brackets and `name=value`, and read a field with a dot. No class is needed.

<!-- dewy-example: {"mode": "run", "stdout": "[x=1 y=2]\n1\n"} -->
```dewy
let q = [x=1 y=2]
printl(q)
printl(q.x)
```

## Naming a shape

A record type names the fields, gives each a type, and can give defaults. A value with that type can leave defaulted fields out:

<!-- dewy-example: {"mode": "run", "stdout": "42\n"} -->
```dewy
Point:type = [x:int64 y:int64=22]
let point:Point = [x=20]
printl(point.x+point.y)
```

You can build a value through the type too, by name or by position:

<!-- dewy-example: {"mode": "run", "stdout": "[x=1 y=2]\n[x=3 y=4]\n"} -->
```dewy
Point:type = [x:int64 y:int64=22]
printl(Point[x=1 y=2])
printl(Point(3 4))
```

## Changing fields

Assign to a field to change it. An object is a value, so assigning one to a new name copies it. The two then change independently, as [Values, Copies, and Places](values-and-places.md) explains.

<!-- dewy-example: {"mode": "run", "stdout": "[x=9 y=6]\n"} -->
```dewy
Point:type = [x:int64 y:int64=22]
let r:Point = [x=5 y=6]
r.x = 9
printl(r)
```

## Spread and unpack

`...` spreads an object's fields into a new one, and later fields override earlier ones. A list of names on the left of `=` pulls fields out by name:

<!-- dewy-example: {"mode": "run", "stdout": "[x=100 y=6]\n3\n"} -->
```dewy
let base = [x=5 y=6]
printl([base... x=100])
let [x y] = [x=1 y=2]
printl(x + y)
```

The [reference](/reference/objects.html) has the complete rules.
