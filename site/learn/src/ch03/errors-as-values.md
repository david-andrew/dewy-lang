# Errors as Values

Mint an error type and include it in a return union. The caller handles that alternative explicitly.

<!-- dewy-example: {"mode": "run", "stdout": "42\n"} -->
```dewy
ParseError:type = type of error & [message:string]
parse = (text:string):>int64|ParseError => {
    let value = to_int(text)
    if value is? none { return ParseError["invalid integer"] }
    return value
}
let result = parse("42")
if result is? int64 { printl(result) }
```

Expected output:

```text
42
```

Run the example from a file with `dewy example.dewy`. Its exact output is checked by the website build on the native release target.

> **Design boundary.** The [Errors as Values reference](/reference/errors-and-forwarding.html) specifies the complete language rules. A passing example covers this program only. See [generated coverage](/status/#ref-errors-and-forwarding) for related acceptance programs and unmeasured areas.
