# Expressions, Produced Values, and Blocks

A block groups work. Use its last expression as a result; parentheses group an expression.

<!-- dewy-example: {"mode": "run", "stdout": "42\n"} -->
```dewy
let answer = { let base = 20; base + 22 }
printl(answer)
```

The [reference](/reference/expressions-and-operators.html) has the complete rules.
