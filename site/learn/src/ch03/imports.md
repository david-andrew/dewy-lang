# Modules, Imports, and the Prelude

Import a named binding from a source-relative module. This example includes the companion file used by the checker.

<!-- dewy-example: {"mode": "run", "stdout": "42\n", "fixtures": {"helpers.dewy": "answer = ():>int64 => 42\n"}} -->
```dewy
from p"helpers.dewy" import answer
printl(answer())
```

Create `helpers.dewy` beside the importing file:

<!-- dewy-example: {"mode": "check"} -->
```dewy
answer = ():>int64 => 42
```

A bare `import` splats the module's top-level names into the importing file; a name that collides is an error. Add `as` to keep them in a namespace instead:

<!-- dewy-example: {"mode": "run", "stdout": "42\n42\n", "fixtures": {"helpers.dewy": "answer = ():>int64 => 42\n"}} -->
```dewy
import p"helpers.dewy"
import p"helpers.dewy" as helpers
printl(answer())
printl(helpers.answer())
```

The [reference](/reference/modules-and-imports.html) has the complete rules.
