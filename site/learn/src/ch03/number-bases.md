# Numbers and Bases

Base prefixes change how an integer is written. They do not change the value.

<!-- dewy-example: {"mode": "run", "stdout": "42 42\n"} -->
```dewy
let binary:int64 = 0b101010
let hex:int64 = 0x2a
printl"{binary} {hex}"
```

Expected output:

```text
42 42
```

Run the example from a file with `dewy example.dewy`. Its exact output is checked by the website build on the native release target.

> **Design boundary.** The [Numbers and Bases reference](/reference/literals.html) specifies the complete language rules. A passing example covers this program only. See [generated coverage](/status/#ref-literals) for related acceptance programs and unmeasured areas.
