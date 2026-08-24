# Branching and Flow Control

## `if` Expressions

An `if` chooses the first body whose condition is true:

```dewy
if temperature <? freezing
    printl"solid"
else if temperature <? boiling
    printl"liquid"
else
    printl"gas"
```

Because it is an expression, an exhaustive conditional can produce a value:

```dewy
let phase = if temperature <? freezing
    "solid"
else if temperature <? boiling
    "liquid"
else
    "gas"
```

The alternatives must produce compatible types. A conditional without `else` normally produces `void`, because no body may run.

## Blocks as Alternatives

Use `{}` when an alternative needs several operations:

```dewy
let result = if cached isnt? undefined {
    record_hit()
    cached
} else {
    let loaded = load()
    record_miss()
    loaded
}
```

Declarations and bookkeeping assignments are `void`; each block produces its final value.

## Narrowing Along the Flow

Conditions establish facts inside their bodies:

```dewy
let answer:int64 | undefined = lookup()

if answer isnt? undefined
    printl"next is {answer + 1}"
```

Earlier failed alternatives also establish facts in later ones. Assignment or a call that may mutate the tested value invalidates facts that are no longer guaranteed.

## Short-Circuit Conditions

`and` evaluates its right side only if the left side succeeds. `or` evaluates its right side only if the left side fails. `nand`, `nor`, `xor`, and `xnor` follow their Boolean definitions.

This makes guarded use concise:

```dewy
if user isnt? undefined and user.active
    open_dashboard(user)
```

## Exiting Control Flow

`return` exits the current function. `break` exits a loop, and `continue` begins its next condition evaluation.

```dewy
let find = (items:array<int64> wanted:int64):>int64 | undefined => {
    loop item in items
        if item =? wanted
            return item
    return undefined
}
```

Labeled exits can target an enclosing loop; [Loops and Multiple Iterators](loops.md) develops those forms.

> **Provisional design:** Pattern matching, unconditional cleanup/finally behavior, and typed error propagation must compose with these expression and narrowing rules. Their complete surface syntax is not yet specified.
