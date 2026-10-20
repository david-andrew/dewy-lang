# Bindings and Scope

A `let` binding holds a value. A nested binding can shadow a name without changing the outer value.

<!-- dewy-example: {"mode": "run", "stdout": "42\n20\n"} -->
```dewy
let score = 20
{ let score = 42; printl(score) }
printl(score)
```

Expected output:

```text
42
20
```

Run the example from a file with `dewy example.dewy`. Its exact output is checked by the website build on the native release target.

> **Design boundary.** The [Bindings and Scope reference](/reference/bindings-and-scope.html) specifies the complete language rules. A passing example covers this program only. See [generated coverage](/status/#ref-bindings-and-scope) for related acceptance programs and unmeasured areas.
