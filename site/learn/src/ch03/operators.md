# Operators

Dewy builds expressions from prefix, infix, and postfix operators. What an operator means depends on the input types (e.g. `and` is logical on booleans and bitwise on integers)

## Arithmetic

- `+` `-` `*` `/` `//` `%` `\` add, subtract, multiply, divide, floor divide, modulus, integer divide
- `^` exponent
- Prefix `+` `-` `*` `/` `//` unary plus/minus, and `/x` for `1/x`

A chain like `n^/2` keeps the precedence of the first operator, so that is `n^(1/2)`. `5+-1` is `5 + (-1)`.

`+` also concatenates strings.

## Comparisons

Comparisons end in `?` and return a boolean. There is no `==`.

- `=?` equal
- `not=?` not equal
- `>?` `<?` `>=?` `<=?` ordered
- `in?` membership
- `is?` / `isnt?` what type a value actually is
- `has?` / `of?` traits and type relations

`not` in front flips it. `not <?` is `>=?`.

## Boolean and Bitwise

On booleans these are logical, and they short-circuit when that makes sense. On integers they are bitwise, using the wider operand's width.

- `and` `or` `xor` `nand` `nor` `xnor`
- `not` invert
- `&` is equivalent to `and`
- `|` is equivalent to `or`
- `~` is equivalent to `not`

> NOTE: `&` vs `and`, `|` vs `or`, and `~` vs `not` are all interchangeable. The symbolic version means the exact same thing as the word. The convention is to use `&`/`|`/`~` when describing types (e.g. `(T|~U) & SomeType`) whereas `and`/`or`/`not` should be used for all other situations.

## Shifts

- `<<` `>>` shift
- `<<<` `>>>` rotate

> NOTE: `>>` is arithmetic for signed inputs, and logical for unsigned inputs.

Once the count hits the width, a left shift or logical right shift is zero. A signed right shift keeps filling in the sign bit.

## Juxtaposition

Two expressions next to each other are a juxtaposition. What that _means_ depends on the types:

- Call is high precedence, above `^`. `sin(x)`, `printl"Hello"`, `f(arg)` when the left side is callable.
- Index is `values[i]`, `text[3..7)`.
- Multiply sits just under `^` and just over `*`. `2(x + 1)`, `10kg`, `a(b)` when both sides are numbers.
- Range juxtaposition is how `1..10` picks up its ends.

```dewy
sin(x)^2 + cos(x)^2     # (sin(x))^2, sin is callable
s = 10
s(x)^2                  # s * (x^2), s is a number
printl'{n}'             # call
arr[i]                  # index
```

If the parser cannot decide, that is a compile error.

## Pipes, Conversion, and Functions

- `|>` pipe. `value |> f` calls `f` with `value`
- `<|` the other direction
- `as` changes representation
- `transmute` keeps the bits
- `=>` function literal
- `:` type annotation
- `:>` return type
- `->` / `<->` dictionary pointers
- `@` select the place a value lives; following fields and indices project it along a route
- `@?` same place, not two copies that happen to share storage

```dewy
40 |> add
let bytes:array<uint8> = text as array<uint8>
let bits:uint64 = duration transmute uint64
```

## Assignment

- `=` bind. Result is `void`
- `:=` bind and also yield the value
- `::` compiletime assignment (kicks off compiletime executions)
- Most infix ops take a trailing `=`

```dewy
a += 5
a <?= 5
a xor= false
```

Combined assignment always sits at `=`'s precedence, not the inner op's.

## Elementwise

A `.` in front of an operator broadcasts it over arrays:

```dewy
primes = [2 3 5 7 11 13 17 19]
mods = 20 .% primes
is_factor = mods .=? 0
p_factors = primes[is_factor]
```

This works if either side is an array, or both are and they have the same shape. Precedence stays with the inner operator.

## Precedence

Highest first. Associativity is left, right, prefix, postfix, flat, or fail. Fail means two of the same operator in a row is an error. Flat means one n-ary node instead of a tree.

| Associativity | Operators |
| --- | --- |
| prefix | `@` |
| left | `.` call-juxtapose (`fn(x)`), index-juxtapose (`x[42]`) |
| fail | type-parameter juxtapose (`<T>(...)=>...`) |
| fail | ellipsis juxtapose (`A...` `...B`) |
| postfix / prefix | `` ` `` |
| prefix | `not` `~` |
| postfix | `?` |
| right | `^` |
| left | multiply-juxtapose (`a(b)` `2x`) |
| prefix | `*` `/` `//` |
| left | `*` `/` `//` `%` `\` |
| prefix | `+` `-` |
| left | `+` `-` |
| left | `<<` `>>` `<<<` `>>>` |
| flat | `,` |
| flat | range juxtapose (`1..2`) |
| fail | `in` |
| left | `=?` `>?` `<?` `>=?` `<=?` `is?` `has?` `of?` `isnt?` `in?` `@?` |
| left | `and` `nand` `&` |
| left | `xor` `xnor` |
| left | `or` `nor` `\|` |
| left | `as` `transmute` |
| fail | `of` `has` |
| fail | `:` |
| left | `:>` |
| right | `=>` |
| left | `\|>` |
| right | `<\|` |
| fail | `->` `<->` |
| fail | `=` `::` `:=` and combined assignment (`+=` etc.) |
| left | semicolon juxtapose (`x;`) |

`else` hangs a flow alternative under all of that. See [Flow Control](flow-control.md).
