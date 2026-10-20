# Functions and Calls

Define a function with `=>`. Parameters are separated by whitespace. `@name` selects a function handle.

<!-- dewy-example: {"mode": "run", "stdout": "42\n"} -->
```dewy
double = (value:int64):>int64 => value*2
let callback = @double
printl(callback(21))
```

Expected output:

```text
42
```

Run the example from a file with `dewy example.dewy`. Its exact output is checked by the website build on the native release target.

> **Design boundary.** The [Functions and Calls reference](/reference/functions-and-calls.html) specifies the complete language rules. A passing example covers this program only. See [generated coverage](/status/#ref-functions-and-calls) for related acceptance programs and unmeasured areas.
