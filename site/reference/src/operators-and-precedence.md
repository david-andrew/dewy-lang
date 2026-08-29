# Operators and Precedence

Operator tokens resolve to typed operations. An operator's spelling determines parsing precedence; operand types and available overloads determine its meaning.

## Main Operator Families

- arithmetic: `+`, `-`, `*`, `/`, `//`, `%`, `^`;
- shifts: `<<`, `>>`, `<<<`, `>>>`;
- comparisons and tests: `=?`, `not =?`, `<?`, `<=?`, `>?`, `>=?`, `is?`, `isnt?`, `in?` (the tests bind like comparisons, so `a is? T and b in? s` needs no grouping);
- symbolic composition: `&`, `|`, `~` — the same operations as `and`, `or`, `not`, binding above the comparisons (see below);
- Boolean logic: `and`, `or`, `xor`, `nand`, `nor`, `xnor`, `not`, binding below the comparisons;
- conversion: `as`, `transmute`;
- type relationships and construction: `of`, `has`, `type of Parent`;
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
| prefix           | `not`, `~`                                           |
| postfix          | `?`                                                  |
| right            | `^`                                                  |
| left             | multiplication juxtaposition                         |
| prefix           | `*`, `/`, `//`                                       |
| left             | `*`, `/`, `//`, `%`                                  |
| prefix           | `+`, `-`                                             |
| left             | `+`, `-`                                             |
| left             | `<<`, `>>`, `<<<`, `>>>`                             |
| flat             | `,`                                                  |
| flat             | range juxtaposition (`1..2`)                         |
| fail             | iterator `in`                                        |
| left             | `&`                                                  |
| left             | `\|`                                                 |
| left             | comparisons, membership, type tests                  |
| left             | `and`, `nand`                                        |
| left             | `xor`, `xnor`                                        |
| left             | `or`, `nor`                                          |
| left             | `as`, `transmute`                                    |
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

In particular, `&` binds more tightly than `of`. A fresh nominal type with structural requirements is therefore written `(type of Parent) & Structure`. Without those parentheses, `type of Parent & Structure` groups as `type of (Parent & Structure)`.

This table lists source-language forms whose place in the expression grammar has been selected. Token spellings reserved by the parser for future operations—such as left division, expression-producing assignment, compile-time assignment, and additional shift forms—do not acquire language semantics merely by being tokenizable.

## Retired Operators

Three test operators were reserved early and removed on 2026-08-28; the symbols are free.

- `of?` — a value-level "is this of type T?". It duplicated `is?`.
- `has?` — a value-level "does this value have this structural binding?", meant to pair with the reserved type-level `has` (the binding side) the way `is?` pairs with `of`. Held back with `has` until structural binding is designed; today the question is a compile-time fact about the value's type.
- `@?` — "do two place expressions designate the same place?". Places are borrows (`@x` parameters, `@` routes), not first-class values, and the ownership model gives every value one owner and never exposes storage sharing, so no program can observe the answer.
