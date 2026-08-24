# Numbers and Bases

An integer literal may use a radix prefix. Dewy supports integer numerals through base 16:

| Base | Prefix | Digits |
| ---: | :---: | --- |
| 2 | `0b` | `0`–`1` |
| 3 | `0t` | `0`–`2` |
| 4 | `0q` | `0`–`3` |
| 6 | `0s` | `0`–`5` |
| 8 | `0o` | `0`–`7` |
| 10 | `0d` | `0`–`9` |
| 12 | `0z` | `0`–`9`, `x`, `e` |
| 16 | `0x` | `0`–`9`, `a`–`f` |

Alphabetic digits are case-insensitive in these integer forms. Decimal is the default, so `42` and `0d42` denote the same value.

```dewy
0b10101010      # 170
0t121010        # 435
0q123           # 27
0s1432          # 380
0o1234567       # 342391
0xdeadbeef      # 3735928559
```

Underscores may group integer digits without changing the value:

```dewy
let population = 1_000_000
let mask = 0b1111_0000
```

## Packed Based Strings

A radix prefix followed by a quoted digit sequence produces exact packed data rather than an integer:

```dewy
const program:array<uint8> = 0q"000000010002"
const header:array<uint8> = 0x"deadbeef"
```

Power-of-two bases have a compositional bit width and can therefore be packed directly:

| Base | Prefix | Bits per digit |
| ---: | :---: | ---: |
| 2 | `0b` | 1 |
| 4 | `0q` | 2 |
| 8 | `0o` | 3 |
| 16 | `0x` | 4 |
| 32 | `0u` | 5 |
| 64 | `0g` | 6 |

Digits contribute bits from left to right, most-significant bit first. A final partial byte is padded with zero bits on the right. Whitespace and comments may separate digits.

Base 64 uses `+` or `-` for digit 62 and `/` or `_` for digit 63. Trailing `=` characters are accepted as explicit padding and do not contribute bits. Unlike numeric underscores, `_` inside a base-64 string is a digit.

Based strings for non-power-of-two bases are reserved until their sequence-width and composition rules are settled. The Reference gives the exact [literal and packing rules](../../reference/literals.html#packed-based-strings).
