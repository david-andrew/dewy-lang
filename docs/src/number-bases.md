# Numbers and Bases

literal numbers in various bases can be specified using prefixes before the number


| Radix | Name | Prefix | Digits |
| ---- | ------ | ------ | ------ |
| 2 | Binary | `0b` | `[01]` |
| 3 | Ternary | `0t` | `[012]` |
| 4 | Quaternary | `0q` | `[0123]` |
| 6 | Seximal | `0s` | `[0-5]` |
| 8 | Octal | `0o` | `[0-7]` |
| 10 | Decimal* | `0d` | `[0-9]` |
| 12 | Dozenal | `0z` | `[0-9xXeE]` |
| 16 | Hexidecimal | `0x` | `[0-9A-Fa-f]` |
| 32 | Duotrigesimal | `0u` | `[0-9A-Va-v]` |
| 36 | Hexatrigesimal | `0r` | `[0-9A-Za-z]` |
| 64 | Tetrasexagesimal | `0y` | `[0-9A-Za-z!$]` |

*Decimal is the default base, so the prefix is generally not necessary, unless the default base is changed.

Some examples:

```dewy
0b10101010  // 170
0t121010    // 435
0q123       // 27
0s1432      // 380
0o1234567   // 342391
0xdeadbeef  // 3735928559
0u1v2u3t    // 66156669
0rz1b2c3    // 2118512019
0yl1z2$3!   // 3231913341182
```


See also: [Base names](https://en.wikipedia.org/wiki/List_of_numeral_systems), and [Seximal](https://en.wikipedia.org/wiki/Senary)

## Examples
