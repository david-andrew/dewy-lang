# Values, Copies, and Places

In Dewy an assignment gives an independent value. Arrays, objects and strings all behave this way, so two names never secretly share something that one of them can change.

## Assignment copies

<!-- dewy-example: {"mode": "run", "stdout": "[20 22]\n[99 22]\n"} -->
```dewy
let original = [20 22]
let copy = original
copy[0] = 99
printl(original)
printl(copy)
```

The compiler is free to avoid a physical copy when nobody can tell the difference, so this costs nothing like a deep copy in Python. It is the same for fields nested inside an object:

<!-- dewy-example: {"mode": "run", "stdout": "1\n50\n"} -->
```dewy
let rec = [pos=[x=1 y=2]]
let rec2 = rec
rec2.pos.x = 50
printl(rec.pos.x)
printl(rec2.pos.x)
```

The compiler warns when you change a copy you never read afterwards, because that is nearly always a mistake: you meant to change the original.

## Changing something in place: `@`

To let a function change its caller's value, mark both sides with `@`. The parameter says it takes a place, and the caller says which place:

<!-- dewy-example: {"mode": "run", "stdout": "[2 2 3]\n"} -->
```dewy
bump = (@xs:array<int64 length=3>):>void => { xs[0] += 1 }
let nums:array<int64 length=3> = [1 2 3]
bump(@nums)
printl(nums)
```

Without the `@` at the call the function would get an ordinary value, and passing `@nums` to a parameter that does not ask for a place is an error. So you can see at every call which arguments may change.

Two `@` arguments in one call must be different places, and the compiler has to be able to tell they are.

## Making a copy on purpose

Assignment is already independent, so you rarely need an explicit copy. `.copy` exists for the case where you want it written down, because it shows a copy you intend to pay for:

<!-- dewy-example: {"mode": "run", "stdout": "[1 2 3]\n[7 2 3]\n"} -->
```dewy
let a = [1 2 3]
let b = a.copy
b[0] = 7
printl(a)
printl(b)
```

The [reference](/reference/values.html) has the complete rules.
