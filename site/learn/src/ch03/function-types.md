# Function Types

Functions are values. A function literal is the parameters, `=>`, and a body expression.

```dewy
my_function = () => { printl'You called my function!' }
my_function
# You called my function!
```

The body can be a block or a single expression. One argument may omit the parentheses. Zero arguments need `()`.

```dewy
pythag_length = (a b) => (a^2 + b^2)^/2
square = x => x^2
foo = () => printl'bar'
```

Return type can be annotated with `:>`:

```dewy
let add = (left:int64 right:int64=2):>int64 => left + right
```

[Effects](effects.md) such as `noreturn` also go in that slot or can be `|` unioned with a return type.

A function type writes the same contract:

```dewy
let callback:<(value:int64):>int64> = add
```

## Calling Functions

Each argument you write binds one parameter that is not set yet. Positional takes the first one still open. Named takes that name, in any order.

```dewy
let subtract = (x:int64 y:int64):>int64 => x - y
subtract(5 2)
subtract(y=2 x=5)
```

If you leave a parameter out of the call, Dewy uses its default. A default does not fill that parameter slot: later positional arguments still fill from left to right.

```dewy
let foo = (a:int64 b:int64=5):>int64 => a + b
foo(3)          # 8
foo(3 b=2)      # 5
foo(3 2)        # 5

let bar = (a:int64 b:int64=5 c:int64):>int64 => a + b + c
bar(3 5 10)
bar(3 c=10)
```

`foo(3 2)` fills `a` and `b`. It does not skip a default in the middle. `combine(10 16)` would bind `left` and `scale`, then complain that `right` is missing.

A bare `...` ends the positional run. After that, arguments are keyword-only:

```dewy
let configure = (value:int64 ... scale:int64):>int64 => value * scale
configure(6 scale=7)
```

Pipes are ordinary calls (including the ability to provide multiple arguments):

```dewy
3 |> foo
(3 2) |> foo
{3 b=2} |> foo  # note the scope so `b` doesn't leak into the surrounding scope
```

## Overloads

`&` combines functions into a set. Argument types at the call site pick the version used:

```dewy
format = ((value:int):>string => 'integer')
       & ((value:string):>string => value)

format(42)
format('life the universe and everything')
```

## Partial Evaluation and Handles

A bare function name _calls_ it if that would be a valid call. `@` gives you a handle, and you can freeze some arguments:

```dewy
sum = (a b) => a + b
add5 = @sum(5)
add5(24)            # 29

reference = @sum
thirtyseven = @add5(32)
thirtyseven         # 37
```

Leave off the `@`, and `sum` with no arguments is a call, not a value. `@fn` is both the handle and the original function's location, so `reference = @sum` does not copy. A parameter whose type is a function already wants that handle; writing `@f` in the signature is optional.

## Scope

The body can see the names around it. Bodies can also mention names declared later. See [Bindings and Scope](bindings-and-scope.md).

## Rest, Spread, and Positional-Only Parameters

A `...rest` parameter that captures leftover arguments, and spreading a bundle into a call with `...`, are not yet determined.

Wrapping a parameter in `<>` makes it position-only while preserving its local name in the function body:

```dewy
let increment = (<value:int64>):>int64 => value + 1

increment(41)
# increment(value=41)  # error
```

A bare identifier in a signature is always a parameter name, never an unnamed type annotation.

An anonymous position only argument can be specified with `<>`.

```dewy
let A = ():>ProofYouCalledA => { ... }
let B = <ProofYouCalledA>:>ProofYouCalledB => { ... }
let C = ():>ProofYouCalledC => { ... }
let D = (<ProofYouCalledB> <ProofYouCalledC>) => { ... }


proof_a = A()
proof_b = B(proof_a)
proof_c = C()
D(proof_b proof_c)
```

Useful for proving some condition is true but don't actually need the values
