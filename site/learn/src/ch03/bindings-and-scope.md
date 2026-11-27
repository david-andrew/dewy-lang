# Bindings and Scope

A binding gives a name to a value. This chapter covers how to make one, how to change it, and where a name can be seen.

## let and const

`let` declares a binding you can change later. `const` declares one you cannot.

<!-- dewy-example: {"mode": "run", "stdout": "3\n10\n"} -->
```dewy
let count = 0
const limit = 10
count = count + 1
count += 2
printl(count)
printl(limit)
```

Assigning to a `const` is a compile error:

<!-- dewy-example: {"mode": "reject", "diagnostic": "it cannot change"} -->
```dewy
const limit = 10
limit = 11
```

A type goes after a colon: `let count:int64 = 0`. Leave it off and the compiler works it out from the value.

## One `=` for declaring and assigning

A name does not need `let`. The first `name = value` for a name that is not yet visible declares it; later ones assign to it. This is the Python habit, and it works the same way here.

<!-- dewy-example: {"mode": "run", "stdout": "welcome\n"} -->
```dewy
message = "hello"     # declares
message = "welcome"   # assigns
printl(message)
```

Use `let` when you want to be explicit, or when you want a new binding even though the name is already visible (see shadowing below).

## Give a name a value before you read it

A binding must have a value on every path that reaches a read. A declaration with a type and no value is fine as long as every branch fills it in:

<!-- dewy-example: {"mode": "run", "stdout": "no\n"} -->
```dewy
let flag = false
let label:string
if flag { label = "yes" } else { label = "no" }
printl(label)
```

Reading `total` after a bare `let total:int64`, or after an `if` that only sometimes assigns it, is an error when you build the program: the compiler names the declaration and says the read comes before any value.

There is no hidden zero value. If you mean zero, write `let total = 0`.

## Blocks and scope

A `{ ... }` block is a scope. Names made inside it end with it. Assigning to a name that already exists outside the block changes that outer name:

<!-- dewy-example: {"mode": "run", "stdout": "2\n"} -->
```dewy
let x = 1
{
    x = 2
    inner = 99
}
printl(x)
```

`inner` is gone after the block. Using it there is an error that says the name belongs to a block that has ended.

<!-- dewy-example: {"mode": "reject", "diagnostic": "inside a block that has ended"} -->
```dewy
{ inner = 5 }
printl(inner)
```

## Shadowing

`let` inside a block makes a new binding with the same name. The outer one is untouched.

<!-- dewy-example: {"mode": "run", "stdout": "2\n3\n1\n"} -->
```dewy
let x = 1
{
    let x = 2
    printl(x)
    x = 3
    printl(x)
}
printl(x)
```

The `x = 3` changed the inner `x`, because that is the one in sight. Parentheses `( ... )` only group an expression; unlike `{ ... }` they do not start a new scope.

## Unpacking

A list of names on the left of `=` binds several at once. See [Container Types](container-types.md) for what you can unpack.

<!-- dewy-example: {"mode": "run", "stdout": "3\n"} -->
```dewy
let [a b] = [1 2]
printl(a + b)
```

The [reference](/reference/bindings-and-scope.html) has the complete rules.
