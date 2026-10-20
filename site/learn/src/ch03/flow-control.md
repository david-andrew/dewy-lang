# Branching and Flow Control

An `if` chooses which block to evaluate. Dewy comparisons use a question mark.

<!-- dewy-example: {"mode": "run", "stdout": "high\n"} -->
```dewy
let score = 42
if score >? 40 { printl"high" } else { printl"low" }
```

Expected output:

```text
high
```

Run the example from a file with `dewy example.dewy`. Its exact output is checked by the website build on the native release target.

> **Design boundary.** The [Branching and Flow Control reference](/reference/control-flow-and-iteration.html) specifies the complete language rules. A passing example covers this program only. See [generated coverage](/status/#ref-control-flow-and-iteration) for related acceptance programs and unmeasured areas.
