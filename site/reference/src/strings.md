# Strings and Graphemes

> [Generated coverage](/status/#ref-strings) names related acceptance programs. Every example on this page compiles with the current compiler unless it is marked **Design only**.

## Semantic Model

A `string` is an immutable sequence of Unicode extended grapheme clusters. Length, indexing, slicing and iteration count graphemes, not bytes or code points: `"é🙂".length` is 2. The exact code points are preserved; equality compares them, with no implicit normalization.

Strings are immutable shares: binding, passing and returning one copies nothing.

<!-- dewy-example: {"mode":"run","stdout":"6\né\n🙂\n0:c 1:a 2:f 3:é 4:  5:🙂 \n[\"a\" \"b\" \"🙂\"]\n"} -->
```dewy
let text = "café 🙂"
printl(text.length)
if text.length >? 5 {
    printl(text[3])
    printl(text[5])
}
loop i in 0.. and ch in text { print"{i}:{ch} " }
printl("")
printl(graphemes("ab🙂"))
```

A string loop streams graphemes from a snapshot of the string; `graphemes(text)` (or `text.chars`) collects them into an array. Indexing scans from the start, so visit every grapheme with a loop rather than indexing in a loop.

## Indexing and Slicing

`text[i]` is grapheme `i`, as a one-grapheme string; `text[a..b)` is a slice. Both are proven in bounds, like array indexes: an ASCII literal's length is known, and a runtime string needs facts such as `i <? text.length`. Inside the brackets, `end` is `text.length - 1`. `text.get(i)` gives the grapheme or `none` past either end.

<!-- dewy-example: {"mode":"run","stdout":"héllo\n"} -->
```dewy
first_word = (text:string):>string => {
    let i:int64 = 0
    loop i <? text.length {
        if text[i] =? " " { return text[0..i) }
        i += 1
    }
    return text
}
printl(first_word("héllo world"))
```

<!-- dewy-example: {"mode":"reject","diagnostic":"index is not in bounds"} -->
```dewy
let s = "abc"
printl(s[3])
```

`text.startswith(prefix)` with a known nonempty prefix proves the text nonempty when true, so `if not text.startswith("=") return` permits `text[1..]` afterward. `text.byte_slice(start stop)` slices by UTF-8 byte offsets; both ends must be proven within the byte length and on character boundaries. Stepped string slices are not implemented.

## Literals

Single and double quotes are equivalent; both support escapes and interpolation. Three matching quotes allow embedded quotes and line breaks, keeping all whitespace. An `r` prefix keeps backslashes and braces literally.

| Escape | Meaning |
|---|---|
| `\n` `\r` `\t` `\a` `\b` `\v` `\f` `\0` | control characters |
| `é`, `\u{1F642}` | a Unicode scalar value: four hex digits, or one to six in braces |
| `\{` `\}` `\'` `\"` `\\` | any ASCII punctuation escapes to itself |
| backslash at end of line | continues the string without the line break |

Surrogates and values above `10FFFF` are errors, as is an unknown letter or digit escape (`\N`).

<!-- dewy-example: {"mode":"run","stdout":"Ada has 6 points\nassets\\{name}.png\nHe said \"go\".\nNext: 3\ntab:\there é 🙂 {braces}\n"} -->
```dewy
let name = "Ada"
let n = 3
printl"{name} has {n * 2} points"
printl(r"assets\{name}.png")
let caption = """He said "go".
Next: {n}"""
printl(caption)
printl("tab:\there é \u{1F642} \{braces\}")
```

`printl"..."` is a call with one string argument; the parentheses may be left out.

## Interpolation

`{expression}` inside a string evaluates an ordinary expression and converts its value as `value as string` does (see [Printing](#printing)). Interpolations may contain nested strings, blocks and comments.

## Building Strings

`+` does not join text. Two strings combine by interpolation, `"{left}{right}"`; many pieces collect in an `array<string>` and `join`. On a local string, `s = "{s}more"` appends in place, so building text in a loop stays linear. `text * n` repeats text; a count of zero or less gives `""`.

<!-- dewy-example: {"mode":"run","stdout":"1, 2, 3\n123\n----------\n"} -->
```dewy
let pieces:array<string> = []
loop v in [1 2 3] { pieces.push"{v}" }
printl(pieces.join(", "))
let s = ""
loop v in [1 2 3] { s = "{s}{v}" }
printl(s)
printl("-" * 10)
```

<!-- dewy-example: {"mode":"reject","diagnostic":"`+` does not join text"} -->
```dewy
let a = "x"
let b = "y"
printl(a + b)
```

`s += x` is an error for the same reason.

## Printing

`print(x)` writes a value; `printl(x)` writes it and a line break. `file=stderr` writes to standard error. Printing, interpolation, `string(value)` and `value as string` show a value as its literal syntax:

- containers as their literals: `[1 2 3]`, `set["a" "b"]`, `["a" -> 1]`, a range as `[0..2]`;
- a record field by field, `[x=1 name="q"]`; a minted type adds its name, `Fault[code=7]`;
- a type that declares `__as__ = ():>string` shows that text instead;
- a string bare on its own, and quoted with its escapes inside a structure (`["a\tb"]`);
- an optional or union as its current member, and an absent optional as `none`.

<!-- dewy-example: {"mode":"run","stdout":"[1 2 3]\nset[\"ab\" \"c\"]\n[\"k\" -> [x=1 y=2]]\n[\"a\\tb\"]\n[true false] and [name=\"q\"]\nnone\nFault[code=7]\n21°C\n"} -->
```dewy
Point:type = [x:int64 y:int64]
Fault:type = type of error & [code:int64]
Temp:type = [c:int64 __as__ = ():>string => "{c}°C"]
printl([1 2 3])
printl(set["ab" "c"])
printl(["k" -> Point[1 2]])
printl(["a\tb"])
printl'{[true false]} and {[name="q"]}'
let n:int64? = none
printl(n)
printl(Fault[7])
printl(Temp[21])
```

The printed text of a structure is for reading, not a stable format.

### Formatting

`fmt'pattern'` is a function that formats one value. The pattern is Python's format spec, `[[fill]align][+][#][0][width][,|_][.precision][type]`. A literal pattern is checked while compiling, including whether it accepts the value's type. `s.pad_start(n)`, `s.pad_end(n)` and `s.pad_center(n)` pad text to a width, with an optional fill. Widths count graphemes; text is never truncated.

<!-- dewy-example: {"mode":"run","stdout":"result is 3.14\n0x00ff\n1,234,567\n**hi**\n"} -->
```dewy
let x = 3.14159
printl'result is {fmt'.2f'(x)}'
printl(fmt'#06x'(255))
printl(fmt','(1234567))
printl("hi".pad_center(6 "*"))
```

## Searching, Splitting and Trimming

Positions are grapheme positions, as indexing counts them. Methods that take no other argument are called without parentheses.

| Method | Gives |
|---|---|
| `contains(part)`, `startswith(p)`, `endswith(s)` | `bool` |
| `find(part)`, `rfind(part)`, `find(part start)` | first or last position, or `Missing` |
| `count(part)` | nonoverlapping occurrences |
| `split(sep)`, `split` | pieces between separators; words between runs of whitespace |
| `lines` | lines without their breaks; a final break adds no empty line |
| `trim`, `trim_start`, `trim_end`, `trim(chars)` | text without surrounding whitespace (or `chars`) |
| `remove_prefix(p)`, `remove_suffix(s)` | text without that end, once, if present |
| `replace(old new)` | every occurrence replaced |
| `upper`, `lower` | Unicode full case mapping, locale-free |
| `is_alpha`, `is_digit`, `is_space`, `is_alnum`, `is_empty` | `bool` |
| `chars` | the graphemes, as an array |

A found position is at most `text.length`, so `text[..at)` and `at + 1` need no check; indexing `text[at]` still needs `at <? text.length`. Default a search with `??` (`text.find("=") ?? -1`), test it with `is? Missing`, or forward it with `or_throw`.

<!-- dewy-example: {"mode":"run","stdout":"key: value\n3\n-1\n[\"a\" \"\" \"b\"]\n[\"one\" \"two\" \"three\"]\n[\"x\" \"y\"]\n2\nfile\nSTRASSE\na+b+c\n"} -->
```dewy
printl("  key: value  ".trim)
let at = "key=value".find("=")
if at isnt? Missing { printl(at) }
printl("key=value".find("#") ?? -1)
printl("a,,b".split(","))
printl("one two  three".split)
printl("x\ny\n".lines)
printl("banana".count("an"))
printl("file.txt".remove_suffix(".txt"))
printl(upper("straße"))
printl("a-b-c".replace("-" "+"))
```

### Regular expressions

`regex(pattern)` prepares a pattern, giving `Regex | RegexError`; a literal pattern is checked while compiling and gives a plain `Regex`. `text.find(r)` gives `Match | Missing`; `find_all`, `contains`, `matches` (whole string), `split` and `replace` also take a `Regex`. A `Match` has `text`, `groups`, `start` and `end`; its offsets are UTF-8 byte offsets, not grapheme positions. `replace` accepts `$0`, `$1`, … and `$$`, or a `(Match):>string` callback. Matching never backtracks exponentially.

<!-- dewy-example: {"mode":"run","stdout":"2026-10\n[\"a\" \"b\" \"c\"]\n10/2026\n"} -->
```dewy
let r = regex(r"(\d{4})-(\d\d)")
let found = "due 2026-10!".find(r)
if found isnt? Missing { printl(found.text) }
printl("a, b;c".split(regex(r"[,;]\s*")))
printl("2026-10".replace(r "$2/$1"))
```

## Bytes

`bytes(text)` and `text as array<uint8>` give a string's UTF-8 bytes. `b"abc"` is an `array<uint8>` literal and `b'a'` a single `uint8`. Decoding needs validation: `bytes as string | none` gives the text or `none` for invalid UTF-8, and `bytes as string ?? ""` decodes with a fallback. Plain `bytes as string` is an error, since nothing proves the bytes valid.

<!-- dewy-example: {"mode":"run","stdout":"[104 105]\n97\n3\nhé\nnone\nA\n"} -->
```dewy
printl(b"hi")
printl(b'a')
let raw = bytes("hé")
printl(raw.length)
printl(raw as string | none)
let bad:array<uint8> = [0xff]
printl(bad as string | none)
printl(chr(0x41))
```

`chr(scalar)` is the one-scalar string of a Unicode scalar value. `bytes.read<uint64>(i)` (and `uint32`, `uint16`) loads little-endian words from a byte array at any alignment; the offset is an obligation.

## Including Files

`$include_bytes(p"path")` embeds a file's bytes at compile time. The path is a literal, resolved against the source file. The result is an `array<uint8>` of known length:

<!-- dewy-example: {"mode":"run","stdout":"6\nhello\n\n","fixtures":{"notes.txt":"hello\n"}} -->
```dewy
let raw = $include_bytes(p"notes.txt")
printl(raw.length)
printl(raw as string ?? "")
```
