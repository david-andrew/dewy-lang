# Functions and calls

Function literals contain parameter contracts, an optional explicit return
contract, and a body.

```dewy
let add = (left:int64 right:int64=2):>int64 => left + right
```

Implemented call behavior includes positional arguments, keyword arguments,
keyword-only parameters, per-call default evaluation, pipe calls, direct and
indirect calls, recursion, forward references from function bodies, and static
overload selection.

```dewy
let describe = ((value:int64):>string => "integer")
             & ((value:string):>string => value)
```

Rest parameters, argument spreading, partial application, capturing closures,
and runtime multifunction values are not yet lowerable.
