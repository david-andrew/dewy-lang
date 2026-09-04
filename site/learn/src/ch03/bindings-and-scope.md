# Bindings and Scope

A binding attaches a name to a value. `let` is mutable. `const` is not. Assigning to a name that has no visible binding implicitly creates a `let`.

```dewy
let mutable = 1
const fixed = 2
inferred = 3       # same as let inferred = 3
mutable = 5        # updates the original `mutable`
mutable += fixed
inferred = inferred + 1
```

Type annotations go after a colon:

```dewy
let count:int = 10
const name:string = 'Dewy'
let Pair:type = [left:int64 right:int64]
```

## Unpacking

A `[…]` of names on the left of `=` takes a value apart. An object unpacks **by field name**: each target takes the field of that name, in any order, and fields you leave out are simply not taken. Arrays unpack **by position**, and so do dictionaries and sets, in insertion order: every element must be named, `_` discards one, and a nested `[…]` unpacks an element further — a dictionary's entries are `[key value]` pairs. `let` (or `const`) declares the names; a bare unpack declares the new ones and assigns the ones already in scope, like any bare `a = …`.

<!-- dewy-example: compiler -->

```dewy
let Hit:type = [length:int64 name:string]
let hits:array<Hit> = [Hit[length=3 name="a"] Hit[length=10 name="b"]]
[name length] = hits[0]         # by name; the element is read once
let [first _ last] = [10 20 30] # by position
[first last] = [last first]     # a swap: both names exist, so both are assigned
let ages = ['ann' -> 30  'bob' -> 7]
let [[k1 v1] [k2 v2]] = ages    # entries in insertion order
let [m1 m2] = set[7 8]          # members in insertion order
```

Positional unpacking needs the count to be known: a literal, an exact-length annotation, or a growable array (or dictionary) whose length is a proven fact at that point (`xs.push` steps it). A runtime-length container is an error there — index or look up what you need under a guard instead.

## Scope

A name is visible in the `{ }` block where you declared it, and in any child blocks. A name declared inside can hide an outer one and disappears when the block ends. `( )` does not start a new scope. It shares the surrounding one.

```dewy
let x = 1
{
    let x = 2   # shadows the outer x
    printl'{x}' # 2
}
printl'{x}'     # 1
```

Code that runs right away cannot read a name before it is set. Function bodies may use names declared later in the same scope. The compiler checks that the name is set at each place that can actually call the function. That is how two functions can call each other, and why a helper can sit below the function that uses it.

```dewy
let first = ():>int64 => second()
let second = ():>int64 => 20

printl(first())  # ok to call at this point
```
