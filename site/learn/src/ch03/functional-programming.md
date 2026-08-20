# Functional Programming

Dewy is ordinary step-by-step code, but functions are values. The same
syntax you use to write a helper is the syntax you use to pass one
around.

## Functions as Values

```dewy
square = x => x^2
apply = (f x) => f(x)
apply(square 5)         # 25
```

A zero-argument field or a pipe is still a call:

```dewy
40 |> ((x) => x + 2)
```

## Overloads and Generics

`&` glues functions together. The argument types pick which one runs:

```dewy
format = ((value:int):>string => 'integer')
       & ((value:string):>string => value)
```

A function can take a type as well as a value:

```dewy
identity = <T>(value:T):>T => value
identity<int>(42)
```

## Freezing Some Arguments

`@` fills in some arguments now and gives you a smaller function:

```dewy
sum = (a b) => a + b
add5 = @sum(5)
add5(24)                # 29
```

That is a common way to fit a function into a slot that wants fewer
parameters.

## Using Names from Outside

A function body sees the names around it. A helper created inside
another function can keep using that function's local names, with no
`self` object.

```dewy
make_counter = (start:int) => {
    let n = start
    () => {
        n += 1
        n
    }
}
```

## Passing Functions and Building Lists

You do not need a separate `map` / `filter` vocabulary. A loop already
builds a list:

```dewy
squares = [loop n in 1..10 n^2]
kept = [loop x in values { if keep(x) x }]
```

Passing `keep` or `n => n^2` into a helper is the same as binding those
functions and calling them. See [Function Types](function-types.md) and
[Loops](loops.md).
