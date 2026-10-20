# Operator precedence — adjustments

Proposed and landed 2026-08-31 (all four moves; `as` left in place). Kept as
the rationale. The live table is `operator_groups` in
`dewy/parser/p0.py`; the user-facing copy is
`site/reference/src/operators-and-precedence.md` (slightly behind: it omits
`or_throw`).

The skeleton is sound: arithmetic, then scale/shift, then compose (`&` `|`),
then ask (`=?` `is?` …), then combine answers (`and`/`or`), then annotate /
convert / bind. The `&` / `and` split, comma above range (`0,2..10`), iterator
`in` between range and `and`, `:>` above `=>` above `|>`, `@` at the top, `^`
above unary minus, and assignment as `fail` should stay.

Three table rows look out of place (`not`, comparisons, `or_throw`). `as`
stays. `of` is not a table move: `type of` should stop being the same
operator as bound-`of`.

## 1. Put word-`not` with the word connectives

Today `not` sits with `~`, above `^` and the tests. That is the C `!x == y`
slot: `not x =? y` is `(not x) =? y`.

`~` belongs there (masks, types: `~flags =? 0`, `int64 & ~0`). Word-`not`
belongs just above `and`, below the tests — the same symbol/word split already
used for `&` / `and`. The fusion of `x not =? y` into one inverted comparison
is a tell that people want `not` next to tests.

After the move:

| spelling | parse |
|---|---|
| `not x =? y` | `not (x =? y)` |
| `~flags =? 0` | `(~flags) =? 0` |
| `not a and b` | `(not a) and b` |
| `x not =? y` | inverted comparison, as today |

## 2. `type of` and bound-`of` should not share a precedence

There is no single infix-`of` level that is right for both:

- minting wants `type of X & Y` = `(type of X) & Y` — mint the parent, then
  intersect (the documented hybrid; `&` never mints);
- a generic bound wants `<T of A & B>` = `T of (A & B)` — the bound is the
  whole right-hand side.

Today they are the same operator, with `&` tighter, so the generic reading
wins and minting is `type of (X & Y)`. The checker then special-cases that
tree (`_mint_branded_object` walks the `&` operands of the `of` right-hand
side). The tests (`type of any & [text:string]`, `type of Token & [text]`)
compile as that special case, not as mint-then-intersect.

Do not raise infix `of` (that breaks `<T of A & B>`). Make `type of` its own
prefix, tighter than `&` / `|`, and leave bound-`of` where it is. Then both
unparenthesized spellings mean what they look like. The minting fixtures
keep their source; the checker has to accept a mint *under* an `&` as the
alias RHS (`(type of Token) & [text:string]`) instead of requiring the
root to be `of`.

`type of error`, `type of any`, `type of [fields]`, and `<T of int>` do not
change. `(type of error) & [fields]` in the docs becomes the same tree
without the parens.

## 3. Chain comparisons, but only one direction

`a <? b <? c` is `(a <? b) <? c` today — a bool compared with `c`. Useless,
and the C-family trap.

Chain (nicer than `fail`). Meaning is consecutive `and`, each interior
operand evaluated once: `0 <? x <? 10` is `0 <? x and x <? 10`.

Do not take Python/Julia's "any comparison, any mix." A chain is one
monotonic statement. Operators are rising (`<?` `<=?`), falling (`>?` `>=?`),
or equal (`=?`, allowed in either without changing direction). Mixing rising
with falling is an error. `not =?`, `is?`, `isnt?`, and `in?` do not chain
(write `and`).

| ok | no |
|---|---|
| `0 <? x <? 10` | `0 <? x >? 10` |
| `0 <=? x <? n` | `x is? int64 <? 10` |
| `10 >? x >=? 0` | `a <? b not =? c` |
| `a =? b =? c` | |
| `0 <? x =? y <=? 10` | |

## 4. Drop `or_throw` below `as`, not up with `?`

`A or_throw ⊗ B` is `(A or_throw) ⊗ B` at any height — postfix applies to `A`
before the infix is seen. Height only changes `A ⊗ B or_throw`: high binds to
`B`, low binds to `(A ⊗ B)`.

High (Rust `?`, with postfix `?`) makes `2 * f(x) or_throw` unwrap the call,
but `f(x) * 2 or_throw` is `f(x) * (2 or_throw)`, which is almost never
meant. Low makes both multiplies agree and matches the name: “this
expression, or throw.” That is also the reading fallible arithmetic wants
(`x * 2 or_throw` on `int64 | Overflow`, `a / b or_throw` on
`DivisionByZero`). `lookup(id) or_throw` and `f(x) or_throw * 2` are the same
either way.

Do not put it *in* the `or` row. `as` sits below `or`, so an `or`-level
`or_throw` is tighter than `as`: `bytes as string | none or_throw` would be
`bytes as ((string | none) or_throw)`. Park it immediately below
`as` / `transmute` (still above `of`, `:`, `=>`, pipes, assignment):

| spelling | parse |
|---|---|
| `lookup(id) or_throw` | `(lookup(id)) or_throw` |
| `f(x) or_throw * 2` | `(f(x) or_throw) * 2` |
| `f(x) * 2 or_throw` | `(f(x) * 2) or_throw` |
| `2f(x) or_throw` | `(2 * f(x)) or_throw` |
| `bytes as string \| none or_throw` | `(bytes as (string \| none)) or_throw` |
| `2 * (f(x) or_throw)` | scale a fallible call (parens required) |

The current row — between juxtaposition-multiply and `*` — is the worst
slot: the two multiplies disagree, and it is neither a tight postfix nor a
loose “or”.

## Leave `as` where it is

`as` below `|` is required for `bytes as string | none`. A single right-binding
cannot eat `|` (looser than `+`) and refuse `+` (tighter than `|`), so
`x as int64 + 1` is `x as (int64 + 1)`. Write `(x as int64) + 1`. Document
that line; do not raise `as`.

Postfix `?` above `|` (`int64|string?` is `int64|(string|none)`) and shifts
below `+` are the same kind of judgment call. Do not reshuffle them with the
four moves above.

## Also

The reference table should list `or_throw` (and the extra shift / `\` rows
that live in `p0.py`) whenever the parser table is treated as the source of
truth, even if none of the moves land.
