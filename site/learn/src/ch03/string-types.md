# String Types

Dewy strings are immutable sequences of Unicode extended grapheme clusters.
`grapheme` is a string of length one. `char` is the same thing. Index,
slice, and iterate by cluster, not by byte.

```dewy
text = "café 👨‍👩‍👧‍👦 🇺🇸"
text.length     # 8
text[5]         # "👨‍👩‍👧‍👦"
```

Literals keep the exact scalar sequence you typed. There is no implicit
normalization, so `"é"` and `"é"` are different even when each is one
grapheme.

Single or double quotes both work. `\u{...}` and `\x{...}` insert a
scalar.

## Interpolation

Curly braces splice an expression into the string:

```dewy
my_age = 24
printl'I am {my_age} years old'
```

Any expression can go in the braces. Non-strings get converted through
their string representation.

## Representations

```dewy
let text:string = "café"
let bytes:array<uint8> = "café"
let scalars:array<uint32> = "café"
let clusters:array<grapheme> = "café"
```

`array<uint8>` is UTF-8. `array<uint32>` is scalars. Surrogates are not
valid string contents. `array<grapheme>` is one handle per cluster.

`as` switches representation:

```dewy
bytes = text as array<uint8>
scalars = text as array<uint32>
clusters = text as array<grapheme>
joined = clusters as string
```

A byte view starts out borrowing the string's UTF-8. The first time you
write through an index, it copies, so the original string does not
change. `transmute` will not turn a string handle into an array handle.

Going from graphemes back to a string concatenates whatever is there and
segments again. Adjacent pieces can merge. `"e"` plus a combining acute
becomes one grapheme.

## Slices, Iteration, and Ranges

Integer ranges give you an immutable grapheme slice:

```dewy
prefix = text[..3]
middle = text[(1..4)]
suffix = text[3..]
```

Iteration yields graphemes:

```dewy
loop cluster in text {
    use(cluster)
}
```

A character range with no extra annotation lives in the grapheme domain.
Each anchor has to be one Unicode scalar. Iteration walks scalar order
and skips the surrogate gap:

```dewy
loop letter in 'a'..'z' { ... }
loop letter in 'z','y'..'a' { ... }
let scalars:range<uint32> = 'a'..'z'
```

How you enumerate multi-scalar graphemes or whole strings, some alphabet
or collation story, is not yet determined. Same for normalization APIs.

[Ranges](range-types.md) has the bound syntax and `end`.
