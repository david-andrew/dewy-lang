# Operators and Precedence

Operator tokens resolve to typed operations. An operator's spelling determines parsing precedence; operand types and available overloads determine its meaning.

## Main Operator Families

- arithmetic: `+`, `-`, `*`, `/`, `//`, `%`, `^`;
- shifts: `<<`, `>>`, `<<<`, `>>>`;
- comparisons and tests: `=?`, `not =?`, `<?`, `<=?`, `>?`, `>=?`, `is?`, `isnt?`, `in?`, `@?`;
- Boolean and bitwise composition: `and`, `or`, `xor`, `nand`, `nor`, `xnor`, `&`, `|`, `~`, `not`;
- conversion: `as`, `transmute`;
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
```

Parsing retains the meaningful call, index, and multiplication alternatives. Semantic analysis resolves the operation from the operand types and context. General juxtaposition multiplication is still a provisional implementation area, but its place in the expression grammar is settled.

## Precedence

The following table is ordered from highest to lowest. “Fail” means an ungrouped repetition at that level is rejected rather than given an arbitrary associativity. “Flat” produces one n-ary sequence.

| Associativity | Operators or forms |
| --- | --- |
| prefix | `@` |
| left | member `.`, call juxtaposition, index juxtaposition |
| fail | type-parameter juxtaposition, ellipsis juxtaposition |
| postfix / prefix | `` ` `` |
| prefix | `not`, `~` |
| postfix | `?` |
| right | `^` |
| left | multiplication juxtaposition |
| prefix | `*`, `/`, `//` |
| left | `*`, `/`, `//`, `%`, `\` |
| prefix | `+`, `-` |
| left | `+`, `-` |
| left | `<<`, `>>`, `<<<`, `>>>` |
| flat | `,` |
| flat | range juxtaposition (`1..2`) |
| fail | iterator `in` |
| left | comparisons, membership, type tests, place identity |
| left | `and`, `nand`, `&` |
| left | `xor`, `xnor` |
| left | `or`, `nor`, `|` |
| left | `as`, `transmute` |
| fail | `of`, `has` |
| fail | `:` |
| left | `:>` |
| right | `=>` |
| left | `|>` |
| right | `<|` |
| fail | `->`, `<->` |
| fail | assignment and combined assignment |
| left | attached semicolon suppression |

`else` attaches flow alternatives outside these operator levels. Grouping with `()` or a scoped `{}` is required when the precedence table does not express the intended tree.
