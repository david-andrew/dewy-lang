# Expressions, Produced Values, and Blocks

Nearly everything in Dewy produces a value, including `if`, `match` and blocks. A block groups work, and its last expression is its value.

## Blocks give a value

<!-- dewy-example: {"mode": "run", "stdout": "42\n"} -->
```dewy
let answer = { let base = 20; base + 22 }
printl(answer)
```

Statements in a block are separated by newlines or `;`. Names made inside the block, like `base`, end with it. [Bindings and Scope](bindings-and-scope.md) has the rules.

## if and match are expressions

Use them where you would reach for a ternary or a helper variable:

<!-- dewy-example: {"mode": "run", "stdout": "A\nbig\n"} -->
```dewy
let score = 91
let grade = { if score >? 90 "A" else "B" }
printl(grade)
printl(if score >? 50 "big" else "small")
```

## Grouping with parentheses

Parentheses group an expression. They do not start a scope, so a name made inside them stays visible after.

<!-- dewy-example: {"mode": "run", "stdout": "8\n"} -->
```dewy
let n = 3
let v = (n + 1) * 2
printl(v)
```

## A function body is a block

The last expression of a function body is its result. `return` leaves early.

<!-- dewy-example: {"mode": "run", "stdout": "25\n"} -->
```dewy
square_it = (x:int):>int => { let y = x * x; y }
printl(square_it(5))
```

## Assignments and loops give nothing

A declaration, an assignment or a loop produces `void`, which cannot be stored. To collect values from a loop, put it inside brackets: `[loop i in 1..3 i * i]` gives `[1 4 9]`. See [Loops](loops.md). Ending a line with `;` after an expression that does give a value discards it, which is how you call a function for its effect only.

The [reference](/reference/expressions-and-operators.html) has the complete rules.
