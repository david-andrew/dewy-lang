# Numbers and Bases

Integer literals may carry a radix prefix. Decimal (base-10) is the default, so `42` and `0d42` are the same value.

| Radix | Name             | Prefix | Digits              |
| ----- | ---------------- | ------ | ------------------- |
| 2     | Binary           | `0b`   | `[01]`              |
| 3     | Ternary          | `0t`   | `[012]`             |
| 4     | Quaternary       | `0q`   | `[0123]`            |
| 6     | Seximal          | `0s`   | `[0-5]`             |
| 8     | Octal            | `0o`   | `[0-7]`             |
| 10    | Decimal          | `0d`   | `[0-9]`             |
| 12    | Dozenal          | `0z`   | `[0-9xXeE]`         |
| 16    | Hexadecimal      | `0x`   | `[0-9A-Fa-f]`       |
| 32    | Duotrigesimal    | `0u`   | `[0-9A-Va-v]`       |
| 36    | Hexatrigesimal   | `0r`   | `[0-9A-Za-z]`       |
| 64    | Tetrasexagesimal | `0g`   | `[0-9A-Za-z+/\-_=]` |

> NOTE: integer literals cannot use bases larger than 16. larger bases need to use the based string or based array notation

> NOTE: base 64 supports `+`/`-` for `62`, and `/`/`_` for `64`. `=` is for explicit padding

```dewy
# some examples
0b10101010      # 170
0t121010        # 435
0q123           # 27
0s1432          # 380
0o1234567       # 342391
0xdeadbeef      # 3735928559
0u'1v2u3t'      # 66156669
0g'l1z2+3/=='   # 3231913341182
```

> Underscores may appear in a numeric literal to group digits, as in `1_000_000`. They have no effect on the actual value.

## Based Strings

A prefix on a _string_ is a different feature. Power-of-two prefixes pack bits into a byte array instead of parsing an integer:

```dewy
const program:array<uint8> = 0q"000000010002"
hex_bytes = 0x"deadbeef"
```

`0b`, `0q`, `0o`, `0x`, `0u`, and `0g` are the packed-string prefixes. They produce exact bytes, not a numeric value. Whitespace and comments may appear among the digits.

See [List of numeral systems](https://en.wikipedia.org/wiki/List_of_numeral_systems) and [Senary](https://en.wikipedia.org/wiki/Senary).
