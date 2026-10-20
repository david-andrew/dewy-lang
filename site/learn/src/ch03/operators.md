# Operators

Use `=?` for equality and `//` for integer division. Group an expression explicitly when that makes its intent clearer.

<!-- dewy-example: {"mode": "run", "stdout": "true\n"} -->
```dewy
let answer:int64 = (80+4)//2
printl(answer =? 42)
```

Expected output:

```text
true
```

Run the example from a file with `dewy example.dewy`. Its exact output is checked by the website build on the native release target.

> **Design boundary.** The [Operators reference](/reference/operators-and-precedence.html) specifies the complete language rules. A passing example covers this program only. See [generated coverage](/status/#ref-operators-and-precedence) for related acceptance programs and unmeasured areas.
