# Precision-preserving inference (2026-10-21)

Accepted design, implementing David's 2026-10-21 decision. Implemented for string
bindings (lazy domains); integers keep range facts.

## Binding rule
An annotation fixes storage's type, including an explicitly wider `string`.
Otherwise infer a common type of the initializer and all possible writes in the
binding's lexical lifetime, before checking consumers. Finite string values
join by set union; a general string source makes the join `string`. The set is
flow-insensitive: writes in either branch or any loop iteration participate.
Thus `let mode = "fast"; mode = "slow"` has `'fast'|'slow'`; an additional
`mode = "other"` adds a member rather than causing a rejected store. A match
covering only fast/slow must then fail, even if it precedes that store.
This is the scalar counterpart of later pushes settling an empty container.

Lexical identity matters: shadowing must not merge distinct bindings. Closure
writes participate in the captured binding; a closure's private binding does
not. Mutable escapes whose write domain is unknown require the base type.
Declared fields retain their declared types; inferred record fields and
container elements are outside this first scalar-storage implementation.
Preserving a field's initializer as its contract would incorrectly reject
ordinary later updates, so it needs the same whole-storage solution first.

The implementation may conservatively use the base type when determining a
write's finite domain requires arbitrary function evaluation or an unbounded
constraint solve. It must never guess a smaller domain or insert a new runtime
failure for a previously valid unannotated store. Keep ordinary string APIs
available through the existing literal-set-to-string conversion.

## Integers
Keep mathematical `int` as the public inferred type; preserve singleton/range
information as facts, not restrictive literal storage types. `count=0;
count+=1` remains valid, as does `a=5; a=300`. Existing flow facts, bounded loop
widening and bigint promotion already implement this separation. Do not infer
int8 from 5: that would change overflow semantics. Reuse existing range proofs
and unboxing; no additional integer analysis or representation pass is justified
without a measured performance benefit. Integer behavior therefore does not
change in this batch; add counter/range regression coverage.

## Payoff and cost
A finite string domain enables matches without else, finite members(), and
literal-key checking, using the existing tagged-word representation. Integer
facts enable existing checks to disappear and existing unboxed lowering.
Discover string candidates on demand and bound analysis; avoid repeat checking
of function bodies or a general fixed-point pass. The synthetic compile gate
must remain within +0.3%; runtime bench must stay within +3% of master.

No new surface needs approval. General aggregate write-domain inference and
precision across arbitrary calls are follow-up implementation work, not new
language syntax. Any inability to meet the compile budget is a failed pilot,
not grounds to weaken the gate.

## Implementation
String domains are collected lazily during checking and materialized only when a
consumer (exhaustive match, `members`, finite keys) needs them; storage stays a
string. An eager finite-set representation was too costly.

Round 6 (integers as ranges): unannotated `int` bindings collect literal writes
and once-run literal `+=`/`-=` deltas the same lazy way, settled only for an
exhaustive match or a literal-union conversion (at most 256 values, 8 deltas;
past that, or for any other write, the set is open and the type is `int`).

## Decided rules

Moved here from the decisions ledger ([decisions.md](decisions.md)), which keeps
a pointer to each rule. The wording is David's.

### Decimal literals and the decimal default

- Decimal literals adapt to context: exact unless next to a float64 operand, in
  a float64 parameter or field, or the binding is later written a float; then
  float64 at compile time (`0.1+0.2 =? 0.3` stays true).
- Decimal default (decided 2026-10-23): exact rationals stay the default; no
  decimal-float default. Principle: an expression's value never depends on
  whether the compiler folded it, so `a = 0.1 b = 0.2; a+b =? 0.3` and
  `x = 1/3; x*3 =? 1` are true everywhere. Costs addressed: an exact value carried
  around a loop through `*` or `/` (size can grow each iteration) gets a warning
  with a fix-it to annotate `float64` or another explicit representation, never
  an automatic switch; values print the way they were written (decimals as
  decimals, with a repeating marker when non-terminating; written fractions as
  fractions), with the exact display rule reported to David.

### Inference keeps the most precise type

- Inference keeps the most precise type it knows; only an explicit wider
  annotation widens (literal unions; integers keep range facts).
- Common parent: literals of sibling types infer the most precise type:
  `[Circle[...] Square[...]]` is the positional `[Circle Square]`, accepted where
  `array<Shape>` is expected. After writes the binding's type becomes the
  covering element type `array<Circle|Square>`; flow-sensitive facts keep exact
  statically known contents and length (`shapes[2]` is a `Circle` after a known
  push) and fade when knowledge runs out (loops, a small position cap).
- Uniform precision: an unannotated binding's type covers every value written.
  Strings are discrete literal unions (`'quiet'|'normal'|'verbose'`); ints are
  ranges (`1..2`, which equals `1|2`); `n += 1` widens the covering set; an
  unbounded written set (loops, `count += 1`, `mode="{mode}!"`) widens to the base
  type. This supersedes "ints widen to the base type".
- Sibling literals: after `let s = Circle[...]` and a later `s = Square[...]`,
  the exact type is tracked flow-sensitively (a `Circle` until the write, a
  `Square` after); the binding's covering type stays the union, with a warning
  suggesting an annotation (either type or the union).
- A later assignment that changes a binding's initially inferred type (e.g. a
  decimal literal adapting to float64) is a warning plus an editor squiggle,
  not an error. For decimals the diagnostic focuses on exact equality checks
  (`=?`, `not=?`) whose result the adaptation affects. Idiomatic code states
  the representation; relying on implicit adaptation is unidiomatic.

### Fixed-width integers (2026-10-22)

- Fixed-width integers (decided 2026-10-22; supersedes "`intN`/`uintN` wrap"):
  arithmetic on `intN`/`uintN` is exact, like `int`; the width is a storage
  property plus facts. Storing into an `intN`/`uintN` binding, field, parameter
  or return is the proven narrowing: free when proven, a compile error with
  fix-its (guard, overflow policy, `$runtime_checks`) when not, a runtime check
  under `$runtime_checks`, always an error under `$no_hidden_costs`.
  Intermediates never overflow spuriously; the compiler picks a wide enough
  machine width (widening multiply for `int64*int64`), never a bigint. The
  overflow policy is a keyword type parameter: `uint32<overflow='wrap'>` wraps
  modulo 2^N (hashes, RNGs, checksums, crypto), `uint8<overflow='saturate'>`
  clamps. Types are callable conversions: `uint8<overflow='wrap'>(x)` keeps the
  low bits and replaces `wrap<uint8>(x)` (removed, no alias);
  `uint8<overflow='saturate'>(x)` clamps; `transmute` stays for same-size
  reinterpretation. `//`, `%`, negation and `abs` follow the same rule
  (`int64.min // -1` is a narrowing obligation); plain `int` `MIN // -1`
  promotes.
- Conversions: `uint8<overflow='wrap'>(x)` keeps the low bits; same-size reinterpretation
  is the infix word `f transmute uint64` (like `as`). No `.bitcast`/`.wrap`
  method spellings.
- `transmute` (`f transmute uint64`) is Dewy's original spelling, restored in
  place of `bitcast`.
- Shifts with an unbounded intermediate (`(a << n) >> n`, `n` unproven) are a
  compile error with fix-its (bound `n`, compute in `int`, or an overflow
  policy).
