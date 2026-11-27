# Literals

> [Generated coverage](/status/#ref-literals) names related acceptance programs. Every example on this page compiles with the current compiler unless it is marked **Design only**.

A literal introduces a value directly in source. A literal keeps its exact value until context needs a type. In a type position the same literal is a singleton type; see [Literal Types](types-and-conversions.md#literal-types).

## Booleans and Absence

`true` and `false` are the two `bool` values. `none` is a storable value used in optionals and unions (`T | none`, written `T?`). `void` is the type of no value; it is not interchangeable with `none`.

## Integers

Decimal integers need no prefix. Based integers take a lowercase prefix; the alphabetic digits after it may be either case:

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

`_` groups digits without changing the value.

<!-- dewy-example: {"mode":"run","stdout":"42 42 42 42 42 42 42 42 42\n255 1000000\n"} -->
```dewy
printl"{42} {0b101010} {0t1120} {0q222} {0s110} {0o52} {0d42} {0z36} {0x2a}"
printl"{0xFF} {1_000_000}"
```

An unannotated integer literal is an `int`, the arbitrary-precision integer; an oversized literal is still exact. In a fixed-width context the literal must fit, and one that does not is an error rather than a truncation:

<!-- dewy-example: {"mode":"reject","diagnostic":"value 200 does not fit in int8"} -->
```dewy
let x:int8 = 200
```

A digit outside the base is an error, never a different token.

## Decimal and Exponent Literals

A numeral with a fraction or a decimal exponent (`9.8`, `1.25e2`, `5e-1`) is an exact `rational`, never a floating-point approximation, so `0.1 + 0.2 =? 0.3` is true. A float context (a `float64` annotation, parameter or operand) makes it a float instead. Binary exponents and based fractions are not supported.

<!-- dewy-example: {"mode":"run","stdout":"9.8 125 0.5 true\n0.30000000000000004\n"} -->
```dewy
printl"{9.8} {1.25e2} {5e-1} {0.1 + 0.2 =? 0.3}"
let a:float64 = 0.1
printl(a + 0.2)
```

See [Numeric Types](numeric-types.md#rationals) for how rationals print and compute.

## Strings

Single and double quotes delimit strings with the same meaning. Both support escapes and `{expression}` interpolation.

- Letter escapes are `\n`, `\r`, `\t`, `\a`, `\b`, `\v` and `\f`, plus `\0`.
- `\u` takes four hex digits (`é`) or one to six inside braces (`\u{1F642}`); `\U` is the same escape. Surrogates and values above `10FFFF` are errors.
- Any ASCII punctuation escapes to itself: `\{`, `\}`, `\'`, `\"`, `\\`.
- An unknown escape of a letter or digit (`\N`, `\x41`) is an error.
- `\` before a line break continues the string without the newline.

An `r` prefix keeps backslashes and braces literally. Three matching quotes allow embedded quotes and multi-line text, with whitespace preserved.

<!-- dewy-example: {"mode":"run","stdout":"café 🙂 {braces}\nraw \\n {x}\nHe said \"go\".\n"} -->
```dewy
printl("café \u{1F642} \{braces\}")
printl(r"raw \n {x}")
printl("""He said "go".""")
```

<!-- dewy-example: {"mode":"reject","diagnostic":"unknown escape `\\x`"} -->
```dewy
printl("\x41")
```

See [Strings and Graphemes](strings.md) for string operations.

## Bytes

`b'a'` is the `uint8` 97: one byte, escapes allowed. `b"abc"` is the `array<uint8>` of the text's UTF-8 bytes, without interpolation.

## Packed Based Strings

A quoted digit sequence after a power-of-two prefix packs those digits densely into bytes, an `array<uint8>`:

<!-- dewy-example: {"mode":"run","stdout":"[240]\n[222 173 190 239]\nhi\n[97] [104 105]\n"} -->
```dewy
printl(0b"11110000")
printl(0x"deadbeef")
printl(0x"6869" as string | none)
printl"{[b'a']} {b"hi"}"
```

The packed prefixes are `0b`, `0q`, `0o`, `0x`, `0u` and `0g`, giving 1, 2, 3, 4, 5 and 6 bits per digit. Bits are appended in source order, most significant bit of each digit first. A final partial byte is padded with zero bits on the right. Base 64 (`0g`) uses the ordered alphabet `0`–`9`, `a`–`z`, `A`–`Z`, `+`, `/`; trailing `=` is padding that contributes no bits. Whitespace between digits is an error.

An unquoted `0x2a` is an integer; a quoted `0x"2a"` is bytes. Non-power-of-two bases (`0t"12"`) are not supported as packed strings.

## Container and Object Literals

Square brackets build arrays, objects (records), dictionaries and sets, chosen by the top-level contents:

<!-- dewy-example: {"mode":"run","stdout":"[1 2 3]\n[active=true name=\"Ada\"]\n[\"Ada\" -> 1 \"Grace\" -> 2]\nset[1 2 3]\n[7 \"seven\"]\n"} -->
```dewy
printl([1 2 3])                       # array
printl([name="Ada" active=true])      # object
printl(["Ada" -> 1 "Grace" -> 2])     # dictionary
printl(set[1 2 3])                    # set
let entry:[int64 string] = [7 "seven"]
printl(entry)                         # tuple: a type per position
```

`[]` takes its type from context: an array, dictionary, set or record with defaults. With no context it is an error.

<!-- dewy-example: {"mode":"reject","diagnostic":"cannot infer the type of 'e'"} -->
```dewy
let e = []
```

Postfix `...` spreads a container into a literal. `[xs... 0 ys...]` builds an array from the elements of arrays (or members of sets) and written elements. `[base... c=3]` builds an object from the fields of objects and written fields; a later entry wins over an earlier one with the same name. This is how containers combine: `+` never concatenates.

<!-- dewy-example: {"mode":"run","stdout":"[1 2 3 0 4]\n[a=9 b=2 c=3]\n"} -->
```dewy
let xs = [1 2 3]
let ys = [4]
printl([xs... 0 ys...])
let base = [a=1 b=2]
printl([base... c=3 a=9])
```

Multidimensional array literals (`[1 2; 3 4]`) and the remaining container forms are in [Arrays and Containers](arrays-and-containers.md).
