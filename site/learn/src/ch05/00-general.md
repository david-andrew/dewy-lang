# A Few Ideas That Organize Dewy

Types describe values. Ordinary value boundaries preserve independence; `@` makes access to a place explicit. Start with a small value-copy example:

<!-- dewy-example: {"mode": "run", "stdout": "42\n"} -->
```dewy
let source = [42]
let copy = source
copy[0] = 0
printl(source[0])
```

Read [values and places](../ch03/values-and-places.md), then [functions](../ch03/function-types.md). Design guarantees extend beyond this example; see [coverage](/status/).
