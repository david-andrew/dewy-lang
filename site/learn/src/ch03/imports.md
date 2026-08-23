# Imports

Dewy imports typed top-level bindings from another source file. Filename extensions have no semantics. `p"stuff.txt"` works when that file contains Dewy source. Relative paths resolve from the file that contains the import, not from the process working directory.

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
# TBD, may also support `from p"mylib.dewy" import ...` to splat everything
```

`p` is an ordinary prelude function. It builds a `[path:string]` object, so `p"stuff.dewy"` is a call, the same as `p("stuff.dewy")`.

A non-top-level item may be imported like so

```dewy
from p'somefile.dewy' import some.interior.item
```

This loads `item` into the current scope

An import source does not need the full `Path` type. It needs a `path` field that is a fixed string known when you compile.

```dewy
from [path="stuff.dewy"] import myfun
```

A string you compute while the program runs cannot choose the file. The compiler has to know every imported file up front.

Values, functions, overloads, constants, and type aliases are all importable. Repeated imports of the same resolved file load and initialize it once. Name collisions and import cycles are compile errors.

## Source Prelude

The compiler automatically imports some stuff for you before your program runs. This is called prelude imports.

The prelude includes `Path` and `p`, `print` / `printl`, `Duration` / `ns` / `ms` / `s`, and host helpers such as `sleep`. A module can opt out without changing any imported module:

```dewy
$no_prelude = true

let Path:type = [path:string]
let p = (path:string):>Path => [path=path]
from p"stuff.dewy" import myfun
```

A prelude-free module can also import things via `from[path="stuff.dewy"] import <stuff to import>`.

## Export and Packages

dewy is unlikely to supporting an explicit `export` keyword. anything in a file is visible and available for import. TBD how we will support imports from names rather than paths (e.g. `from units.SI.derived import xyz`), but for the most part, path based imports are the primary method of import.
