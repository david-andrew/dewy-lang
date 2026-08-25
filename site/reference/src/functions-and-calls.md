# Functions and Calls

A function literal consists of a parameter contract, an optional return contract, `=>`, and a body expression:

```dewy
let add = (left:int64 right:int64=2):>int64 => left + right
```

One bare parameter name may omit parentheses: `x => x + 1`. Here `x` is always the local parameter name, never an anonymous argument whose type happens to be named `x`. Whether the body can infer a generic contract without other type context depends on the provisional generic-function design. Annotated parameters use `(x:int64)`, and zero parameters use `()`.

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

## Rest Parameters and Spreading

The direction for `...rest` is to capture arguments not claimed by earlier parameters and allow the resulting bundle to be forwarded with `...`. Exact bundle types and all interactions with named arguments remain provisional.

## Function Contracts

A function type records its parameter and return contract:

```dewy
let callback:<(value:int64):>int64> = increment
```

Position-only function contracts use `<name:type>`, just like function literals. The name describes the parameter inside the contract but is absent from the keyword-call interface. A bare identifier is always a parameter name, so Dewy does not infer an anonymous type-only parameter from its spelling.

Expected failures appear as direct [error alternatives](errors-and-forwarding.md) in the return contract. Public functions should normally declare a stable set of returned errors even where an unexposed helper could infer them.

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

## Function Handles

A bare function name calls the function whenever a valid call is available. `@fn` selects the function binding as a first-class callable handle instead:

```dewy
let sum = (a:int64 b:int64) => a + b
let reference = @sum
let add5 = @sum(5)
```

Selectors use the ordinary whole-route place rule: `@worker.on_event` selects the function-valued place at the end of the route, and it cannot be written `worker.@on_event`. Although parsing groups the leading prefix first, `@worker` is not the semantic result of that complete expression.

A leading `@` suppresses calls at every function-valued node in its complete ungrouped selector-and-application chain. The route still selects only its final place; intermediate nodes are not separately observable place values. Argument groups within that chain partially evaluate functions. A grouping boundary ends the `@` chain, so an argument group outside it performs an ordinary call.

```dewy
@worker.on_event.metadata     # metadata belonging to the function value
worker.on_event().metadata    # call on_event, then read result.metadata
(@worker.on_event)(5).metadata # select on_event, call it, then read result.metadata
```

An ordinary call resolves the callable at that node without automatically calling it first. `@sum(5)` saves `5`, while `(@sum)(5)` invokes the selected function. Repeated argument groups do not implicitly end the chain:

```dewy
@sum(1)(2)       # two stages of partial evaluation
(@sum(1))(2)     # partially evaluate with 1, then call with 2
@sum(1)()        # empty second partial evaluation; still a function
(@sum(1))()      # call the partially evaluated function with no arguments
```

An empty partial evaluation does not invoke the function or evaluate its signature defaults. If code needs a place within a returned value, it must bind that result and select a place from the stable binding; `@` does not make a temporary call result into an escaping place.

Partial evaluation also works when the selected function is an object member:

```dewy
let on_item = @worker.on_event(5)
```

This selects `on_event` at the endpoint of the route, preserves its receiver, and saves `5`; it does not call either `worker` or `on_event`. When the object must first be produced by a call, bind that result before selecting its function member:

```dewy
let worker = make_worker()
let on_item = @worker.on_event(5)
```

`@make_worker()` means an empty partial evaluation of `make_worker`, not an explicit call followed by place selection. A temporary call result is not a valid root for a place route.

Partial evaluation binds explicitly supplied values immediately. Defaults remain fallbacks evaluated when the resulting function is eventually called.

Handle identity, explicit function copying, escaping captures, and closure storage remain provisional.
