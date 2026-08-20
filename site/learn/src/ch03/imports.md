# Imports

Dewy imports typed top-level bindings from another source file. Filename
extensions have no semantics. `p"stuff.txt"` works when that file
contains Dewy source. Relative paths resolve from the file that contains
the import, not from the process working directory.

```dewy
# Import one binding.
from p"stuff.dewy" import myfun

# The order may be reversed.
import myfun from p"stuff.dewy"

# Rename one binding.
from p"../some/other/path/to/stuff.dewy" import myfun as myfun2

# Import several unrenamed bindings. Commas and parenthesized whitespace
# are equivalent collection spellings.
from p"stuff.dewy" import first, second, third
from p"stuff.dewy" import (first second third)

# When any entry is renamed, use the parenthesized whitespace form.
from p"stuff.dewy" import (first second as other_second third)
import (first second as other_second third) from p"stuff.dewy"

# Capture every top-level name under a namespace.
import p"mylib.dewy" as mylib
let result = mylib.myfun()
let value:mylib.MyType = mylib.default_value

# Splat every top-level binding directly into the current scope.
import p"mylib.dewy"
let result = myfun()
```

`p` is an ordinary prelude function. It builds a `[path:string]`
object, so `p"stuff.dewy"` is a call, the same as `p("stuff.dewy")`.

An import source does not need the full `Path` type. It needs a `path`
field that is a fixed string known when you compile.

```dewy
from [path="stuff.dewy"] import myfun
```

A string you compute while the program runs cannot choose the file. The
compiler has to know every imported file up front.

Values, functions, overloads, constants, and type aliases are all
importable. Repeated imports of the same resolved file
load and initialize it once. Name collisions and import cycles are
compile errors.

## Source Prelude

The compiler makes an ordered list of Dewy source prelude files
available as fallback names. Module declarations and explicit imports
may shadow those names.

The prelude includes `Path` and `p`, `print` / `printl`, `Duration` /
`ns` / `ms` / `s`, and host helpers such as `sleep`. A module can opt
out without changing any imported module:

```dewy
$no_prelude = true

let Path:type = [path:string]
let p = (path:string):>Path => [path=path]
from p"stuff.dewy" import myfun
```

A prelude-free module can also import from `[path="stuff.dewy"]`.

## Export and Packages

`export`, installed package lookup, directory and glob imports, and
versioned package names are not yet determined.
