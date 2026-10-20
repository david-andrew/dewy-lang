# Loops and Multiple Iterators

A finite range supplies loop values. Keep a running total in a binding.

<!-- dewy-example: {"mode": "run", "stdout": "15\n"} -->
```dewy
let total:int64 = 0
loop value in 1..5 { total += value }
printl(total)
```

Expected output:

```text
15
```

Run the example from a file with `dewy example.dewy`. Its exact output is checked by the website build on the native release target.

> **Design boundary.** The [Loops and Multiple Iterators reference](/reference/ranges-and-iteration.html) specifies the complete language rules. A passing example covers this program only. See [generated coverage](/status/#ref-ranges-and-iteration) for related acceptance programs and unmeasured areas.
