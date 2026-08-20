# One Loop to Rule them All

Other languages make use of sometimes multiple keywords such as `for`, `while`, `do-while`, `for each`, etc., to handle looping over a piece of code. Dewy instead simply uses the `loop` keyword to handle all forms of looping.

Syntactically, loops are quite simple. The syntax for a loop is:

```dewy
loop <condition> <expression>
```

Where `<condition>` (which must result in a boolean) determines if the loop continues, and `<expression>` (which can be anything) is executed each time the loop repeats.

The various types of loops seen in other languages are formed simply by changing the `<condition>` part of the loop.

## Infinite Loops

An infinite loop is one that never ends. They are constructed by hardcoding the condition to `true`, which ensures that the loop will always repeat.

```dewy
loop true
{
    #do something repeatedly forever
}
```

The only way to leave an infinite loop is via the `break`, and `return` keywords.

## While Loops

A while loop is a loop that executes "while" some condition is true. A simple boolean expression can be used as the condition. When the condition is false, the loop ends.

```dewy
loop i >? 0
{
    #while i is greater than 0, do something
}
```

## For Loops

Many languages feature for loops, which iterate over some iterable object. The simplest case of this would be iterating over a range of numbers. In Dewy, the `in` operator manages iteration for loops. `in` has two aspects:

1. the variable on the left is assigned with the next value of the iterable on the right (or `undefined` if there are no more values)
2. the expression returns `true` or `false` depending on if there was a value to assign to the variable this iteration.

This means that `in` expressions can be used to trivially construct a for-loop.

```dewy
loop i in [1..5]
{
    print('{i}, ')
}
```

Which prints out `1, 2, 3, 4, 5, ` to the console. Each iteration, `in` causes `i` to be assigned the next value in the sequence, while returning true for the loop condition. When the sequence is exhausted, `in` returns false, and the loop ends.

Integer ranges use a unit step by default. A second anchor specifies another
step, including a negative one:

```dewy
loop even in 0,2..10 { printl(even) }
loop descending in 5,4..0 { printl(descending) }
```

The step is the second anchor minus the first. A zero step is an iteration
error. A right-unbounded form such as `0..` has a first value and is
semantically iterable forever; a left-unbounded form such as `..10` has no
first value and cannot be iterated.

The current udewy target intentionally rejects right-unbounded iteration until
bigint-backed iterator values are available. This preserves Dewy's
arbitrary-precision semantics instead of allowing an `int64` counter to wrap.

For loops can also iterate over the items in any type of container. Iterating over a list looks like this

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

loop [show rating] in ratings
{
    printl('I give {show} a {rating} out 100')
}
```

This takes advantage of the fact that iterating over a dictionary returns each pair, which can then be unpacked into separate variables `show` and `rating`. This prints out the following to the console

```
I give star wars a 73 out of 100
I give star trek a 89 out of 100
I give star gate a 84 out of 100
I give battlestar galactica a 87 out of 100
I give legend of the galactic heroes a 100 out of 100
```

### Multiple Conditions

A neat side effect of `in` statements returning a boolean is that it provides a free method for looping over multiple sequences simultaneously. Simply combine two `in` statements with a logical operator. The loop will continue until one sequence is exhausted, both, or something else, depending on which logical operator is used. The behavior `zip` from other languages can be achieved by combining sequences with `and`

```dewy
names = ['Alice' 'Bob' 'Charlie']
colors = ['Red' 'Blue' 'Green' 'Yellow']

loop name in names and color in colors
    printl'{name} chose {color}'
```

In this case, the loop runs until either sequence is exhausted (as `and` requires both conditions to be true, so as soon as one is false, the loop ends). This prints out the following to the console

```
Alice chose Red
Bob chose Blue
Charlie chose Green
```

Other languages commonly have an `enumerate` function which will count how many iterations have occurred on top of looping over some sequence. This can be achieved by combining an infinite range with any sequence using `and`:

```dewy
loop i in [0..] and fruit in ['apple' 'banana' 'peach' 'pear']
    printl'{i}) {fruit}'
```

`i` will never run out of values, so the loop continues so long as `fruit` has values remaining. This prints out the following to the console

```
0) apple
1) banana
2) peach
3) pear
```

Using the `or` operator to combine sequences will loop until so long as either of the sequences have values remaining.

```dewy
A = [1 2 3]
B = [4 5 6 7 8]
loop a in A or b in B
    printl[a b]
