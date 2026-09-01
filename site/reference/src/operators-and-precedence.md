# Operators and Precedence

Operator tokens resolve to typed operations. An operator's spelling determines parsing precedence; operand types and available overloads determine its meaning.

## Main Operator Families

- arithmetic: `+`, `-`, `*`, `/`, `//`, `%`, `^`;
- shifts: `<<`, `>>`, `<<<`, `>>>`;
- comparisons and tests: `=?`, `not =?`, `<?`, `<=?`, `>?`, `>=?`, `is?`, `isnt?`, `in?` (the tests bind like comparisons, so `a is? T and b in? s` needs no grouping; comparisons chain one direction, see below);
- symbolic composition: `&`, `|`, `~` — the same operations as `and`, `or`, `not`, binding above the comparisons (see below);
- Boolean logic: `and`, `or`, `xor`, `nand`, `nor`, `xnor`, `not`, binding below the comparisons (`not x =? y` is `not (x =? y)`);
- conversion: `as`, `transmute`; propagation: postfix `or_throw`, below `as` ("this expression, or throw");
- type relationships and construction: `of`, `has`, and the prefix `type of Parent`, which binds above `&` and `|`;
- call pipes: `|>` and `<|`;
- construction and binding: `:`, `:>`, `=>`, `->`, `<->`, `=`;
- suppression: an attached postfix `;`.

English Boolean operators short-circuit according to their truth rules. Explicit calls to the corresponding implementation functions are ordinary eager calls.

Most infix operations have a combined-assignment spelling such as `+=`. Combined assignment has assignment precedence, not the precedence of its inner operation.

## Juxtaposition

Adjacent expressions can form several operations:

```dewy
function(argument)
values[index]
2distance
values...
```

Parsing retains the meaningful call, index, and multiplication alternatives. Semantic analysis resolves the operation from the operand types and context. General juxtaposition multiplication is still a provisional implementation area, but its place in the expression grammar is settled.

## Precedence

The following table is ordered from highest to lowest. “Fail” means an ungrouped repetition at that level is rejected rather than given an arbitrary associativity. “Flat” produces one n-ary sequence.

