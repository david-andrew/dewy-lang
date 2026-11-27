# Modules, Imports, and the Prelude

Every source file is a module. An import brings names from another module into this one. This chapter covers importing your own files, importing from the library, and the names you get without importing anything.

## A file of your own

Put shared code in a second file beside the first. Here is `helpers.dewy`, with two functions. The examples below assume it sits next to the file that imports it.

<!-- dewy-example: {"mode": "check", "fixtures": {}} -->
```dewy
answer = ():>int => 42
double = (n:int):>int => n * 2
```

A path literal `p"..."` names a file, relative to the file that imports it. List the names you want after `from`:

<!-- dewy-example: {"mode": "run", "stdout": "52\n", "fixtures": {"helpers.dewy": "answer = ():>int => 42\ndouble = (n:int):>int => n * 2\n"}} -->
```dewy
from p"helpers.dewy" import (answer double)
printl(answer() + double(5))
```

`as` renames a name as you take it:

<!-- dewy-example: {"mode": "run", "stdout": "47\n", "fixtures": {"helpers.dewy": "answer = ():>int => 42\ndouble = (n:int):>int => n * 2\n"}} -->
```dewy
from p"helpers.dewy" import (answer as a, double)
printl(a() + 5)
```

## Splat imports

`import` of a path with no list brings in every top-level name of that module at once:

<!-- dewy-example: {"mode": "run", "stdout": "42\n", "fixtures": {"helpers.dewy": "answer = ():>int => 42\ndouble = (n:int):>int => n * 2\n"}} -->
```dewy
import p"helpers.dewy"
printl(answer())
```

Splatting is convenient for a small module you own and hard to read in a large program, since the reader cannot tell where `answer` came from. If two splats bring the same name, the compiler refuses and tells you to choose:

<!-- dewy-example: {"mode": "reject", "diagnostic": "is imported from both", "fixtures": {"helpers.dewy": "answer = ():>int => 42\n", "other.dewy": "answer = ():>int => 7\n"}} -->
```dewy
import p"helpers.dewy"
import p"other.dewy"
printl(answer())
```

## Keeping a namespace with `as`

Add `as name` and the names stay behind that prefix, so nothing can collide:

<!-- dewy-example: {"mode": "run", "stdout": "49\n10\n", "fixtures": {"helpers.dewy": "answer = ():>int => 42\ndouble = (n:int):>int => n * 2\n", "other.dewy": "answer = ():>int => 7\n"}} -->
```dewy
import p"helpers.dewy" as h
import p"other.dewy" as o
printl(h.answer() + o.answer())
printl(h.double(5))
```

A name that starts with `_` is private to its module. Neither a splat nor a qualified name reaches it.

## The library

A bare name instead of a path looks in the compiler's library, not beside your file. `units` is a library module:

<!-- dewy-example: {"mode": "run", "stdout": "3000\n5000\n"} -->
```dewy
from units import (m km)
import units
printl(3km/m)
printl(5 * units.kg / units.g)
```

The [Standard Library](../ch04/00-stdlib.md) chapter tours what is there.

## The prelude

A few names need no import: `printl` and the other printing functions, paths (`p"..."`), `rational`, time (`s`, `ms`, `Duration`, `now`) and the services of the target you build for. Those come from a source prelude that the compiler adds in front of every module.

You can shadow a prelude name with your own declaration. A `let` makes a fresh binding in your module:

<!-- dewy-example: {"mode": "run", "stdout": "5\nb.txt\n"} -->
```dewy
let run = 5
printl(run)
printl(p"a/b.txt".name)
```

A splat import that shadows a prelude name works but warns, naming both. Selecting the name, or importing the module `as` a name, is quiet.

Only the `main` of the file you run executes. An imported file's `main` is just a function in that module.

The [reference](/reference/modules-and-imports.html) has the complete rules.
