# Refinements and Proven Facts

A refinement is a type together with facts its values must satisfy. Length is a familiar example:

```dewy
let triple:array<int64 length=3> = [10 20 30]
```

The type says more than “array of integers”; it also says that the valid shape has exactly three elements.

## Why Refinements Matter

Useful facts let Dewy reject invalid programs and remove unnecessary runtime work:

```dewy
let first = triple[0]
```

The index needs no dynamic bounds check because the type already proves it valid.

The same idea can describe nonempty containers, positive values, relationships between parameters and results, and state changes such as an operation reducing a collection's length by one.

## Writing Refinements

A parameterize block after a type may hold conditions. A one-argument lambda states a condition on the value itself; a `?`-comparison on `length` states one on a container:

<!-- dewy-example: compiler -->

```dewy
Positive = int< i=>i>?0 >
NonEmptyArray = array< length>?0 >

score:Positive = 42
values:NonEmptyArray<int> = [3 5 8]

first = values[0]
```

Conditions and parameters are told apart by their shape: a lambda, a `?`-comparison, or a `length=N` assignment is a condition; anything else is a parameter. `NonEmptyArray` leaves the element type open, so `NonEmptyArray<int>` supplies it later.

Checking a value against a refined type has three outcomes: **proven** (a literal or known fact establishes the condition, with no runtime cost), **refuted** (`score:Positive = -3` is an error), and **unknown**, which is reported as unproven rather than false. The binding then carries the base type plus the proven facts, so `values[0]` needs no runtime check.

Each condition is a *fact*, and a block of facts is a type of its own that `&` combines with any type: `int & <i => i >? 0>` is `Positive` again, and `(int64 | uint64) & <i => i >? 0>` refines both members. That is how a function states what it establishes about its *inputs*. A boolean result says it per arm — `startswith` is declared `(text:string prefix:string):> true & <prefix.length <=? text.length> | false` — and a proposition as the result type is a *type predicate*, `true` when it holds and `false` when it doesn't:

<!-- dewy-example: compiler -->

```dewy
let Token:type = $abstract type of any & [text:string]
let Word = type of Token & []
let is_word = (tok:Token) => tok is? Word          # inferred: `:> tok is? Word`

let name_of = (tok:Token):>string => {
    if is_word(tok) { let w:Word = tok  return w.text }   # `tok` is a Word here
    return "?"
}

let skip_marker = (src:string i:uint64):>uint64<n => n <=? src.length> | none => {
    if i >=? src.length return none
    if src[i..].startswith("[[") { return i + 2 }  # the fact keeps `i + 2` within `src`
    return i
}
```

The function proves its facts at every `return` (`return tok is? Word` is its own proof; `return true` needs `tok` narrowed to `Word` at that point), and every caller gets them where the result is known.

## Facts from Ordinary Control Flow

Dewy should infer common refinements from the code programmers already write:

```dewy
if index >=? 0 and index <? values.length
    use(values[index])
```

Inside the body, the condition establishes the indexing precondition. Assignment or a call that may mutate a relevant value invalidates facts that are no longer guaranteed.

## Assertions

Sometimes the fact you rely on is not one the compiler would state on its own. `$assert` states it and asks the compiler to prove it — proven assertions cost nothing, refuted ones are errors, and an assertion the compiler cannot decide is reported as unproven rather than silently trusted:

<!-- dewy-example: compiler -->

```dewy
let xs:array<int64> = [1 2 3]
$assert xs.length =? 3, "three elements"

let get = (ys:array<int64> i:int64):>int64 => {
    $runtime_assert i >=? 0 and i <? ys.length, "index {i} out of range"
    return ys[i]
}

let main = ():>int64 => get(xs 1)     # 2
```

`$runtime_assert` checks at runtime instead. Its failure path leaves the program with a report on stderr laid out like a compiler error — the line with the condition underlined, the message under it, and notes with the values that went into it — and exit status 101, so after it the compiler knows the condition held: `ys[i]` above needs no further proof, just as it would not after `if i <? 0 or i >=? ys.length { return 0 }`.

## Explicit Boundaries

The intended model distinguishes several outcomes:

- a fact the compiler proves automatically has no runtime cost;
- an explicit runtime check refines the value after it succeeds;
- a checked proof can discharge an obligation outside automatic inference;
- `unsafe` can assert an unproved obligation while making that trust boundary visible for review.

A refinement on a *parameter* is a contract: every call has to prove it, and the body gets to assume it. Since the parameter has a name, the condition just uses it (`whole >? 0`); the `i => …` lambda form is for type aliases, where there is no name yet. Guards are the usual proof:

<!-- dewy-example: compiler -->
```dewy
let percent = (part:int64 whole:int64<whole >? 0>):>int64 => part * 100 // whole

let share = (part:int64 whole:int64):>int64 => {
    if whole >? 0 { return percent(part whole) }
    return 0
}

printl"{share(3 4)}%"   # 75%
```

Without the guard, `percent(part whole)` is an error — "cannot prove refinement" — and so is dividing by `whole` directly, since Dewy proves every division's divisor nonzero instead of letting it crash.

The same contract works the other way round on results — `(n:int64):>int64<i => i >=? 1>` promises every caller a positive number, and every `return` inside has to prove it — and on fields: `let Ratio:type = [top:int64 bottom:int64<bottom >? 0>]` is checked wherever a `Ratio` is built or `bottom` is stored, and assumed wherever `bottom` is read, so `r.top // r.bottom` never needs a guard. Dewy's own `Rational` is declared exactly like that.

> **Provisional design:** Refined annotations on bindings, parameters, results, and fields, integer comparisons against constants, length facts, and interval reasoning are settled. Richer propositions, checked proof values, and the `unsafe` syntax are not fully specified. Unsupported general Dewy expressions must not silently become refinement claims.

The design goal is inference-first: ordinary code should expose enough facts for routine safety without requiring programmers to write proofs throughout application code.
