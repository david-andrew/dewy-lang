# Dewy at a Glance

Dewy aims to make the straightforward version of a program look straightforward. This tour shows the language's main ideas without trying to teach every rule at once.

## Small Programs Stay Small

<!-- dewy-example: compiler -->
```dewy
name = "Dewy"
printl"Hello, {name}!"
```

Bindings do not require a declaration keyword when the meaning is clear. `let` and `const` are available when you want to state mutability explicitly.

```dewy
let attempts = 0
const limit = 3
attempts += 1
```

## Expressions Compose

Conditionals and blocks produce values:

```dewy
let access = if signed_in
    "account"
else
    "sign in"

let circumference = {
    let diameter = 2 * radius
    pi * diameter
}
```

Declarations and assignments produce `void`, so the circumference block expresses only its final calculation.

## Functions Read Like Their Calls

<!-- dewy-example: compiler -->
```dewy
let greet = (name:string greeting:string="Hello"):>void =>
    printl"{greeting}, {name}!"

greet("Ada")
greet("Grace" greeting="Welcome")
```

Parameters may be supplied by position or name. Defaults are evaluated for each call that needs them.

## One Loop Covers the Common Cases

```dewy
loop true reconnect()                       # repeat forever

loop attempts <? limit attempts += 1       # repeat while true

loop task in pending
    process(task)                           # consume an iterator

loop i in 0.. and task in pending
    printl"{i}: {task}"                     # combine iterators
```

A loop may also express values for a surrounding container to collect:

```dewy
let active_names = [
    loop user in users
        if user.active
            user.name
]
```

## Text Means User-Perceived Characters

Strings are immutable sequences of Unicode grapheme clusters. Iteration and indexing therefore treat a family emoji or an accented character as one element:

<!-- dewy-example: compiler -->
```dewy
text = "café 👨‍👩‍👧‍👦 🍀"

loop i in 0.. and character in text
    if character not =? ' '
        printl"{i}: {character}"
```

Byte and scalar views remain available when a program actually needs those representations.

## Values Do Not Alias by Accident

<!-- dewy-example: compiler -->
```dewy
let original = [1 2 3]
let edited = original
edited[0] = 9                 # original is still [1 2 3]
```

Use a place when a function should deliberately update the caller's value:

<!-- dewy-example: compiler -->
```dewy
let reset = (@value:int64):>void => (value = 0)

let count:int64 = 42
reset(@count)
```

The `@` appears in both the function contract and the call, so shared mutation is visible where it matters.

## Objects Need No Class Sublanguage

An object is a structural value with named fields. A constructor is an ordinary function that returns one:

<!-- dewy-example: compiler -->
```dewy
let Counter:type = [value:int64 increment:<():>void>]

let counter = (start:int64=0):>Counter => [
    value = start
    increment = () => (value += 1)
]

let count = counter(40)
count.increment
count.increment
printl"count is {count.value}"
```

Functions inside an object can use sibling fields directly.

## Types Add Meaning Where It Helps

```dewy
let names:array<string> = ["Ada" "Grace"]
let answer:int64 | undefined = find_answer()

if answer isnt? undefined
    printl"the answer after this one is {answer + 1}"
```

Overloads use the same function syntax and are selected by their contracts:

<!-- dewy-example: compiler -->
```dewy
let format = ((value:int64):>string => "integer {value}")
           & ((value:string):>string => value)

format(42)
format("already text")
```

## Specialized Domains Use the Same Language

Physical quantities are one example of Dewy's general type model carrying useful facts:

```dewy
let timeout = 300ms
sleep(timeout)

let distance = 120m
let elapsed = 10s
let speed = distance / elapsed
```

The unit portion can be checked and simplified at compile time rather than requiring a large runtime wrapper. The same goal—express meaning clearly, prove what can be proved, and keep runtime representation minimal—guides Dewy's facilities for applications, services, systems work, and numerical programming alike.

Continue with [Getting Started](ch01/00-getting-started.md), or use the [Language Feature Index](01-features-list.md) to jump to a particular subject.
