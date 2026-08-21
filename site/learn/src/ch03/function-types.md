# Function Types

Functions are values. A function literal is the parameters, `=>`, and a
body expression.

```dewy
my_function = () => { printl'You called my function!' }
my_function
```

The body can be a block or a single expression. One argument may omit
the parentheses. Zero arguments need `()`.

```dewy
pythag_length = (a b) => (a^2 + b^2)^/2
square = x => x^2
foo = () => printl'bar'
```

Return type is `:>`:

```dewy
let add = (left:int64 right:int64=2):>int64 => left + right
```

[Effects](effects.md) such as `noreturn` also go in that slot.

A function type writes the same contract:

```dewy
let callback:<(value:int64):>int64> = add
```

## Calling Functions

Each argument you write binds one parameter that is not set yet.
Positional takes the first one still open. Named takes that name, in any
order.

```dewy
let subtract = (x:int64 y:int64):>int64 => x - y
subtract(5 2)
subtract(y=2 x=5)
```

Defaults are fallbacks. They keep their slots. The default expression
runs every time that call leaves the parameter out, so a mutable default
like an array is new each time.

```dewy
let foo = (a:int64 b:int64=5):>int64 => a + b
foo(3)          # 8
foo(3 b=2)      # 5
foo(3 2)        # 5

let bar = (a:int64 b:int64=5 c:int64):>int64 => a + b + c
bar(3 5 10)
bar(3 c=10)
```

`foo(3 2)` fills `a` and `b`. It does not skip a default in the middle.
`combine(10 16)` would bind `left` and `scale`, then complain that
`right` is missing.

A bare `...` ends the positional run. After that, arguments are
keyword-only:

```dewy
let configure = (value:int64 ... scale:int64):>int64 => value * scale
configure(6 scale=7)
```

Pipes are ordinary calls:

```dewy
40 |> add
```

## Overloads

`&` combines functions into a set. Argument types pick the branch:

```dewy
format = ((value:int):>string => 'integer')
       & ((value:string):>string => value)

format(42)
format('life the universe and everything')
```

## Handles and Frozen Arguments

A bare function name *calls* it if that would be a valid call. `@` gives
you a handle, and you can freeze some arguments:

```dewy
sum = (a b) => a + b
add5 = @sum(5)
add5(24)            # 29

reference = @sum
thirtyseven = @add5(32)
thirtyseven         # 37
```

Leave off `@` and `sum` with no arguments is a call, not a value.

## Scope

The body can see the names around it. Bodies can also mention names
declared later. See [Bindings and Scope](bindings-and-scope.md).

## Rest, Spread, and Positional-Only Parameters

A `...rest` parameter that captures leftover arguments, and spreading a
bundle into a call with `...`, are not yet determined.

Positional-only and anonymous parameter syntax are not yet determined
either. A bare identifier in a signature is always a parameter name,
never an unnamed type annotation.
