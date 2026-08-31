# Function Values and Composition

Dewy does not require a separate “functional mode.” Functions, loops, blocks, and ordinary values compose using the same expression rules as the rest of the language.

## Selecting and Passing Functions

A function contract can appear anywhere another type can:

```dewy
let apply = (
    transform:<(value:int64):>int64>
    value:int64
):>int64 => transform(value)

let square = (value:int64) => value^2
apply(@square 5)
```

`@square` selects the function binding rather than calling `square` with no arguments.

A leading `@` governs the complete ungrouped selector-and-application chain. Function-valued nodes inside that chain are selected rather than called. Grouping ends the chain, so a following argument group performs an ordinary call:

```dewy
@worker.callback.metadata        # metadata on the callback function value
worker.callback(5).status        # call callback normally, then read its result
(@worker.callback)(5).status     # select callback explicitly, then call it
```

The parentheses around `@worker.callback` terminate the selection chain. This uses ordinary grouping rather than a separate “call this handle” operator.

## Partial Evaluation

A function handle can bind some arguments now and leave the rest open:

<!-- dewy-example: design-only -->

```dewy
let add = (left:int64 right:int64) => left + right
let add5 = @add(5)

add5(24)       # 29
```

Explicit arguments are captured when the partial function is created. Default expressions remain per-call fallbacks.

Every argument group still inside an unbroken `@` chain performs another partial-evaluation step. An argument group outside a grouping boundary calls:

```dewy
@add(1)(2)       # save 1, then save 2; still a function
(@add(1))(2)     # save 1, then call with 2
@add(1)()        # empty second partial evaluation; still a function
(@add(1))()      # call the partially evaluated function
```

An empty partial evaluation neither invokes the function nor evaluates defaults.

A function member can be selected and partially evaluated at the end of a stable object route:

```dewy
let on_item = @worker.callback(5)
```

This preserves the function field's receiver. If another call produces the object, bind that result first because a temporary call result is not a place-route root:

```dewy
let worker = make_worker()
let on_item = @worker.callback(5)
```

`@make_worker()` is an empty partial evaluation of `make_worker`, not a call.

## Transforming and Selecting Values

A loop already expresses the operations often called `map` and `filter`:

```dewy
let values = [1 2 3 4 5 6]

let squares = [
    loop value in values
        value^2
]

let odd = [
    loop value in values
        if value % 2 =? 1
            value
]
```

The array collects what the loop expresses. No separate comprehension or callback vocabulary is required for these direct cases.

Reusable library functions can be built from the same pattern once generic function contracts are available:

<!-- dewy-example: design-only -->

```dewy
let map = <T U>(
    transform:<(value:T):>U>
    values:array<T>
):>array<U> => [
    loop value in values
        transform(value)
]
```

Generic functions work today for the direct cases: declare the type parameters in `<…>` before the parameter list, give the result a type, and call the function by name — the compiler infers the type arguments from the call and compiles one instance per distinct binding:

<!-- dewy-example: compiler -->

```dewy
let first = <T>(xs:array<T>):>T | none =>
    if xs.length >? 0 xs[0] else none

let main = ():>int64 => {
    let nums:array<int64> = [7 8 9]
    let n = first(nums)           # first<int64>
    if n is? int64 { return n }
    return 0
}
```

`T of int` bounds a parameter to a family of types; inside the body, the operations available are those of the concrete types the call supplied, checked at that call. A generic function cannot yet be passed as a value or declared inside another function.

## Capturing an Enclosing Scope

A nested function can use names from its lexical environment:

```dewy
let counter = (start:int64=0) => [
    value = start
    increment = () => (value += 1)
]
```

A local function may read the locals and parameters of the functions around it, and it sees them as they are when it is called:

<!-- dewy-example: compiler -->

```dewy
let main = ():>int64 => {
    let base:int64 = 10
    let scale = (v:int64):>int64 => v * base
    let a = scale(2)          # 20
    base = 100
    let b = scale(2)          # 200: the current value of `base`
    return a + b
}
```

In the current compiler such a function is *lambda-lifted*: the values it reads become hidden trailing parameters, passed at every direct call. Two things follow from that and are rejected for now: a local function cannot assign to a captured variable (keep shared mutable state in an object, or return the new value), and a capturing function cannot be used as a value — stored, passed to another function, or returned — because that needs a closure record, which is not implemented yet. Non-capturing functions are unrestricted as values.

> **Provisional design:** The lexical meaning of captures is settled. Escaping closure storage, handle identity, explicit function copying, and general user-written generics remain under design and implementation.

See [Functions and Calls](function-types.md) for ordinary argument behavior and the Reference for exact [function-handle rules](../../reference/functions-and-calls.html#function-handles).
