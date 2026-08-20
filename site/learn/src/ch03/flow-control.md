# Flow Control

The two main ways to choose what runs next are `if` and `loop`. Both are
expressions.

## If Expressions

```dewy
my_var = 10
if my_var =? 10
    printl"my_var is ten"
```

The form is `if <condition> <expression>`. The condition has to be a
boolean. The body is often a block:

```dewy
if a >? b
{
    # do something
}
```

## Loop Expressions

```dewy
i = 0
loop i <? 10
{
    printl"i is {i}"
    i += 1
}
```

There is no separate do-while form. To run a body at least once, or to
decide in the middle, use `break` inside `loop true`. See
[Early Exit](loops.md#early-exit).

Loops are covered in more detail in
[One Loop to Rule Them All](loops.md).

## Flow Chains

`else` chains them. The last piece does not have to be `if` or `loop`:

```dewy
my_var = 'apple'
if my_var =? 'banana'
    printl'A fruit enjoyed by monkeys'
else
    printl'monkeys don\'t like {my_var}, only bananas!'
```

```dewy
my_var = 42
if my_var <=? 10
    printl'a small number'
else if my_var <=? 50
    printl'a medium number'
else
    printl'a number larger than 50'
```

`loop` can sit in the chain as well:

```dewy
if a >? b
{
    printl'a is greater than b'
}
else loop a <? b
{
    printl'a is less than b. Increasing a until it matches b'
    a += 1
}
else
{
    printl'a is equal to b'
}
```

The conditions share a scope. A binding introduced in an earlier
condition is visible to later conditions, and to a later body, if they
run.

```dewy
if (got = item in items got)
    process(item)
else
    printl'no item'
```

## Capturing Values

`if` is Dewy's ternary. The branch you take is the value of the whole
expression:

```dewy
my_fruit = 'kiwi'
tropical_fruits = ['banana' 'pineapple' 'kiwi' 'papaya']
my_var = if my_fruit in? tropical_fruits
    'a tropical fruit'
else
    'some other type of fruit'
```

`my_var` is `'a tropical fruit'`. An `if` with no `else`, used as a
statement, is `void`.

Values from a loop become a sequence when you capture them. See
[Loop Generators](loops.md#loop-generators).

## `break`, `continue`, `return`

`break` and `continue` can name an outer loop with `$outer`. The rules
are on
[the loops page](loops.md#break-continue-return-inside-loops).

`return` leaves the function.

## Match

There will be a `match` for picking among patterns. The syntax is not
yet determined.

## Finally

A `finally` that always runs at the end of a chain is not yet determined.
