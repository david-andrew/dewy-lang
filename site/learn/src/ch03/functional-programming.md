# Function Values and Composition

Functions are values. You can name them, pass them to other functions, return them and build new ones from old ones. [Functions and Calls](function-types.md) covers the basics; this chapter is about using functions as data.

## Passing functions

`@name` is the function itself. Give it to a function that takes a function. A function type is written in parentheses: `(int:>int)` is a function from an `int` to an `int`.

<!-- dewy-example: {"mode": "run", "stdout": "12\n"} -->
```dewy
inc = (n:int) => n + 1
twice = (f:(int:>int) x:int):>int => f(f(x))
printl(twice(@inc 10))
```

## Short functions

A lambda with one parameter drops the parentheses: `n => n * n`. It ends at the next argument, so it fits inside a call. The array methods `map`, `filter` and `sum` are the everyday users:

<!-- dewy-example: {"mode": "run", "stdout": "[1 4 9]\n[2 4]\n10\n"} -->
```dewy
printl([1 2 3].map(n => n * n))
printl([1 2 3 4].filter(n => n % 2 =? 0))
printl([1 2 3 4].sum)
```

Sort takes a `key` function and reorders the array in place:

<!-- dewy-example: {"mode": "run", "stdout": "[3 2 1]\n"} -->
```dewy
let xs = [3 1 2]
xs.sort(key=n => -n)
printl(xs)
```

## Operator sections

For the commonest tiny functions you do not even need a lambda. An operator with only its right side, in parentheses, is a function of the left: `(* 3)` is `x => x * 3`, `(>? 4)` is `x => x >? 4`, and `(.length)` is `x => x.length`.

<!-- dewy-example: {"mode": "run", "stdout": "[2 1 3]\n18\n"} -->
```dewy
twice = (f:(int:>int) x:int):>int => f(f(x))
printl(["bb" "a" "ccc"].map((.length)))
printl(twice((* 3) 2))
```

## Returning functions

A function can build and return another. The inner function keeps the values it needs from where it was made:

<!-- dewy-example: {"mode": "run", "stdout": "15\n"} -->
```dewy
make_adder = (n:int) => (x:int) => x + n
let add5 = make_adder(5)
printl(add5(10))
```

A closure copies what it captures when it is made. It never sees a later change to the variable it copied.

## Pipes and composition

`x |> @f` is `f(x)`, and pipes chain left to right, so a series of steps reads in order. Composition is an ordinary function that returns a function:

<!-- dewy-example: {"mode": "run", "stdout": "8\n12\n"} -->
```dewy
inc = (n:int) => n + 1
dbl = (n:int) => n * 2
printl(3 |> @inc |> @dbl)

compose = (f:(int:>int) g:(int:>int)):>(int:>int) => x => g(f(x))
let h = compose(@inc @dbl)
printl(h(5))
```

`@f <| x` is the same call written right to left. Pipes bind more loosely than arithmetic and `=>`, so `3 + 1 |> @dbl` doubles 4.

The [reference](/reference/functions-and-calls.html) has the complete rules.
