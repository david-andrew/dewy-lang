# Functions and Calls

A function literal consists of a parameter contract, an optional return contract, `=>`, and a body expression:

```dewy
let add = (left:int64 right:int64=2):>int64 => left + right
```

One unannotated parameter may omit parentheses: `x => x + 1`. Zero parameters use `()`.

## Argument Binding

Each explicit argument binds one currently unset parameter. Arguments are processed from left to right.

- A positional argument binds the first parameter still available by position.
- A named argument binds the unset parameter with that name.
- After explicit arguments are processed, each unset defaulted parameter evaluates its default for that completed call.
- A required parameter still unset after binding is an error.

Defaults are fallbacks, not values bound when the function is defined. They retain their positions:

```dewy
let combine = (
    left:int64
    scale:int64=2
    right:int64
):>int64 => left + right * scale

combine(10 3 16)       # left=10, scale=3, right=16
combine(10 right=16)   # left=10, scale=2, right=16
combine(scale=3 10 16) # scale=3, then left=10 and right=16
```

`combine(10 16)` binds `left` and `scale`; it does not skip `scale`, and therefore reports missing `right`.

Default expressions evaluate independently for every completed call that omits them. Mutable objects created by a default are not shared accidentally between calls.

## Parameter Kinds

### Positional or keyword

An ordinary named parameter before the positional divider may be bound by position or name:

```dewy
let subtract = (left:int64 right:int64):>int64 => left - right
subtract(7 2)
subtract(right=2 left=7)
```

### Keyword-only

A bare `...` ends the positional run. Parameters after it require names:

```dewy
let offset = (value:int64 ... amount:int64):>int64 => value + amount
offset(40 amount=2)
```

### Position-only

Wrapping the name and type in `<>` preserves the local name but removes it from the keyword interface:

```dewy
let increment = (<value:int64>):>int64 => value + 1
increment(41)
```

`increment(value=41)` is an error. A default inside the wrapper remains a per-call fallback.

Types and names share identifier syntax, so a bare identifier in a function literal is a parameter name, not an anonymous argument whose type happens to have that spelling.

## Function Contracts

A function type records its parameter and return contract:

```dewy
let callback:<(value:int64):>int64> = increment
```

Structural contracts may omit externally visible names where a position-only interface is required. Function literals still require usable local names for parameters their bodies access.

## Calls and Pipes

Parenthesized or juxtaposed arguments call a callable expression. `|>` supplies values to the callable on its right; `<|` supplies right-hand values to the callable on its left according to their associativity.

Argument expressions evaluate from left to right before the function body begins, except that omitted defaults evaluate as part of completing the call.

## Overloads

`&` combines compatible functions into an overload set. The call contract selects a unique applicable alternative:

```dewy
let describe = ((value:int64):>string => "integer")
             & ((value:string):>string => value)
```

Ambiguous or unmatched calls are errors. Runtime multifunction values remain part of the provisional dynamic-dispatch design; ordinary overload resolution is static.

## Rest Parameters and Spreading

The direction for `...rest` is to capture arguments not claimed by earlier parameters and allow the resulting bundle to be forwarded with `...`. Exact bundle types and all interactions with named arguments remain provisional.

## Function Handles

A bare function name calls the function whenever a valid call is available. `@fn` selects the function binding as a first-class callable handle instead:

```dewy
let sum = (a b) => a + b
let reference = @sum
let add5 = @sum(5)
```

Selectors use the ordinary place route: `@worker.on_event` reaches the function-valued field at the end of `(@worker).on_event`; it is not `worker.@on_event`.

Partial evaluation binds explicitly supplied values immediately. Defaults remain fallbacks evaluated when the resulting function is eventually called.

Handle identity, explicit function copying, escaping captures, and closure storage remain provisional.
