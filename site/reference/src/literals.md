# Literals

A literal introduces a value directly in source. Literal syntax may preserve more exact type information than the eventual context requires.

## Booleans and Absence

`true` and `false` are the two `bool` values. `undefined` is a storable value used in unions such as `T | undefined`. `void` describes the absence of a produced value and is not interchangeable with `undefined`.

## Integers

Decimal integers require no prefix. Integer numerals support the following bases and case-insensitive alphabetic digits:

| Base | Prefix | Digits            |
| ---: | :----: | ----------------- |
|    2 |  `0b`  | `0`–`1`           |
|    3 |  `0t`  | `0`–`2`           |
|    4 |  `0q`  | `0`–`3`           |
|    6 |  `0s`  | `0`–`5`           |
|    8 |  `0o`  | `0`–`7`           |
|   10 |  `0d`  | `0`–`9`           |
|   12 |  `0z`  | `0`–`9`, `x`, `e` |
|   16 |  `0x`  | `0`–`9`, `a`–`f`  |

```dewy
42
0b101010
0t1120
0q222
0s110
0o52
0d42
0z36
0x2a
```

An integer literal initially has an exact value type. Context may place it in `int`, `uint`, or a compatible fixed-width integer type. A literal outside the destination range is rejected rather than truncated.

Underscores may group digits without affecting the value: `1_000_000`.

Prefixes for bases above 16 are available only on quoted packed data. An unquoted higher-base digit sequence is rejected rather than silently tokenized as a different value.

## Decimal and Exponent Literals

A numeral with a fraction or a decimal exponent — `9.8`, `1.25e2`, `5e-1` — is an exact rational (`49/5`, `125`, `1/2`), never a floating-point approximation. Binary exponents and non-decimal bases in such literals are not yet supported.

Integer numeral prefixes and packed based-string prefixes are related spellings with different results. An unquoted `0x2a` is an integer; quoted `0x"2a"` is packed data.

## Strings

Single and double quotes delimit strings. Both forms have the same string semantics.

```dewy
'short text'
"text with {interpolation}"
```

Escape syntax may insert code points. Interpolation braces contain ordinary Dewy expressions. See [Strings and Graphemes](strings.md).

## Packed Based Strings

Power-of-two based strings encode digit sequences densely as exact bytes:

```dewy
0b"11110000"
0x"deadbeef"
```

The supported packed prefixes are `0b`, `0q`, `0o`, `0x`, `0u`, and `0g`, contributing 1, 2, 3, 4, 5, and 6 bits per digit respectively. Bits are appended in source order from each digit's most-significant bit to its least-significant bit. A final partial byte is padded with zero bits on the right.

Whitespace and comments may separate digits. Base 64 uses the ordered alphabet `0`–`9`, `a`–`z`, `A`–`Z`, `+`, `/`; `-` aliases `+`, `_` aliases `/`, and trailing `=` is explicit padding that contributes no bits. `_` is therefore a digit in a base-64 string rather than a visual separator.

Non-power-of-two dense packing remains a provisional design because the width of concatenated subsequences is not generally compositional.

## Container and Object Literals

Square brackets use the top-level contents to determine the constructed form:

<!-- dewy-example: design-only -->

```dewy
[1 2 3]                       # array
[name="Ada" active=true]     # object
["Ada" -> 1 "Grace" -> 2]   # dictionary
set[1 2 3]                    # set
```

Array, object, dictionary, and set forms are settled; a dictionary or set literal may appear in any expression, and an empty one needs a `dict<K V>` or `set<T>` context. Bidictionary and multidimensional literal details are catalogued in [Arrays and Containers](arrays-and-containers.md) and the [design appendix](design-status.md).
