# Operators

Use `=?` for equality and `//` for integer division. Group an expression explicitly when that makes its intent clearer.

<!-- dewy-example: {"mode": "run", "stdout": "true\n"} -->
```dewy
let answer:int64 = (80+4)//2
printl(answer =? 42)
```

The [reference](/reference/operators-and-precedence.html) has the complete rules.
