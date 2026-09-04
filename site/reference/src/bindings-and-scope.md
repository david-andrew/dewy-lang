# Bindings, Initialization, and Scope

## Declarations

`let` creates a mutable binding. `const` creates a binding that cannot be reassigned after initialization.

```dewy
let count = 0
const limit = 10
```

An assignment to a name with no visible binding implicitly declares a mutable binding. Otherwise it updates the visible mutable binding:

```dewy
message = "hello"     # implicit let
message = "welcome"   # reassignment
```

Type annotations follow `:`:

```dewy
let count:int64 = 0
const Name:type = string
```

Declarations and assignments produce `void`.

An unpacking target `[a b]` on the left of `=` (with or without `let`/`const`) binds each name. An object source is unpacked by field name: each target names the field it takes, in any order and any subset. An array, dictionary, or set source is unpacked by position (insertion order for dictionaries and sets), and its exact count must be known: the target count must equal it, `_` discards a value, a nested `[…]` unpacks an element further, and a dictionary entry is unpacked as `[key value]`. Each name follows the ordinary declaration rule: `let`/`const` declare, and a bare target declares a new name or assigns an existing one. The source value is evaluated once.

## Lexical Identity

Each declaration creates a distinct lexical binding. A child scope may shadow an outer binding without changing the outer value.

`{}` creates a child lexical scope. `()` groups expressions in the surrounding scope.

```dewy
let value = 1
{
    let value = 2
    printl"{value}"    # 2
}
printl"{value}"        # 1
```

## Initialization

An eager expression cannot read a binding before that binding is initialized on every reachable path.

A binding is assigned only within the module that declared it. The prelude's bindings and a module's imports are read here but not written: `run = …` or `A = …` at the top of a module is an error naming where the binding belongs and suggesting `let` — `let run = …` declares a new `run` that shadows the prelude's within this module.

Function bodies may refer to declarations that occur later in the same enclosing scope — whether the later function is declared with `let` or by a bare `name = (…) => …` (a first `name = value` in a block declares; a later one assigns). The relevant requirement is that each reachable call occurs after every eagerly read captured binding has been initialized. This permits mutually recursive and forward-declared function relationships without permitting an uninitialized runtime read.

## Captures

A function body may refer to bindings in enclosing lexical scopes. If the function escapes the lifetime of those bindings, its closure must preserve the captured state according to Dewy's value and place semantics.

The complete representation and identity rules for escaping closures remain provisional. This does not change lexical name resolution.
