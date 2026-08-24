# Functions and Calls

A function combines a parameter contract with a body expression:

```dewy
let greet = (name:string):>void =>
    printl"Hello, {name}!"
```

`:>void` is the return contract. Dewy can infer a result from a body whose parameter types are already known:

```dewy
let square = (value:int64) => value^2
let add = (left:int64 right:int64) => left + right
```

One parameter can omit parentheses. Zero parameters use `()`.

## Positional and Named Arguments

Ordinary parameters may be supplied by position or name:

```dewy
let describe = (name:string count:int64):>string =>
    "{name}: {count}"

describe("messages" 3)
describe(count=3 name="messages")
```

Dewy processes arguments from left to right. A positional argument fills the first parameter still open by position; a named argument fills that name.

## Defaults Are Per Call

A default is used only if the completed call leaves its parameter unset:

```dewy
let greet = (name:string greeting:string="Hello"):>void =>
    printl"{greeting}, {name}!"

greet("Ada")
greet("Grace" greeting="Welcome")
greet("Linus" "Hi")
```

The default expression evaluates separately for every call that needs it. A mutable value created by a default is not shared between callers.

A default does not remove its position. This matters when a required parameter follows one:

```dewy
let combine = (left:int64 scale:int64=2 right:int64):>int64 =>
    left + scale * right

combine(10 3 16)
combine(10 right=16)
```

`combine(10 16)` supplies `left` and `scale`, then reports that `right` is missing.

## Keyword-Only and Position-Only

A bare `...` ends the positional run:

```dewy
let connect = (host:string ... timeout:Duration<int64>):>void => {
    # ...
}

connect("example.test" timeout=2s)
```

Wrapping a parameter in `<>` makes its name private to the function's body and requires callers to use its position:

```dewy
let increment = (<value:int64>):>int64 => value + 1

increment(41)
```

`increment(value=41)` is an error. A bare identifier in a function literal is always a parameter name, not an anonymous type annotation.

## Function Contracts

A function type writes the same interface without a body and can be used anywhere another annotation can:

```dewy
let apply = (
    transform:<(value:int64):>int64>
    value:int64
):>int64 => transform(value)
```

Names in a contract determine which keyword calls it accepts. Position-only parameters use the same `<name:type>` form in a function type as in a function literal. Dewy does not reinterpret a bare identifier as an unnamed type annotation.

## Overloads

`&` combines functions into an overload set. Argument contracts select the applicable alternative:

```dewy
let format = ((value:int64):>string => "integer {value}")
           & ((value:string):>string => value)

format(42)
format("already text")
```

An unmatched or ambiguous call is an error.

## Pipes

Pipes are calls written in data-flow order:

```dewy
3 |> square
("Grace" greeting="Welcome") |> greet
```

Grouping several piped arguments keeps any named bindings local to the group.

## Function Handles and Partial Evaluation

> **Provisional design:** The root syntax and argument-binding behavior are settled; escaping identity, captures, and storage remain under design.

A bare function name calls it whenever a valid call exists. `@` selects the function binding as a callable value:

```dewy
let sum = (a:int64 b:int64) => a + b
let reference = @sum
let add5 = @sum(5)

add5(24)       # 29
```

Explicitly supplied partial arguments are saved immediately. Defaults remain per-call fallbacks until the resulting function is called.

The route rule is the same as for data places: `@worker.callback` selects the function-valued place at the end of the entire route, and `@` cannot appear as `worker.@callback`. The parser's intermediate `(@worker).callback` grouping does not make `@worker` the semantic result.

> **Open edge:** Dewy's automatic call behavior still needs an exact rule for member access when a function-valued node occurs before the end of a route. In particular, the language must distinguish deliberately selecting a member of a function value from calling the function and selecting a member of its result. The leading-`@` whole-route rule above is settled; that auto-call interaction is not.

Rest capture, spreading, and complete handle semantics are summarized in the [design appendix](../appendices/language-and-compiler.md). Exact argument binding is defined in the [Reference](../../reference/functions-and-calls.html).
