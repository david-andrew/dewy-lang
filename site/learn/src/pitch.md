# A Tour of Dewy

This page shows the language in about fifteen minutes of reading. Every example is compiled by the website build with the current compiler, under its default rules (no runtime checks switched on), and its printed output is compared with what the page shows. To run one yourself, save it as `tour.dewy` and run `dewy tour.dewy`.

## Hello, values

A file runs from top to bottom. `let` declares a binding (at the top of a file, `total = 0` also declares one the first time). `printl` prints a line, and a string can interpolate any expression in braces. A function that takes one string or array can be called without parentheses.

<!-- dewy-example: {"mode": "run", "stdout": "Hello from Dewy, 2026!\nnext year: 2027\n"} -->
```dewy
let name = "Dewy"
let year = 2026
printl"Hello from {name}, {year}!"
printl"next year: {year + 1}"
```

Comparisons end in a question mark (`=?`, `<?`, `>=?`), which keeps `=` for binding and makes a test easy to spot. Logic is spelled `and`, `or` and `not`.

## Numbers that mean what they say

`int` is the mathematical integer: it never overflows or wraps. Dividing integers gives an exact fraction, and a decimal literal is exact unless you ask for a float.

<!-- dewy-example: {"mode": "run", "stdout": "1267650600228229401496703205376\n7/2\n3\ntrue\n0.30000000000000004\n"} -->
```dewy
printl(2^100)              # big when it needs to be
printl(7 / 2)              # 7/2, exactly
printl(7 // 2)             # 3: floor division
printl(0.1 + 0.2 =? 0.3)   # true: decimal literals are exact

x:float64 = 0.1            # IEEE floats when you want them
printl(x + 0.2)
```

Fixed-width types such as `int32` and `uint8` exist for storage and speed. Storing a result that might not fit is a compile error, unless the type says it wraps (`uint32<overflow='wrap'>`, for a hash) or saturates.

## Functions

A function is a value written `(parameters) => body`. Arguments are separated by spaces, can be passed by name, and can have defaults. The last expression of a body is its result.

<!-- dewy-example: {"mode": "run", "stdout": "144\nHello, Ada!\nHello, Grace!\nHello, Grace!\n"} -->
```dewy
square = (x:int) => x * x
printl(square(12))

greet = (name:string times:int=1) => {
    loop _ in [0..times) printl"Hello, {name}!"
}
greet("Ada")
greet("Grace" times=2)
```

Parameter types are written after a colon, and `:>` gives a return type when you want to state it. `@square` is the function itself, ready to pass to another function.

## Arrays and the one loop

There is no `for`, `while` or `do`: `loop` takes any condition, and `x in xs` binds the next value and reports whether there was one. A loop in brackets builds an array.

<!-- dewy-example: {"mode": "run", "stdout": "95\n88\n[144 190 176 122]\n[95 88 72 61]\n0: ada\n1: grace\n"} -->
```dewy
scores = [72 95 88 61]
loop s in scores if s >=? 80 printl(s)

doubled = [loop s in scores s * 2]
printl(doubled)
printl(scores.sorted(reverse=true))

# Iterators combine with `and`: this stops when the names run out.
loop i in 0.. and name in ["ada" "grace"] printl"{i}: {name}"
```

Elements are separated by spaces, not commas.

## Ranges with visible bounds

A square bracket includes its end and a parenthesis excludes it, so `[0..10)` is 0 through 9. A second value sets the step. The same forms drive loops, membership tests and slices.

<!-- dewy-example: {"mode": "run", "stdout": "[0 2 4 6 8 10]\nfalse\n[5 9 2 6]\nhello\n"} -->
```dewy
printl([loop i in 0,2..10 i])
printl(16 in? (5..15])

samples = [3 1 4 1 5 9 2 6]
printl(samples[end-3..])
printl('hello world'[0..5))
```

## Records and dictionaries

A record is a set of named fields; a record type names the fields and their types. `...` spreads one value into another, so updating a copy is one expression. A dictionary maps keys to values with `->`.

