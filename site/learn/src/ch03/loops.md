# One Loop to Rule Them All

Other languages split looping across `for`, `while`, `do-while`, and `for-each`. Dewy uses one keyword, `loop`.

```dewy
loop <condition> <expression>
```

The condition must be a boolean. The expression is the body. Changing the condition is how you get every familiar loop shape.

## Infinite Loops

```dewy
loop true
{
    # something forever
}
```

Leave with `break` or `return`.

## While Loops

```dewy
loop i >? 0
{
    # while i is greater than 0
}
```

## For Loops

`in` does two things:

1. The name on the left gets the next value of the iterable on the right, or `undefined` if there is nothing left.
2. The expression is `true` when a value was produced, `false` when the iterable is exhausted.

That is enough to write a for-each:

```dewy
loop i in 1..5
{
    print('{i}, ')
}
```

This prints `1, 2, 3, 4, 5, `. Integer ranges default to a unit step. A second anchor sets another step, including a negative one:

```dewy
loop even in 0,2..10 { printl(even) }
loop descending in 5,4..0 { printl(descending) }
```

The step is the second anchor minus the first. A step-size of zero is an iteration error. `0..` starts at 0 and never ends. `..10` has no first value and cannot be iterated.

Any container works:

```dewy
loop fruit in ['apple' 'banana' 'peach' 'pear']
{
    print('I like to eat {fruit}!')
}
```

Iterating a dictionary yields pairs, which you can unpack:

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

> **Provisional design:** General unpack-and-collect syntax must extend this iterator model without introducing a separate loop grammar. Its complete binding forms are not yet specified.

## Multiple Conditions

Because `in` returns a boolean, you can combine iterators with logical operators. `and` is zip. The loop stops when the first sequence ends.

```dewy
names = ['Alice' 'Bob' 'Charlie']
colors = ['Red' 'Blue' 'Green' 'Yellow']

loop name in names and color in colors
    printl'{name} chose {color}'
```

```
Alice chose Red
Bob chose Blue
Charlie chose Green
```

Enumerate by zipping an infinite range:

```dewy
loop i in 0.. and fruit in ['apple' 'banana' 'peach' 'pear']
    printl'{i}) {fruit}'
```

```
0) apple
1) banana
2) peach
3) pear
```

`or` continues while either side still has values. Exhausted names become `undefined`:

```dewy
A = [1 2 3]
B = [4 5 6 7 8]
loop a in A or b in B
    printl[a b]
```

```
[1 4]
[2 5]
[3 6]
[undefined 7]
[undefined 8]
```

Any boolean formula is allowed. Multiiterator conditions are eager even though ordinary `and` and `or` short-circuit. Each `in` leaf advances once, left to right, then the formula is evaluated. An exhausted leaf assigns `undefined` and contributes `false`. The formula then uses the truth table for `and`, `or`, `xor`, `nand`, `nor`, and `xnor`.

> NOTE: A formula such as `xnor` can stay true after every input is exhausted, creating an infinite loop unless `break` is hit.
>
> ```dewy
> loop i in 1..26 xnor c in 'a'..'z' {
>     # never exits, even after `i` and `c` run out
> }
> ```
>
> In general one should stick to `and`, and `or` when combining iterators.

The compiler types each target as plain `T` when it is defined on every reachable body iteration, and as `T | undefined` when an iteration can happen after that input is exhausted. Narrow optionals before use:

```dewy
short_list = [1 2 3]
long_list = ['this' 'is' 'a' 'long' 'list' 'of' 'values']
loop short in short_list or long in long_list
{
    if short isnt? undefined {
        process(short)
    }
    process(long)
}
```

You can also combine iterators with arbitrary conditions

```dewy
limit = time.now + 5(minutes)
loop batch in batches and time.now <? limit
    process(batch)
```

> NOTE: iterators combined with conditions DO short circuit. e.g.
>
> ```dewy
> loop i in task_list or time.now <? limit {
>    # `time.now <? limit` is only checked after the task list is exhausted
> }
> ```

## Early Exit

The condition always sits in front of the body. For work before the decision, use `loop true` and `break`.

```dewy
i = 0
loop true
{
    i += 1
    printl'this runs at least once'
    if i >=? 20 break
}
```

A flow condition has its own scope, so `if item in items ...` would keep `item` inside that `if`. Bind in the surrounding body when later statements need the item:

```dewy
loop true
{
    prepare()
    got_item = item in items  # save bool: there are more values | exhausted
    if not got_item break
    process(item)
}
```

After `if not got_item break`, `item` is defined for the rest of the body.

When the taken work is a single expression, a compact `if` / `else` is fine:

```dewy
loop true
{
    prepare()
    if item in items process(item) else break
}
```

Once `process` is more than one expression, prefer the `got_item` form so the rest of the body stays at the happy-path indent.

## Break, Continue, Return Inside Loops

`break` leaves the nearest enclosing loop. `continue` starts that loop's next iteration. `return` leaves the containing function.

```dewy
loop running
{
    if should_skip { continue }
    if finished { break }
    process()
}
```

`$name` names the surrounding `{ }` or file scope. `break $name` or `continue $name` then hits the nearest loop inside that scope.

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

`$rows` is not attached to the next loop. It labels every loop directly inside that scope, so two loops next to each other may share it. Putting `$rows` just before the first loop that uses it is the usual style.

The name is visible throughout its scope, even on lines above it. Two `$rows` in the same scope is an error, and a nested scope cannot hide an outer one that is still active. A sibling block may reuse the name. Labels do not cross function boundaries.

## Loop Generators

A loop _expresses_ the value of its body each iteration. Wrap the loop in `[]` to capture those values:

```dewy
loop i in 1..10 {i}

my_array = [loop i in 1..10 {i}]  # `{}` are not necessary for a single value
```

That produces `[1 2 3 4 5 6 7 8 9 10]`.

Several values per iteration:

```dewy
my_array = [loop i in 1..5 { i i^2 }]
# [1 1 2 4 3 9 4 16 5 25]
```

`->` builds a dictionary instead:

```dewy
squares = [loop i in 1..5 i -> i^2 ]
# [1->1 2->4 3->9 4->16 5->25]
```

Nested loops build higher dimensions:

```dewy
indices = [
    loop i in 1..5 [
        loop j in 1..5
            [i j]
    ]
]
```

```
indices = [
    [[1 1] [1 2] [1 3] [1 4] [1 5]]
    [[2 1] [2 2] [2 3] [2 4] [2 5]]
    [[3 1] [3 2] [3 3] [3 4] [3 5]]
    [[4 1] [4 2] [4 3] [4 4] [4 5]]
    [[5 1] [5 2] [5 3] [5 4] [5 5]]
]
```
