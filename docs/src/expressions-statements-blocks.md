# Expressions, Statements, and Blocks

## Expressions

Dewy is an expression based language. An expression is literally just a value, or something that evaluates to a value. Results of expressions can be stored in variables, or used to build up more complicated expressions.

The simplest type of expression is any literal value, such as an integer for instance

```dewy
42  //an integer expression
```

This expression can easily be bound to a variable

```dewy
my_expression = 42
```

Calling a function is an expression if the function returns a value. For example, the `sqrt` function returns the square root of a value

```dewy
my_expression = sqrt(64)  //returns 8
```

And now `my_expression` contains the value `8`.

Expressions can also be used to build up more complicated expressions

```dewy
my_expression = 'string with the expression {sqrt(64) + 9 * cos(pi)}'
```

In this example, at the highest level, there is a string expression, which contains a nested expression. The nested expression `sqrt(64) + 9 * cos(pi)` is a mathematical expression, built up from smaller expressions combined with math operators `+` and `*`. `sqrt(64)` and `cos(pi)` are both a function call expressions, and `64`, `9` are literal expressions and `pi` is an identifier for a constant value.


## Statements

A statement is a single piece of code that expresses no value (typically referred to as `void`). For example calling the `printl` function, which prints out a string to the console

```dewy
printl'Hello'
```

This function call doesn't return a value. If you tried to store the result into a variable, you'd get a compilation error

```dewy
my_var = printl'Hello'  // Error: can't assign void to a variable
```

Most expressions in Dewy will return something, but you can easily convert an expression into a `void` statement by appending a semicolon `;` to the end of the expression

```dewy
my_expression = [
    sqrt(1);
    sqrt(4);
    sqrt(9);
    sqrt(16);
    sqrt(36);
    sqrt(49);
    sqrt(64);
]
```

In this example, the resulting value of each `sqrt` call is suppressed by the semicolon, and the array captures no values, meaning `my_expression = []`.

> Note: the one context where semicolon does not suppress the value of an expression is in a multidimensional array literal. In this context, semicolons are used to indicate new dimensions of the array, and values with semicolons are still captured.

## Blocks

A block is just a sequence of expressions or statements wrapped in either `{}` or `()`. A block is itself an expression.

> Note: the distinction between `{}` and `()` blocks has to do with the scope of the block. Any expressions inside a `{}` block receive a new child execution scope, while those inside a `()` block share the same scope as the parent where the block is written. Scope will be explained in greater detail later (TODO: link)

Let's start with the simplest type of a block, the empty block

```dewy
{ }  // an empty block
( )  // also an empty block
```

Empty blocks have type `void` since they don't contain any expressions, thus making the overall block not express anything.

Adding a single expression to a block makes the block itself express that value

```dewy
{ 42 }  // a block that expresses the value 42
```

Adding multiple expressions to a block makes the block express multiple values (TODO: link to generators)
    
```dewy
{ 1 2 3 4 5 6 7 8 9 10 }  // a block that expresses the values 1 through 10
```



TODO->rest of explanation of blocks.
- catching values expressed in blocks
- blocks for precedence overriding
- blocks work anywhere an expression is expected