# Blocks, Statements, and Expressions

## Statements

a statement is a single piece of code that expresses no value. For example the `printl` function, which prints out a string to the console

```dewy
printl('Hello')
```

This function call doesn't return a value. If you tried to store the result into a variable, you'd get a compilation error

```dewy
my_var = printl('Hello')  //produces a compilation error
```

Many things can be a statement, including (TODO->make list of statmenet examples)

## Expressions

An expression is any single piece of code that "expresses" a value. I.e. the expression produces a value that can be stored as a variable, or in a container, or is part of a larger expression or statement.

The simplest type of expression is any literal value, such as an integer for instance

```dewy
42  //an integer expression
```

This expression can easily be bound to a variable

```dewy
my_expression = 42
```

Functions can be expressions if they return a value. For example, the `sqrt` function returns the square root of a value

```dewy
my_expression = sqrt(64)  //returns 8
```

And now my expression contains the value `8`.

Expressions can also be used to build up more complicated expressions

```dewy
my_expression = sqrt(64) + 9 * sin(pi) //returns -72
interpolation = 'string with the expression {my_expression}'
```

TODO->more expression examples
- an example with a string expression + explanation of how string interpolation is a nested expression
- expressions inside of containers


## Blocks

A block is many things in Dewy. The simplest explanation is that a block is a collection of statements and expressions. Though there's much more to what you can do with blocks

Let's start with the simplest type of a block, the empty block

```dewy
{ } 
```

Blocks can also be expressed using parenthesis (the distinction will be explained later)

```dewy
( )
```

Lastly, the empty block can be expressed with a semicolon

```dewy
;
```

TODO->rest of explanation of blocks.
- putting code in blocks
- catching values expressed in blocks
- external access to values assigned in a block
- blocks for functions
- turning a block into an object
- scopes on `{}` vs `()` blocks