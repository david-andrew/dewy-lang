# Expressions, Statements, and Blocks

Dewy is expression-based. An expression is a value, or something that
evaluates to one. You can bind it, pass it to a function, or build a
larger expression from it.

## Expressions

The simplest expression is a literal:

```dewy
42  # an integer expression
```

Bind it, or nest it:

```dewy
my_expression = 42
my_expression = sqrt(64)  # 8
my_expression = 'string with the expression {sqrt(64) + 9 * cos(pi)}'
```

Function calls are expressions when they return a value. In the string
above, `+` and `*` combine smaller pieces. `sqrt(64)` and `cos(pi)` are
calls. `64` and `9` are literals. `pi` is a constant.

## Statements

A statement is an expression that produces no value. Dewy calls that
`void`. Printing is the usual example:

```dewy
printl'Hello'
```

`printl` returns `void`. Assigning it is an error:

```dewy
my_var = printl'Hello'  # error: can't assign void
```

Declarations and ordinary assignments are `void` too.

Appending `;` discards the value. The expression still runs. That is
useful when a block or array would otherwise capture every result:

```dewy
my_expression = [
    sqrt(1);
    sqrt(4)
    sqrt(9);
    sqrt(16)
    sqrt(25);
    sqrt(36);
    sqrt(49);
    sqrt(64)
]
```

The semicolons suppress those `sqrt` results, so the array is `[2 4 8]`.

In a multidimensional array literal, `;` starts a new dimension instead
of suppressing values. Those elements are still captured.

## Blocks

A block is a sequence of expressions wrapped in `{ }` or `( )`. The block
itself is an expression.

`{ }` opens a child scope. Names declared inside are not visible
outside. `( )` shares the surrounding scope, which is also why you use
it for grouping.

```dewy
{ }  # empty block, type void
( )  # also empty, also void
```

A block with one expression has that expression's value:

```dewy
{ 42 }
(1 + 2) * 3
```

A block with several expressions *expresses* each non-void value. Wrap
it in `[]` to capture them, the same idea as a generator.

```dewy
{ 1 2 3 4 5 6 7 8 9 10 }
[ { 1 2 3 4 5 } ]           # [1 2 3 4 5]
circumference = {
    diameter = 2 * radius
    pi * diameter
}
```

`diameter` is local to the `{ }` block. Treat the block as a single
result and the last expression is the value, as in `circumference`.

`if` and `loop` take a following expression, often a block. See
[Flow Control](flow-control.md) and [Loops](loops.md).
