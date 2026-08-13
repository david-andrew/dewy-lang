# String Types

Dewy strings are immutable sequences of Unicode extended grapheme clusters.
`grapheme` is a string of length one, and `char` is its alias. The default
representation is grapheme-indexed:

```dewy
text = "café 👨‍👩‍👧‍👦 🇺🇸"
text.length  % 8
text[5]      % "👨‍👩‍👧‍👦"
```

String literals retain their exact Unicode scalar sequence until context chooses
a representation. Dewy does not normalize literals implicitly, so `"é"` and
`"é"` are distinct values even though each contains one grapheme.

## Representations

The core representations are:

```dewy
let text:string = "café"
let bytes:array<uint8> = "café"
let scalars:array<uint32> = "café"
let clusters:array<grapheme> = "café"
```

`array<uint8>` contains UTF-8 code units. `array<uint32>` contains Unicode
scalar values directly; surrogate values are not valid string contents.
`array<grapheme>` contains one immutable string handle per element.

Use `as` for a representation-changing conversion:

```dewy
bytes = text as array<uint8>
scalars = text as array<uint32>
clusters = text as array<grapheme>
joined = clusters as string
```

A byte view initially borrows the string's immutable UTF-8 storage. Its first
indexed mutation copies the bytes, so the source string remains unchanged.
`transmute` is only for bit-preserving reinterpretation and cannot reinterpret a
string handle as an array handle.

Converting a grapheme array back to a string concatenates its current elements
and segments the result again. This matters when adjacent elements merge, such
as `"e"` followed by a combining acute accent.

Converting arbitrary `array<uint8>` or `array<uint32>` values into strings is
not currently allowed. A future refinement system must prove valid UTF-8 or
valid Unicode scalar contents before those conversions become available.

## Slices, iteration, and ranges

Integer range indexing returns an immutable grapheme slice:

```dewy
prefix = text[..3]
middle = text[(1..4)]
suffix = text[3..]
```

Iteration also yields graphemes:

```dewy
loop cluster in text {
    use(cluster)
}
```

Unannotated character ranges use the grapheme domain. Their anchors must each
contain exactly one Unicode scalar; iteration advances in scalar order and
skips the surrogate interval:

```dewy
loop letter in 'a'..'z' { ... }
loop letter in 'z','y'..'a' { ... }
let scalars:range<uint32> = 'a'..'z'
```

Enumeration of multi-scalar graphemes or whole strings requires an explicit
alphabet or collation model and is not defined yet.

The current Unicode tables implement UAX #29 for Unicode 16.0.0. Interpolation
and normalization APIs are separate future features.