<!-- dewy-example: {"mode": "run", "stdout": "[x=3 y=4]\n[x=10 y=4]\n[\"ada\" -> 36 \"alan\" -> 41]\n0\n"} -->
```dewy
Point:type = [x:int y:int]
let p:Point = [x=3 y=4]
moved = [p... x=10]
printl(p)
printl(moved)

ages = ["ada" -> 36 "alan" -> 41]
printl(ages)
printl(ages.get("grace") ?? 0)
```

## Values, not shared surprises

Assignment, argument passing and return give the receiver its own value. Changing a copy never changes the original behind your back. When a function should change the caller's variable, both sides say so with `@`.

<!-- dewy-example: {"mode": "run", "stdout": "[20 22]\n[99 22]\n[73 96 89 62]\n"} -->
```dewy
original = [20 22]
copy = original
copy[0] = 99
printl(original)
printl(copy)

bump = (@xs:array<int>) => { loop i in [0..xs.length) xs[i] += 1 }
scores = [72 95 88 61]
bump(@scores)          # visible at the call: scores may change
printl(scores)
```

Arrays and strings share their storage until one side writes, so a copy is cheap until it is needed.

## Missing values are values

There is no `null` and no `unwrap`. A result that may be absent has a type like `int | none` (written `int?`), and the code handles both cases: test it with `is?`, give a default with `??`, or `match` on it.

<!-- dewy-example: {"mode": "run", "stdout": "found at 1\nnot found\n2\n"} -->
```dewy
position_of = (xs:array<string> target:string):>int? => {
    loop i in 0.. and x in xs if x =? target return i
    none
}

names = ["ada" "grace" "alan"]
loop who in ["grace" "linus"] {
    let at = position_of(names who)
    if at is? int printl"found at {at}" else printl"not found"
}
printl(position_of(names "alan") ?? -1)
```

## Errors are values too

An error is a type you declare and return. The signature lists it, so a caller can see what can go wrong and must handle it before using the result.

<!-- dewy-example: {"mode": "run", "stdout": "43\nnot a number: forty-two\n"} -->
```dewy
ParseError:type = type of error & [message:string]

parse = (text:string):>int|ParseError => {
    let value = to_int(text)
    if value is? error return ParseError["not a number: {text}"]
    value
}

loop text in ["42" "forty-two"] {
    let result = parse(text)
    if result is? int printl(result + 1) else printl(result.message)
}
```

## No hidden crashes

This is the idea Dewy is built around. An index can be out of bounds, a divisor can be zero, and a conversion to a narrower type can lose the value. Most languages check these at run time and crash, throw, or silently wrap. Dewy proves each one from facts in your code. If it cannot, the program does not compile:

<!-- dewy-example: {"mode": "reject", "diagnostic": "cannot prove index is in bounds"} -->
```dewy
first = (xs:array<int>) => xs[0]
printl(first([3 1 4]))
```

```text
error: cannot prove index is in bounds: missing upper bound
    first = (xs:array<int>) => xs[0]
                               ^
    note: missing upper bound: nothing establishes `0 <? xs.length` here
    help: establish `0 <? xs.length` with a current guard or a stronger checked contract, or check it at run time with `$runtime_assert`
```

The fix is ordinary code. A guard, a loop over the positions an array has, or `get` with a fallback all give the compiler the fact it needs, and a proven check costs nothing at run time:

<!-- dewy-example: {"mode": "run", "stdout": "3\nnone\n14\n-1\n"} -->
```dewy
first = (xs:array<int>) => {
    if xs.length =? 0 return none   # the empty case becomes a value
    xs[0]                           # proven: xs has an element
}
printl(first([3 1 4]))
printl(first([]))

xs = [3 1 4 1 5]
total = 0
loop i in [0..xs.length) total += xs[i]   # every i is in bounds
printl(total)
printl(xs.get(9) ?? -1)
```

While you are sketching, write `$runtime_checks` at the top of a file or function: unproven operations then compile to checks that stop the program with a report of the values they saw. [Safer than Rust](safer-than-rust.md) goes further.

