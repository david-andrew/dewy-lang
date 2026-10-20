# Optional Values and Narrowing

An optional value is a union with `none`. Test its member type before using the contained value.

<!-- dewy-example: {"mode": "run", "stdout": "42\n"} -->
```dewy
find = (present:bool):>int64|none => { if present { return 42 }; return none }
let result = find(true)
if result is? int64 { printl(result) }
```

Expected output:

```text
42
```

Run the example from a file with `dewy example.dewy`. Its exact output is checked by the website build on the native release target.

> **Design boundary.** The [Optional Values and Narrowing reference](/reference/types-and-conversions.html) specifies the complete language rules. A passing example covers this program only. See [generated coverage](/status/#ref-types-and-conversions) for related acceptance programs and unmeasured areas.
