# Refinements

Start with an explicit runtime assertion when a condition must be checked during execution.

<!-- dewy-example: {"mode": "run", "stdout": "42\n"} -->
```dewy
let count:int64 = 42
$runtime_assert count >? 0
printl(count)
```

Expected output:

```text
42
```

Run the example from a file with `dewy example.dewy`. Its exact output is checked by the website build on the native release target.

> **Design boundary.** The [Refinements reference](/reference/refinements-and-effects.html) specifies the complete language rules. A passing example covers this program only. See [generated coverage](/status/#ref-refinements-and-effects) for related acceptance programs and unmeasured areas.

The example above does not measure general refinement proofs, effect inference, or a no-allocation guarantee. Those remain separate design contracts.
