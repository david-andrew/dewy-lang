# Strings and Graphemes

## Semantic Model

A `string` is an immutable sequence of Unicode extended grapheme clusters. A `grapheme` is a string whose length is one; `char` is an alias for the same semantic type.

Length, indexing, slicing, and default iteration operate in grapheme-cluster units rather than UTF-8 bytes or Unicode scalar values.

```dewy
let text = "café 👨‍👩‍👧‍👦"
text.length
text[4]
```

The exact scalar sequence is preserved. Canonically equivalent spellings are not implicitly normalized, and exact equality compares the preserved spelling. Normalization-aware operations are a separate API design.

## Indexing and Slicing

`text[i]` is the grapheme at `i` and `text[a..b]` a slice; both are proven in bounds, never checked at runtime. A string with a known length (a literal, or a binding initialized from one and not reassigned) is checked against that length. A runtime-length string is indexed from facts, exactly like a runtime-length array: a guard `i <? text.length` (or a failed `i >=? text.length`) proves `text[i]` for that binding, a proven minimum length (`text.length >? 0`) proves constant indexes and `text[text.length - k]`, and a slice needs both endpoints proven the same way. Reassigning the binding drops its facts. Inside an index, `end` is the last index — `text.length - 1` — and may take part in any expression: `text[end]`, `text[end - 1]`, `text[2..end]` (each proven the same way, so `text[end]` needs `text.length >? 0`).

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

let main = ():>int64 => first_word("héllo world").length   # 5
```

## Interpolation

Braces inside a string literal evaluate an ordinary Dewy expression and convert its value to string:

```dewy
let message = "item {index}: {value}"
let combined = "{left}{right}"
```

A field's value converts the way `value as string` does: numbers, booleans, and strings directly, a declared type through its conversion method `__as__ = ():>string => …` (see [`as`](types-and-conversions.md#as)) — user-defined formatting participates in the general conversion protocol rather than a string-only hook — and a container or an object without one as its literal syntax (see [Printing](#printing)). A field whose type cannot convert is an error.

An implementation may stream the literal chunks and converted fields directly to a consumer such as `printl`, or materialize a string value when the surrounding context needs one. That representation choice is not observable.

## Printing

`print` writes a value; `printl` writes it and a newline. Both are ordinary generic functions of the prelude (`library/io.dewy`): a string, an integer, a boolean, or one of the number objects (`Rational`, `BigInt`, …) prints through its own arm — the arms are type tests decided per instance — and anything else prints as its `as string` text. So every value with a string conversion prints: a container as its literal syntax (`[1 2 3]`, `set["a" "b"]`, `["a" -> 1]`), an object through its `__as__ = ():>string` when its type declares one and otherwise field by field (`[x=1 name="q"]`), members the same way, so nesting is arbitrary. A string inside a structure is quoted, with the escapes of its literal syntax (`"a\tb"`); a string printed on its own prints bare.

<!-- dewy-example: compiler -->

```dewy
let Point:type = [x:int64 y:int64]

