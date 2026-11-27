# Safer than Rust

Rust is the standard for memory safety, and Dewy does not claim to beat it there. The claim is about everything else a safe Rust program can still do: abort on `v[i]`, abort on `unwrap`, panic on overflow in a debug build and wrap in a release build. Dewy's rule is that none of these happens behind your back. Each partial operation is proven from facts the compiler can see, handled as a value, or written out by the author.

Everything on this page works in today's compiler. Every example is compiled by the website build under the default rules, and each rejection shown is one the current compiler makes.

## No hidden panics

Rust panics on an out-of-range index, on `unwrap()` of a `None`, on division by zero, and on integer overflow in debug builds. Dewy has no `unwrap`: an optional is a `T | none` that the code narrows or gives a default with `??`, and `int` arithmetic is exact, so it cannot overflow.

<!-- dewy-example: {"mode": "run", "stdout": "-1\n1\n9223372036854775808\n"} -->
```dewy
let xs = [3 1 4]
printl(xs.get(7) ?? -1)      # no element 7: the fallback
printl(xs.get(1) ?? -1)      # 1
let big = 9223372036854775807
printl(big + 1)              # int is exact: no overflow
```

An index, a nonzero divisor or a narrowing that the compiler cannot prove is an obligation. By default it is a compile error that names the missing fact:

<!-- dewy-example: {"mode": "reject", "diagnostic": "cannot prove index is in bounds"} -->
```dewy
at = (xs:array<int> i:int):>int => xs[i]
printl(at([3 1 4] 1))
```

The fix is more facts (a guard such as `if 0 <=? i and i <? xs.length`, or a refined parameter) or a value (`xs.get(i)`), not a hidden check.

A program, file, function or block that prefers runtime checks says `$runtime_checks`. Its unproven obligations then compile to checks that stop the program with exit status 101 and a report of the values they saw, and proven ones still cost nothing. That is a choice written in the source, never a silent default.

## Fixed-width arithmetic never wraps silently

Rust's `i32` overflow panics in a debug build and wraps in a release build, so the same program can behave differently by build mode. In Dewy, arithmetic on `int32`, `uint8` and the other fixed-width types is exact like `int`; the width is a storage property. Storing a result back into a narrower binding, field, parameter or return is the narrowing obligation: free when the compiler proves it fits, otherwise a compile error with fix-its. Wrapping and saturating are still available, but only when the type says so (`uint32<overflow='wrap'>` for hashes and checksums).

<!-- dewy-example: {"mode": "reject", "diagnostic": "cannot prove exact integer result fits int32"} -->
```dewy
let x:int32 = 2147483647
let y:int32 = x + 1
```

The error offers three fixes: widen the destination to `int`, state the domain as a refinement, or say what overflow means in the type:

<!-- dewy-example: {"mode": "run", "stdout": "1\n"} -->
```dewy
let h:uint32<overflow='wrap'> = 4294967295
h += 2
printl(h)
```

## Data-race freedom from value semantics

Rust prevents data races with a borrow checker and the `Send` and `Sync` traits. Dewy reaches the same guarantee from the other side: assignment, argument passing and return give the receiver its own value, so there is no shared mutable state to race on unless the source writes it (`@` at the parameter and at the call, or an atomic). A `parallel` body cannot change a variable it captured:

<!-- dewy-example: {"mode": "reject", "diagnostic": "(a data race)"} -->
```dewy
total = 0
parallel i in [0..100) { total += i }
```

Return values from the body instead, and the results are collected in input order:

<!-- dewy-example: {"mode": "run", "stdout": "[0 1 4 9 16]\n"} -->
```dewy
squares = [parallel i in [0..5) i*i]
printl(squares)
```

Rust also has data-race freedom, so this is not an advantage over Rust. It is the same guarantee without lifetimes in the signatures, which is why it belongs on this page.

The compiler infers which values may cross threads (Rust's `Send` and `Sync`) from their structure, so there is nothing to declare.

## `panics` and `blocks` as checkable effects

An effect row says what a function may do, and `& no ...` forbids one. A function can promise that it never blocks, and the compiler checks the promise through everything it calls:

<!-- dewy-example: {"mode": "reject", "diagnostic": "blocking operation exceeds the contract"} -->
```dewy
tick = (n:int):>int & no blocks => {
    printl(n)
    return n + 1
}
```

`printl` does I/O, so `tick` is rejected. Rust has no checked equivalent in the language: whether a function panics or blocks is a convention in its documentation.

The `panics` effect is the same idea for failure. "May fail a runtime check", or any other possible panic, is an inferred effect that shows in rows. `& no panics` forbids it outright, and code that opted into runtime checks cannot be called from a scope that did not.

Code that opted into runtime checks may panic, and the effect follows it through every call:

<!-- dewy-example: {"mode": "reject", "diagnostic": "it may panic, and its row excludes panics"} -->
```dewy
at = (xs:array<int> i:int):>int => {
    $runtime_checks
    xs[i]
}
safe = (xs:array<int>):>int & no panics => at(xs 0)
printl(safe([1 2]))
```

## `$no_hidden_costs`

A module, function or block can ask for the strict lane with one line. It turns on explicit copies, turns off runtime checks and `$prototype`, and gives functions without a row of their own `no allocates`. An unproven index is then an error, and so is an allocation or an implicit costly copy:

<!-- dewy-example: {"mode": "reject", "diagnostic": "cannot prove index is in bounds"} -->
```dewy
at = (xs:array<int> i:int):>int => {
    $no_hidden_costs
    xs[i]
}
```

Code that needs more opts out with `$no_hidden_costs = false` in its body, or declares a row of its own. Game code never has to enter this lane.



## What this does not claim

- Memory safety and data-race freedom are table stakes, and Rust has them too.
- Dewy's `unsafe` boundary and foreign calls are trusted, as in Rust.
- Proofs come from facts the compiler can see. Some correct programs need a guard, a refined type or a value-returning form before they compile, and the error messages say which.
