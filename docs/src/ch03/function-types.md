# Function Types

Functions are first class citizens in Dewy. In fact many concepts from functional programming are included in Dewy, as they frequently allow for cleaner and more concise code.

## Function Literals

To create a function, simply bind a function literal to a variable

```dewy
my_function = () => { printl'You called my function!' }

my_function  %calls the function
```

A function literal consists of the arguments, followed by the `=>` operator, followed by a single expression that is the function body. In the above example, the function takes no input arguments, and doesn't return any values. Instead is simply prints a string to the terminal.

Here's an example that takes two arguments

```dewy
pythag_length = (a b) => { return (a^2 + b^2)^/2 }
```

In fact we can simplify the above function's declaration quite a bit since blocks return expressions present in the body.

```dewy
pythag_length = (a b) => (a^2 + b^2)^/2
```

When there is a single argument, you may omit the parenthesis around the argument list

```dewy
square = x => x^2
```

Zero arguments functions require an empty pair of parenthesis:

```dewy
foo = () => printl'bar'
```

### Default Arguments

Function arguments can have default values, which are used if the argument is not specified in the function call.

```dewy
foo = (a b=5) => a + b
foo(3)      %returns 8
foo(3 b=2)  %returns 5

bar = (a:int b:int=5 c:int=10) => a + b + c
bar(3)      %returns 18
bar(3 c=2)  %returns 10
```

## Calling functions

TODO

- calling a function with name, parenthesis, and args
- functions with no arguments can omit the parenthesis

## Optional, Name-only and Positional-only Arguments

TODO

- also explain about overwriting previously specified arguments (e.g. from partial evaluation, or in the same call)

## Scope Capture

TODO

- what variables are available to a function's body

## Partial Function Evaluation

First note that if you want to pass a function around as an object, you need to get a handle to the function using the `@` ("handle") operator.

```dewy
my_func = () => printl'foo'

reference_to_my_func = @my_func
```

If you don't include the `@` operator, then the evaluation of the right-hand side would be stored into the left side

```dewy
reference_to_my_func = my_func  %this doesn't work
```

what happens is `my_func` prints out "foo" to the command line, and then since it returns no value, `reference_to_my_func` is not able to be assigned, causing a compiler error. We'd also get a compiler error if `my_func` required arguments, as we essentially are trying to call my_func without an arguments.

```dewy
another_func = (a b c x) => a^2*x + b*x + c

good_reference = @another_func
bad_reference = another_func  %this causes a compilation error
```

Now, using the `@` operator, we can not only create a new reference to an existing function, but we can also **apply arguments to the reference**. What this means is we can fix the value of given arguments, allowing us to create a new function.

```dewy
sum = (a b) => a + b   %simple addition function
add5 = @sum(5)          %partially evaluate sum with a=5
```

Here we've created a new function `add5` which takes a single argument, and return the result of that argument plus 5.

```dewy
add5(24)        %returns 29
add5(-7)        %returns -2

thirtyseven = @add5(32) %new function that takes 0 arguments
thirtyseven   %returns 37
```

TODO->explain about overwriting arguments.

```dewy
new_sum = (x y) => thirtyseven(a=x b=y)
```
