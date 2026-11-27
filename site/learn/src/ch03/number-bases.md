# Numbers and Bases

Base prefixes change how an integer is written. They do not change the value.

<!-- dewy-example: {"mode": "run", "stdout": "42 42 42 42\n"} -->
```dewy
let binary:int64 = 0b101010
let hex:int64 = 0x2a
printl"{binary} {hex} {0o52} {42}"
```

The prefixes are `0b` (binary), `0o` (octal), `0x` (hex), and a few less common ones such as `0t` (base 3) and `0z` (base 12). Hex digits may be either case. `_` groups digits wherever you like, and changes nothing:

<!-- dewy-example: {"mode": "run", "stdout": "255 255 1000000\n"} -->
```dewy
printl"{0xFF} {0b1111_1111} {1_000_000}"
```

## Whole numbers have no fixed size

An unannotated integer is an `int`: exact, any size, never overflowing. A literal too large for a machine word is still exact. Fixed widths (`int64`, `uint8`) are opt-in with an annotation, and a literal that does not fit is a compile error rather than a silent truncation. [Basic Data Types](basic-data-types.md) covers them.

## Writing numbers in a base

Printing always gives decimal. To print another base, use a `fmt` pattern. The pattern letters are `x` and `X` for hex, `b` for binary and `o` for octal, and `#` adds the prefix. `0` pads with zeros up to a width:

<!-- dewy-example: {"mode": "run", "stdout": "ff\nFF\n1010\n00001010\n0xff\n"} -->
```dewy
printl(fmt'x'(255))
printl(fmt'X'(255))
printl(fmt'b'(10))
printl(fmt'08b'(10))
printl(fmt'#x'(255))
```

## Bit operations

On integers, `&`, `|`, `~` and the shifts work on bits, which is where based literals earn their keep:

<!-- dewy-example: {"mode": "run", "stdout": "15\n256\n"} -->
```dewy
printl(0xff & 0x0f)
printl(1 << 8)
```

## Decimals are exact

A number with a decimal point is an exact fraction, not a binary float, so `0.1 + 0.2 =? 0.3` is true. A `float64` annotation asks for a float instead. See [Operators](operators.md) for how `/` treats integers.

<!-- dewy-example: {"mode": "run", "stdout": "true\n0.30000000000000004\n"} -->
```dewy
printl(0.1 + 0.2 =? 0.3)
let a:float64 = 0.1
printl(a + 0.2)
```

The [reference](/reference/literals.html) has the complete rules, including every base.
