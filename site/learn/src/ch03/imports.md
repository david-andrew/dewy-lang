# Modules, Imports, and the Prelude

Every source file is a module. Imports bring typed top-level bindings from another module into the current one.

## Importing Names

Paths resolve relative to the importing file:

```dewy
from p"helpers.dewy" import format_name
import format_name from p"helpers.dewy"
```

The order may be written either way. Import several names with a comma sequence or a parenthesized whitespace sequence:

```dewy
from p"helpers.dewy" import parse, validate, save
from p"helpers.dewy" import (parse validate save)
```

Rename a binding with `as`:

```dewy
from p"helpers.dewy" import (save as save_document)
```

## Namespaces and Splats

Bind a module namespace when several uses should remain qualified:

```dewy
import p"helpers.dewy" as helpers

let result = helpers.parse(input)
let item:helpers.Item = result
```

Importing only the path splats its top-level bindings into the current scope:

```dewy
import p"helpers.dewy"
```

Name collisions and import cycles are compile errors.

## Paths Are Compile-Time Values

`p` is an ordinary prelude function constructing a structural path value:

```dewy
from [path="helpers.dewy"] import parse
```

The compiler must know the exact path while building the module graph. A runtime-computed string cannot choose a source import.

File suffixes are conventional; a file containing Dewy source does not acquire different language semantics because of its extension.

## Initialization

Reachable modules initialize once in dependency order. Their top-level expressions run before the entry module proceeds to `main`.

## Targets

`$target` is the compile-time name of the backend being compiled for (`x86_64`, `riscv`, `arm`, `c`, `wasm32`), the same names udewy uses. Comparing it selects code during checking, so an arm for another target is skipped entirely and may import files that exist only there:

```dewy
if $target in? ["x86_64" "riscv" "arm" "c"] {
    from p"linux/io.dewy" import (_write_stdout _write_stderr)
}
if $target not =? "wasm32" { import p"native_only.dewy" }
```

`$supported_targets = ["x86_64" "c"]` rejects compilation for any other target. Only comparisons of `$target` fold this way; an ordinary `if true` still checks every arm.

## The Source Prelude

Ordinary modules receive a small set of default imports: path construction, printing, rationals and fixed-point numbers, units, and host facilities such as `sleep` where the target supplies them. The prelude's portable files import their target-specific primitives with the same `$target` gating.

A module can opt out:

```dewy
$no_prelude = true
```

That choice applies to the containing module and does not silently change modules it imports.

> **Provisional design:** Installed package lookup, non-source artifacts, and the naming policy for domain libraries are still evolving. File-relative source imports and the per-module prelude rule are settled.

The Reference defines [module resolution and initialization](../../reference/modules-and-imports.html).
