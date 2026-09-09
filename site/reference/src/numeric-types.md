# Numeric Types

## Integer Semantics

`int` is an arbitrary-precision signed integer type. `uint` is its nonnegative counterpart. Their semantics do not silently change to machine-width overflow because a compiler chooses a compact representation.

Fixed-width types use `intN` and `uintN` names such as `int8`, `int32`, and `uint64`. Arithmetic and bitwise operations on a fixed-width value remain at that width and roll over according to its bit representation.

The *natural* numbers, `nat` and `natN` (`nat8` … `nat64`), are the non-negative integers of a signed width: `nat64` is `int64 & <(>=? 0)>`, an `int64` carrying the fact that it is never negative. It is what a count is; a size is the `addr` below. Being an `int64` underneath, a `nat64` takes part in `int64` arithmetic without conversion (`src.length - i`), and stores into a `uint64` by its own fact; storing an `int64` into a `nat64` is the proven conversion described below (`let n:nat64 = a - b` after `if a >=? b`), never a wrap. A `nat64` may carry further facts (`nat64<(<=? src.length)>`). Use `uint64` for what is genuinely a bit pattern — hashes, masks, wrapping arithmetic — not for sizes.

`addr` is the natural that fits the target's address space: a `nat64` carrying one more fact, that it is a *position* — below `2^bits`, where `bits` is the target's address width (48 on `x86_64`, `arm`, `riscv`, and `c`; 32 on `wasm32`), so it is `[0, 2^48)` on a 64-bit target and `[0, 2^32)` on `wasm32`. It is what `.length` is, and what an offset or an index is. Two positions in one address space add and subtract without leaving it — the same axiom that lets a length grow one element at a time — so `s.start + by`, `end - start` after `if start <=? end`, and `i + 1` under `i <? src.length` are `addr` values with no further proof, where a `nat64 + nat64` is an `int64` sum that may wrap. Storing an arbitrary `nat64` or `int64` into an `addr` is the proven conversion: it passes when the facts bound the value by a length (`i <=? src.length` after a guarded loop, an index fact, a `:>addr<(<=? src.length)>` result) or by a constant below the cap, and is otherwise an error naming the obligation (`value is a position in the address space`); a product or an unbounded sum is not a position. A constant at or above the cap is refuted. An `addr` is a `nat64` wherever one is wanted, and a record field or binding made from an `addr` keeps the name (`[length=result]` from an `addr` is `[length:addr]`). Spans and offsets in the standard reports are `addr`.

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

