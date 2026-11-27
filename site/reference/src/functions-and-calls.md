# Functions and Calls

> [Generated coverage](/status/#ref-functions-and-calls) names related acceptance programs. Every example on this page compiles with the current compiler unless it is marked **Design only**.

## Function Literals

A function literal is a parameter list, an optional result type after `:>`, `=>`, and a body expression. The body's final expression is the result; `return` exits early. Parameter and result types may be omitted and inferred. `:>void` declares a function with no result. One bare parameter may omit the parentheses: `x => x + 1`. The name is always the parameter, even when a type has that spelling.

<!-- dewy-example: {"mode":"run","stdout":"42\n[2 4 6]\n"} -->
```dewy
twice = (x) => x + x
add = (a:int b:int=2):>int => a + b
main = () => {
    printl(add(twice(20)))
    printl([1 2 3].map(x => x * 2))
}
```

A function declared `:>never` never returns: every path ends in `exit(…)`, a panic or an endless loop, and a call to it ends its branch like `exit` does.

<!-- dewy-example: {"mode":"run","stdout":"bye\n","exit":3} -->
```dewy
fail = (msg:string):>never => {
    printl(msg)
    exit(3)
}
main = () => fail("bye")
```

How deep calls can nest depends on the target: the main thread and each task have an 8 MB stack, and each `parallel` worker 7 MB. An overflow ends the program with `panic: stack overflow` and exit code 101.

## Calls

Arguments are separated by whitespace and the parentheses touch the callee: `add(1 2)`. A single delimited argument may follow a function directly: `total[1 2 3]` passes the array, and `printl"hi"` passes the string.

A bare function name calls the function. A function whose parameters all have defaults is called by its name alone: `seven` is `seven()`. A function called for its effect keeps `()`, as `hello()`. Naming a function that needs arguments without calling it is an error; `@name` is the function itself (see [Function Handles](#function-handles)).

<!-- dewy-example: {"mode":"run","stdout":"7\nhello\n"} -->
```dewy
seven = (x:int=7) => x
hello = ():>void => printl"hello"
main = () => {
    printl(seven)
    hello()
}
```

<!-- dewy-example: {"mode":"reject","diagnostic":"'add' needs arguments: call it, `add(...)`, or write `@add`"} -->
```dewy
add = (a:int b:int) => a + b
printl(add)
```

## Argument Binding

Each argument binds one parameter that is still unset, left to right:

- a positional argument binds the first parameter still available by position;
- a named argument (`name=value`) binds the parameter with that name;
- each parameter left unset then takes its default, evaluated for this call;
- a required parameter still unset is an error.

Defaults keep their positions, and are evaluated anew for every call that omits them, so a mutable default is never shared between calls. A default may refer to an earlier parameter.

<!-- dewy-example: {"mode":"run","stdout":"58\n42\n58\n"} -->
```dewy
combine = (left:int scale:int=2 right:int):>int => left + right * scale
main = () => {
    printl(combine(10 3 16))       # left=10 scale=3 right=16
    printl(combine(10 right=16))   # scale defaults to 2
    printl(combine(scale=3 10 16)) # then left=10 right=16
}
```

`combine(10 16)` binds `left` and `scale`; it does not skip `scale`, so `right` is missing:

<!-- dewy-example: {"mode":"reject","diagnostic":"missing argument 'right'"} -->
```dewy
combine = (left:int scale:int=2 right:int):>int => left + right * scale
printl(combine(10 16))
```

The callee evaluates first, then explicit arguments in written order, then omitted defaults in parameter order.

## Parameter Kinds

- An ordinary parameter may be bound by position or by name.
- `...` after a parameter ends the positional run: the parameters after it must be named. A leading bare `...` makes every parameter keyword-only.
- A parameter wrapped in `<>` is position-only: it keeps its local name, but a call cannot name it.
- A parameter named `_` accepts positional arguments only.

<!-- dewy-example: {"mode":"run","stdout":"42 42\n5 5\n"} -->
```dewy
offset = (value:int ... amount:int) => value + amount
increment = (<value:int>) => value + 1
subtract = (left:int right:int) => left - right
main = () => {
    printl"{offset(40 amount=2)} {increment(41)}"
    printl"{subtract(7 2)} {subtract(right=2 left=7)}"
}
```

<!-- dewy-example: {"mode":"reject","diagnostic":"too many positional arguments: 'amount' takes its name"} -->
```dewy
offset = (value:int ... amount:int) => value + amount
printl(offset(40 2))
```

<!-- dewy-example: {"mode":"reject","diagnostic":"parameter 'value' is position-only"} -->
```dewy
increment = (<value:int>) => value + 1
printl(increment(value=41))
```

### Rest Parameters and Spreading

An attached `...rest:T` collects the positional arguments the earlier parameters leave into an `array<T>`; the parameters after it are keyword-only. A function has at most one, with no default, and it cannot be named in a call. `xs...` spreads a container into a call's positional parameters.

<!-- dewy-example: {"mode":"run","stdout":"6\n13\nx: a-b\n"} -->
```dewy
total = (...xs:int):>int => {
    let t:int = 0
    loop x in xs { t += x }
    t
}
label = (name:string ...parts:string sep:string=", ") => "{name}: {parts.join(sep)}"
main = () => {
    let ys = [4 5]
    printl(total(1 2 3))
    printl(total(1 ys... 3))
    printl(label("x" "a" "b" sep="-"))
}
```

Written arguments give the rest parameter a fixed-length array, passed in place. Rest parameters work on declared functions, not on lambdas.

### Pattern Parameters

A parameter can unpack its argument with the patterns of `let`: arrays and tuples by position, records by field name. `([a b]) =>` is one patterned parameter; `(a b) =>` is two parameters. The pattern's length is an obligation on entry, like an index.

<!-- dewy-example: {"mode":"run","stdout":"42 7\n"} -->
```dewy
sum2 = ([left right]:array<int length=2>) => left + right
score = ([damage armor]:[damage:int armor:int]) => damage - armor
main = () => printl"{sum2([20 22])} {score([damage=10 armor=3])}"
```

## Function Types

A function type is written in parentheses: `(int:>int)`, `(x:int:>int)`, `(():>int)`, `((x:int y:string):>int)`. One parameter needs no parentheses of its own; zero or several do, since `(int string)` alone is several values. A label lets a call name the argument. Inside the parentheses `:>` binds loosest, then `:`, then `|` and `&`. An optional or union of function types, or a function type as a parameter or result, takes its own group: `(int:>int)?`, `((int:>int):>int)`. `<x:int:>int>` is the same type as `(x:int:>int)`.

A function type works wherever a type does: a parameter, a record field (`[run:(int:>int)]`), a type argument (`dict<string (int:>int)>`) or an alias (`Unary:type = (int:>int)`). Named arguments work through function values; an annotation supplies the names at that boundary:

<!-- dewy-example: {"mode":"run","stdout":"42\n"} -->
```dewy
main = () => {
    let f:(amount:int:>int) = (x) => x * 2
    printl(f(amount=21))
}
```

A function value fits a slot of a wider contract by the usual rules: parameters contravariant, the result covariant.

## Function Handles

`@name` is the function itself, a value that can be passed, stored, chosen and called later. This holds for named functions, function-valued locals and parameters, and function-valued record fields (`w.on_event` calls it; `@w.on_event` selects it). A handle keeps its function's parameter names and defaults. A handle prints as its type.

<!-- dewy-example: {"mode":"run","stdout":"42\n8 6\n(x:int:>int)\n5 6\n3 11\n"} -->
```dewy
double = (x:int):>int => x * 2
apply = (f:(x:int:>int) x:int):>int => f(x)
add = (a:int b:int=2) => a + b
Worker:type = [id:int64 on_event:(n:int:>int)]

main = () => {
    printl(apply(@double 20) + 2)
    let table:dict<string (x:int:>int)> = ["double" -> @double]
    let op = if table.length >? 0 @double else @apply(@double)
    printl"{table["double"](4)} {op(3)}"
    printl("{@double}")
    let w = Worker(1 (n:int) => n + 1)
    let h = @w.on_event
    printl"{w.on_event(4)} {h(5)}"
    let g = @add
    printl"{g(1)} {g(1 b=10)}"
}
```

Passing a function where a function value is expected needs `@`:

<!-- dewy-example: {"mode":"reject","diagnostic":"'double' is a function: write `@double`"} -->
```dewy
double = (x:int):>int => x * 2
apply = (f:(x:int:>int) x:int):>int => f(x)
printl(apply(double 20))
```

### Partial Evaluation

`@f(args)` partially evaluates `f`: the arguments are evaluated now, and the result is a function of the remaining parameters. Every argument group in an ungrouped `@` chain partially evaluates (`@sum3(1)(2)`); parentheses end the chain, after which an argument group calls (`(@sum3(1 2))(3)`). `@text.split(" ")` saves the receiver with the arguments. A parameter left to its default must have a literal default for now. An overloaded or generic function partially evaluates too: the arguments choose the version.

<!-- dewy-example: {"mode":"run","stdout":"6 6\n(int:>int)\n[\"a\" \"b\" \"c\"]\n"} -->
```dewy
sum3 = (a:int b:int c:int) => a + b + c
main = () => {
    let p = @sum3(1)(2)
    printl"{p(3)} {(@sum3(1 2))(3)}"
    printl(@sum3(1 2))
    let text = "a b c"
    let words = @text.split(" ")
    printl(words())
}
```

A partial is a value like any other, so a comprehension collects partials: `[loop s in sources @load(s)]`.

## Closures

A function literal may read locals of the enclosing function. It captures a snapshot of each when it is created; later changes to the enclosing local do not reach it.

A closure that changes a local must capture it explicitly. `$capture name` gives the closure its own private copy, kept between calls; `$capture @name` shares the enclosing binding. Captures can appear anywhere among the parameters and take no argument when called. Copying a closure (`@a`) copies its private state; shared captures stay shared.

<!-- dewy-example: {"mode":"run","stdout":"11\n1 1 2\n2\n"} -->
```dewy
make_counter = () => {
    let count = 0
    return ($capture count) => { count += 1; count }
}
main = () => {
    let base = 10
    let add = (x:int) => x + base
    base = 20
    printl(add(1))              # the snapshot: 10 + 1
    let a = make_counter()
    let b = @a
    let first = a()
    let other = b()
    printl"{first} {other} {a()}"
    let n = 0
    let next = ($capture @n) => { n += 1; n }
    next();
    next();
    printl(n)
}
```

<!-- dewy-example: {"mode":"reject","diagnostic":"this closure changes 'count', which it captures implicitly"} -->
```dewy
main = () => {
    let count = 0
    let bump = () => { count += 1 }
    bump()
}
```

A function may return a closure. Ordinary callback parameters receive independent values: to advance a caller's state, take an `@` parameter and pass `@state`.

<!-- dewy-example: {"mode":"run","stdout":"7\n3\n"} -->
```dewy
make_adder = (n:int) => ((x:int) => x + n)
main = () => {
    let add3 = make_adder(3)
    printl(add3(4))
    let adders = [loop k in [1..3] @make_adder(k)]
    printl(adders.length)
}
```

## Overloads

`&` joins function literals into an overload set. A call selects the most specific applicable member from the argument types; an ambiguous or unmatched call is an error. Members may differ in arity, defaults and type parameters. A literal-typed parameter makes a specialization (see [Literal Types](types-and-conversions.md#literal-types)). When an overloaded function is passed as a value, the expected function type selects a member.

<!-- dewy-example: {"mode":"run","stdout":"42\n"} -->
```dewy
measure = ((value:int):>int => value)
    & ((text:string):>int => text.length)
main = () => printl(measure(40) + measure("ab"))
```

Overload groups are module-level, and their members must be function literals.

## Pipes

`x |> @f` is `f(x)` and `@f <| x` is the same call written right to left; see [Pipes](operators-and-precedence.md#pipes).

## Effect Contracts

A result type may carry an effect row with `&`. `reads<x>` and `mutates<x>` name a place parameter the function may read or change; `no_effects` is the empty row. A positive row is an upper bound, and callers are checked against what the callee declares. `no reads<R>` excludes one effect; `& no allocates & no blocks` excludes several. Omitted rows are inferred when a checked contract needs them; an unannotated callback is never assumed pure.

<!-- dewy-example: {"mode":"run","stdout":"41\n42\n42\n"} -->
```dewy
read = (@x:int64):>int64 & reads<x> => x
write = (@x:int64 value:int64):>void & mutates<x> => { x = value }
quiet = (x:int32):>int64 & no_effects => x * 2
answer = ():>int64 => 42
use = (f:(():>int64 & no_effects)):>int64 & no_effects => f()

Action:type = <E:Effect>(x:int64:>int64 & E)
apply = <E:Effect>(f:Action<E> x:int64):>int64 & E => f(x)
inc = (x:int64):>int64 => if x <? 100 x + 1 else x

main = () => {
    let v:int64 = 1
    write(@v 41)
    printl(read(@v) + quiet(0))
    printl(use(@answer))
    printl(apply(@inc 41))
}
```

<!-- dewy-example: {"mode":"reject","diagnostic":"mutation of 'value' exceeds the closed row"} -->
```dewy
bad = (@value:int64):>void & reads<value> => { value = 42 }
```

Effect parameters have kind `Effect`: the callback's contract determines `E`. See [Effects](refinements-and-effects.md#effects) for the full vocabulary.
