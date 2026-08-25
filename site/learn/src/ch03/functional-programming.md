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

## Capturing an Enclosing Scope

A nested function can use names from its lexical environment:

```dewy
let counter = (start:int64=0) => [
    value = start
    increment = () => (value += 1)
]
```

> **Provisional design:** The lexical meaning of captures is settled. Escaping closure storage, handle identity, explicit function copying, and general user-written generics remain under design and implementation.

See [Functions and Calls](function-types.md) for ordinary argument behavior and the Reference for exact [function-handle rules](../../reference/functions-and-calls.html#function-handles).
