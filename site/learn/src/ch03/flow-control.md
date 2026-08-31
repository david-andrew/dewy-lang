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
let result = if cached isnt? none {
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
let answer:int64 | none = lookup()

if answer isnt? none
    printl"next is {answer + 1}"
```

Earlier failed alternatives also establish facts in later ones. Assignment or a call that may mutate the tested value invalidates facts that are no longer guaranteed.

A chain of `is?` tests that covers every alternative of a union is exhaustive, so it needs no `else` — whether it returns or produces a value:

<!-- dewy-example: compiler -->

```dewy
let describe = (v:int64 | string):>int64 => {
    if v is? int64 {
        return v * 2
    } else if v is? string {
        return v.length
    }
}
```

When a value-producing chain misses an alternative, the error names it: `` `none` is not handled by any `is?` arm``.

## `match`

When a value has several shapes, `match` writes the cases as *signatures*: an arm `pattern => body` matches when the value would satisfy that parameter list.

```dewy
let describe = (v:bool|int64|string):>string => match v {
    <bool>                    => "a flag"        # a type narrows and binds nothing
    answer:42                 => "the answer"    # a singleton
    small:int64<small <? 100> => "small"         # a refinement is the arm's guard
    n:int64                   => "large"         # `n` is the value at `int64`
    s:string                  => s
}
```

Object shapes bind fields (`[sign:1 limbs] => limbs.length` on a `bigint`), sequences match element-wise (`match (x y) (a:int64 b:int64) => a + b`), and a bare name is the catch-all that binds the whole value — `_` idiomatically; another name warns, since it shadows whatever it meant (write `n:T` to bind with a type). `else` attaches outside the arms and chains with `if` as usual. A chain with a `match` must be total — the arms cover the type, guards included when the type lets them (`<? 0` and `>=? 0` cover `int64`; over `-1|0|1`, `<? 0` and `>? 0` miss `0`, and the error says so) — or end in `else`; an arm nothing can reach is an error too.

## Short-Circuit Conditions

`and` evaluates its right side only if the left side succeeds. `or` evaluates its right side only if the left side fails. `nand`, `nor`, `xor`, and `xnor` follow their Boolean definitions.

This makes guarded use concise:

```dewy
if user isnt? none and user.active
    open_dashboard(user)
```

## Exiting Control Flow

`return` exits the current function. `break` exits a loop, and `continue` begins its next condition evaluation.

```dewy
let find = (items:array<int64> wanted:int64):>int64 | none => {
    loop item in items
        if item =? wanted
            return item
    return none
}
```

Labeled exits can target an enclosing loop; [Loops and Multiple Iterators](loops.md) develops those forms. [Errors as Values](errors-as-values.md#propagating-an-exception) later introduces the corresponding concise form for passing an exception value back to the caller.

## Related Control-Flow Designs

> **Provisional design:** General pattern matching, unconditional cleanup/finally behavior, and transformed error propagation must compose with these expression and narrowing rules. Their complete surface syntax is not yet specified.