| Associativity    | Operators or forms                                   |
| ---------------- | ---------------------------------------------------- |
| prefix           | `@`                                                  |
| left             | member `.`, call juxtaposition, index juxtaposition  |
| fail             | type-parameter juxtaposition, ellipsis juxtaposition |
| postfix / prefix | `` ` ``                                              |
| prefix           | `~`                                                  |
| postfix          | `?`                                                  |
| right            | `^`                                                  |
| left             | multiplication juxtaposition                         |
| prefix           | `*`, `/`, `//`                                       |
| left             | `*`, `/`, `//`, `%`, `\` (left division, reserved)  |
| prefix           | `+`, `-`                                             |
| left             | `+`, `-`                                             |
| left             | `<<`, `>>`, `<<<`, `>>>`, `<<!`, `!>>`               |
| flat             | `,`                                                  |
| flat             | range juxtaposition (`1..2`)                         |
| fail             | iterator `in`                                        |
| prefix           | `type of`                                            |
| left             | `&`                                                  |
| left             | `\|`                                                 |
| left             | comparisons (chaining), membership, type tests       |
| prefix           | `not`                                                |
| left             | `and`, `nand`                                        |
| left             | `xor`, `xnor`                                        |
| left             | `or`, `nor`                                          |
| left             | `as`, `transmute`                                    |
| postfix          | `or_throw`                                           |
| fail             | `of`, `has`                                          |
| fail             | `:`                                                  |
| left             | `:>`                                                 |
| right            | `=>`                                                 |
| left             | `\|>`                                                |
| right            | `<\|`                                                |
| fail             | `->`, `<->`                                          |
| fail             | assignment and combined assignment                   |
| left             | attached semicolon suppression                       |

## Symbolic and Word Composition

`&` and `and` are the same operation, as are `|` and `or` and `~` and `not`: both spellings dispatch to the same builtin, so on booleans they agree, on integers both are bitwise, on sets both are algebra, on types both compose. They differ only in precedence, the way `*` and multiplication juxtaposition do. The symbolic forms bind *above* the comparisons and the word forms *below* them, because each spelling is idiomatic for a different kind of operand:

- symbols compose types, overload sets, sets, and masks — `x is? A|B`, `d:int64 & ~0`, `Rational|Overflow`, `@print_int & @print_string`, `keys & other_keys`, `flags & MASK =? 0` — where the composed thing is then compared or tested as a whole;
- words are boolean logic over comparisons — `x >? 0 and y <? n`, `k in? d or default` — where the comparisons are the operands.

The cost is the one expression that mixes them the wrong way round: `x >? 0 & y >? 0` parses as `x >? (0 & y) >? 0`, not as a conjunction. That spelling is unidiomatic — it works directly on boolean values, which is what `and` is for — and the checker rejects the misparse in nearly every case (a boolean compared with an integer). Write `x >? 0 and y >? 0`.

`else` attaches flow alternatives outside these operator levels. Grouping with `()` or a scoped `{}` is required when the precedence table does not express the intended tree.

Word-`not` sits just above `and`, below the comparisons — the same symbol/word split — so `not x =? y` is `not (x =? y)` and `not a and b` is `(not a) and b`, while `~flags =? 0` is `(~flags) =? 0`. `x not =? y` is still the one inverted comparison.

## Chained Comparisons

`a <? b <? c` is a chain: consecutive comparisons joined by `and`, each interior operand evaluated once (`0 <? x <? 10` is `0 <? x and x <? 10`; `0 <=? f(x) <? n` calls `f` once). A chain is one monotonic statement: its operators are rising (`<?`, `<=?`) or falling (`>?`, `>=?`), and `=?` may appear in either without changing direction. Mixing directions is an error, and `not =?`, `is?`, `isnt?`, and `in?` do not chain — write `and`. Parenthesizing the left comparison (`(a <? b) =? c`) compares its boolean instead.

<!-- dewy-example: compiler -->
```dewy
let x = 5
$assert 0 <? x <? 10
$assert 10 >? x >=? 0
$assert 0 <? x =? 5 <=? 5
```

## `type of`, `as`, and `or_throw`

`type of` is a prefix that binds above `&` and `|`, so `type of Parent & Structure` mints the parent and then strengthens it — `(type of Parent) & Structure` without the parentheses; a generic bound `<T of A & B>` uses the infix `of`, which stays loose, so the bound is the whole right-hand side.

`as` sits below `|` so that `bytes as string | none` converts to the union. The cost is that `x as int64 + 1` is `x as (int64 + 1)`: write `(x as int64) + 1`.

`or_throw` is a postfix just below `as`: it applies to the whole expression on its left, so `f(x) * 2 or_throw` is `(f(x) * 2) or_throw`, `bytes as string | none or_throw` is `(bytes as (string | none)) or_throw`, and `lookup(id) or_throw` and `f(x) or_throw * 2` read as they look. Scaling a fallible call before propagating needs parentheses: `2 * (f(x) or_throw)`.

This table lists source-language forms whose place in the expression grammar has been selected. Token spellings reserved by the parser for future operations—such as left division, expression-producing assignment, compile-time assignment, and additional shift forms—do not acquire language semantics merely by being tokenizable.

## Retired Operators

Three test operators were reserved early and removed on 2026-08-28; the symbols are free.

- `of?` — a value-level "is this of type T?". It duplicated `is?`.
- `has?` — a value-level "does this value have this structural binding?", meant to pair with the reserved type-level `has` (the binding side) the way `is?` pairs with `of`. Held back with `has` until structural binding is designed; today the question is a compile-time fact about the value's type.
- `@?` — "do two place expressions designate the same place?". Places are borrows (`@x` parameters, `@` routes), not first-class values, and the ownership model gives every value one owner and never exposes storage sharing, so no program can observe the answer.
