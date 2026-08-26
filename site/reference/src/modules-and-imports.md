# Modules and Imports

Each source file defines a module containing its top-level bindings and executable initialization expressions.

## Relative Source Imports

An import path resolves relative to the file containing the import:

```dewy
from p"lib.dewy" import (answer add)
import p"lib.dewy" as library
```

Selective imports bind the requested names directly. `as` renames a selected binding. A namespace import retains qualification. Importing a path without a selection splats its top-level bindings into the current scope.

The `from path import names` and `import names from path` orders are equivalent.

## Import Sources

`p` is an ordinary prelude function producing a structural path value. Any exact compile-time object with the required string `path` field satisfies the source-import contract:

```dewy
from [path="lib.dewy"] import answer
```

Source imports must be known while constructing the module graph. Runtime strings cannot select source modules.

## Binding Kinds

Values, constants, functions, overload sets, and type aliases are importable. Imported type values remain compile-time values in the receiving module.

## Graph and Initialization

Reachable source modules share a coherent type environment, initialize once in dependency order, and reject unresolved names, cycles, and collisions. A source suffix is conventional and does not select different Dewy semantics.

## Targets

`$target` is a compile-time string naming the backend (`x86_64`, `riscv`, `arm`, `c`, `wasm32`). Comparing `$target` with a string literal (`=?`, `not =?`, `in?` and `not in?` against a literal list, combined with `not`, `and`, `or`) folds during checking; an `if` whose condition is such a comparison skips its dead arms without checking them — they may import files that exist only for other targets — and splices the live arm's `{}` body into the enclosing scope so gated imports and declarations bind there. Plain literal conditions keep ordinary flow semantics.

`$supported_targets = ["x86_64" ...]` lists the backends a module accepts; compiling for another target is an error.

## Prelude

Before checking an ordinary module, the compiler supplies a source prelude of shadowable bindings: paths, printing, `rational` and `fixed` numbers, units, and the current target's services layer. `$no_prelude = true` disables those implicit bindings for its containing module only. Imported modules retain their own prelude decision.

## Provisional Package Facilities

Installed package lookup, directory or glob imports, non-source artifacts, project-wide freestanding policy, and domain-library naming remain provisional. They must extend rather than contradict file-relative module identity and one-time initialization.
