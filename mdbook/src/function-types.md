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

TODO->decide if a single argument can omit the parenthesis e.g.

```dewy
abs = (x) => if x <? 0 -x else x
abs = x => if x <? 0 -x else x
```

TODO->Originally I had the syntax be `@(args) => {}`, but I'm thinking that we can actually probably omit the `@` because as an operator, it doesn't really make sense here. TODO is to make a final decision on this