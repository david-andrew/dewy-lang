# Functions and calls

Function literals contain parameter contracts, an optional explicit return contract, and a body.

```dewy
let add = (left:int64 right:int64=2):>int64 => left + right
```

## Parameter states

Dewy's call model follows one rule: each explicit argument binds one currently unset parameter. A positional argument takes the first parameter still available by position; a named argument takes the parameter with that name. Defaults are fallbacks rather than pre-bound values, so they retain their declared positions.

### Required positional-or-keyword

Unbound parameters before `...` may be supplied in their declared position or by name. Named arguments may appear in any order.

```dewy
let subtract = (left:int64 right:int64):>int64 => left - right

subtract(7 2)
subtract(right=2 left=7)
```

Both calls bind `left=7` and `right=2`.

### Positional-or-keyword with a default

A parameter with a default may still be supplied either by position or by name. The default is used only when a completed call leaves that parameter unset.

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

Named arguments remove their parameters from the remaining positional sequence. Arguments are processed from left to right, which is why the last example is unambiguous. The shorter `combine(10 16)` does _not_ skip `scale`: it supplies `left` and `scale`, then reports that required `right` is missing.

The default expression is evaluated separately for every completed call that omits it, and binds a value like any other argument.

### Required keyword-only

A bare `...` ends the positional parameter run. Required parameters after it must be supplied by name.

```dewy
let offset = (value:int64 ... amount:int64):>int64 => value + amount

offset(40 amount=2)
```

Here `value` remains positional-or-keyword, while `amount` is required and keyword-only.

### Position-only

Wrapping a parameter in `<>` keeps its name inside the function but removes that name from the call interface. It must be supplied by position.

```dewy
let increment = (<value:int64>):>int64 => value + 1

increment(41)
# increment(value=41)  # error: `value` is not a keyword parameter
```

Annotations and defaults work normally inside the wrapper. A position-only default remains a per-call fallback:

```dewy
let increment = (<value:int64=0>):>int64 => value + 1

increment()   # 1
increment(9)  # 10
```

### Function type contracts

Types and parameter names use the same identifier syntax. A bare identifier in a function signature is therefore a parameter name, not an unnamed parameter whose type happens to have that spelling. Structural function contracts make the name and type explicit in the same way as function literals.

```dewy
let increment = (value:int64):>int64 => value + 1
let callback:<(value:int64):>int64> = increment

callback(41)
callback(value=41)
```

A structural contract may omit a parameter name to require positional access, as in `<int64:>int64>`. Source function literals still give every parameter a local name; `<value:int64>` makes that name private to the function rather than reinterpreting a bare identifier as a type.

### Rest parameters and spreading

The planned `...rest` form captures arguments not claimed by earlier parameters. A captured bundle will be forwardable with the same `...` syntax.

```dewy
# planned
let wrapper = (...rest) => target(...rest)
```

Rest capture and argument spreading are recognized design directions but are not yet lowerable by the current compiler. A bare `...` used only as the keyword-only divider is implemented. Partial evaluation will follow the same binding rule. Explicitly supplied values will be evaluated and saved immediately, while defaults remain per-call fallbacks until the resulting function is called.

## Call behavior

Implemented calls include positional and keyword arguments, per-call default evaluation, pipe calls, direct and indirect calls, recursion, forward references from function bodies, and static overload selection.

Overloads combine with `&`; the argument contract selects the matching function statically.

```dewy
let describe = ((value:int64):>string => "integer")
             & ((value:string):>string => value)
```

## Handles

Function handles and partial evaluation are a design direction and do not yet lower in the current compiler. The intended syntax uses the same place rule as ordinary data: a bare function name calls it when that would be valid, while `@fn` starts at the function binding's place and exposes it as a callable handle instead.

```dewy
# planned
sum = (a b) => a + b
add5 = @sum(5)
reference = @sum

callback = @worker.on_event  # (@worker).on_event, not worker.@on_event
```

Selectors project the root place before producing the handle, so `@worker.on_event` reaches the function-valued field at the end of that route. The older interpreter spelling `worker.@on_event` is not the current language direction.

A parameter whose type is a function is intended to request a callable handle directly, making `@f` optional in that signature. The call site still uses `@sum`, because bare `sum` would call. Details of escaping handle identity and explicit function copying remain part of the unfinished function-handle work. For implemented nonescaping data places, see [Values, places, and containers](values.md).
