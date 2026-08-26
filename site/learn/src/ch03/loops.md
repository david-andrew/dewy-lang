# Loops and Multiple Iterators

Dewy uses one `loop` expression for repetition. Its condition can be an ordinary Boolean expression, an iterator clause, or a logical formula made from iterator clauses.

## Repeating While a Condition Holds

The condition is evaluated before each iteration:

```dewy
let attempts = 0

loop attempts <? 3 {
    reconnect()
    attempts += 1
}
```

Use `loop true` for repetition that ends through `break` or `return`:

```dewy
loop true {
    let message = receive()
    if message is? undefined
        break
    handle(message)
}
```

## Consuming an Iterable

In a loop condition, `name in iterable` advances the iterable and binds its next value to `name`. The body runs when a value was produced:

```dewy
loop fruit in ["apple" "banana" "peach"]
    printl"I like {fruit}."
```

Ranges are iterables. Integer ranges use a unit step unless a second anchor states another step:

```dewy
loop number in 1..5
    printl(number)

loop even in 0,2..10
    printl(even)

loop descending in 5,4..0
    printl(descending)
```

`0..` has a first value and no right bound, so it can iterate indefinitely. A left-unbounded range such as `..10` has no first value and cannot be iterated. [Ranges](range-types.md) covers bounds and steps in detail.

## Combining Iterators

Iterator clauses combine with the ordinary logical operators. `and` provides the familiar zip behavior: every required iterator advances once, and the loop ends when the formula becomes false.

```dewy
let names = ["Alice" "Bob" "Charlie"]
let colors = ["red" "blue" "green" "yellow"]

loop name in names and color in colors
    printl"{name} chose {color}."
```

Pairing a finite source with a right-unbounded counter provides enumeration without a separate construct:

```dewy
loop index in 0.. and fruit in ["apple" "banana" "peach"]
    printl"{index}: {fruit}"
```

For a multiiterator formula, every iterator leaf advances once from left to right before the logical formula is evaluated. This is deliberately different from ordinary Boolean short-circuit evaluation: skipping a leaf would make its position drift relative to the others.

`or` continues while either source produces a value. A target that can be exhausted during a body iteration has optional type `T | undefined`:

```dewy
loop left in left_items or right in right_items {
    if left isnt? undefined
        process_left(left)

    if right isnt? undefined
        process_right(right)
}
```

This applies the same narrowing rules introduced in [Optional Values and Narrowing](optional-types.md). By contrast, `and` stops before a required source's missing value reaches the body.

The same rule extends to `xor`, `nand`, `nor`, and `xnor`: each iterator contributes the Boolean result of its current advance, and the operator's truth rule decides whether the body runs. Some formulas remain true after every input is exhausted. For example, `xnor` of two exhausted iterators is true, so such a loop needs another exit if it can reach that state.

> **Provisional design:** Combining iterator clauses with ordinary Boolean predicates is a separate case from a formula containing only iterator leaves. Its advancement and short-circuit rules have not been selected, so this book does not infer behavior for expressions such as `item in items and clock.now <? deadline`.

## Exiting a Loop

`break` leaves the nearest loop. `continue` starts its next condition evaluation. `return` leaves the containing function.

```dewy
loop task in tasks {
    if task.cancelled
        continue
    if shutting_down
        break
    process(task)
}
```

A scope metatag can name its directly contained loops so an exit can target one through nested control flow:

```dewy
{
    $rows

    loop row in rows {
        loop column in columns {
            if retry_row()
                continue $rows
            if complete()
                break $rows
            process(row column)
        }
    }
}
```

The label belongs to the scope, not textually to the next loop. It cannot duplicate or shadow an active label, and labels do not cross function boundaries.

## Loop Capture

A loop expresses the non-`void` values produced by its body. Surrounding `[]` collects them into an array; this is loop capture:

```dewy
let squares = [
    loop number in 1..5
        number^2
]
```

A body may produce no value on some iterations, which makes filtering use the same ordinary `if` expression:

```dewy
let odd = [
    loop number in 1..10
        if number % 2 =? 1
            number
]
```

Nested collectors build nested arrays:

```dewy
let table = [
    loop row in 1..3 [
        loop column in 1..3
            row * column
    ]
]
```

## Iterating Dictionaries and Sets

`loop [key value] in dictionary` unpacks each entry in insertion order, and `loop member in set` visits each member in first-seen order. The iterated key or member is a proven key inside the body, so `dictionary[key]` needs no check there. A loop must not change the container it iterates — stores, `pop`, and `clear` on it inside the body are compile errors, the static counterpart of Python's "changed size during iteration".

> **Provisional design:** General destructuring in iterator targets and collecting dictionary or multidimensional results must extend this model without creating a separate loop grammar. Their complete binding and shape rules are still being designed.

The Reference defines the exact [iterator advancement and exhaustion rules](../../reference/ranges-and-iteration.html).
