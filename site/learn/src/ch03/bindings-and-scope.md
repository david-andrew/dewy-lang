# Bindings and Scope

A `let` binding holds a value. A nested binding can shadow a name without changing the outer value.

<!-- dewy-example: {"mode": "run", "stdout": "42\n20\n"} -->
```dewy
let score = 20
{ let score = 42; printl(score) }
printl(score)
```

The [reference](/reference/bindings-and-scope.html) has the complete rules.
