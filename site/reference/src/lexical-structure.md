# Lexical Structure

## Source Text

Dewy source is Unicode text. Source-file suffixes are conventional and do not alter tokenization or semantic rules.

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

## Tokens and Ambiguity

Tokenization chooses the longest valid token subject to explicit lexical rules. Parsing may preserve several structurally valid interpretations—most notably call, indexing, and multiplication juxtaposition—until types and context resolve them.

See [Literals](literals.md) for literal tokens and [Operators and Precedence](operators-and-precedence.md) for expression grouping.
