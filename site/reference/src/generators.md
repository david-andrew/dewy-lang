# Generators and Lazy Sequences

> [Generated coverage](/status/#ref-generators) names related acceptance programs. Every example on this page compiles with the current compiler unless it is marked **Design only**. For a guided introduction, read [Generators and Lazy Sequences](/learn/ch03/generators.html) in *Learning Dewy*.

A generator produces values one at a time, on demand. `lazy` turns a group, block or loop into a `generator<T>`. Nothing in the body runs until a value is pulled from it.

## `lazy` and `generator<T>`

`lazy` prefixes a group `( … )`, a block `{ … }` or a loop. Function calls stay eager; a function returns a generator like any other value, and its return type is `generator<T>`.

<!-- dewy-example: {"mode":"run","stdout":"0 1 4 9 16 \n2 3 5 7 11 13 17 19 23 29 \n0:0 1:1 2:1 3:2 4:3 5:5 \n"} -->
```dewy
squares = ():>generator<int> => lazy loop i in 0.. { i * i }

primes = ():>generator<int> => $outer lazy loop n in 2.. {
    loop d in 2..n {
        if d * d >? n { break }
        if n % d =? 0 { continue $outer }
    }
    n
}

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

main = () => {
    loop _ in [0..5) and s in squares() { print"{s} " }
    printl()
    loop _ in [0..10) and p in primes() { print"{p} " }
    printl()
    loop _ in [0..6) and (i x) in fib() { print"{i}:{x} " }
    printl()
}
```

## What a Body Yields

There is no `yield` keyword. Inside a `lazy` body, each expression statement with a value yields that value; `let` declarations, assignments and `void` calls yield nothing. A conditional with no `else` yields only when its branch runs.

- **One value per advance.** `lazy (1 (2 3) 4)` yields four values, as `[1 (2 3) 4]` holds four elements.
- **Multivalue items.** When the element type is a multivalue, such as `generator<(int int)>`, each multivalue is yielded as one step.
- **Delegation.** `child()...` yields every value of another generator in turn; `xs...` spreads a sequence.

<!-- dewy-example: {"mode":"run","stdout":"[1 2 3 4]\n[3 2 1 10 20 99]\n[20 40 60 80]\n"} -->
```dewy
countdown = (n:int):>generator<int> => lazy loop i in [0..n) { n - i }
combined = ():>generator<int> => lazy {
    countdown(3)...
    [10 20]...
    99
}
naturals = ():>generator<int> => lazy loop i in 1.. { i }
evens = (source:generator<int>):>generator<int> => lazy loop x in source { if x % 2 =? 0 { x } }

main = () => {
    let g = lazy (1 (2 3) 4)
    printl([g...])
    printl([combined()...])
    printl([loop _ in [0..4) and v in evens(naturals()) 10*v])
}
```

## Ending Early

A label before `lazy` names the generator body; `break $label` ends it. On a body that is a single loop (`$outer lazy loop …`), `continue $outer` also targets that loop. `return` is not allowed in a `lazy` body.

<!-- dewy-example: {"mode":"run","stdout":"[1 2 3 4 5 6]\n"} -->
```dewy
products = ():>generator<int> => $done lazy {
    loop a in [1..10) {
        loop b in [1..10) {
            if a * b >? 6 { break $done }
            a * b
        }
    }
}
main = () => printl([products()...])
```

<!-- dewy-example: {"mode":"reject","diagnostic":"'return' is not allowed inside a lazy generator"} -->
```dewy
main = ():>void => {
    let g = lazy { return 1 }
    printl([g...])
}
```

## Consuming a Generator

- `loop x in g { … }` pulls values until the generator ends or the loop leaves.
- Combined loop headers limit an infinite generator: `loop _ in [0..10) and p in primes() { … }`.
- `[g...]` collects every value into an array.
- `f(lazy (20 22)...)` spreads a generator into fixed parameters only when it is visibly fresh with a fixed item count. Across a function boundary, pass a multivalue instead.
- To read one value, loop and return from the first step: `loop w in words { return w }`, then the fallback.

A loop borrows a named generator: leaving the loop does not end it, and the variable still owns what is left. A temporary written in the loop header is owned by the loop and cleaned up as the loop exits.

<!-- dewy-example: {"mode":"run","stdout":"hello\n-\n[20]\n"} -->
```dewy
tokens = (text:string):>generator<string> => lazy loop w in text.split(" ") { if w not=? "" { w } }
first_token = (text:string):>string? => {
    loop w in tokens(text) { return w }
    none
}
main = () => {
    printl(first_token("  hello world") ?? "-")
    printl(first_token("   ") ?? "-")
    let g = lazy (10 20)
    loop _ in g { break }
    printl([g...])
}
```

Generators are move-only: a generator moves at its last use, and copying one is an error.

<!-- dewy-example: {"mode":"reject","diagnostic":"cannot copy a generator"} -->
```dewy
main = ():>void => {
    let g = lazy (1 2 3)
    let h = g
    printl([g...] [h...])
}
```

Indexing and slicing a generator (`g[0]`, `g[0..2)`) are not decided; the compiler says so and points to a loop or `[g...]`.

## Failures

A failure travels as one of the generator's values: `generator<int | BadLine>`. Inside a `lazy` body, `or_throw` yields the failure as the generator's last value and ends it; `or_throw<E>` does so only for failures of type `E`. A consumer can inspect each item, or write `loop x in g or_throw { … }` to leave the enclosing function with the failure.

<!-- dewy-example: {"mode":"run","stdout":"1\nBadLine[line=2]\n6\nbad line 2\n"} -->
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

## Cleanup with `defer`

`defer` inside a `lazy` body registers cleanup. Deferred cleanups run in reverse order when the generator finishes, when the consumer stops early, when it fails, and when a suspended generator is dropped. A generator that never started runs none. Deferred cleanup must not fail: a fallible expression in `defer` is rejected as not decided yet, and `return` or `break` out of a `defer` is an error.

<!-- dewy-example: {"mode":"run","stdout":"made\nstarted\n1\ncleanup\nafter\n"} -->
```dewy
ticks = ():>generator<int> => lazy {
    defer printl("cleanup")
    printl("started")
    1
    2
}
main = () => {
    let _idle = ticks       # made, never started: no cleanup
    printl("made")
    loop x in ticks() { printl(x) break }
    printl("after")
}
```

## Performance

A local, non-escaping pipeline of generators consumed by one loop fuses into that loop, with no heap allocation.

## Not in Version 1

These are cut from version 1 or not decided; the compiler rejects them with a note: a generator `.next`, `generator<T length=…>`, a `failure=` argument, yielding places (`lazy { @x }`), mutable iteration (`loop @x in g`), indexing and slicing. Who reports a generator's failed close is an open question.
