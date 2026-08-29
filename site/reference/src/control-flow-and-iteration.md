# Control Flow

## Conditionals

`if`, `else if`, and `else` form an ordered flow expression. Conditions evaluate from left to right until one succeeds; only the selected body evaluates.

```dewy
let label = if count =? 0
    "empty"
else if count =? 1
    "one item"
else
    "{count} items"
```

An exhaustive conditional may produce a value when its alternatives have a compatible result type. A nonexhaustive conditional produces `void` unless its context collects another well-defined result form.

Facts established by a condition narrow values inside the corresponding body and along later paths where earlier alternatives are known false.

A chain whose arms are all `is?` tests on one union binding is exhaustive when the alternatives excluded by every arm leave no member; such a chain needs no `else` for return coverage or for producing a value, and a value-producing chain that misses a member reports which member is unhandled. Statement-form chains may remain partial.

## `match`

`match <scrutinee> <arm | { arms }>` is a member of the flow chain, so `else` (and `else if`, `else match`) attaches outside the arms. An arm is `<signature> => <body>`, and it matches when the scrutinee satisfies the signature, exactly as a call satisfies a parameter list:

```dewy
let describe = (v:bool|int64|string):>string => match v {
    <bool>              => "a flag"          # a type: narrows, binds nothing
    answer:42           => "the answer"      # a singleton
    small:int64<small <? 100> => "small"     # the refinement is the arm's guard, and a fact in the body
    n:int64             => "large"           # binds `n` at `int64`
    s:string            => s
}
let sign_of = (b:bigint):>int64 => match b {
    <0>                 => 0
    [sign:1 limbs]      => limbs.length      # an object shape: the member with those fields, fields bound
    [sign:-1 limbs]     => -limbs.length
}
let sum = match (x y) (a:int64 b:int64) => a + b   # a sequence scrutinee; `(<T1> b:T2)` mixes anonymous and named
```

The scrutinee is evaluated once; a bare identifier is matched in place, so the arms narrow it. Arms are tried top to bottom and the first that matches wins. A bare name matches everything and binds the value, shadowing what the name meant, as a parameter would; `_` is the idiomatic catch-all, and any other bare name warns (saying whether it shadows a type or a value) — write `name:T` to bind with a type or `<T>` to match one. An anonymous refined type, `<int64<i => i <? 100>>`, is a guard without a binding.

A chain that contains a `match` must be **total**: the arms must cover every member of the scrutinee's type, or the chain must end in `else`. Coverage is computed on value sets, so guards count where the type is known: `a:int64<a <? 0>` and `b:int64<b >=? 0>` cover `int64`; over `-1|0|1`, guards `<? 0` and `>? 0` leave `0` unhandled and the error says so. An arm that cannot match anything the earlier arms left (`unreachable match arm`) is an error. Value-producing arms combine like conditional branches: the result is the union of the arm types, so a match whose arms are `'A'` and `'B'` produces the enum `'A' | 'B'`. An enum — a union of string and/or integer singletons — is one word at runtime, the member's index: `c =? 'A'`, `c is? 'A'`, and `match` arms compare that word, no string is built or compared, and the text exists only where the value meets a `string`.

## Loops

`loop condition body` reevaluates its condition and executes its body according to the condition's Boolean or iterator behavior.

```dewy
loop connected
    receive_message()

loop item in items
    process(item)
```

See [Ranges and Iteration](ranges-and-iteration.md) for iterator conditions and multiiterator formulas.

## Exits

`break` exits a loop. `continue` begins its next condition evaluation. `return` exits the current function, optionally supplying its result.

An exit may target an enclosing labeled loop through Dewy's scope metatag mechanism. Exiting more loop levels than exist is an error.

`never` is the type of a path that cannot complete normally. It is distinct from `void`, which represents normal completion without a produced value.

Postfix `or_throw` propagates an [exception value](errors-and-forwarding.md) from an expression through the current function. Its ordinary alternatives continue locally; its exception alternatives must be accepted by the enclosing return contract.

## Related Provisional Control Flow

Cleanup/finally behavior and transformed error-propagation forms are provisional designs (`match` is settled; see above and `dewy/semantic/match.md`). Their eventual forms must compose with expression results and flow-sensitive narrowing rather than creating separate statement-only semantics.
