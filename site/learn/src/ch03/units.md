# Physical Quantities and Units

Import units from the library. Dividing a quantity by its unit gives a dimensionless value.

<!-- dewy-example: {"mode": "run", "stdout": "42\n"} -->
```dewy
from units import m
let distance = 42m
printl(distance/m)
```

Expected output:

```text
42
```

Run the example from a file with `dewy example.dewy`. Its exact output is checked by the website build on the native release target.

> **Design boundary.** The [Physical Quantities and Units reference](/reference/physical-quantities.html) specifies the complete language rules. A passing example covers this program only. See [generated coverage](/status/#ref-physical-quantities) for related acceptance programs and unmeasured areas.
