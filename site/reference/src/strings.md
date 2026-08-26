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

## Interpolation

Braces inside a string literal evaluate an ordinary Dewy expression and convert its value to string:

```dewy
let message = "item {index}: {value}"
let combined = "{left}{right}"
```

The intended conversion path is the same conversion used by `value as string`, so user-defined formatting participates in the general conversion protocol rather than a string-only hook.

An implementation may stream the literal chunks and converted fields directly to a consumer such as `printl`, or materialize a string value when the surrounding context needs one. That representation choice is not observable.

## Representation Views

Explicit array views expose lower-level representations:

- `array<uint8>` contains UTF-8 code units;
- `array<uint32>` contains Unicode scalar values;
- `array<grapheme>` contains grapheme values.

Converting a grapheme array to string concatenates its contents and segments the result again, so boundaries between adjacent inputs need not remain grapheme boundaries.

Conversions from arbitrary integers to string representations require proof that the input is valid UTF-8 or valid Unicode scalar data.

## Character Ranges

A range whose unannotated anchors are one-grapheme strings advances in Unicode scalar order when each anchor contains exactly one scalar. Iteration skips the surrogate interval. Enumerating multi-scalar graphemes or natural-language collation order is unspecified.
