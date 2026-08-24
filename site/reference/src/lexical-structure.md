# Lexical Structure

## Source Text

Dewy source is Unicode text. Source-file suffixes are conventional and do not alter tokenization or semantic rules.

## Identifiers

Identifiers support Latin and Greek letters, selected mathematical symbols, decimal digits after the first character, and language-defined decorations. Identifiers and word operators are case-sensitive unless a particular imported API specifies otherwise.

Reserved operator words such as `and`, `or`, `not`, `in`, `as`, and `transmute` tokenize as operators in their grammatical contexts.

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
