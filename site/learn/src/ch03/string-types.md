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

Braces insert an expression into a string. Adjacent fields produce one string:

```dewy
let unread = 3
printl"You have {unread} unread messages."
let combined = "{greeting}{name}"
```

Interpolation uses the same conversion as `value as string`. A type can therefore participate through the general conversion protocol rather than needing a special interpolation-only method.

An implementation may stream literal chunks and converted values directly into `print` or `printl`. When the expression itself must survive as a string value, it materializes an equivalent immutable string. That representation difference is not visible to the program.

## Joining Strings

`+` does not concatenate. Two strings combine by interpolation, and any number of them by `join` on an array of strings:

<!-- dewy-example: compiler -->

```dewy
let main = ():>int64 => {
    let words:array<string> = ["one" "two" "three"]
    printl(words.join", ")           # one, two, three

    let pieces:array<string> = []    # the string builder is an array
    let i:int64 = 0
    loop i <? 3 {
        pieces.push"{i * i}"
        i += 1
    }
    printl(pieces.join"-")           # 0-1-4
    return 0
}
```

`join` without a separator concatenates directly. It never mutates the array, so it works on any array of strings — including exact-length ones — and the result can be returned or stored like any other string.

Bytes that should be text are decoded with a check: `bytes as string | undefined` gives the string when the bytes are valid UTF-8 and `undefined` otherwise, so invalid input is a case to handle rather than an exception.

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

## Indexing by Position

Iterating covers most text handling, but a tokenizer wants to look at positions: `text[i]` for the grapheme at `i`, `text[a..b]` for a slice. Dewy proves those in bounds instead of checking at runtime, and for a string whose length is only known at runtime the proof comes from what your code already says — a loop or guard on `i <? text.length` is enough:

<!-- dewy-example: compiler -->
```dewy
let first_word = (text:string):>string => {
    let i:int64 = 0
    loop i <? text.length {
        if text[i] =? " " { return text[0..i) }
        i += 1
    }
    return text
}

printl(first_word("héllo world"))   # héllo
```

Without such a guard, `text[i]` is a compile error ("string index is not proven in bounds") rather than a possible crash.

## Slicing

Range indexes select immutable grapheme slices:

```dewy
let text = "this is some text"
let prefix = text[..4]
let middle = text[5..11]
let suffix = text[13..]
```

`end` refers to the final grapheme index — it is `text.length - 1`, so `text[end - 1]` and `text[2..end]` work too, on strings of any length as long as the length is proven large enough. Open and closed range boundaries retain their ordinary meanings.

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
