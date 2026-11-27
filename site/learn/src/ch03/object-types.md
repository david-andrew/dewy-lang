# Structural Objects

A record type names fields and can give defaults. Field selection uses a dot.

<!-- dewy-example: {"mode": "run", "stdout": "42\n"} -->
```dewy
Point:type = [x:int64 y:int64=22]
let point:Point = [x=20]
printl(point.x+point.y)
```

The [reference](/reference/objects.html) has the complete rules.
