# Function Values and Composition

A handle can be stored and called. Here a generic identity function is specialized before its handle is selected.

<!-- dewy-example: {"mode": "run", "stdout": "42\n"} -->
```dewy
identity = <T>(value:T):>T => value
let callback = @identity<int64>
printl(callback(42))
```

The [reference](/reference/functions-and-calls.html) has the complete rules.
