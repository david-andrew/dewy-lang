# Imports

Dewy imports typed top-level bindings from another source file. Filename
extensions have no semantics: a path such as `p"stuff.txt"` works when that file
contains Dewy source. Relative paths are resolved from the file containing the
import, not from the process working directory.

```dewy
# Import one binding.
from p"stuff.dewy" import myfun

# The order may be reversed.
import myfun from p"stuff.dewy"

# Rename one binding.
from p"../some/other/path/to/stuff.dewy" import myfun as myfun2

# Import several unrenamed bindings. Commas and parenthesized whitespace are
# equivalent collection spellings.
from p"stuff.dewy" import first, second, third
from p"stuff.dewy" import (first second third)

# When any entry is renamed, use the parenthesized whitespace form.
from p"stuff.dewy" import (first second as other_second third)
import (first second as other_second third) from p"stuff.dewy"

# Capture every top-level binding under a compile-time namespace.
import p"mylib.dewy" as mylib
let result = mylib.myfun()
let value:mylib.MyType = mylib.default_value

# Splat every top-level binding directly into the current scope.
import p"mylib.dewy"
let result = myfun()
```

`p` is an ordinary function defined by the standard source prelude. It
constructs a thin `[path:string]` object, so `p"stuff.dewy"` is call
juxtaposition equivalent to `p("stuff.dewy")`.

Import sources use a smaller structural protocol rather than requiring the
standard `Path` alias. They need a `path` field containing an exact compile-time
string:

```dewy
from [path="stuff.dewy"] import myfun
```

An equivalent source-defined constructor preserves literal paths as well.
Dynamically computed strings cannot determine the module graph.

## Source prelude

The compiler checks an ordered list of Dewy source prelude files once and makes
their top-level bindings available as fallback names in ordinary modules.
Module declarations and explicit imports may shadow those names.

The current prelude contains `library/path.dewy`, which defines `Path` and `p`.
A module can opt out independently without changing any imported module:

```dewy
$no_prelude = true

let Path:type = [path:string]
let p = (path:string):>Path => [path=path]
from p"stuff.dewy" import myfun
```

A prelude-free module can also import directly from `[path="stuff.dewy"]`.
Strict project-wide freestanding compilation is separate future work.

Every top-level binding is importable for now, including values, functions,
overloads, constants, and type aliases. Repeated imports of the same resolved
file load and initialize it once. Name collisions and import cycles are compile
errors.

Installed package lookup, directory and glob imports, explicit export control,
non-source artifact loading, and incremental per-module artifacts remain future
work.
