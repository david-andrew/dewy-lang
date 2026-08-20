# Bindings and Scope

A binding attaches a name to a value. `let` is mutable. `const` is not.
Assigning to a name that has no visible binding implicitly creates a
`let`.

```dewy
let mutable = 1
const fixed = 2
inferred = 3
mutable += fixed
inferred = inferred + 1
```

Type annotations go after a colon:

```dewy
let count:int = 10
const name:string = 'Dewy'
let Pair:type = [left:int64 right:int64]
```

## Scope

A name is visible in the `{ }` block where you declared it, and in
blocks inside that one. A name declared inside can hide an outer one
and disappears when the block ends. `( )` does not start a new scope.
It shares the surrounding one.

```dewy
let x = 1
{
    let x = 2   # shadows the outer x
    printl'{x}' # 2
}
printl'{x}'     # 1
```

Code that runs right away cannot read a name before it is set.
Function bodies may use names declared later in the same scope. The
compiler checks that the name is set at each place that can actually
call the function. That is how two functions can call each other, and
why a helper can sit below the function that uses it.

```dewy
let first = ():>int64 => second()
let second = ():>int64 => 20
```

Chained `if` / `else if` / `else` conditions share a scope, so a binding
from an earlier condition is visible to later ones if they run. See
[Flow Control](flow-control.md).

## Comments

`#` starts a line comment. `#{` and `}#` wrap a block comment.

```dewy
# one line
#{ more
   than one line }#
```
