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

## Shifts

Shift counts are unsigned. A negative literal count is therefore a type error.

For a fixed-width value, shifting by at least its width reaches the continuation bits of that shift:

- left shift produces `0`;
- unsigned right shift produces `0`;
- signed right shift produces `0` for a nonnegative value and `-1` for a negative value.

Operands are evaluated once.

## Rationals

`rational` is an exact fraction, kept normalized: a positive denominator and coprime parts. `a / b` on integers yields a rational (`//` is floor division and stays integral); a decimal literal such as `9.8` or `1.25e2` is an exact rational. `+`, `-`, `*`, `/`, negation, and the ordered comparisons apply, and an integer operand promotes to a rational. Constant rational expressions fold at compile time; a constant zero divisor is a compile error. Rationals print as `n/d`, or as an integer when the denominator is one.

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
