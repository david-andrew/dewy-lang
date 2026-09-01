# Refinements, Effects, and Safety

This area has a settled semantic direction and a provisional general syntax. The rules below constrain the eventual design; they do not authorize arbitrary expressions as refinements or effects.

## Refinements

A refinement combines a base type with facts every value of that type satisfies. Exact array length is a concrete instance:

```dewy
array<int64 length=3>
```

A parameterize block may attach conditions to any type. An entry is a condition when it is a one-argument lambda about the value (`int< i => i >? 0 >`), a `?`-comparison on `length` (`array< length >? 0 >`), or a `length=N` assignment; every other entry is a type parameter. A refined array type may leave its element open and receive it on application (`NonEmptyArray<int>`). A condition compares against an integer literal or a fixed-width type's `min`/`max` (`uint64.max`), and may be a one-direction comparison chain — `0 <? length <=? uint64.max` is the two conditions `length >? 0` and `length <=? uint64.max`, `i => 0 <=? i <=? 100` likewise — following the [chaining rules](operators-and-precedence.md#chained-comparisons). A refined type is named like any other:

<!-- dewy-example: compiler -->
```dewy
nonemptystring = string<0 <? length <=? uint64.max>
let eat_whitespace = (src:nonemptystring):>uint64? => {
    loop i in 0..uint64.max and i <? src.length {
        if src[i] not =? ' ' return i
    }
    return src.length
}
```

Checking a value against a refined type yields one of three outcomes: proven, refuted (a compile error), or unknown (reported as unproven, never as false). A binding declared with a refined type carries the base type together with the proven facts: integer bounds feed range analysis and minimum lengths feed bounds proofs. Refinements currently apply to bindings; refined parameters and results are provisional.

Refinement facts may arise from annotations, literals, ordinary control-flow conditions, successful explicit checks, and trusted interfaces. The facts the compiler tracks today include exact and minimum array lengths, `i <? xs.length` index guards, integer intervals, narrowed union members, and proven dictionary and set keys.

```dewy
if index >=? 0 and index <? values.length
    use(values[index])
```

Inside the body, the index relationship is available to prove the access valid. Mutation and calls invalidate any fact they may falsify.

The general proposition language must be a deliberately bounded, decidable fragment. Unsupported Dewy expressions produce an unknown proof result or a diagnostic; they do not silently enter refinement checking as trusted predicates.

### Refined Parameters

A parameter may carry a refinement: `(n:int64 d:int64<d not=? 0>)`, `(xs:array<int64 xs.length >? 0>)` — inside the annotation the parameter's own name is the value, so no lambda is needed (the lambda form `int64<i => i not=? 0>` remains for aliases). `int64 & ~0` spells the same exclusion structurally. An object value may be refined by an integer field: `r:Ratio<bottom >? 0>` (also `r:Ratio<r.bottom >? 0>` or `q => q.bottom >? 0`) — proven from a literal's field, from a guard on the field (`if r.bottom >? 0 { value(r) }`), and assumed for `r.bottom` inside the body. Dispatch applies on the base type; the refinement is an obligation at every call site, proven the way `$assert` is — from constants at check time, otherwise by the bounds analysis from guards (`if d not=? 0 { f(n d) }`, `$runtime_assert d >? 0`), intervals (a loop variable over `1..3`), and length facts (`xs.length >? 0`). A refuted obligation and an unprovable one are both errors (`refinement refuted`, `cannot prove refinement`), with a note on what the analysis knew. Inside the body the refinement is a fact: `n // d` is proven with `d:int64<i => i not=? 0>`, `xs[0]` with `length>?0`.

Two related spellings make invalid states unrepresentable rather than merely checked. A union of integer singletons — `sign:-1|1` as a field, `s:-1|1` as a binding or parameter, `:>-1|1` as a result — is a word whose value set is its invariant: storing into it is an obligation (`sign = -a.sign` is proven from `a.sign`'s facts) and reading it yields the facts; `s is? 1` on such a word is the comparison `s =? 1`, and `s is? -1|1` an `or` of comparisons (`|` binds above `is?`). A union that mixes literals of different kinds (`1 | 2 | "fast"`) remains a tagged union tested with `is?`. A field may also carry a length invariant, `limbs:array<uint64 length >? 0>`, proven at construction and assumed on every read (`v.limbs[0]` needs no guard). And a literal beside an object type, `0 | [sign:-1|1 limbs:…]`, is a tagged union that `x =? 0` / `x not=? 0` narrow like `is?`; `T & ~0` on such a union names it without the literal member — the nonzero object — so a parameter `d:bigint & ~0` is satisfied by a binding narrowed with `if d not=? 0 { … }`. A field may also be refined by a field of its own type — `start:Point<x >=? 0>` — proven where the enclosing value is built (from a literal, or from a guard such as `if p.x >=? 0 { [start = p …] }`) and a fact wherever `s.start.x` is read; on a `0 | [...]` type the same spelling refines the object member, so `bigint<sign =? 1>` is a positive big integer, nonzero by construction (the abstract rational's denominator is one).

