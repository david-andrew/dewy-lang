# Effects

Keep a computation in a function so its inputs and outputs are clear. The reference specifies the wider effect-contract design.

<!-- dewy-example: {"mode": "run", "stdout": "42\n"} -->
```dewy
sum = (left:int64 right:int64):>int64 => left+right
printl(sum(20 22))
```

Expected output:

```text
42
```

Run the example from a file with `dewy example.dewy`. Its exact output is checked by the website build on the native release target.

> **Design boundary.** The [Effects reference](/reference/refinements-and-effects.html) specifies the complete language rules. A passing example covers this program only. See [generated coverage](/status/#ref-refinements-and-effects) for related acceptance programs and unmeasured areas.

The example above does not measure general refinement proofs, effect inference, or a no-allocation guarantee. Those remain separate design contracts.
