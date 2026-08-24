# Effects

An effect describes an observable interaction a function may perform beyond producing its return value. Effects let callers and the compiler reason about mutation, blocking, I/O, allocation, failure, and other behavior relevant to composition.

## `noreturn`

`noreturn` is a settled effect marking a function that does not return to its caller:

```dewy
let die = (message:string):>noreturn => {
    printl(message)
    exit(1)
}
```

It is not the same as `never`. `noreturn` describes what the call does; `never` is the type of a path with no resulting value.

## Why Effects Belong in Contracts

Knowing that a function only reads a value allows the compiler to preserve refinements and borrow storage invisibly. Knowing that it may mutate, block, or escape a value changes what remains safe afterward.

Effects are therefore not only documentation. They participate in call checking, optimization, lifetime reasoning, and the construction of restricted execution environments.

## General Effect Design

> **Provisional design:** The full effect vocabulary and syntax are not yet fixed. It must support inferred ordinary code, explicit public contracts, transitive effects through calls, effect-polymorphic helpers, and deliberate handling or masking at a clear boundary.

The design should keep common programs uncluttered: most local effects should be inferred, while APIs state the effects that matter to their callers.
