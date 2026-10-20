# Types and Numbers

Use explicit widths when a program needs machine integer arithmetic. Type annotations follow a colon.

<!-- dewy-example: {"mode": "run", "stdout": "42 true\n"} -->
```dewy
let count:int64 = 40
let ready:bool = true
printl"{count+2} {ready}"
```

Expected output:

```text
42 true
```

Run the example from a file with `dewy example.dewy`. Its exact output is checked by the website build on the native release target.

> **Design boundary.** The [Types and Numbers reference](/reference/numeric-types.html) specifies the complete language rules. A passing example covers this program only. See [generated coverage](/status/#ref-numeric-types) for related acceptance programs and unmeasured areas.
