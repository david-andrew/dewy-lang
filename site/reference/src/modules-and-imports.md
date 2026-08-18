# Modules and imports

Imports resolve relative to the importing source file. The current system
supports selective names, aliases, whole-module namespaces, and splats.

```dewy
from p"lib.dewy" import (answer add)
import p"lib.dewy" as library
```

`p` is an ordinary prelude function producing a structural `Path` value. An
exact structural object with a string `path` field also satisfies the import
contract.

Reachable source modules share one type system and binding registry, initialize
once in dependency order, reject import cycles and collisions, and merge into
one µDewy executable. `$no_prelude = true` disables prelude bindings for its
containing module only.
