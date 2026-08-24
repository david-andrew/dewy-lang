# Strings and Graphemes

Dewy strings are immutable sequences of Unicode extended grapheme clusters: the units people usually perceive as characters.

```dewy
let text = "café 👨‍👩‍👧‍👦 🇺🇸"
text.length
text[5]
```

Indexing and iteration do not split an accent from its letter or a joined emoji sequence into unrelated pieces. `grapheme` is a string of length one; `char` is an alias for the same type.

Single and double quotes have the same string semantics.

## Interpolation

Braces insert an expression into a string:

```dewy
let unread = 3
printl"You have {unread} unread messages."
```

Interpolation uses the same conversion as `value as string`. A type can therefore participate through the general conversion protocol rather than needing a special interpolation-only method.

An implementation may stream literal chunks and converted values directly into `print` or `printl`. When the expression itself must survive as a string value, it materializes an equivalent immutable string. That representation difference is not visible to the program.

## Iterating Text

Iteration yields graphemes:

```dewy
let text = "café 👨‍👩‍👧‍👦 🍀"

loop index in 0.. and character in text
    if character not =? ' '
        printl"{index}: {character}"
```

Character ranges use scalar order when every anchor is a one-scalar grapheme:

```dewy
loop letter in 'a'..'z'
    print(letter)
```

Natural-language collation and enumeration of arbitrary multi-scalar graphemes require explicit APIs rather than an invented universal ordering.

## Slicing

Range indexes select immutable grapheme slices:

```dewy
let text = "this is some text"
let prefix = text[..4]
let middle = text[5..11]
let suffix = text[13..]
```

`end` refers to the final grapheme index. Open and closed range boundaries retain their ordinary meanings.

## Representation Views

Use explicit conversions when code needs a lower-level representation:

```dewy
let bytes:array<uint8> = text as array<uint8>
let scalars:array<uint32> = text as array<uint32>
let clusters:array<grapheme> = text as array<grapheme>
```

The byte view is UTF-8. The scalar view contains valid Unicode scalar values. Converting grapheme pieces back to a string concatenates and segments them again, so adjacent pieces may combine into a new grapheme.

Strings preserve the exact scalar spelling supplied by the program. Equality does not silently normalize canonically equivalent text; normalization-aware comparison belongs to an explicit text API.

See the Reference for exact [string semantics](../../reference/strings.html).
