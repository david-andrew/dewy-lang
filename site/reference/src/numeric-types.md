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

## Numeric Hierarchy

Dewy's intended numeric model includes exact integers and rationals, real numbers, concrete floating-point representations, complex numbers, and quaternions. The relationship among these types is intended to permit information-preserving use of a narrower domain where a broader one is required.

The complete construction, promotion, literal, rounding, and exceptional-value rules outside integers remain provisional. Until those rules are specified, names such as `rational`, `real`, `float32`, and `float64` identify the intended domains but do not imply undocumented coercions.

## Representation Selection

Semantic type and storage representation are separate. A value with `int` semantics may use a fixed-width machine representation when compile-time range analysis proves that choice equivalent for every reachable value. If the proof is unavailable, an implementation must preserve arbitrary-precision behavior rather than silently choosing overflow.
