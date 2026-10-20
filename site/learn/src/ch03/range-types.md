# Ranges

The two-dot range includes both ends. This loop visits three values.

<!-- dewy-example: {"mode": "run", "stdout": "1\n2\n3\n"} -->
```dewy
loop value in 1..3 { printl(value) }
```

Expected output:

```text
1
2
3
```

Run the example from a file with `dewy example.dewy`. Its exact output is checked by the website build on the native release target.

> **Design boundary.** The [Ranges reference](/reference/ranges-and-iteration.html) specifies the complete language rules. A passing example covers this program only. See [generated coverage](/status/#ref-ranges-and-iteration) for related acceptance programs and unmeasured areas.
