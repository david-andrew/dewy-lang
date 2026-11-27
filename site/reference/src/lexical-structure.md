# Lexical Structure

> [Generated coverage](/status/#ref-lexical-structure) names related acceptance programs. Every example on this page compiles with the current compiler unless it is marked **Design only**.

## Source Text

Dewy source is Unicode text in UTF-8. Source files conventionally end in `.dewy`; the suffix does not change how a file is read.

## Case

Dewy is case-sensitive. Keywords (`let`, `loop`, `if`), word operators (`and`, `or`, `not`, `in?`, `is?`), the booleans `true` and `false`, and type names are matched exactly as written: `True` and `AND` are ordinary identifiers.

<!-- dewy-example: {"mode":"run","stdout":"3\n"} -->
```dewy
let True = 1
let AND = 2
printl(True + AND)
```

Case is ignored in two places. Inside a numeral, the alphabetic digits of a based integer (`0xff`, `0xFF`) and the exponent marker (`1e5`, `1E5`) may be either case; the base prefix itself is lowercase (`0x`, never `0X`). In strings, `\u` and `\U` both introduce a Unicode escape. Every other escape is lowercase, and an unknown escape of a letter or digit is an error (see [Literals](literals.md#strings)).

## Identifiers

An identifier contains at least one base character. Decorations may appear before or after it, and decimal digits may follow it.

Base characters are ASCII Latin letters, the Greek alphabet, `_`, `‾`, `!`, `°`, and mathematical letters such as `ℂ`, `ℕ`, `ℤ`, `ℚ` and `ℝ`. Decorations are Unicode superscript and subscript letters and digits, prime marks, and `℠`, `™`, `©` and `®`.

A name has one spelling however it is written:

- `_` followed by digits spells subscript digits: `x_12`, `x_1_2` and `x₁₂` are one name.
- `‾` (U+203E) followed by digits spells superscript digits: `x‾12` is `x¹²`, distinct from `x₁₂` and `x12`.
- The micro sign `µ` is Greek `μ`. ASCII and Greek letters stay distinct: `A` is not `Α`.
- Letter decorations are written directly: `xᵢ` and `x_i` are different names.

Superscripts in identifiers are labels, not exponentiation.

<!-- dewy-example: {"mode":"run","stdout":"42 7 3\n1 2\n0.5\n"} -->
```dewy
let x_12 = 42
let x‾12 = 7
let foo_2_bar = 3
printl"{x₁₂} {x¹²} {foo₂_bar}"
let xᵢ = 1
let x_i = 2
printl"{xᵢ} {x_i}"
let Δt = 0.5
printl(Δt)
```

### Reserved names

Word operators (`and`, `or`, `not`, `xor`, `nand`, `nor`, `xnor`, `in`, `as`, `transmute`, …) are operators, not names. The names `none`, `void`, `end` and `new` are reserved: they cannot name a variable, parameter, field, method, loop binding, type alias or import alias. `none` is the absence value, `void` the type of no value, `end` the last index inside brackets (`xs[end]`), and `new` inserts an axis inside brackets. `extern`, `intrinsic` and `untyped` are ordinary names.

<!-- dewy-example: {"mode":"reject","diagnostic":"'end' is reserved, not a name"} -->
```dewy
let end = 1
```

<!-- dewy-example: {"mode":"reject","diagnostic":"`and` is a word operator, not a name"} -->
```dewy
let and = 1
```

## Whitespace and Juxtaposition

Whitespace separates tokens. Arguments, parameters and array elements are separated by whitespace, not commas. Whitespace always separates expressions, so `a b` is two values, never a product.

Spacing also decides whether a sign belongs to a value. Inside an array, `-2` written against its digits is a negative element, while `- 2` with spaces on both sides is subtraction:

<!-- dewy-example: {"mode":"run","stdout":"[1 -2 3]\n[-1 3]\n"} -->
```dewy
printl([1 -2 3])
printl([1 - 2 3])
```

Adjacent tokens without whitespace form calls, indexing and restricted multiplication; see [Juxtaposition](operators-and-precedence.md#juxtaposition).

### Line breaks

Newlines behave as whitespace except where a construct gives them meaning:

- Inside an array literal, a line break or `;` separates rows (see [Arrays and Containers](arrays-and-containers.md)).
- `return` and `yield` take a value only from their own line. At a line end they return nothing, so `if done return` followed by a statement returns without a value. A value that spans lines starts on the keyword's line (`return (` … `)`).
- A `\` at the end of a line cancels that line break everywhere: in code, in array literals and in strings.

<!-- dewy-example: {"mode":"run","stdout":"3\nline one continues\n"} -->
```dewy
let total = 1 + \
    2
printl(total)
printl("line one \
continues")
```

## Comments

`#` begins a line comment. `#{` and `}#` delimit a block comment, which nests and may span lines or sit inside one. Comment markers inside strings are string contents.

<!-- dewy-example: {"mode":"run","stdout":"3\n# not a comment\n"} -->
```dewy
# one line
#{ outer
   #{ nested }#
   outer again
}#
let total = 1 #{ inline }# + 2
printl(total)
printl("# not a comment")
```

A documentation string is an ordinary call of the prelude's `doc` with a string, usually a `"""` block at the top of a module, a function body or a type. Nothing is kept from it yet, so the call does nothing.

<!-- dewy-example: {"mode":"check"} -->
```dewy
doc"""
Tokenizer framework.
"""
```

## Tokens and Ambiguity

Tokenization takes the longest valid token. At `head(...)`, the head's type decides once between a call and a juxtaposed multiplication; no alternative parse is kept (see [Operators and Precedence](operators-and-precedence.md#juxtaposition)).

See [Literals](literals.md) for literal tokens and [Operators and Precedence](operators-and-precedence.md) for expression grouping.
