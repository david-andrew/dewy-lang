# Control Flow

## Conditionals

`if`, `else if`, and `else` form an ordered flow expression. Conditions evaluate from left to right until one succeeds; only the selected body evaluates.

```dewy
let label = if count =? 0
    "empty"
else if count =? 1
    "one item"
else
    "{count} items"
```

An exhaustive conditional may produce a value when its alternatives have a compatible result type. A nonexhaustive conditional produces `void` unless its context collects another well-defined result form.

Facts established by a condition narrow values inside the corresponding body and along later paths where earlier alternatives are known false.

## Loops

`loop condition body` reevaluates its condition and executes its body according to the condition's Boolean or iterator behavior.

```dewy
loop connected
    receive_message()

loop item in items
    process(item)
```

See [Ranges and Iteration](ranges-and-iteration.md) for iterator conditions and multiiterator formulas.

## Exits

`break` exits a loop. `continue` begins its next condition evaluation. `return` exits the current function, optionally supplying its result.

An exit may target an enclosing labeled loop through Dewy's scope metatag mechanism. Exiting more loop levels than exist is an error.

`never` is the type of a path that cannot complete normally. It is distinct from `void`, which represents normal completion without a produced value.

Postfix `or_return` propagates an [exception value](errors-and-forwarding.md) from an expression through the current function. Its ordinary alternatives continue locally; its exception alternatives must be accepted by the enclosing return contract.

## Pattern Selection and Cleanup

General `match`, cleanup/finally behavior, and transformed error-propagation forms are provisional designs. Their eventual forms must compose with expression results and flow-sensitive narrowing rather than creating separate statement-only semantics.
