# Strings and Graphemes

Strings are Unicode text. Length and indexing count graphemes, the characters a reader sees, so an emoji family or an accented letter counts once. Braces interpolate any expression.

<!-- dewy-example: {"mode": "run", "stdout": "café: 4\nstarts with c\n[\"red\" \"green\" \"blue\"]\nred+green+blue\n"} -->
```dewy
let word = "café"
printl"{word}: {word.length}"
if word.startswith("c") printl"starts with c"

colors = "red,green,blue".split(",")
printl(colors)
printl(colors.join("+"))
```

Single and double quotes mean the same thing; pick whichever avoids escaping. A function given a single string can be called without parentheses, which is why `printl"..."` works.

The [reference](/reference/strings.html) has the complete rules.
