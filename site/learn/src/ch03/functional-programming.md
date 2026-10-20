# Function Values and Composition

A handle can be stored and called. Here a generic identity function is specialized before its handle is selected.

<!-- dewy-example: {"mode": "run", "stdout": "42\n"} -->
```dewy
identity = <T>(value:T):>T => value
let callback = @identity<int64>
printl(callback(42))
```

Expected output:

```text
42
```

Run the example from a file with `dewy example.dewy`. Its exact output is checked by the website build on the native release target.

> **Design boundary.** The [Function Values and Composition reference](/reference/functions-and-calls.html) specifies the complete language rules. A passing example covers this program only. See [generated coverage](/status/#ref-functions-and-calls) for related acceptance programs and unmeasured areas.
