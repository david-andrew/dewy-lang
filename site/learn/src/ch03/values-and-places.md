# Values, Copies, and Places

An ordinary assignment gives an independent array value. Updating the copy leaves the original alone.

<!-- dewy-example: {"mode": "run", "stdout": "42\n"} -->
```dewy
let original = [20 22]
let copy = original
copy[0] = 99
printl(original[0]+original[1])
```

Expected output:

```text
42
```

Run the example from a file with `dewy example.dewy`. Its exact output is checked by the website build on the native release target.

> **Design boundary.** The [Values, Copies, and Places reference](/reference/values.html) specifies the complete language rules. A passing example covers this program only. See [generated coverage](/status/#ref-values) for related acceptance programs and unmeasured areas.
