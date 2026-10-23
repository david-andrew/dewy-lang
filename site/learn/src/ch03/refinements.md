# Refinements

A refinement is a condition a type carries. The compiler proves it from literals and control flow, and rejects a call that provably breaks it. A condition written as a single comparison uses a partial operator.

<!-- dewy-example: {"mode": "run", "stdout": "7\n42\n"} -->
```dewy
span = (a:int64 b:int64<(>=? a)>):>int64 => b - a
share = (total:int64 n:int64<(>? 0)>):>int64 => total // n
printl(span(3 10))
printl(share(84 2))
```

Passing a value that provably breaks the condition is a compile error:

<!-- dewy-example: {"mode": "reject", "diagnostic": "argument 'n' expects"} -->
```dewy
share = (total:int64 n:int64<(>? 0)>):>int64 => total // n
printl(share(84 0))
```

When a condition can't be proven, `$runtime_assert` states it explicitly:

<!-- dewy-example: {"mode": "run", "stdout": "42\n"} -->
```dewy
let count:int64 = 42
$runtime_assert count >? 0
printl(count)
```

Expected output of the first example:

```text
7
42
```

Run the example from a file with `dewy example.dewy`. Its exact output is checked by the website build on the native release target.

> **Design boundary.** The [Refinements reference](/reference/refinements-and-effects.html) specifies the complete language rules. A passing example covers this program only. See [generated coverage](/status/#ref-refinements-and-effects) for related acceptance programs and unmeasured areas.

These examples do not measure every refinement proof, effect inference, or a no-allocation guarantee. Those remain separate design contracts.
