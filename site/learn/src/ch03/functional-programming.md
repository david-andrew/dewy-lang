# Functional Programming

Dewy has strong support for functional programming concepts. There is one unified syntax for writing functions, and they are first class objects you may use and pass around like any other value in the language.

## Functions as Values

```dewy
square = x => x^2
apply = (f x) => f(x)
apply(@square 5)         # => square(5) => 25
```

A zero-argument field or a pipe is still a call:

```dewy
40 |> ((x) => x + 2)
```

## Overloads and Generics

`&` glues functions together. When calling, the argument types of the caller picks which one runs:

```dewy
format = ((value:int):>string => 'integer')
       & ((value:string):>string => value)

# input arguments select the version
format(42)           # returns 'integer'
format('apple')      # returns 'apple'
```

A function can take a type as well as a value:

```dewy
identity = <T>(value:T):>T => value
identity<int>(42)    # <int> is not neccessary since it's inferred from the argument type
```

## Freezing Some Arguments

`@` fills in some arguments now and gives you a smaller function:

```dewy
sum = (a b) => a + b
add5 = @sum(5)        # `add5` is `add` with a=5
add5(24)              # 29
```

That is a common way to fit a function into a slot that wants fewer parameters.

## Using Names from Outside

A function body sees the names around it. A helper created inside another function can keep using that function's local names, with no `self` object.

```dewy
make_counter = (start:int) => {
    let n = start
    () => {
        n += 1
        n
    }
}

counter = make_counter(0)
i = counter()  # 1
i = counter()  # 2
i = counter()  # 3
```

## Passing Functions and Building Lists

You do not need a separate `map` / `filter` vocabulary. A loop already builds a list:

```dewy
values = [1 2 3 4 5 6 7 8 9 10]
square = x => x^2
is_odd = x => x % 2 =? 1

# map
squared_values = [loop v in values square(v)]
# [1 4 9 16 25 36 49 64 81 100]

# filter
odd_values = [loop v in values if is_odd(v) v]
# [1 3 5 7 9]
```

You could even create the typical `map` and `filter` functions directly like so

```dewy
map = <T U>(f:(T:>U) xs:array<T>):>array<U> => [
    loop x in xs f(x)
]

filter = <T>(f:(T:>bool) xs:array<T>):>array<T> => [
    loop x in xs
        if f(x)
            x
]
```

See [Function Types](function-types.md) and [Loops](loops.md) for more details.
