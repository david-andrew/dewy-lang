# Operators and Precedence

> [Generated coverage](/status/#ref-operators-and-precedence) names related acceptance programs. Every example on this page compiles with the current compiler unless it is marked **Design only**.

An operator's spelling decides how it parses; its operand types and the available overloads decide what it means.

## Operator Families

- Arithmetic: `+`, `-`, `*`, `/`, `//`, `%`, `^`. See [Numeric Types](numeric-types.md) for their results.
- Shifts: `<<`, `>>`.
- Comparisons and tests: `=?`, `not =?`, `<?`, `<=?`, `>?`, `>=?`, `is?`, `isnt?`, `in?`, `not in?`.
- Symbolic composition: `&`, `|`, `~`, the same operations as `and`, `or`, `not` at a tighter precedence.
- Logic: `and`, `or`, `xor`, `nand`, `nor`, `xnor`, `not`.
- Fallback: `??` gives its right side when the left is `none` or an error.
- Conversion: `as`, `transmute`. Propagation: postfix `or_throw`.
- Types: prefix `type of`, postfix `?` (optional type).
- Pipes: `|>`, `<|`.
- Binding and construction: `:`, `:>`, `=>`, `->`, `=` and compound assignment.
- Discard: postfix `;`.
- Broadcast: `.+`, `.*`, `.<?` and the like apply elementwise and bind like their scalar forms.

`and` and `or` short-circuit. `a nand b` is `not (a and b)`; `nor` and `xnor` negate `or` and `xor` the same way. On integers the logical operators work on bits; `~x` is `not x` at a tight precedence. Use `xor`, not `^`, for exclusive-or.

<!-- dewy-example: {"mode":"run","stdout":"2 7 5 -1\nfalse false true\n"} -->
```dewy
printl"{6 & 3} {6 | 3} {6 xor 3} {~0}"
printl"{true and false} {true nand true} {false nor false}"
```

Most binary operators have a compound assignment (`+=`, `//=`, `<<=`, `and=`). It has assignment precedence, evaluates its destination route once, and keeps the destination's type: integer `/=` cannot store a fraction in an `int`. On booleans `and=` and `or=` short-circuit.

<!-- dewy-example: {"mode":"run","stdout":"3 7/2 false [1 12 3]\n"} -->
```dewy
let x = 7
x //= 2
let y = 7/1
y /= 2
let b = true
b and= false
let xs = [1 2 3]
xs[1] += 10
printl"{x} {y} {b} {xs}"
```

## Precedence

Operators bind from tightest to loosest:

| Operators | Grouping |
|---|---|
| `@` (covers the whole place route: `@items[i].x`) | prefix |
| member `.`, call `f(x)`, index `xs[i]`, `f"…"`, `f<T>`, spread `xs...` | left |
| `~`, effect `no` | prefix |
| `?` (optional type) | postfix |
| `^` | right |
| juxtaposed multiplication (`2x`, `a(x)`) | left |
| `*` `/` `//` `%` | left |
| `+` `-` | prefix |
| `+` `-` | left |
| `<<` `>>` | left |
| `,` | flat |
| `..` | range |
| iterator `in` | |
| `type of` | prefix |
| `&` | left |
| `\|` | left |
| `??` | right |
| `=?` `not =?` `<?` `<=?` `>?` `>=?` `is?` `isnt?` `in?` | chain |
| `not` | prefix |
| `and` `nand` | left |
| `xor` `xnor` | left |
| `or` `nor` | left |
| `as` `transmute` | left |
| `or_throw` | postfix |
| `:` | |
| `:>` | left |
| `=>` | right |
| `\|>` | left |
| `<\|` | right |
| `->` | |
| `=` and compound assignment | |
| `;` (discard) | postfix |

Consequences worth knowing:

- `-x^2` is `-(x^2)` and `-7 // 2` is `-(7 // 2)`: unary minus binds below `^` and the multiplicative operators.
- `~x^2` is `(~x)^2`.
- `not x =? y` is `not (x =? y)`, and `not a and b` is `(not a) and b`.
- `x as int64 + 1` is `x as (int64 + 1)`, which is an error: write `(x as int64) + 1`. `bytes as string | none` converts to the union.
- `f(x) * 2 or_throw` is `(f(x) * 2) or_throw`; propagate first with `(f(x) or_throw) * 2`.
- `value ?? 0 + 1` is `value ?? (0 + 1)`, with a warning; write `(value ?? 0) + 1`.
- `type of Parent & [fields]` mints the parent, then adds the fields.

<!-- dewy-example: {"mode":"reject","diagnostic":"`as` binds looser than `+`"} -->
```dewy
let x:int = 5
let n = x as int64 + 1
```

`else` attaches flow alternatives outside these levels. Group with `( … )` or a scoped `{ … }` when the table does not give the tree you want.

## Symbolic and Word Composition

`&` and `and` are the same operation, as are `|` and `or` and `~` and `not`: on booleans they agree, on integers both are bitwise, on sets both are set algebra, and on types both compose. They differ only in precedence. Symbols bind above the comparisons and words below, because each is idiomatic for a different kind of operand:

- Symbols compose types, overload sets, sets and masks, which are then compared or tested as a whole: `x is? A|B`, `d:int64 & ~0`, `flags & MASK =? 0`.
- Words combine comparisons: `x >? 0 and y <? n`.

Mixing them the wrong way round parses differently: `x >? 0 & y >? 0` is the chain `x >? (0 & y) >? 0`. Write `and`.

<!-- dewy-example: {"mode":"run","stdout":"true\ntrue\nfalse\n"} -->
```dewy
let flags = 6
let x = 5
let y = 3
printl(flags & 4 =? 4)          # (flags & 4) =? 4
printl(x >? 0 and y >? 0)
printl(x >? 0 & y >? 0)         # x >? (0 & y) >? 0
```

## Chained Comparisons

`a <? b <? c` is `a <? b and b <? c`, with each interior operand evaluated once and later comparisons evaluated only while the chain holds. A chain is monotonic: rising (`<?`, `<=?`) or falling (`>?`, `>=?`), with `=?` allowed in either. Mixing directions is an error, and `not =?`, `is?`, `isnt?` and `in?` do not chain. A parenthesized comparison is a `bool`: `(a <? b) =? c` compares it.

<!-- dewy-example: {"mode":"run","stdout":"true true true\n"} -->
```dewy
let x = 5
$assert 0 <? x <? 10
$assert 10 >? x >=? 0
printl"{0 <? x =? 5 <=? 5} {not x =? 4} {(x =? 5) =? true}"
```

<!-- dewy-example: {"mode":"reject","diagnostic":"a comparison chain goes one way"} -->
```dewy
let x = 5
printl(0 <? x >? 3)
```

## Juxtaposition

Writing expressions next to each other without whitespace forms calls, indexing and spreads: `f(x)`, `xs[i]`, `xs...`. A single delimited argument may follow a function directly: `total[1 2 3]`, `printl"hi"`. An empty `()` after any expression calls it.

Juxtaposition multiplies only in these forms:

- a numeric literal before a name, member or parenthesized group: `2x`, `3(x+1)`, `2^3x`;
- a named number or field before a group: `a(x)`, `material.k(T)`, `n(n+1)/2`;
- a parenthesized number before a group, a name or a number: `(x+1)(x-1)`, `(5)x`, `(x)2`.

At `head(...)` the head decides once, before anything is called: a function is called, and a number or quantity multiplies, with exactly one value inside the parentheses. A failed call never becomes a product, and a head that may be either must be narrowed first. A call result, an indexed element or an array is never a coefficient.

A juxtaposed product binds below `^` and above `*`, `/`, `//` and `%`, and unary minus applies to all of it:

| Expression | Means |
|---|---|
| `2x^2` | `2*(x^2)` |
| numeric `a(x)^2` | `a*(x^2)` |
| `-a(x)^2` | `-(a*x^2)` |
| `2^3x` | `(2^3)*x` |
| numeric `a(x)(y)^2` | `a*x*y^2` |
| `1/2a` | `1/(2a)` |

<!-- dewy-example: {"mode":"run","stdout":"15 6 24 18 12 8\n18 -18 96 1/4\n"} -->
```dewy
let x = 3
let a = 2
let y = 4
printl"{(5)x} {(x)2} {2^3x} {2x^2} {3(x+1)} {(x+1)(x-1)}"
printl"{a(x)^2} {-a(x)^2} {a(x)(y)^2} {1/2a}"
```

<!-- dewy-example: {"mode":"reject","diagnostic":"its parentheses hold exactly one value"} -->
```dewy
let a = 2
let x = 3
printl(a(x x))
```

<!-- dewy-example: {"mode":"reject","diagnostic":"a call result is not a coefficient"} -->
```dewy
f = (x:int):>int => x
g = (x:int):>int => x
printl(f(2)g(3))
```

Whitespace always separates expressions: `a b` is two values, never a product.

## Partial Operators

A binary operator with only its right operand, in parentheses, is a one-parameter function of the missing left operand: `(<? n)` is `i => i <? n`, `(* 2)` doubles, `(.x)` reads a field, `(as string)` converts. The operand runs to the closing parenthesis, so `(* 2 + 2)` is `x => x * 2 + 2`. Operators with a prefix meaning keep it: `(- 1)` is negative one.

A partial operator is typed like an unannotated lambda, from the function type it is checked against: a parameter, a `key=`, an annotation. It also serves as a refinement: `int64<(>? 0)>`.

<!-- dewy-example: {"mode":"run","stdout":"[\"a\" \"bb\" \"ccc\"]\ntrue true false\n3 -1\n"} -->
```dewy
main = () => {
    let names:array<string> = ["bb" "a" "ccc"]
    names.sort(key=(.length))
    printl(names)
    let small:(x:int64:>bool) = (<? 10)
    let digit:(x:int64:>bool) = (in? [0..9])
    printl"{small(3)} {digit(7)} {digit(12)}"
    let getx:([x:int y:int]:>int) = (.x)
    let neg = (- 1)
    printl"{getx([x=3 y=4])} {neg}"
}
```

## Pipes

`x |> @f` is `f(x)` and chains left to right; `@f <| x` chains right to left. The callable side is an ordinary expression: a named function is written `@name`, and a function literal pipes as written.

<!-- dewy-example: {"mode":"run","stdout":"10 10 30\n"} -->
```dewy
inc = (x:int):>int => x + 1
square = (x:int):>int => x * x
main = () => {
    let a = 3 |> @square |> @inc
    let b = @inc <| @square <| 3
    let c = 3 |> ((x:int) => x * 10)
    printl"{a} {b} {c}"
}
```

## Discard

An attached `;` evaluates the expression before it and discards what it expresses: `xs.pop();`. Directly inside an array literal `;` separates rows instead; to discard there, use a group: `[(f();) 7]`.