## Types that carry facts

A refinement attaches a condition to a type. Inside the function the condition is known, and at every call the compiler proves it or rejects the call.

<!-- dewy-example: {"mode": "run", "stdout": "3\n7\n42\n"} -->
```dewy
Positive:type = int<(>? 0)>
NonEmpty:type = array<int length >? 0>

first = (xs:NonEmpty) => xs[0]        # no guard needed
span = (a:int b:int<(>=? a)>) => b - a
share = (total:int n:Positive) => total // n

printl(first([3 5 8]))
printl(span(3 10))
printl(share(84 2))
```

<!-- dewy-example: {"mode": "reject", "diagnostic": "refinement refuted: 0 violates the declared contract"} -->
```dewy
Positive:type = int<(>? 0)>
share = (total:int n:Positive) => total // n
printl(share(84 0))
```

## Physical units

Units are values, and writing one against a number multiplies. Dimensions are checked at compile time and erased at run time, so `3m + 5s` does not compile and correct code costs nothing extra.

<!-- dewy-example: {"mode": "run", "stdout": "4500 J  9800 N  50 W\n"} -->
```dewy
from units import kg, m, N, J, W

mass = 10kg
velocity = 30m/s
energy = 1/2 * mass * velocity^2
force = 1000kg * 9.8(m/s^2)
power = 20N * 10m / 4s

printl"{energy/J} J  {force/N} N  {power/W} W"
```

Seconds, minutes and hours are always available, and time has its own types: `now`, instants, durations and calendar dates.

<!-- dewy-example: {"mode": "run", "stdout": "2026-10-24T13:30:00Z\n150min\n"} -->
```dewy
const launch = instant"2026-10-24T12:00:00Z"
printl(launch + 90minute)
printl(2hour + 30minute)
```

## Generators

`lazy` in front of a loop or block makes a generator: nothing runs until a value is pulled. Combined with another iterator in one loop header, an endless generator is easy to cut short.

<!-- dewy-example: {"mode": "run", "stdout": "[2 3 5 7 11 13 17 19 23 29]\n"} -->
```dewy
primes = ():>generator<int> => $outer lazy loop n in 2.. {
    loop d in 2..n {
        if d * d >? n { break }
        if n % d =? 0 { continue $outer }
    }
    n
}

printl([loop _ in [0..10) and p in primes() p])
```

## Tests live next to the code

A test is an ordinary function marked `$test`. `$expect` states what it checks, and a failure shows the source line and the values that were compared. Run them with `dewy test file.dewy`.

<!-- dewy-example: {"mode": "check"} -->
```dewy
add = (a:int b:int) => a + b

$test
adds_numbers = () => $expect add(20 22) =? 42

$test(cases=(1 2 -3))
adds_zero = (x:int) => $expect add(x 0) =? x, "{x} changed"
```

## Whole programs

A program can define `main`, which runs once. Its `argv` parameter receives the command line, and the `argparse` library reads it into a typed record. The help text, defaults and checks come from the types.

<!-- dewy-example: {"mode": "run", "args": ["Ada", "times=2", "--shout"], "stdout": "HELLO, ADA!\nHELLO, ADA!\n"} -->
```dewy
import argparse

Args:type = [
    name = argparse.Positional<string>(help="who to greet")
    times = argparse.Named<int<(>? 0)>>(default=1 help="how many times")
    shout = argparse.Flag(help="use capitals")
]

main = (argv:array<string>) => {
    let args = argparse.parse(Args argv about="greet someone")
    let line = "Hello, {args.name}!"
    loop _ in [0..args.times) printl(if args.shout line.upper else line)
}
```

`greet --help` prints a usage message built from `Args`, and `times=0` is refused because the type says the count is positive.

## Where next

- [Getting started](ch01/00-getting-started.md): install Dewy and set up the edit loop.
- [The core language](ch05/00-general.md): the same ideas, one chapter at a time.
- [Examples](/examples/): games, simulations and tools written in Dewy.
- [The reference](/reference/): the full language design.