let main = ():>int64 => {
    printl(5)
    printl([1 2 3])                  # [1 2 3]
    printl(set["ab" "c"])            # set["ab" "c"]
    printl(["k" -> Point(1 2)])      # ["k" -> [x=1 y=2]]
    printl'{[true false]} and {[name="q"]}'
    let text:string = [1 2 3] as string
    return text.length               # 7
}
```

Because printing is `as string`, an array of graphemes prints as the text they form (`printl(["a" "b"])` writes `ab`), as [`as`](types-and-conversions.md#as) converts it. A value that cannot convert — a member of an optional type, a container whose members are containers, or a number object inside a structure (they print, but have no string form yet) — is an error where it is printed. An interpolated argument is written part by part rather than built into one string first; that representation choice is not observable. Printing a structure is for looking at values: its exact text is not a stable format.

## Searching, Splitting, and Trimming

Strings have methods, written in Dewy in the prelude's `strings.dewy`; positions and lengths are graphemes, like indexing. `text.contains(x)`, `text.starts_with(x)`, `text.ends_with(x)`; `text.find(x)` and `text.rfind(x)` yield the first or last position or `undefined`; `text.split(sep)` yields the pieces between separators (adjacent separators give empty pieces; an empty separator splits into graphemes); `text.lines` the lines without their breaks (a final break adds no empty line); `text.trim`, `text.trim_start`, `text.trim_end` drop spaces, tabs, and line breaks; `text.replace(old new)` replaces every occurrence. Zero-argument methods are called without parentheses.

<!-- dewy-example: compiler -->

```dewy
let main = ():>int64 => {
    let line:string = "  key: value  ".trim
    match line.find": " {
        i:int64 => printl"key ends at {i}"
        <undefined> => printl"no separator"
    }
    let parts = line.split": "
    return parts.length                    # 2
}
```

`text.casefold` is the Unicode full case folding (`CaseFolding.txt`, statuses C and F): the form for case-insensitive comparison, not a lowercase for display — `"Straße".casefold` is `"strasse"`, `"İ".casefold` is `"i̇"`. Compare `a.casefold =? b.casefold`, or test `head.casefold is? BasePrefix` (see [Unions and Narrowing](types-and-conversions.md#unions-and-narrowing)).

## Joining and Building

`xs.join` concatenates the elements of a string array (`array<string>`, `array<grapheme>`) into a new string; `xs.join(sep)` — or, juxtaposed, `xs.join", "` — places the separator between neighbours. The result is re-segmented, so clusters may span the joins. `join` reads its receiver: it applies to any array value, of any length, and is not a mutation.

Loop-built strings use an `array<string>` as the builder: push each piece (an interpolation such as `"{value}"` converts anything printable), then `join`:

```dewy
let render = (values:array<int64>):>string => {
    let pieces:array<string> = []
    loop v in values { pieces.push"{v}" }
    return pieces.join", "
}
```

`+` is not string concatenation; two strings combine by interpolation (`"{left}{right}"`), many by `join`.

## Decoding Bytes

`bytes as string` requires a proof that the bytes are valid UTF-8, which the compiler cannot make for runtime data. The checked form is `bytes as string | undefined`: it validates the bytes (RFC 3629 — no overlong forms, no surrogates, nothing above U+10FFFF, no truncated sequences) and yields the decoded string, or `undefined` for invalid input, so the program decides what to do at that point:

```dewy
let text = read_text(path)          # `string`, or a file error, or `InvalidUtf8`
if text is? string { printl(text) } else { printl"not readable text" }
```

`read_text` is `read_bytes` followed by this decode, with `undefined` reported as the `InvalidUtf8` error alongside the file errors (`FileNotFound`, `FileAccessDenied`, `IsDirectory`, `FileError`); a decode of bytes you already hold is `bytes as string | undefined`.

## Including Files

`$include_bytes(p"path")` embeds a file's bytes at compile time. The path must be known when compiling — a path literal today, resolved against the source file — and the result is a binary literal (`array<uint8>` of a known length), usable like `0x"…"`: `.length`, indexing, `as string | undefined`. `$include_bytes(p"path") as name` is the statement form, declaring `name`. The generated program does not spell the bytes out; the target embeds the file itself, which is how the compiler's Unicode tables travel.

```dewy
let table = $include_bytes(p"data/table.bin")
$include_bytes(p"data/notes.bin") as notes
let text = $include_bytes(p"data/notes.txt") as string | undefined
```

## Representation Views

Explicit array views expose lower-level representations:

- `array<uint8>` contains UTF-8 code units;
- `array<uint32>` contains Unicode scalar values;
- `array<grapheme>` contains grapheme values.

Converting a grapheme array to string concatenates its contents and segments the result again, so boundaries between adjacent inputs need not remain grapheme boundaries.

Conversions from arbitrary integers to string representations require proof that the input is valid UTF-8 or valid Unicode scalar data; `array<uint8>` has the checked form `as string | undefined` described above.

## Character Ranges

A range whose unannotated anchors are one-grapheme strings advances in Unicode scalar order when each anchor contains exactly one scalar. Iteration skips the surrogate interval. Enumerating multi-scalar graphemes or natural-language collation order is unspecified.

`chr(scalar)` is the one-scalar string of a Unicode scalar value (`chr(0x1F600)` is `"😀"`). The scalar's range, `0` to `0x10FFFF`, is a proof obligation at the call — a loop over `[0x41..0x5B)` proves it — and a surrogate code point, which no string can hold, yields the replacement character U+FFFD.

<!-- dewy-example: compiler -->

```dewy
let main = ():>int64 => {
    let letters:array<string> = []
    loop i in [0x41..0x44) { letters.push(chr(i)) }
    return letters.join.length      # "ABC": 3
}
```
