# Flow Control

## If Expressions
If expressions allow you to conditionally evaluate code based on whether or not some condition is met.

```
my_var = 10
if my_var =? 10 
{
    printl("my_var is ten")
}
``` 

If statements require the expression to be a `boolean` value. Any other type will result in a compilation error.

If the first condition is false, you can use an `else` clause to execute something else instead

```
my_var = 'apple'
if my_var =? 'banana' 
{
    printl('A fruit enjoyed by monkies')
}
else
{
    printl('monkies don\'t like {my_var}, only bananas!')
}
```

You can also nest multiple conditions using `else if`

```
my_var = 42
if my_var <=? 10
{
    printl('a small number')
}
else if my_var <=? 50
{
    printl('a medium number')
}
else
{
    printl('a number larger than 50')
}
```

Unlike if statements from other languages, ifs in Dewy are expressions, allowing them to be used like the ternary operator from other languages

```
my_fruit = 'kiwi'
tropical_fruits = ['banana' 'pineapple' 'kiwi' 'papaya']
my_var = if my_fruit in? tropical_fruit
{
    'a tropical fruit'
}
else
{
    'some other type of fruit'
}
```

`my_var` would have a value of `'a tropical fruit'` at the end of the above example.


## Loops Expressions

All loop behavior is handled with the `loop` keyword. It is capable of performing every other type of loop, including while, for, do-while, and infinite loops from other languages.

Basic examples of loops

```
loop 
{
    printl('this is an infinite loop')
}

i = 0
loop my_var <? 10
{
    i += 1
    printl('this is a while loop')
}

loop i in 0:10
{
    printl('this is a for loop')
}
```

The do-while version of the loop can be constructed by putting the loop keyword after the block to loop. This can also be performed with for and infinite versions of the loop. In each case, the loop body is executed once before the condition is checked. The syntax is still slightly TBD--currently this is the only syntax in the language that relies on whitespace to determine what the user intends

```
i = 0
{
    i += 1
    printl('this is a do-while loop')
}
loop i <? 20


{
    printl('this is a do-for loop')
}
loop i in 0:10

{
    printl('this is a do-infinite loop')
}
loop
```

Lastly you can combine the normal loop with the do form of the loop. This will give you a block executed before the condition and a block executed after the condition

```
i = 0
{
    printl('before condition is checked')
}
loop i <? 20
{
    printl('after condition is checked')
    i += 1
}
```

## Match Expressions

(TODO) switch statement equivalent

## Break, Continue, Return, <expr-return>

(TODO) branch inside body of conditional

## Advanced Flow Control

(TODO) combining conditionals
(TODO) list and dictionary generators