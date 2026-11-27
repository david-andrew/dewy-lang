# Control Flow

> [Generated coverage](/status/#ref-control-flow-and-iteration) names related acceptance programs. Every example on this page compiles with the current compiler unless it is marked **Design only**.

This page covers conditionals, `match`, the loop statement and exits. Iterator headers (`loop x in xs`, ranges, combined headers) are in [Ranges and Iteration](ranges-and-iteration.md); generators are in [Generators](generators.md) and concurrent waits in [Concurrency](concurrency.md).

## Conditionals

`if`, `else if` and `else` form one chain. Conditions run from left to right until one holds; only the chosen body runs. A condition must be a `bool`: an optional or a union holding a `bool` is not one.

A chain is an expression. When every path gives a value, the chain gives the union of the branch values:

<!-- dewy-example: {"mode":"run","stdout":"3 items\n"} -->
```dewy
let count = 3
let label = if count =? 0 "empty" else if count =? 1 "one item" else "{count} items"
printl(label)
```

A chain without `else` gives `void`. A body may be a single expression or a `{ }` block; no line break or indentation is required.

A condition's facts hold inside its body, and along later paths where it is known false. `is?` narrows a union or optional binding in the same way; a chain of `is?` tests that names every member of a union is exhaustive and gives a value without `else`:

<!-- dewy-example: {"mode":"run","stdout":"int\nstr\n"} -->
```dewy
kind = (v:int64|string):>string => if v is? int64 "int" else if v is? string "str"
printl(kind(7))
printl(kind("x"))
```

An optional is not a condition:

<!-- dewy-example: {"mode":"reject","diagnostic":"an optional is not true or false"} -->
```dewy
flag = (id:int64):>bool|none => if id >? 0 true else none
if flag(1) { printl("yes") }
```

## `match`

`match scrutinee { arms }` tests a value against arms in order; the first arm that matches runs. An arm is `pattern => body`. The scrutinee runs once. `match` is a member of the flow chain, so `else` may follow it.

| Pattern | Matches | Binds |
|---|---|---|
| `<T>` | a member of type `T` | nothing |
| `name:T` | a member of type `T` | `name`, narrowed to `T` |
| `<42>`, `<"quit">`, `<none>` | that literal | nothing |
| `small:int64<small <? 100>` | an `int64` the refinement holds for | `small`; the bounds are facts in the body |
| `[sign:1 limbs]` | a record with those field values | the named fields |
| `(a <7> c)` | a sequence of that length and elements | the named positions |
| `_` | anything | nothing |

<!-- dewy-example: {"mode":"run","stdout":"a flag\nthe answer\nsmall 7\nlarge 1000\nhi\n"} -->
```dewy
describe = (v:bool|int64|string):>string => match v {
    <bool>                    => "a flag"
    <42>                      => "the answer"
    small:int64<small <? 100> => "small {small}"
    n:int64                   => "large {n}"
    s:string                  => s
}
printl(describe(true))
printl(describe(42))
printl(describe(7))
printl(describe(1000))
printl(describe("hi"))
```

An object pattern names fields; a field given a literal must equal it, and a bare field name binds it. A sequence scrutinee is several values matched at once:

<!-- dewy-example: {"mode":"run","stdout":"-2\n20\n"} -->
```dewy
Big:type = [sign:-1|1 limbs:array<int64>]
size = (b:Big):>int64 => match b {
    [sign:1 limbs]  => limbs.length
    [sign:-1 limbs] => -limbs.length
}
printl(size(Big[-1 [1 2]]))

let x:int64 = 20
let y = "s"
printl(match (x y) (a:int64 <string>) => a)
```

A binding arm narrows the scrutinee too: inside `n:int64 => ...`, a scrutinee variable or field is an `int64`. A bare name other than `_` also matches everything and binds it, with a warning: write `name:T` to bind with a type, or `<T>` to test one.

### Coverage

A chain containing a `match` must be total: the arms cover every member of the scrutinee's type, or the chain ends in `_` or `else`. Coverage is computed on value sets, so guards count: `a:int64<a <? 0>` and `b:int64<b >=? 0>` cover `int64`, and `<true>` with `<false>` covers `bool`. A missing case is an error that names it:

<!-- dewy-example: {"mode":"reject","diagnostic":"this match has no arm for 0"} -->
```dewy
sign = (n:-1|0|1):>string => match n {
    a:int64<a <? 0> => "negative"
    b:int64<b >? 0> => "positive"
}
printl(sign(1))
```

An arm that can match nothing the earlier arms left is an error:

<!-- dewy-example: {"mode":"reject","diagnostic":"this arm is unreachable"} -->
```dewy
f = (v:int64|string):>string => match v {
    _ => "any"
    s:string => s
}
printl(f(1))
```

Value-producing arms combine like conditional branches: the result is the union of the arm types. Arms giving `'A'` and `'B'` give the enumeration `'A' | 'B'`. An enumeration is one word at run time, so comparing and matching it compares words, not text.

## Loops

A loop has one form, `loop condition body`, wherever its line breaks fall. The condition is evaluated before each pass:

- a `bool` expression repeats while it is true (`loop true { ... }` runs until `break` or `return`);
- an iterator clause, `name in source`, binds the next value and stops when the source is exhausted (see [Ranges and Iteration](ranges-and-iteration.md));
- a block condition runs its statements each pass and uses its last value: `loop { n -= 1; n >? 0 } { ... }`.

<!-- dewy-example: {"mode":"run","stdout":"3\ntick 2\ntick 1\n"} -->
```dewy
let n:int64 = 0
loop n <? 3 { n += 1 }
printl(n)
loop { n -= 1; n >? 0 } { printl"tick {n}" }
```

`loop { ... }` alone has a condition but no body, and is an error.

### Fallback arms

An `else` after a loop runs only when the body never ran. After any pass, including one ending in `break` or `continue`, it is skipped. Chains may mix `if`, `loop`, `else if` and `else loop`. A loop's bindings and label belong to that arm and are not visible in its fallback.

<!-- dewy-example: {"mode":"run","stdout":"9\n4\n"} -->
```dewy
head_or = (values:array<int64> fallback:int64):>int64 => {
    loop value in values { return value }
    else { return fallback }
}
printl(head_or([] 9))
printl(head_or([4] 9))
```

### Loop values

A loop expresses its body's values. A collector (`[loop ...]`, `set[loop ...]`) gathers them, and a function without a written result type that ends in a loop gives them:

<!-- dewy-example: {"mode":"run","stdout":"[1 4 9]\n[0 2 4]\n"} -->
```dewy
squares = (k:int) => { loop i in 1..k i^2 }
printl([squares(3)])
printl([loop i in [0..6) if i % 2 =? 0 i])
```

See [Loop Capture](arrays-and-containers.md#loop-capture) for collectors.

## Exits

`break` leaves the nearest loop. `continue` starts its next condition evaluation. `return` leaves the current function, with a value if the function gives one.

A `$name` label before a loop lets nested loops target it with `break $name` and `continue $name`. Labels are unique among the active loops of a function and may be reused after their loop ends. A closure cannot exit its caller's loop.

<!-- dewy-example: {"mode":"run","stdout":"0,0\n1,0\n1,1\n1,2\n"} -->
```dewy
$rows
loop row in [0..3) {
    loop col in [0..3) {
        if col =? 1 and row =? 0 { continue $rows }
        if row =? 2 { break $rows }
        printl"{row},{col}"
    }
}
```

`exit(code)` ends the process with that status. The code is a `uint8`: a constant outside 0–255 is an error, and a computed code must be proven in range. See [`main` and exit codes](errors-and-forwarding.md#main-and-exit-codes) for how errors reaching `main` set the status.

### `never`

`never` is the type of a path that cannot complete. It differs from `void`, which completes without a value. A function declared `:>never` must end every path in `exit(...)`, a panic or an endless loop. A call to one contributes no type, and code after `if v is? none fail(...)` sees the narrowed value:

<!-- dewy-example: {"mode":"run","stdout":"7\nempty\n","exit":3} -->
```dewy
fail = (msg:string):>never => {
    printl(msg)
    exit(3)
}
first = (xs:array<int64>):>int64 => {
    if xs.length =? 0 fail("empty")
    return xs[0]
}
printl(first([7 8]))
first([])
```

<!-- dewy-example: {"mode":"reject","diagnostic":"a function giving `never` must not finish"} -->
```dewy
bad = ():>never => { printl("x") }
bad()
```

Postfix `or_throw` returns an exception value from the current function and continues with the success value; `?? return x`, `?? break` and `?? continue` exit on a missing value. Both are described in [Errors and Forwarding](errors-and-forwarding.md).
