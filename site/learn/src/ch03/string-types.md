# String Types

Dewy strings are immutable sequences of Unicode extended grapheme clusters. `grapheme` is a string of length one. `char` is the same thing. Index, slice, and iterate by cluster, not by byte.

```dewy
text = "café 👨‍👩‍👧‍👦 🇺🇸"
text.length     # 8
text[5]         # "👨‍👩‍👧‍👦"
```

Literals keep the exact scalar sequence you typed. There is no implicit normalization, so `"é"` and `"é"` are different even when each is one grapheme. (TODO: verify this is the correct behavior)

Single or double quotes both work. `\u{...}` and `\x{...}` insert a scalar.

## Interpolation

Curly braces splice an expression into the string:

```dewy
my_age = 24
printl'I am {my_age} years old'
```

Any expression can go in the braces. Non-strings get converted through their string representation via `__as__` i.e. `'mything={mything}'` does `mything as string` to determine its string representation.

> NOTE: most values (including user-defined types) have a default `__as__` conversion to `string`. Users are free to override it with a custom conversion function.

## Representations

```dewy
let text:string = "café"
let bytes:array<uint8> = "café"
let scalars:array<uint32> = "café"
let clusters:array<grapheme> = "café"
```

`array<uint8>` is UTF-8. `array<uint32>` is scalars. Surrogates are not valid string contents. `array<grapheme>` is one handle per cluster.

`as` switches representation:

```dewy
bytes = text as array<uint8>
scalars = text as array<uint32>
clusters = text as array<grapheme>
joined = clusters as string
```

Going from graphemes back to a string concatenates whatever is there and segments again. Adjacent pieces can merge. `"e"` plus a combining acute becomes one grapheme.

## Slices, Iteration, and Ranges

Integer ranges give you an immutable grapheme slice:

```dewy
text = 'this is some text'
prefix = text[..4]     # 'this '
middle = text(4..12)   # 'is some'
suffix = text[13..]    # ' text'
```

Iteration yields graphemes:

```dewy
loop char in 'café 👨‍👩‍👧‍👦 🍀' {
    print'{char} | '
}
printl'\nDone.'
```

prints out

```
c | a | f | é |   | 👨‍👩‍👧‍👦 | 🍀 |
Done.
```

A character range with no extra annotation lives in the grapheme domain. Each anchor has to be one Unicode scalar. Iteration walks scalar order and skips the surrogate gap:

```dewy
loop letter in 'a'..'z' { ... }        # a, b, c, d, ..., z
loop letter in 'z','y'..'a' { ... }    # z, y, x, w, ..., a
let scalars:range<uint32> = 'a'..'z'
```

How you enumerate multi-scalar graphemes or whole strings, some alphabet or collation story, is not yet determined. Same for normalization APIs.

[Ranges](range-types.md) has the bound syntax and `end`.