<!-- dewy-example: compiler -->
```dewy
let percent = (part:int64 whole:int64<whole >? 0>):>int64 => part * 100 // whole

let share = (part:int64 whole:int64):>int64 => {
    if whole >? 0 { return percent(part whole) }   # the guard proves the obligation
    return 0
}

let main = ():>int64 => percent(1 4) + share(3 4)   # 25 + 75
```

### Refined Results and Field Invariants

A result may be refined — `let positive = (n:int64):>int64<i => i >=? 1> => …` — in which case every `return` (and the body's value) is an obligation, and every call is a fact: `n // positive(n)` is proven, and `let g = positive(n)` carries the fact on `g`.

A field may declare an invariant: `let Ratio:type = [top:int64 bottom:int64<bottom >? 0>]`. It is proven wherever a `Ratio` is made — `Ratio(1 2)`, a literal, or a plain object flowing into the type — and wherever the field is stored (`r.bottom = z` needs `z >? 0`), and it is assumed wherever the field is read, so `r.top // r.bottom` is proven for any `Ratio`. The prelude's `rational<int64>` (`Rational`) declares `denominator:int64<denominator >? 0>` this way.

<!-- dewy-example: compiler -->
```dewy
let Ratio:type = [top:int64 bottom:int64<bottom >? 0>]
let scale = (r:Ratio):>int64 => r.top // r.bottom      # the invariant proves the division

let main = ():>int64 => {
    let r = Ratio(84 2)
    let q:rational<int64> = 1 / 3                        # the word rational declares the same invariant
    return scale(r) // 42 * (9 // q.denominator)         # 3
}
```

Facts about an object's integer field (`if r.bottom >? 0 { r.top // r.bottom }`) are tracked by member route, like array lengths, until the field or its object is reassigned; and a loop over an array or dictionary literal of constants that is never mutated bounds the loop variable by those constants.

## No Traps

Dewy is a trap-free language. A compiled program never aborts, panics, or crashes on a path the programmer did not write: the only exits are the ones spelled out in the source — `return`, a failed `$runtime_assert`, an explicit call to exit. Every operation that could fail is handled in one of two ways, and never a third:

1. **A compile-time proof.** If the precondition is provable — an index within a proven length, a divisor a guard or refinement makes nonzero, a refinement an obligation discharges — the operation compiles to the bare instruction, with no check at runtime. If it is *not* proven, that is a compile error, and the fix is more facts (a guard, a refined type, an assertion), not a runtime check inserted by the compiler.
2. **A value.** If a failure is genuinely undecidable at compile time — arithmetic on 64-bit parts that may overflow, `tan` of an angle whose cosine may be exactly zero, reading a file that may not exist — the operation's type says so: `rational | Overflow`, `fixed | DivisionByZero`, `T | none`, and the caller handles that branch explicitly (`is?`, `or_throw`, a default).

The compiler therefore never emits a fallback that changes an operation's meaning, and the library never contains one: no silent wrap-to-zero, no clamping, no "unreachable" abort. The rule follows from proofs-over-exceptions — whatever raises in Python must in Dewy be proven safe or return a value — and it is what makes the proofs worth trusting: a program that compiles has no hidden exit.

The same holds for code written *for* others. It is unidiomatic for a library to exit the process on its own account: an explicit exit is a decision about the whole program, which only the program's author can make. A library that cannot prove a precondition moves the proof to its caller (a refined parameter — `divide = (a:int64 b:int64 & ~0)`), and one that meets a failure it cannot rule out returns it (`:> T | Overflow`). Exits and `$runtime_assert` belong in applications, at the points their authors chose. The standard library is written this way throughout.

## Operation Preconditions

An ordinary partial operation is valid when its precondition is proven. Examples include indexing within bounds, dividing by a nonzero value, narrowing a number into a smaller representation, and satisfying a function's refined input contract. Integer `//` and `%` require the divisor proven nonzero: an interval that excludes zero (`d >? 0`, a loop variable over `1..3`), a `d not=? 0` guard (or a failed `d =? 0`), a refined parameter, or a `$runtime_assert`; otherwise `cannot prove the divisor is nonzero` is reported with the divisor's known range.

When a fact cannot be proven statically, the program chooses an explicit checked operation, establishes the fact with control flow, supplies a checked proof, or crosses an explicit `unsafe` boundary. The compiler must not insert a hidden semantic fallback that changes the operation's type.

## Assertions

`$assert condition` states a fact the compiler must prove; `$assert condition, message` adds a string literal to the diagnostic. It has the three refinement outcomes: proven (nothing is emitted), refuted (`assertion refuted`), or unknown (`cannot prove assertion` — the fact is neither proven nor refuted). Facts come from the checker's folding and from the bounds analysis: constants, exact and minimum lengths, integer intervals, and index facts from guards.

A refuted or unproven `$assert` underlines the condition, uses the message as the pointer text, and explains in `note:` lines what the analysis knows about each operand and what that decides for each comparison (`` `i` is 3 ``, `` `xs.length` is 3 (the array has exactly 3 elements) ``, ``so `i <? xs.length` is false``).

`$runtime_assert condition` and `$runtime_assert condition, message` evaluate the condition at runtime. When it fails, the program writes the same report shape to stderr through `library/reporting.dewy` — the excerpt with the condition underlined, the message (which may interpolate values) as the pointer text, and `note:` lines with the value of each non-literal comparison operand (re-evaluated on the failure path) — and exits with status 101. The failure path diverges, so the code after the assertion holds the condition's facts exactly as code after an early-return guard does. A runtime assertion whose condition the analyses refute is still a compile-time error.

<!-- dewy-example: compiler -->

```dewy
let xs:array<int64> = [1 2 3]
$assert xs.length =? 3, "three elements"

let get = (ys:array<int64> i:int64):>int64 => {
    $runtime_assert i >=? 0 and i <? ys.length, "index {i} out of range"
    return ys[i]                      # proven by the assertion
}

let main = ():>int64 => {
    loop i in 0..2 { $assert i <? 3 }
    return get(xs 1)                  # 2
}
```

`$expect condition, message` is the assertion form for tests: a failure is recorded and returns from the enclosing function instead of exiting, a refuted condition is a warning rather than an error, and the code after it holds the condition's facts like the code after an assertion. See [Testing](testing.md).

The assertion directives are *forms* with their own argument grammar, like `if cond body` or `return expr`, not operators: `$assert expr [, expr]`. The directive owns the top-level comma of its argument — it separates the condition from the message — so the comma's operator precedence (tighter than the comparisons) never applies there, and `x <? 3, "message"` is the condition `x <? 3` with the message `"message"`. A condition that is itself a tuple comparison is parenthesized, `$assert pair =? (1, 2)`, as a form's argument would be anywhere. A compile-time message must be a string literal.

## Effects

An effect describes observable behavior relevant beyond a function's return value. The intended effect model covers at least mutation, allocation, blocking, I/O or host capability access, failure, nonreturning control flow, and escape of storage or handles.

Effects propagate through calls. A caller may preserve a refinement or borrow storage only when the callee's effects prove that behavior safe. Unresolved indirect calls require a conservative effect contract.

`noreturn` is a settled effect used by a function that cannot return to its caller. It is distinct from the `never` result type.

Expected failures remain [error alternatives in the return type](errors-and-forwarding.md), not members of the effect set. A contract may contain both a returned error union and effects, but `|` combines the returned alternatives while the effect syntax describes evaluation behavior separately.

## `unsafe`

`unsafe` identifies a proof or memory-safety obligation the compiler has not established. It is an auditable trust boundary, not a request to turn off unrelated checking.

## Provisional Boundary

The complete proposition grammar, qualifier inference, proof-value form, effect vocabulary, effect polymorphism, and surface syntax for `unsafe` remain provisional. Error-value propagation has its own settled core and provisional surface details; see [Errors and Forwarding](errors-and-forwarding.md) and [Design Maturity](design-status.md).
