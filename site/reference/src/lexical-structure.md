# Lexical structure

## Identifiers

Dewy identifiers support Latin and Greek letters, selected mathematical
symbols, decimal digits after the first character, and several decorations.
Identifiers and word operators are case-sensitive except where a construct is
documented otherwise.

## Comments

`#` begins a line comment. `#{` and `}#` delimit a block comment.

```dewy
# one line
#{ multiple
   lines }#
```

## Literals

Implemented literal categories include booleans, integers in bases 2 through
16, strings, and power-of-two based strings. String semantics are based on
Unicode extended grapheme clusters; based strings represent exact packed bits.

Whitespace is generally insignificant but establishes token separation and can
create juxtaposition between adjacent expressions.
