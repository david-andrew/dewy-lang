# Literals

A literal introduces a value directly in source. Literal syntax may preserve more exact type information than the eventual context requires.

## Booleans and Absence

`true` and `false` are the two `bool` values. `undefined` is a storable value used in unions such as `T | undefined`. `void` describes the absence of a produced value and is not interchangeable with `undefined`.

## Integers

Decimal integers require no prefix. Radix prefixes provide bases used by the language's numeral syntax:

```dewy
42
0b101010
0o52
0x2a
```

An integer literal initially has an exact value type. Context may place it in `int`, `uint`, or a compatible fixed-width integer type. A literal outside the destination range is rejected rather than truncated.

Underscores may group digits without affecting the value: `1_000_000`.

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

Whitespace and comments may separate digits where tokenization remains unambiguous. Non-power-of-two dense packing remains a provisional design because the width of concatenated subsequences is not generally compositional.

## Container and Object Literals

Square brackets use the top-level contents to determine the constructed form:

```dewy
[1 2 3]                       # array
[name="Ada" active=true]     # object
["Ada" -> 1 "Grace" -> 2]   # dictionary
set[1 2 3]                    # set
```

Array and object forms are settled. Dictionary, bidictionary, set, and multidimensional literal details are catalogued in [Arrays and Containers](arrays-and-containers.md) and the [design appendix](design-status.md).