Arithmetic, comparisons, `//`, `%`, `^`, and `/` (an exact `rational`) apply to big integers. A `bigint` is `0 | [sign:-1|1 limbs:array<uint64 length >? 0>]`: zero is its own case rather than a sign value, so no negative zero and no zero with limbs is representable (canonical limbs — no leading zeros — remain the constructors' convention). `if x =? 0` / `x not=? 0` narrow between the two cases like `is?`, `bigint & ~0` names the nonzero form, and a big divisor must have it: `a // b`, `a % b`, and `a / b` need `if b not=? 0 { … }` or a `b:bigint & ~0` parameter (`cannot prove the divisor is nonzero` otherwise); a word divisor is proven the way any `int64 & ~0` argument is.

```dewy
let ratio = (n:bigint d:bigint & ~0):>rational => n / d
let half = (n:bigint):>bigint => n // 2          # a constant divisor proves itself
let big:bigint = 2^128
if big not=? 0 { let q = ratio(1 big) }          # `big` is `bigint & ~0` here
```

## Shifts

Shift counts are unsigned. A negative literal count is therefore a type error.

For a fixed-width value, shifting by at least its width reaches the continuation bits of that shift:

- left shift produces `0`;
- unsigned right shift produces `0`;
- signed right shift produces `0` for a nonnegative value and `-1` for a negative value.

Operands are evaluated once.

## Rationals

`rational` is an exact fraction, kept normalized: a positive denominator and coprime parts. Like `bigint` it is `0 | [numerator:bigint & ~0 denominator:bigint<sign =? 1>]` (the positive denominator is a type fact) — zero has no parts, so `q.numerator` and `q.denominator` are read behind `if q not=? 0 { … }`, which is also what a rational divisor needs. `a / b` on integers yields a rational (`//` is floor division and stays integral); a decimal literal such as `9.8` or `1.25e2` is an exact rational. `+`, `-`, `*`, `/`, negation, and the ordered comparisons apply, and an integer operand promotes to a rational. Constant rational expressions fold at compile time; a constant zero divisor is a compile error. Rationals print as `n/d`, or as an integer when the denominator is one. A decimal literal is a rational unless `fixed` is requested explicitly — by an annotation (`let x:fixed = 0.1`) or a `fixed` operand — and that coercion is the one lossy step: the constant rounds to the nearest Q32.32 value there (a constant outside the fixed range is a compile error).

The runtime representation is a pair of `int64` parts; overflow beyond that range is currently unchecked, and a runtime zero divisor is an open error-value question.

## Fixed-Point

`fixed` is a signed fixed-point number with 32 integer and 32 fraction bits. Conversions from integers and rationals round to nearest; multiplication and division truncate toward zero. A fixed operand absorbs integer and rational operands, so mixed arithmetic yields `fixed`. Trigonometric functions produce `fixed` values. Fixed values print in decimal with trailing zeros trimmed.

## Powers

`base ^ exponent` is right-associative. An integer base with a constant non-negative exponent, or an unsigned runtime exponent, yields an integer; a negative constant exponent yields a rational; a rational base takes any integer exponent. Dimensioned quantities raise their dimension to the same power and require a constant exponent.

## Floating Point

First-class IEEE floating-point types and arithmetic are planned. The initial focus is on making the numeric types people reach for without specialist mathematical or engineering knowledge work intuitively: integers, exact rationals, and fixed-point values. This sequencing does not limit the eventual numerical scope of Dewy; conventional scientific computing, including the kinds of array and tensor operations supported by NumPy and PyTorch, is an intended use case.

Floating-point arithmetic is not implemented yet. It is expected to arrive alongside the full matrix math system, although that sequencing is tentative. Supported formats, conversions, mixed-type promotion, exceptional values, and numerical execution policies remain design work; floats are not restricted to host interoperability.

## Numeric Hierarchy

The intended hierarchy places `int` below `rational`, both below `real` and `number`, with complex numbers and quaternions as further domains whose rules remain provisional.

## Representation Selection

Semantic type and storage representation are separate. A value with `int` semantics uses a 64-bit machine representation when compile-time range analysis proves every reachable value fits; the analysis validates every abstract-integer arithmetic result and every narrowing (an `int` meeting `int64`, printing, a fixed-width parameter). When the proof is unavailable, the compiler reports the obligation — the value is only known to lie in some interval — rather than silently choosing overflow; the program annotates a fixed width or narrows the value with a comparison.

`min(a b)` and `max(a b)` are the smaller and larger of two values, for `int64` and `uint64` (a call on integer literals alone takes `int64`, unless the expected type says `uint64`). Their results carry [type facts](refinements-and-effects.md#type-facts): `min(k src.length)` is at most `k` and at most `src.length`, so `src[..min(k src.length))` slices without a guard; `max(a b)` is at least either.

## Meeting Another Width

A value of one integer width meeting another — an abstract `int` or an `addr` length stored into a `uint64`, an `int8` widened to `int64` — is a conversion the bounds analysis must prove in range from the facts it has: the type's own range (widening always passes), a comparison, a length (never negative), or a loop guard. An unproven narrowing is a compile error naming the known range (`let b:int8 = w` for an arbitrary `w:int64`), never a silent wrap. The same holds when the target is a union with one fixed-width integer member such as `uint64?`: the integer becomes that member, with that member's proof. Spelling the conversion explicitly (`src.length as uint64`, `n as int8` after `if n <=? 127`) is the same proven cast, not a reinterpretation: an unproven `as` reports the same obligation. Comparisons between different widths (`i:uint64 <? s.length`) compare in the left operand's width — the right operand takes the same proven cast, so no value is ever reinterpreted.

<!-- dewy-example: compiler -->
```dewy
first_over = (xs:array<int64> limit:int64):>uint64? => {
    loop i in 0.. and i <? xs.length {
        if xs[i] >? limit return i      # `i` lies in [0, int64.max]: a `uint64`
    }
    return none
}
```

An abstract-integer counter stepped inside a guarded loop needs no annotation: in `i = 0  loop i <? src.length { i += 1 }` the analysis first widens `i` to `[0, ∞]` and then narrows it back to what the guard admits, `[0, cap]`, so the comparison and the steps fit a word (a counter that can genuinely pass the word, `loop true { i += 1  if i >? n break }` for an arbitrary `n:int64`, is still reported).

A comparison between two terms — bindings, fields, lengths — is also kept as a fact about their *difference*, the one relational fact the analysis holds: under `i <? src.length` the value `src.length - i` is at least 1, under `start <=? end` the value `end - start` is at least 0, and after `a =? b` the difference is exactly 0. So `let rest:nat64 = src.length - i` proves inside the guarded loop, and a span width proves after `if 0 <=? start <=? end` (the lower bounds also keep the subtraction within `int64`). A slice's length is its endpoints' difference read the same way — `src[i..]` under `loop i <? src.length` has length at least 1, so it satisfies a `string<length >? 0>` parameter. The fact drops when either side is assigned (except `i += c` / `i -= c` by a constant, which moves the difference by `c` and keeps the fact while it stays nonnegative — `i <? src.length` then `i += 1` leaves `i <=? src.length`), when the sequence shrinks, and at a join where only one path established it — unless the other path implies it from its intervals (`i = 0` before a loop implies `i <=? src.length`, so a counter that steps by one is within the length at the loop's exit); arithmetic on fixed widths stays at the operands' width and meets the annotated width afterwards, so `let w:nat64 = end - start` is `int64 - int64` followed by the proven cast.

<!-- dewy-example: compiler -->
```dewy
remaining = (src:string):>nat64 => {
    i:int64 = 0
    total:nat64 = 0
    loop i <? src.length {
        let rest:nat64 = src.length - i    # at least 1 while the guard holds
        total += rest
        i += 1                              # the fact drops here, and returns with the next test
    }
    return total
}
```
