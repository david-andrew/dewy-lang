# Flow Control

In Dewy, the two main methods of conditionally executing code are `if` and `loop` expressions.

## If Expressions

If expressions allow you to conditionally evaluate code based on whether or not some condition is met.

```dewy
my_var = 10
if my_var =? 10
    printl"my_var is ten"
```

The syntax for an `if` expression is:

```dewy
if <condition> <expression>
```

where `<condition>` must result in a boolean value, and `<expression>` can be anything. Commonly, `<expression>` will be a block containing multiple expressions.

```dewy
if a >? b
{
    %do something
    %do another thing
}
```

## Loop Expressions

Loop expressions allow you to repeat the execution of some code while some condition is met.

```dewy
i = 0
loop i <? 10
{
    printl"i is {i}"
    i += 1
}
```

The syntax for a `loop` expression is:

```dewy
loop <condition> <expression>
```

where `<condition>` must be an expression that evaluates to a boolean value, and `<expression>` can be anything.

Loops will be explored in more detail in [One Loop To Rule Them All](loops.md).

## Flow Chains

Multiple flow expressions can be chained together via the `else` operator, along with an optional final default case that need not be a flow expression. In normal languages, this would be `if-else-if` kinds of sequences, which are certainly possible in Dewy:

```dewy
my_var = 'apple'
if my_var =? 'banana'
    printl'A fruit enjoyed by monkeys'
else
    printl'monkeys don\'t like {my_var}, only bananas!'
```

or even

```dewy
my_var = 42
if my_var <=? 10
    printl'a small number'
else if my_var <=? 50
    printl'a medium number'
else
    printl'a number larger than 50'
```

But Dewy also allows `loop` expressions to be combined in this way as well:

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

In the above example, if `a` is greater than `b`, the first block would be executed, and the rest of the blocks are skipped. If `a` is less than `b`, the loop in the second block executes, incrementing `a` until it is equal to `b`, at which point the rest of the chain is skipped. Only if `a` is neither greater than nor less than `b` (i.e. `a` equals `b`) will the final block be executed exclusively.

(TODO: add an example for how all conditions share the same scope, so variables defined in one condition will be available in later bodies if they execute)

(TODO: probably add a `finally` operator which can be used to always execute code at the end)

## Capturing Values

Unlike if statements from other languages, `if`s and `loop`s in Dewy are themselves expressions, allowing any expressed values to be captured. `if` expressions basically act like Dewy's version of the ternary operator

```dewy
my_fruit = 'kiwi'
tropical_fruits = ['banana' 'pineapple' 'kiwi' 'papaya']
my_var = if my_fruit in? tropical_fruit
    'a tropical fruit'
else
    'some other type of fruit'
```

`my_var` would have a value of `'a tropical fruit'` at the end of the above example.

Values from loops can be captured to construct sequences, which is explored more in [One Loop To Rule Them All](loops.md#loop-generators).

## Match Expressions

(TODO) switch statement equivalent

## Break, Continue, Return, <expr-return>

(TODO) branch inside body of conditional

## Advanced Flow Control

(TODO) combining conditionals
(TODO) list and dictionary generators
