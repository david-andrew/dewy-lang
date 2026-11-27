# Branching and Flow Control

An `if` chooses which block to evaluate. Dewy comparisons use a question mark.

<!-- dewy-example: {"mode": "run", "stdout": "high\n"} -->
```dewy
let score = 42
if score >? 40 { printl"high" } else { printl"low" }
```

The [reference](/reference/control-flow-and-iteration.html) has the complete rules.
