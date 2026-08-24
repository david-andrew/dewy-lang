# Effects

An effect describes an observable interaction a function may perform beyond producing its return value. Effects let callers and the compiler reason about mutation, blocking, I/O, allocation, failure, and other behavior relevant to composition.

## `noreturn`

`noreturn` is the settled semantic effect of a function that does not return to its caller. The result of calling such a function has type `never`:

```dewy
let die = (message:string):>never => {
    printl(message)
    exit(1)
}
```

The two ideas remain distinct: `noreturn` describes what the call does, while `never` is the type of the path after that call. The spelling for declaring `noreturn` in a general effect contract has not been selected, so this book does not place it in the return-type position.

## Why Effects Belong in Contracts

Knowing that a function only reads a value allows the compiler to preserve refinements and borrow storage invisibly. Knowing that it may mutate, block, or escape a value changes what remains safe afterward.

Effects are therefore not only documentation. They participate in call checking, optimization, lifetime reasoning, and the construction of restricted execution environments.

## General Effect Design

> **Provisional design:** The full effect vocabulary and syntax are not yet fixed. It must support inferred ordinary code, explicit public contracts, transitive effects through calls, effect-polymorphic helpers, and deliberate handling or masking at a clear boundary.

The design should keep common programs uncluttered: most local effects should be inferred, while APIs state the effects that matter to their callers.