```

Which prints

```
[1 4]
[2 5]
[3 6]
[undefined 7]
[undefined 8]
```

Since this is just combining boolean expressions, any combination of expressions that results in a boolean may be used.

Multiiterator conditions are eager even though ordinary Boolean `and` and `or`
expressions short-circuit. Each `in` leaf advances exactly once, from left to
right, before the logical formula is evaluated. An exhausted leaf assigns
`undefined` and contributes `false`; the formula then uses its literal truth
table for `and`, `or`, `xor`, `nand`, `nor`, and `xnor`. Consequently, a formula
such as `nor` can remain true after every input is exhausted and continue until
the body exits explicitly.

The compiler uses known iterator lengths to type each target. A target is plain
`T` when it is defined on every reachable body iteration and `T | undefined`
when the condition can admit an iteration after that input is exhausted. When
lengths cannot be proven, the safe fallback is `T | undefined`. Optional targets
must be narrowed before use:

```dewy
loop short_item in short_items or long_item in long_items
{
    if short_item isnt? undefined {
        process(short_item)
    }
    process(long_item)
}
```

```dewy
limit = time.now + 5(minutes)
loop batch in batches and time.now <? limit
    process(batch)
```

As a similar approach, perhaps there might be iterators in this style where they don't have a fixed value, but instead track over some changing resource

```dewy
loop batch in batches and t in timer(5(minutes))
{
    process(batch)
    printl'timeout in {t}'
}
```

## Early Exit

There is no separate do-while or mid-test loop. The condition always sits in front of the body. To run some work before deciding whether to continue, use `loop true` and `break`.

A loop that should run at least once looks like this:

```dewy
i = 0
loop true
{
    i += 1
    printl'this runs at least once'
    if i >=? 20 break
}
```

The same shape covers a decision in the middle of the body, including advancing an iterator with `in`. A flow condition has its own scope, so `if item in items ...` would keep `item` inside that `if`. Bind in the surrounding body when later statements need the item:

```dewy
loop true
{
    prepare()
    got_item = item in items
    if not got_item break
    process(item)
}
```

`in` assigns the next value (or `undefined` when the iterator is exhausted) and returns whether a value was produced. After `if not got_item break`, `item` is defined for the rest of the body.

When the taken work is a single expression, a compact `if`/`else` is also fine:

```dewy
loop true
{
    prepare()
    if item in items process(item) else break
}
```

Once `process` is more than one expression, prefer the `got_item` form from above so the rest of the body stays at the happy-path indent.

## Break, Continue, Return inside Loops

`break` exits the nearest enclosing loop, while `continue` begins that loop's
next iteration. `return` leaves the containing function.

```dewy
loop running
{
    if should_skip { continue }
    if finished { break }
    process()
}
```

A scope metatag can select an outer loop from nested control flow. A bare
`$name` declares a generic metatag for its entire lexical scope. A labeled
`break` or `continue` targets the nearest enclosing loop whose parent scope
declares that name:

```dewy
$rows
loop next_row()
{
    loop next_column()
    {
        if retry_row() { continue $rows }
        if table_complete() { break $rows }
        process_cell()
    }
}
```

The metatag is not syntactically attached to the following loop. It is a scope
marker that labels every loop directly contained by that scope, so multiple
sibling loops may share it. Placing the metatag immediately before the first
loop that uses it is the conventional style.

Scope metatags are visible throughout their scope, including before their
source position. Declaring the same name twice in one scope is an error, as is
shadowing an active metatag in a nested scope. The same name may be reused in
disjoint sibling scopes after the first declaration is no longer visible.
Labels never cross function boundaries.

The compiler reports an error when a labeled exit names an unknown metatag, or
when the metatag is visible but its scope is not the parent of an enclosing
loop. The latter commonly means the marker was placed inside the loop body
instead of in the loop's parent scope.

## Loop Generators

Let's look at this example

```dewy
loop i in [1..10] {i}
```

Every iteration of the loop, the current value of `i` is "expressed", that is to say, the value could be stored in a variable or a container.

Lets capture the expressed value in a container by wrapping the loop in `[]` brackets

```dewy
[loop i in [1..10] {i}]
```

This "generates" the array `[1 2 3 4 5 6 7 8 9 10]`, which we can then store into a variable

```dewy
my_array = [loop i in [1..10] {i}]

#optional to omit the braces since only a single expression is in the body
my_array = [loop i in [1..10] i]
```

And thus we have created the simplest list generator.

### Multiple Expressions per Iteration

Generators can do a lot of interesting things. For example we can express multiple values on a single loop iteration

```dewy
#note the braces are not optional in this case
my_array = [loop i in [1..5] { i i^2 }]
```

producing the array `[1 1 2 4 3 9 4 16 5 25]`.

We can also construct a dictionary by expressing with a `->` between two values

```dewy
squares = [loop i in [1..5] { i -> i^2 }]
```

which produces the dictionary `[1->1 2->4 3->9 4->16 5->25]` which points from values to their squares.

### Multidimensional Generators

You can generate a multidimensional array using multiple nested loops. For example

```dewy
indices =
[
    loop i in [1..5]
    [
        loop j in [1..5]
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
