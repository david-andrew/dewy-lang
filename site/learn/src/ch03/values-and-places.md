# Values, Copies, and Places

An ordinary assignment gives an independent array value. Updating the copy leaves the original alone.

<!-- dewy-example: {"mode": "run", "stdout": "42\n"} -->
```dewy
let original = [20 22]
let copy = original
copy[0] = 99
printl(original[0]+original[1])
```

The [reference](/reference/values.html) has the complete rules.
