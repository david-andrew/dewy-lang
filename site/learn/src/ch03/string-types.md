# Strings and Graphemes

String length counts graphemes. Interpolation puts values inside braces.

<!-- dewy-example: {"mode": "run", "stdout": "café: 4\n"} -->
```dewy
let word = "café"
printl"{word}: {word.length}"
```

Expected output:

```text
café: 4
```

Run the example from a file with `dewy example.dewy`. Its exact output is checked by the website build on the native release target.

> **Design boundary.** The [Strings and Graphemes reference](/reference/strings.html) specifies the complete language rules. A passing example covers this program only. See [generated coverage](/status/#ref-strings) for related acceptance programs and unmeasured areas.
