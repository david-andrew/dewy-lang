# Expressions, Produced Values, and Blocks

A block groups work. Use its last expression as a result; parentheses group an expression.

<!-- dewy-example: {"mode": "run", "stdout": "42\n"} -->
```dewy
let answer = { let base = 20; base + 22 }
printl(answer)
```

Expected output:

```text
42
```

Run the example from a file with `dewy example.dewy`. Its exact output is checked by the website build on the native release target.

> **Design boundary.** The [Expressions, Produced Values, and Blocks reference](/reference/expressions-and-operators.html) specifies the complete language rules. A passing example covers this program only. See [generated coverage](/status/#ref-expressions-and-operators) for related acceptance programs and unmeasured areas.
