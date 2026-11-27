# Modules and Imports

> [Generated coverage](/status/#ref-modules-and-imports) names related acceptance programs. Every example on this page compiles with the current compiler unless it is marked **Design only**.

Each source file is a module. Its top-level declarations are the module's bindings, and its top-level statements run when the program starts.

## Import Forms

| Form | Binds |
|---|---|
| `import p"shapes.dewy"` | every top-level declaration of the module, here |
| `import p"shapes.dewy" as shapes` | the module as a namespace: `shapes.area(…)` |
| `import units` | a library module as a namespace, under its own name |
| `from p"helpers.dewy" import advance, fresh` | the selected names |
| `from p"helpers.dewy" import (advance as step fresh)` | the selected names, `advance` renamed |
| `import (advance fresh) from p"helpers.dewy"` | the same as `from … import` |

A selection lists names with commas or inside parentheses, each optionally renamed with `as`. The selection may also go on the line after `from p"…"`.

<!-- dewy-example: {"mode":"run","stdout":"42 6 1\n","fixtures":{"shapes.dewy":"area = (w:int h:int):>int => w*h\nperimeter = (w:int h:int):>int => 2*(w+h)\n_scale = 2\n","helpers.dewy":"advance = (x:int):>int => x + 1\nfresh = ():>int => 0\n"}} -->
```dewy
import p"shapes.dewy"
import p"shapes.dewy" as shapes
from p"helpers.dewy" import advance as step, fresh
printl(area(6 7) shapes.perimeter(1 2) step(fresh()))
```

### Splat imports

An import with no selection and no `as` name binds each of the module's top-level declarations, as if every one were selected. Names starting with `_` stay private to their module, and the module's own imports are not passed on.

<!-- dewy-example: {"mode":"reject","diagnostic":"unknown function '_scale'","fixtures":{"shapes.dewy":"area = (w:int h:int):>int => w*h\n_scale = (x:int):>int => 2*x\n"}} -->
```dewy
import p"shapes.dewy"
printl(_scale(area(2 3)))
```

Two imports that bind different declarations under one name are an error naming both modules. Import one under a name, or select what you need.

<!-- dewy-example: {"mode":"reject","diagnostic":"'area' is imported from both shapes.dewy and rooms.dewy","fixtures":{"shapes.dewy":"area = (w:int h:int):>int => w*h\n","rooms.dewy":"area = (side:int):>int => side*side\n"}} -->
```dewy
import p"shapes.dewy"
import p"rooms.dewy"
printl(area(3))
```

## Module Lookup

- `p"…"` names a file, relative to the importing file. Subfolders work: `import p"sub/greet.dewy" as greet`.
- A bare name (`import physics`) searches beside the importing file, then the bundled library folders. The importing file itself is skipped, so `physics.dewy` can import the bundled `physics`.
- Within a folder, a Dewy importer prefers `.dewy` and falls back to `.jo`.
- `p"@lib/…"` names a file in the active toolchain's library directory, even when a neighbouring file has the same name: `import p"@lib/units.dewy" as units`.

The import source must be a literal. A runtime string cannot choose a module.

<!-- dewy-example: {"mode":"run","stdout":"3000 2km\n"} -->
```dewy
import units
from units import km
import p"@lib/units.dewy" as u
printl(3km/units.m 2u.km)
```

## Shadowing and the Prelude

Before checking a module, the compiler supplies the *prelude*: printing, numbers and their formatting, arrays, text, paths and files, processes, time units and clocks, channels and the rest of the everyday library. Every other module (`units`, `argparse`, game libraries) is imported.

The prelude's bindings are `$shadowable`. A `$shadowable const` at module top level may be shadowed by inner scopes and importing modules: there a plain `name = …` declares a new binding instead of being an error.

<!-- dewy-example: {"mode":"run","stdout":"3\n"} -->
```dewy
$shadowable const limit = 10
main = () => {
    limit = 3     # a new binding in this scope
    printl(limit)
}
```

A plain `const` cannot be reassigned or shadowed by assignment; `let` declares a new binding deliberately.

<!-- dewy-example: {"mode":"reject","diagnostic":"cannot modify const 'limit'; use let"} -->
```dewy
const limit = 10
main = () => {
    limit = 3
    printl(limit)
}
```

Name conflicts resolve this way:

- A module's own declaration may shadow an imported `$shadowable` one. Declaring a name that a non-`$shadowable` import also binds is an error; import that module under a name or rename the selection.
- An import may shadow the prelude's names.
- A non-`$shadowable` import outranks a `$shadowable` one.

<!-- dewy-example: {"mode":"reject","diagnostic":"is not `$shadowable`","fixtures":{"helpers.dewy":"advance = (x:int):>int => x + 1\n"}} -->
```dewy
import p"helpers.dewy"
advance = (x:int):>int => x + 10
printl(advance(1))
```

A splat import that shadows a prelude name warns, naming both. Selecting the name, or importing the module under a name, is quiet. Shadowing replaces the whole overload family: a module's own `max` hides every prelude `max` overload. Members are still found through their value, so `xs.hash()` reaches the prelude's.

`$no_prelude`, which turns the prelude off for one module, is part of the design but not built: the compiler reports it as not implemented.

## Import Cycles and Initialization

Modules may import each other in cycles. A program runs as if its modules were one file: each module sees the others' functions, types and values whichever imports first.

<!-- dewy-example: {"mode":"run","stdout":"42\n","fixtures":{"totals.dewy":"import p\"example.dewy\"\ntotal = ():>int => base + 2\n"}} -->
```dewy
import p"totals.dewy"
let base = 40
main = () => printl(total())
```

- Each module's top-level code runs once, in its own order. Imported modules go first, each running as far as it can.
- Within a cycle, a line that reads or writes another module's value (directly or through a function it calls) runs after that value is initialized.
- The only errors are the ones one file would have: values that need each other's first values, or a module's own order putting a line before a value it needs. Both name the chain of values and lines.
- A top-level call waits until the values its functions read or write are initialized, through statically known calls. In one file, calling such a function before the value's declaration is an error; statements are never reordered. Calls through opaque function values are not checked here.

<!-- dewy-example: {"mode":"reject","diagnostic":"a value cycle across modules","fixtures":{"second.dewy":"import p\"example.dewy\"\nlet b = a + 1\n"}} -->
```dewy
import p"second.dewy"
let a = b + 1
```

## Conditional Imports

An `if` whose condition compares `$target`, `$target.arch`, `$target.os` or `$build.mode` with string literals is decided while compiling. Only the live arm is checked, and its body is spliced into the enclosing scope, so imports in it bind as if written outside. The dead arms may name modules that exist only for other targets.

<!-- dewy-example: {"mode":"run","stdout":"42\n","fixtures":{"native_audio.dewy":"level = (x:int):>int => x + 1\n"}} -->
```dewy
if $target =? "wasm32" {
    import p"web_audio.dewy" as audio
} else {
    import p"native_audio.dewy" as audio
}
printl(audio.level(41))
```

`$supported_targets = ["x86_64-linux" "wasm32"]` at file scope lists the targets a module accepts. See [Settings](settings.md#target-and-build-mode) for `$target` and `$build`.

## Files and Processes

Paths (`p"…"`), files, processes and command-line arguments are prelude services, described in [Command-Line Programs, Files, and Processes](command-line-programs.md).
