# Containers

Arrays store values of a common type. A comprehension builds a new array from a loop.

<!-- dewy-example: {"mode": "run", "stdout": "42\n"} -->
```dewy
let values = [20 21]
let doubled = [loop value in values value*2]
printl(doubled[1])
```

Expected output:

```text
42
```

Run the example from a file with `dewy example.dewy`. Its exact output is checked by the website build on the native release target.

> **Design boundary.** The [Containers reference](/reference/arrays-and-containers.html) specifies the complete language rules. A passing example covers this program only. See [generated coverage](/status/#ref-arrays-and-containers) for related acceptance programs and unmeasured areas.
