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

Function bodies may refer to declarations that occur later in the same enclosing scope. The relevant requirement is that each reachable call occurs after every eagerly read captured binding has been initialized. This permits mutually recursive and forward-declared function relationships without permitting an uninitialized runtime read.

## Captures

A function body may refer to bindings in enclosing lexical scopes. If the function escapes the lifetime of those bindings, its closure must preserve the captured state according to Dewy's value and place semantics.

The complete representation and identity rules for escaping closures remain provisional. This does not change lexical name resolution.
