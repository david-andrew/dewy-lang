# Function Types

Functions are first class citizens in Dewy. In fact many concepts from functional programming are included in Dewy, as they frequently allow for cleaner and more concise code.

## Function Literals

To create a function, simply bind a function literal to a variable

```dewy
my_function = () => 
{ 
    printn('You called my function!') 
}

my_function()  //calls the function
```

In the above example, the function takes no input arguments, and doesn't return any values. Instead is simply prints a string to the terminal


Here's an example that takes two arguments

```dewy
pythag_length = (a, b) => 
{ 
    return (a^2 + b^2)^/2
}
```

In fact we can simplify the above function's declaration quite a bit via syntactic sugar

```dewy
pythag_length = (a, b) => (a^2 + b^2)^/2
```

In fact, if we have exactly one argument, we can omit the parenthesis around the argument list

```dewy
abs = x => if x <? 0 -x else x
```

Note that zero arguments require an empty pair of parenthesis, in order to be parsed correctly

```dewy
foo = () => printl('bar')
```

TODO->Originally I had the syntax be `@(args) => {}`, but I'm thinking that we can actually probably omit the `@` because as an operator, it doesn't really make sense here. TODO is to make a final decision on this

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
my_func = () => printl('foo')

reference_to_my_func = @my_func
```

If you don't include the `@` operator, then the evaluation of the right-hand side would be stored into the left side

```dewy
reference_to_my_func = my_func  //this doesn't work
```

what happens is `my_func` prints out "foo" to the command line, and then since it returns no value, `reference_to_my_func` is `undefined`. If `my_func` required arguments, we'd actually get a compilation error at this point, as we essentially are trying to call my_func without an arguments.

```dewy
another_func = (a, b, c, x) => a^2*x + b*x + c

good_reference = @another_func
bad_reference = another_func  //this causes a compilation error
```

Now, using the `@` operator, we can not only create a new reference to an existing function, but we can also **apply arguments to the reference**. What this means is we can fix the value of given arguments, allowing us to create a new function.

```dewy
sum = (a, b) => a + b   //simple addition function
add5 = @sum(5)          //partially evaluate sum with a=5
```

Here we've created a new function `add5` which takes a single argument, and return the result of that argument plus 5.

```dewy
add5(24)        //returns 29
add5(-7)        //returns -2

thirtyseven = @add5(32) //new function that takes 0 arguments
thirtyseven()   //returns 37
```

TODO->explain about overwriting arguments

```dewy
new_sum = (x, y) => thirtyseven(a=x, b=y)
```

