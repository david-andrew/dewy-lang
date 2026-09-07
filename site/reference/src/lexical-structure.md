# Lexical Structure

## Source Text

Dewy source is Unicode text. Source-file suffixes are conventional and do not alter tokenization or semantic rules.

## Case

Dewy is case-sensitive. Keywords (`let`, `loop`, `if`), word operators (`and`, `or`, `not`, `in?`, `is?`), the booleans `true` and `false`, and symbols are matched exactly as written: `True`, `AND`, and `Loop` are ordinary identifiers, distinct from each other and from `true`, `and`, and `loop`. Case does not matter in two places, both where the strict reading would silently mean something else: inside a numeral, the alphabetic digits of a based integer (`0xff` and `0xFF`) and the exponent marker (`1e5` and `1E5`) may be written either way, while the base prefix itself is lowercase (`0x`, `0b`; `0X` is not a prefix); and the two string escapes that take digits, `\u`/`\U` (a scalar, `\u{1F600}`) and `\x`/`\X` (a hex byte escape, which Dewy rejects), are recognized in either case. Every other escape is lowercase (`\n`), and a backslash before any other character is that character itself (`\N` is `N`).

## Identifiers

An identifier contains at least one base character. Decorations may appear before or after that base character, and decimal digits may follow it.

The current base repertoire contains ASCII Latin letters, the ordinary Greek alphabet, `_`, `‾`, `!`, `°`, and selected mathematical letter symbols such as `ℂ`, `ℕ`, `ℤ`, `ℚ`, and `ℝ`. Decorations include the supported Unicode superscript and subscript letters and digits, prime marks, and `℠`, `™`, `©`, and `®`.

Identifiers are case-sensitive. The exact Unicode repertoire and its normalization/security policy remain provisional; implementations must document the repertoire they accept and must not silently normalize two distinct source spellings into one binding.

Reserved operator words such as `and`, `or`, `not`, `in`, `as`, and `transmute` tokenize as operators in their grammatical contexts. A word operator cannot simultaneously be used as an ordinary identifier in that context.

## Whitespace and Juxtaposition

Whitespace separates tokens. Dewy does not generally use commas to separate arguments, parameters, or array elements.

Spacing can also determine whether expressions are juxtaposed with a punctuation operator. Range endpoints are the clearest example:

```dewy
first..last    # both endpoints
first ..last   # no left endpoint
first.. last   # no right endpoint
first .. last  # no endpoints
```

Newlines normally behave as whitespace. A construct may assign additional structural meaning to line boundaries only where its grammar explicitly says so.

## Comments

`#` begins a line comment. `#{` and `}#` delimit a nestable block comment.

```dewy
# one line
#{ outer
   #{ nested }#
   outer again
}#
```

Comment markers inside strings are string contents.

A documentation string is an ordinary call of the prelude's `doc` with a string — usually a `"""` block — at the top of a module, a function body, or a type. The compiler keeps nothing from it yet, so the call is a no-op:

```dewy
doc"""
Tokenizer framework.
"""
```

## Tokens and Ambiguity

Tokenization chooses the longest valid token subject to explicit lexical rules. Parsing may preserve several structurally valid interpretations—most notably call, indexing, and multiplication juxtaposition—until types and context resolve them.

See [Literals](literals.md) for literal tokens and [Operators and Precedence](operators-and-precedence.md) for expression grouping.
