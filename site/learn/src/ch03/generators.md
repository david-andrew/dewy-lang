# Generators and Lazy Sequences

An array holds all of its values at once. A generator holds none of them: it makes each value when the code using it asks for the next one. That makes it the natural shape for a sequence that is long, endless, or expensive to compute, and for a pipeline of steps that should run one item at a time.

## Making a generator with `lazy`

Put `lazy` in front of a group, a block or a loop and you get a `generator<T>` instead of the values themselves. A loop pulls from it like any other sequence:

<!-- dewy-example: {"mode": "run", "stdout": "10\n20\n30\n"} -->
```dewy
main = () => {
    let g = lazy (10 20 30)
    loop x in g printl(x)
}
```

Nothing in a `lazy` body runs until a value is pulled. The prints below show the generator and the loop taking turns:

<!-- dewy-example: {"mode": "run", "stdout": "before the loop\nmaking 1\ngot 1\nmaking 2\ngot 2\n"} -->
```dewy
main = () => {
    let g = lazy {
        printl"making 1"
        1
        printl"making 2"
        2
    }
    printl"before the loop"
    loop x in g printl"got {x}"
}
```

The generator runs up to its first value, hands it over and stops there. The loop body runs, asks for another, and the generator continues from where it stopped.

## What a body yields

There is no `yield` keyword. Inside a `lazy` body, every expression statement that has a value yields it, exactly as each element of an array literal becomes an element. Statements without a value (`let`, assignments, `printl`) yield nothing, and an `if` with no `else` yields only when its branch runs.

A function that makes a generator says so in its return type. Here `lazy loop` yields one square per pass, forever:

<!-- dewy-example: {"mode": "run", "stdout": "0 1 4 9 16 \n"} -->
```dewy
squares = ():>generator<int> => lazy loop i in 0.. { i * i }

loop _ in [0..5) and s in squares() print"{s} "
printl()
```

The call `squares()` itself is eager: it returns a generator at once. Only pulling from it does work, which is why an endless loop inside is fine. The combined header `_ in [0..5) and s in squares()` stops after five values, because an `and` of two iterators ends when either side runs out (see [Loops](loops.md)).

A body can keep state between values in ordinary variables. This one yields Fibonacci numbers in pairs with their index; with a multivalue element type, each `(i a)` is one step:

<!-- dewy-example: {"mode": "run", "stdout": "0:0 1:1 2:1 3:2 4:3 5:5 6:8 \n"} -->
```dewy
fib = ():>generator<(int int)> => lazy {
    let a = 0
    let b = 1
    loop i in 0.. {
        (i a)
        let next = a + b
        a = b
        b = next
    }
}

loop _ in [0..7) and (i x) in fib() print"{i}:{x} "
printl()
```

## Pulling values out

A loop is the main way to pull. There are three other things you will reach for:

- `[g...]` spreads a generator into an array, collecting every value. Use it only on one that ends.
- `[loop ... ]` collects from a loop, so it can take a limited number from an endless one.
- To get just the first value, loop and return from the first pass, with the fallback after the loop.

<!-- dewy-example: {"mode": "run", "stdout": "[1 2 3]\n[0 1 4 9]\nhello\n-\n"} -->
```dewy
squares = ():>generator<int> => lazy loop i in 0.. { i * i }
words = (text:string):>generator<string> => lazy loop w in text.split(" ") { if w not=? "" { w } }

first_word = (text:string):>string? => {
    loop w in words(text) { return w }
    none
}

main = () => {
    printl([lazy (1 2 3)...])
    printl([loop _ in [0..4) and s in squares() s])
    printl(first_word("  hello world") ?? "-")
    printl(first_word("   ") ?? "-")
}
```

### A loop borrows a named generator

Leaving a loop early does not end a generator held in a variable. The variable still owns whatever is left, so a later loop picks up where the first one stopped:

<!-- dewy-example: {"mode": "run", "stdout": "header: id,name\n[\"1,ada\" \"2,grace\"]\n"} -->
```dewy
main = () => {
    let lines = lazy ("id,name" "1,ada" "2,grace")
    loop line in lines {
        printl"header: {line}"
        break
    }
    printl([lines...])
}
```

A generator made right in the loop header, as in `loop w in words(text)`, belongs to that loop instead, and is cleaned up as the loop exits.

A generator has a position, so there is no sensible copy of one: two copies would either share a position or replay work. Generators are move-only, and copying one is an error:

<!-- dewy-example: {"mode": "reject", "diagnostic": "cannot copy a generator"} -->
```dewy
main = ():>void => {
    let g = lazy (1 2 3)
    let h = g
    printl([g...] [h...])
}
```

## Chaining generators

A function can take a generator and return another. Each one pulls from the one before it only when it is asked for a value, so a chain of steps handles one item at a time from end to end:

<!-- dewy-example: {"mode": "run", "stdout": "made 0 1 2 3 4 5 6 7 8 \n[0 4 16 36 64]\n"} -->
```dewy
naturals = ():>generator<int> => lazy loop i in 0.. {
    print"{i} "
    i
}

only_even = (g:generator<int>):>generator<int> => lazy loop x in g {
    if x % 2 =? 0 { x }
}

squared = (g:generator<int>):>generator<int> => lazy loop x in g { x * x }

take = (n:int g:generator<int>):>generator<int> => lazy loop _ in [0..n) and x in g { x }

main = () => {
    print"made "
    let firsts = [take(5 squared(only_even(naturals())))...]
    printl()
    printl(firsts)
}
```

`naturals` is endless, and prints each number it makes. Nothing runs ahead: `take` stops after five values, and since `and` checks its left side first, it never asks for a sixth. Only the naturals up to 8 are ever made.

