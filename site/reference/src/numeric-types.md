# Numeric Types

## Integer Semantics

`int` is an arbitrary-precision signed integer type. `uint` is its nonnegative counterpart. Their semantics do not silently change to machine-width overflow because a compiler chooses a compact representation.

Fixed-width types use `intN` and `uintN` names such as `int8`, `int32`, and `uint64`. Arithmetic and bitwise operations on a fixed-width value remain at that width and roll over according to its bit representation.

```dewy
let count:int = 10
let byte:uint8 = 255
let offset:int32 = -12
```

An integer literal is admitted to a numeric context only when its exact value belongs to that type.

## Representation and `bigint`

The compiler chooses how an `int` is stored. Range analysis proves most values fit a 64-bit word, and those lower to machine integers. A value it cannot prove word-sized — an oversized literal, a product of unbounded operands, a loop accumulator without a bound — takes the arbitrary-precision representation automatically, and every binding it flows into follows. The semantics are the same either way; only the cost differs, and `dewy analyze` reports each place a big integer was chosen and the range that forced it.

`bigint` names that representation explicitly: a `bigint` binding is always arbitrary precision, and any integer converts to it.

```dewy
let seed = 3000000000
let cube = seed * seed * seed      # 2.7e28: stored as a big integer
let big:bigint = 5                 # explicitly arbitrary precision
let f = 2^100                      # constant, folded exactly
```

A big value cannot silently cross a word-sized boundary. Returning it from a function whose result type is `int` or `int64`, passing it to a word-sized parameter, or storing it in a fixed-width binding is a compile error unless a comparison proves the range or the boundary is annotated `bigint`; `int` in a signature is a 64-bit word, so functions that carry big values say `bigint`.

Arithmetic, comparisons, `//`, `%`, and `^` apply to big integers; `/` (exact rational division) over big integers is not yet available.

## Shifts

Shift counts are unsigned. A negative literal count is therefore a type error.

For a fixed-width value, shifting by at least its width reaches the continuation bits of that shift:

- left shift produces `0`;
- unsigned right shift produces `0`;
- signed right shift produces `0` for a nonnegative value and `-1` for a negative value.

Operands are evaluated once.

## Rationals

`rational` is an exact fraction, kept normalized: a positive denominator and coprime parts. `a / b` on integers yields a rational (`//` is floor division and stays integral); a decimal literal such as `9.8` or `1.25e2` is an exact rational. `+`, `-`, `*`, `/`, negation, and the ordered comparisons apply, and an integer operand promotes to a rational. Constant rational expressions fold at compile time; a constant zero divisor is a compile error. Rationals print as `n/d`, or as an integer when the denominator is one. A decimal literal is a rational unless `fixed` is requested explicitly — by an annotation (`let x:fixed = 0.1`) or a `fixed` operand — and that coercion is the one lossy step: the constant rounds to the nearest Q32.32 value there (a constant outside the fixed range is a compile error).

The runtime representation is a pair of `int64` parts; overflow beyond that range is currently unchecked, and a runtime zero divisor is an open error-value question.

## Fixed-Point

`fixed` is a signed fixed-point number with 32 integer and 32 fraction bits. Conversions from integers and rationals round to nearest; multiplication and division truncate toward zero. A fixed operand absorbs integer and rational operands, so mixed arithmetic yields `fixed`. Trigonometric functions produce `fixed` values. Fixed values print in decimal with trailing zeros trimmed.

## Powers

`base ^ exponent` is right-associative. An integer base with a constant non-negative exponent, or an unsigned runtime exponent, yields an integer; a negative constant exponent yields a rational; a rational base takes any integer exponent. Dimensioned quantities raise their dimension to the same power and require a constant exponent.

## Floating Point

Dewy provides no floating-point arithmetic. Its targets are integer-only, and rationals and fixed-point supply exact and approximate fractions with predictable results. Floating-point types are reserved for a future host-interoperability role and imply no arithmetic or coercions.

## Numeric Hierarchy

The intended hierarchy places `int` below `rational`, both below `real` and `number`, with complex numbers and quaternions as further domains whose rules remain provisional.

## Representation Selection

Semantic type and storage representation are separate. A value with `int` semantics uses a 64-bit machine representation when compile-time range analysis proves every reachable value fits; the analysis validates every abstract-integer arithmetic result and every narrowing (an `int` meeting `int64`, printing, a fixed-width parameter). When the proof is unavailable, the compiler reports the obligation — the value is only known to lie in some interval — rather than silently choosing overflow; the program annotates a fixed width or narrows the value with a comparison.
