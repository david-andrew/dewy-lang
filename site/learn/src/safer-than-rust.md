# Safer than Rust

Rust is the standard for memory safety, and Dewy does not claim to beat it there. The claim is about everything else a safe Rust program can still do: abort on `v[i]`, abort on `unwrap`, panic on overflow in a debug build and wrap in a release build. Dewy's rule is that none of these happens behind your back. Each partial operation is proven from facts the compiler can see, handled as a value, or written out by the author.

Some of this works in today's compiler and some is decided and landing. Each section below says which. Every example on this page is compiled by the website build, and a rejection example appears only where today's compiler rejects it.

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

An index, a nonzero divisor or a narrowing that the compiler cannot prove is an obligation. With checks off, it is a compile error that names the missing fact:

<!-- dewy-example: {"mode": "reject", "diagnostic": "cannot prove index is in bounds"} -->
```dewy
$runtime_checks=false
at = (xs:array<int64> i:int64):>int64 => xs[i]
```

The fix is more facts (a guard such as `if 0 <=? i and i <? xs.length`, or a refined parameter) or a value (`xs.get(i)`), not a hidden check.

**Status.** Working today: exact `int`, `get`, `??`, and the compile error above under `$runtime_checks=false`. Landing: that compile error becomes the default. Until then an unproven index in a default build still compiles to a runtime check that stops the program with exit status 101 and a report.

## Fixed-width arithmetic never wraps silently

Rust's `i32` overflow panics in a debug build and wraps in a release build, so the same program can behave differently by build mode. In Dewy, arithmetic on `int32`, `uint8` and the other fixed-width types is exact like `int`; the width is a storage property. Storing a result back into a narrower binding, field, parameter or return is the narrowing obligation: free when the compiler proves it fits, otherwise a compile error with fix-its. Wrapping and saturating are still available, but only when the type says so (`uint32<overflow='wrap'>` for hashes and checksums).

**Status.** Decided, in progress, and not yet today's behavior. Today's compiler still wraps a fixed-width result when it is stored (an `int32` holding `2147483647` plus one stores `-2147483648`), and the explicit wrap form is currently `wrap<uint8>(x)`. The exact arithmetic, the narrowing error and the `overflow=` spelling are landing.

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

**Status.** Working today, including the rejection above and the structural `Send` and `Sync` checks.

## `panics` and `blocks` as checkable effects

An effect row says what a function may do, and `& no ...` forbids one. A function can promise that it never blocks, and the compiler checks the promise through everything it calls:

<!-- dewy-example: {"mode": "reject", "diagnostic": "blocking operation exceeds the contract"} -->
```dewy
tick = (n:int64):>int64 & no blocks => {
    printl(n)
    return n + 1
}
```

`printl` does I/O, so `tick` is rejected. Rust has no checked equivalent in the language: whether a function panics or blocks is a convention in its documentation.

The `panics` effect is the same idea for failure. "May fail a runtime check", or any other possible panic, is an inferred effect that shows in rows. `& no panics` forbids it outright, and code that opted into runtime checks cannot be called from a scope that did not.

**Status.** `& no blocks` works today. `panics` and `& no panics` are decided and in progress; today's compiler does not accept `no panics` yet.

## `$no_hidden_costs`

A module, function or block can ask for the strict lane with one line. It turns on explicit copies, turns off runtime checks and `$prototype`, and gives functions without a row of their own `no allocates`. An unproven index is then an error, and so is an allocation or an implicit costly copy:

<!-- dewy-example: {"mode": "reject", "diagnostic": "cannot prove index is in bounds"} -->
```dewy
$no_hidden_costs
at = (xs:array<int64> i:int64):>int64 => xs[i]
```

Code that needs more opts out with `$no_hidden_costs=false` in its body, or declares a row of its own. Game code never has to enter this lane.

**Status.** Working today for checks, allocation and copies. `no panics` joins the bundle when the `panics` effect lands.

## What this does not claim

- Memory safety and data-race freedom are table stakes, and Rust has them too.
- Dewy's `unsafe` boundary and foreign calls are trusted, as in Rust.
- The strongest form of the claim, no hidden traps by default, describes where the language is going. This page marks what a current build does.