### Ending early with a label

`return` is not allowed in a `lazy` body, since there is no caller waiting for a result. To end a generator from inside nested loops, put a label in front of `lazy` and `break` to it:

<!-- dewy-example: {"mode": "run", "stdout": "[1 2 3 4 5 6]\n"} -->
```dewy
products = ():>generator<int> => $done lazy {
    loop a in [1..10) {
        loop b in [1..10) {
            if a * b >? 6 { break $done }
            a * b
        }
    }
}
printl([products()...])
```

When the body is a single loop, as in `$outer lazy loop n in 2.. { ... }`, `continue $outer` also skips to that loop's next pass. That makes a prime sieve short:

<!-- dewy-example: {"mode": "run", "stdout": "2 3 5 7 11 13 17 19 23 29 \n"} -->
```dewy
primes = ():>generator<int> => $outer lazy loop n in 2.. {
    loop d in 2..n {
        if d * d >? n { break }
        if n % d =? 0 { continue $outer }
    }
    n
}

loop _ in [0..10) and p in primes() print"{p} "
printl()
```

## Delegation

`g...` inside a `lazy` body yields every value of another generator in turn, and `xs...` does the same for an array. Delegating to the same function makes recursive walks direct:

<!-- dewy-example: {"mode": "run", "stdout": "[\"assets\" \"textures\" \"sky.png\" \"grass.png\" \"audio\" \"wind.ogg\"]\n[3 2 1 10 20 99]\n"} -->
```dewy
Node:type = [name:string children:array<Node>]

walk = (node:Node):>generator<string> => lazy {
    node.name
    loop child in node.children { walk(child)... }
}

countdown = (n:int):>generator<int> => lazy loop i in [0..n) { n - i }

combined = ():>generator<int> => lazy {
    countdown(3)...
    [10 20]...
    99
}

main = () => {
    let tree = Node["assets" [
        Node["textures" [Node["sky.png" []] Node["grass.png" []]]]
        Node["audio" [Node["wind.ogg" []]]]
    ]]
    printl([walk(tree)...])
    printl([combined()...])
}
```

## Failures are values

A generator whose work can fail carries the failure as one of its values. Its element type says so: `generator<int | BadLine>`. Inside the body, `or_throw` on a failure yields it as the generator's last value and ends the generator.

The code that pulls decides what to do. It can look at each item, or write `or_throw` after the loop header to leave its own function with the first failure:

<!-- dewy-example: {"mode": "run", "stdout": "1\nBadLine[line=2]\n6\nbad line 2\n"} -->
```dewy
BadLine:type = type of error & [line:int]

parse = (i:int text:string):>int | BadLine => to_int(text) ?? BadLine[line=i]

numbers = (lines:array<string>):>generator<int | BadLine> => lazy {
    loop i in 1.. and text in lines {
        parse(i text) or_throw
    }
}

total = (lines:array<string>):>int | BadLine => {
    let sum = 0
    loop n in numbers(lines) or_throw { sum = sum + n }
    sum
}

main = () => {
    loop item in numbers(["1" "x" "3"]) { printl(item) }
    printl(total(["1" "2" "3"]))
    let r = total(["4" "oops"])
    if r is? BadLine { printl("bad line {r.line}") }
}
```

The first loop prints the value, then the failure, and stops: `"3"` is never parsed. In `total`, the failure leaves the function, so its return type lists `BadLine`, and the compiler makes `main` deal with it. Nothing is thrown past code that did not ask for it.

## Cleanup with `defer`

A generator may hold something that needs closing, such as a file or a connection. `defer` inside a `lazy` body registers cleanup, and it runs however the generator ends: it finishes, the consumer stops early, it fails, or it is dropped while suspended. A generator that never started runs none, because it never acquired anything.

<!-- dewy-example: {"mode": "run", "stdout": "made one, never started\nopened\n1\nclosed\ndone\n"} -->
```dewy
readings = ():>generator<int> => lazy {
    defer printl("closed")
    printl("opened")
    1
    2
    3
}

main = () => {
    let _unused = readings()
    printl("made one, never started")
    loop x in readings() {
        printl(x)
        break
    }
    printl("done")
}
```

The loop takes one value and breaks. The generator in its header belongs to the loop, so it is dropped as the loop exits, and its `defer` runs before `done` prints. Several `defer`s run in reverse order. Cleanup must not fail, so a fallible expression in a `defer` is rejected.

## Loop fusion

A chain of generators looks as if each value travels through several suspended functions. Often it does not. When a pipeline is local, does not escape, and is what one loop iterates, the compiler fuses the whole chain into that loop: the steps become ordinary code in the loop body, with no heap allocation and no call per value.

<!-- dewy-example: {"mode": "run", "stdout": "1140\n"} -->
```dewy
upto = (n:int):>generator<int> => lazy loop i in [0..n) { i }
only_even = (g:generator<int>):>generator<int> => lazy loop x in g { if x % 2 =? 0 { x } }
squared = (g:generator<int>):>generator<int> => lazy loop x in g { x * x }

sum_even_squares = (n:int):>int => {
    let total = 0
    loop v in squared(only_even(upto(n))) { total += v }
    total
}

printl(sum_even_squares(20))
```

The compiled `sum_even_squares` is one loop over `[0..20)` with the test and the multiplication inline. So you can write a pipeline as small named steps without paying for the abstraction. A generator that is returned, stored, spread or passed somewhere the compiler cannot follow keeps its own state and is advanced one step at a time, and so, for now, is one in a combined loop header.

The [reference](/reference/generators.html) has the complete rules, including what is not in version 1.
