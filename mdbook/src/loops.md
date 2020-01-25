# One Loop to Rule them All

Other languages make use of sometimes multiple keywords such as `for`, `while`, `do-while`, `for each`, etc., to handle looping over a piece of code. Dewy instead simply uses the `loop` keyword to handle all forms of looping.

Loops start with the `loop` keyword followed by either an expression the produces a boolean `true`/`false` value, or a `<value> in <iterable>` expression. The loop is then attached either below, or above, to a block/expression which is executed multiple times

## Infinite Loops

An infinite loop is one that never ends. They are constructed by calling loop with the condition fixed to `true`, which ensures that the loop will always repeat.

```dewy
loop true
{
    //do something repeatedly forever
}
```

The only way to leave an infinite loop is via the `break`, and `return` keywords.

## While Loops

A while loop is a loop that executes "while" some condition is true. 

```dewy
loop i >? 0
{
    //while i is greater than 0, do something 
}
```

If the condition is false before the loop starts, the body of the loop will never be entered. If you want the loop body to be entered at least once, you can use a do while loop

```dewy
{
    //do something, while i is less or equal to 10
}
loop i <=? 10
```

Instead of checking the condition at the start of the loop, the condition is checked at the end of each cycle. This way, the body is guaranteed to execute at least once.


## For Loops

A for loop, and similarly a for-each loop is a loop that performs the body "for each" item in a range or collection.

```dewy
loop i in 1:5
{
    print('{i}, ') 
}
``` 

Which prints out `1, 2, 3, 4, 5, ` to the console. For loops can also iterate over the items in any type of container. Iterating over a list looks like this

```dewy
loop fruit in ['apple' 'banana' 'peach' 'pear']
{
    print('I like to eat {fruit}!')
}
```

Which prints the following to the console

```
I like to eat apple
I like to eat banana
I like to eat peach
I like to eat pear
```

Items in a dictionary can be iterated over like so

```dewy
ratings = [
    'star wars' -> 73
    'star trek' -> 89
    'star gate' -> 84
    'battlestar galactica' -> 87
    'legend of the galactic heroes' -> 100
]

loop show, rating in ratings
{
    printl('I give {show} a {rating} out 100')
}

//TODO->syntax might change, depending on if dicts can return either 1 or 2 values for iterating over 
//loop show, rating in ratings.keys, ratings.values
//I think the 1 instance where left parameters doesn't match the right parameters is in the case of a single dict? otherwise you have to specify with _ to ignore
```

This prints out the following to the console

```
I give star wars a 73 out of 100
I give star trek a 89 out of 100
I give star gate a 84 out of 100
I give battlestar galactica a 87 out of 100
I give legend of the galactic heroes a 100 out of 100
```

Lastly, you can also put the loop condition at the end of the block, to ensure the block executes at least once

```
{
    //body is looped through 11 times.
}
loop i in 1:10
``` 

Note that the variable `i` does note exist on the first iteration of the loop, so do while loops don't tend to be used for iterating over lists or dictionaries. 

(TODO->perhaps talk about introspection to check if a variable exists, thus indicating actions to do/not do on the first iteration when the variable doesn't exist)

## Do Loop Do

Following the pattern that a regular loop has the condition at the top, and a do-loop has the condition at the bottom, we can construct a loop that is sandwiched between two loop bodies

```
{
    //occurs before condition is checked
}
loop i not =? 42
{
    //occurs after condition is checked
}
```

In this loop, the first block is guaranteed to execute at least once. Then we check the condition, and then if true, we execute the second block, then repeat the loop, execute the first block, and then check the condition again, repeating until the condition is false, or we have iterated over all elements. 

## Whitespace and Semicolons

If you're wondering how the loop keyword knows whether it's a regular `loop {block}` or a do-while `{block} loop`, so am I.

Absent any other indicators, the loop keyword will use the spacing between it and surrounding blocks of code or expressions, to determine what it is looping. If a block/expression is on the same line or adjacent line as the `loop` keyword, then that block will be executed as part of the loop

```
{
    //part of the loop
} loop condition {
    //part of the loop
}


{
    //part of the loop
}
loop condition
{
    //part of the loop
}


{
    //NOT part of the loop
}

loop condition
{
    //part of the loop
}



//This will (probably) raise an error during compilation as it is ambiguous
//the alternative might be whichever block is closer
{
    //NOT part of the loop
}

loop condition

{
    //NOT part of the loop
}

```

If you want to be more explicit about which block is attached to the loop, you can use `;` semicolons which act as a sort of empty block that binds to the loop. (Or you could use an actual empty block `{}`)

```
{
    //NOT part of the loop
};
loop condition
{
    //part of the loop
}

{
    //part of the loop
} loop condition; {
    //NOT part of the loop
}
```

## Break, Continue, Return inside Loops

TODO->write this. follows basic principles of other languages. extra is that you can use `#hashtags` to break/continue from inside nested loops

## Loop Generators

Let's look at this example

```
loop i in 1:10
{
    i
}
```

Every iteration of the loop, the current value of `i` is "expressed", that is to say, the value could be stored in a variable or a container.

Lets capture the expressed value in a container by wrapping the loop in `[]` brackets

```
[loop i in 1:10 {i}]
```

This "generates" the array `[1 2 3 4 5 6 7 8 9 10]`, which we can then store into a variable

```
my_array = [loop i in 1:10 {i}]

//optional to omit the braces since only a single expression is in the body
my_array = [loop i in 1:10 i]
```

And thus we have created the simplest list generator. 

### Multiple Expressions per Iteration

Generators can do a lot of interesting things. For example we can express multiple values on a single loop iteration

```
//note the braces are not optional in this case
my_array = [loop i in 1:5 { i i^2 }]
```

producing the array `[1 1 2 4 3 9 4 16 5 25]`. 

We can also construct a dictionary by expressing with a `->` between two values

```
squares = [loop i in 1:5 { i -> i^2 }]
```

which produces the dictionary `[1->1 2->4 3->9 4->16 5->25]` which points from values to their squares.

### Multidimensional Generators

You can generate a multidimensional array using multiple nested loops. For example

```
indices = 
[
    loop i in 1:5 
    [
        loop j in 1:5 
        [ 
            i 
            j 
        ] 
    ] 
]
```

which produces the following 3D array representing the indices of a 5x5 matrix as tuples

```
indices = [
    [[1 1] [1 2] [1 3] [1 4] [1 5]]
    [[2 1] [2 2] [2 3] [2 4] [2 5]]
    [[3 1] [4 2] [3 3] [3 4] [3 5]]
    [[4 1] [4 2] [4 3] [4 4] [4 5]]
    [[5 1] [5 2] [5 3] [5 4] [5 5]]
]
```

And so many more things are possible. Loop generators are about as flexible a feature as one could imagine. It's really up to you how you want to apply them


### (Maybe) Repeated Function Calls

(TODO->decide how this plays with function vectorization...)

In the same way a container can capture expressed items from a loop, and collect them all together, a function can capture expressed items from a loop, and perform a function on each item

```
//example definition of printl
printl = str => system.console.write('{s}\n')
printl( loop i in 1:10 {i} )
```

In this example, `printl` is called for each value of `i`, thus printing out

```
1
2
3
4
5
6
7
8
9
10
```