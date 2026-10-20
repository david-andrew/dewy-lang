# Stopping to Look

Build with debug information, then use a native debugger or the VS Code extension with CodeLLDB.

```sh
dewy build hello.dewy -g -o hello-debug
```

Configure `dewy.core.path` for the extension to point to your standalone `bin/dewy-core` or the checkout launcher. See [tools](/tools/) and the [debugging reference](/reference/debugging.html).

<!-- dewy-example: {"mode": "run", "stdout": "42\n"} -->
```dewy
let answer:int64 = 42
printl(answer)
```

Printing is enough to inspect this example. The reference separately specifies the `$breakpoint` directive; this lesson does not claim to test that directive.
