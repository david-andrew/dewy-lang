# Bindings, Initialization, and Scope

> [Generated coverage](/status/#ref-bindings-and-scope) names related acceptance programs. Every example on this page compiles with the current compiler unless it is marked **Design only**.

## Declarations

`let` declares a mutable binding. `const` declares a binding that cannot be reassigned, and whose fields and elements cannot change. A type annotation follows `:`. Declarations and assignments produce `void`.

<!-- dewy-example: {"mode":"run","stdout":"0 10 ada\n"} -->
```dewy
let count:int64 = 0
const limit = 10
const Name:type = string
let who:Name = "ada"
printl"{count} {limit} {who}"
```

An assignment to a name with no visible binding declares a new mutable binding. Otherwise it updates the visible binding:

<!-- dewy-example: {"mode":"run","stdout":"welcome\n"} -->
```dewy
message = "hello"     # declares message
message = "welcome"   # assigns it
printl(message)
```

Assigning to a `const`, or to a module function, is an error. `let` declares a new binding that shadows it instead.

<!-- dewy-example: {"mode":"reject","diagnostic":"'limit' is a constant"} -->
```dewy
const limit = 10
limit = 11
```

A `const` initializer runs each time its declaration runs and may call ordinary code. Reading the binding later gives that value, as an independent snapshot. Make a mutable copy with `let`:

<!-- dewy-example: {"mode":"run","stdout":"[20 22] [99 22] [0 22]\n"} -->
```dewy
let values = [20 22]
const saved = values
values[0] = 99
let editable = saved
editable[0] = 0
printl"{saved} {values} {editable}"
```

## Unpacking

A target `[a b]` on the left of `=` (with or without `let`/`const`) binds several names from one value, evaluated once.

- An object is unpacked by field name, in any order and any subset. `[x as h]` binds field `x` to the name `h`.
- An array, tuple, dictionary or set is unpacked by position (insertion order for dictionaries and sets). `_` discards a value, a nested `[…]` unpacks an element further, and a dictionary entry unpacks as `[key value]`.

<!-- dewy-example: {"mode":"run","stdout":"1 2\n10 30\n1 3 4\na 2\n"} -->
```dewy
let point = [x=1 y=2]
let [y x as horizontal] = point
printl"{horizontal} {y}"
let [first _ third] = [10 20 30]
printl"{first} {third}"
let t:[int64 int64 [int64 int64]] = [1 2 [3 4]]
let [a _ [b c]] = t
printl"{a} {b} {c}"
let [[k1 v1] [k2 v2]] = ["a" -> 1 "b" -> 2]
printl"{k1} {v2}"
```

The target count must match the source's known count. Each name follows the ordinary declaration rule: `let`/`const` declare, and a bare target declares a new name or assigns an existing one.

## Scopes

`{ … }` is a scoped block: names declared inside stay inside, and a declaration there may shadow an outer binding without changing it. `( … )` is an unscoped block: names declared inside are visible after it, as if declared in the enclosing block.

<!-- dewy-example: {"mode":"run","stdout":"2\n1\n12\n"} -->
```dewy
let value = 1
{
    let value = 2
    printl(value)
}
printl(value)
(
    let width = 3
    let height = 4
)
printl(width * height)
```

<!-- dewy-example: {"mode":"reject","diagnostic":"unknown name 'y'"} -->
```dewy
{
    let y = 5
}
printl(y)
```

Declarations in unscoped `if` branches and `match` arms are visible after the construct when every continuing path gives them a value of a compatible type:

<!-- dewy-example: {"mode":"run","stdout":"3\n"} -->
```dewy
let c = true
if c (let q = 3) else (let q = 4)
printl(q)
```

## Shadowing the Prelude

`$shadowable const` at module top level declares a constant that inner scopes and importing modules may shadow: there a plain `name = …` declares a new binding instead of being an error. The prelude is declared this way, so a module may reuse prelude names. Shadowing replaces the whole overload family in that scope.

<!-- dewy-example: {"mode":"run","stdout":"3\n10\n"} -->
```dewy
$shadowable const limit = 10
main = () => {
    limit = 3     # a new binding in this scope
    printl(limit)
    show()
}
show = () => printl(limit)
```

## Initialization

A binding is never read before it has a value. `let x:T` without a value declares a binding that every path must assign before it is read. There is no zero value.

<!-- dewy-example: {"mode":"run","stdout":"1\n"} -->
```dewy
let x:int64
if true { x = 1 } else { x = 2 }
printl(x)
```

<!-- dewy-example: {"mode":"reject","diagnostic":"'y' is read before it is given a value"} -->
```dewy
main = () => {
    let y:int64
    if args.length >? 1 { y = 1 }
    printl(y)
}
```

Paths that return, break or continue do not count. At module level, a binding declared without a value must be given one by the top-level statements or by `main` before any read, including reads in functions called before the assignment.

Function bodies may refer to declarations later in the same scope, which permits mutual recursion. What matters is that each call runs after every binding it reads has its value:

<!-- dewy-example: {"mode":"run","stdout":"42\ntrue\n"} -->
```dewy
let f = ():>int => g() + 1
let g = ():>int => 41
printl(f())
is_even = (n:int):>bool => if n =? 0 true else is_odd(n - 1)
is_odd = (n:int):>bool => if n =? 0 false else is_even(n - 1)
printl(is_even(10))
```

<!-- dewy-example: {"mode":"reject","diagnostic":"'later' is used before it has its value"} -->
```dewy
let f = ():>int64 => later + 1
printl(f())
let later = 41
```

## Captures

A function body may read bindings of enclosing scopes. A closure captures a snapshot of them when it is created; changing a captured local requires an explicit `$capture`. See [Closures](functions-and-calls.md#closures).
