# Structural Objects

A record type names fields and can give defaults. Field selection uses a dot.

<!-- dewy-example: {"mode": "run", "stdout": "42\n"} -->
```dewy
Point:type = [x:int64 y:int64=22]
let point:Point = [x=20]
printl(point.x+point.y)
```

Expected output:

```text
42
```

Run the example from a file with `dewy example.dewy`. Its exact output is checked by the website build on the native release target.

> **Design boundary.** The [Structural Objects reference](/reference/objects.html) specifies the complete language rules. A passing example covers this program only. See [generated coverage](/status/#ref-objects) for related acceptance programs and unmeasured areas.
