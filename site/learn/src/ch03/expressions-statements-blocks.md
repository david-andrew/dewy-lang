# Expressions, Produced Values, and Blocks

Dewy is expression-based. A literal, call, conditional, block, or loop can participate in a larger expression when it produces a value.

```dewy
let answer = 42
let larger = answer + 1
let label = if larger >? 40 "large" else "small"
```

## Values, `void`, and `never`

Most expressions produce a value. Some operations perform useful work without producing one; their type is `void`.

Declarations, ordinary assignments, and `printl` are common `void` expressions:

```dewy
let count = 0       # void
count += 1          # void
printl"ready"       # void
```

`never` describes a path that cannot complete normally, such as an exit operation. It is not another spelling of `void`.

`undefined` is different again: it is a real value that can be stored in an optional type. [Optional Values and Narrowing](optional-types.md) develops that distinction.

## Suppressing a Value

An attached semicolon evaluates an expression but suppresses what it would otherwise produce:

```dewy
let selected = [
    load_primary();
    load_secondary()
]
```

Both calls run, but the array collects only the value from `load_secondary()`.

The semicolon is attached to the expression it suppresses. It is not general statement-ending punctuation. An unattached semicolon is reserved for selecting another array dimension.

## Blocks

`{}` forms a scoped block. Expressions inside run from top to bottom, and the block expresses their non-`void` results:

```dewy
let circumference = {
    let diameter = 2 * radius
    pi * diameter
}
```

The declaration is `void`, so the block produces only `pi * diameter`. `diameter` belongs to the child scope and is not visible afterward.

Parentheses also group expressions, but do not create a child lexical scope:

```dewy
let result = (1 + 2) * 3
```

A block can express several values when its surrounding context knows how to collect them:

```dewy
let digits = [{ 1 2 3 }]
```

Loops use the same rule, which is why an array-producing loop needs no separate comprehension syntax. [Loop Capture](../ch03/loops.md#loop-capture) falls out for free.

## Comments

`#` begins a line comment. `#{ ... }#` is a nestable block comment:

```dewy
# one line
#{
    an outer comment
    #{ with a nested comment }#
}#
```

Comment markers inside strings are ordinary string contents.

The Reference specifies [evaluation behavior](../../reference/expressions-and-operators.html) and [operator grouping](../../reference/operators-and-precedence.html) precisely.
