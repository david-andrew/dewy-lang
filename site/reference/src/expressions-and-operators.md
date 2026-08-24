# Expressions and Evaluation

Every executable construct in Dewy is an expression. An expression may produce one value, several values for a surrounding collector, `void`, or `never` when it cannot complete.

## Produced Values

Literals, value-returning calls, exhaustive conditionals, and value-producing blocks can supply surrounding expressions. Declarations and ordinary assignments produce `void`.

An attached postfix semicolon evaluates an expression and suppresses the values it would otherwise produce:

```dewy
operation();
```

An unattached semicolon is reserved for array-dimension selection and does not act as generic statement punctuation.

## Blocks

`{}` is a scoped block. `()` groups expressions without introducing a child lexical scope.

A block evaluates its expressions in source order and expresses each non-`void` result. A context requiring one value rejects a block that can produce an incompatible number of values.

```dewy
let circumference = {
    let diameter = 2 * radius
    pi * diameter
}
```

Only the final calculation produces a value because the declaration is `void`.

## Evaluation Order

Within the expression tree established by grouping and precedence, operands and call arguments evaluate from left to right. A construct documented as evaluating an operand once must preserve that behavior even if lowering expands it into several primitive operations.

Boolean short-circuit expressions evaluate only the operands required by their truth rule. Flow alternatives evaluate conditions in order and execute only the selected body.

## Assignment

Assignment evaluates its destination place and source, updates the binding or selected field/element, and produces `void`. Combined assignment loads the old value, applies the selected typed operator, and stores the result while evaluating the destination route only once.

See [Operators and Precedence](operators-and-precedence.md), [Bindings](bindings-and-scope.md), and [Values, Copies, and Places](values.md).

## Place Projection

The prefix `@` selects a place. Following member and index expressions project the place to the location at the end of the route:

```dewy
@pair.left
@values[i]
@box.rows[row][column]
```

These parse as projections from the prefixed root. `@(pair.left)` is equivalent to `@pair.left`; Dewy has no `pair.@left` form.
