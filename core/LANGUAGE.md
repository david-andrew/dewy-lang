# Try the compact Dewy core

This guide covers the implementation on `restart/sloppy-frontend`. Build it from
the repository root with Python, a C compiler and `make` on Linux x86-64:

```sh
python3 -m tools.sloppy_core.build --bootstrap --output /tmp/dewy-core
/tmp/dewy-core/bin/dewy-core examples/sloppy_core/tour.dewy
```

The build directory must be new. The toolchain is standalone and does not replace
an installed Dewy compiler. A clean bootstrap currently takes about 18 seconds
on the development machine.

The [executable tour](../examples/sloppy_core/tour.dewy) prints:

```text
Independent array: 42
Record fields: 42
Dependent default: 42
Filtered comprehension: 44
Graphemes: 4 1
Optional match: 4
```

For day-to-day work in the checkout, `python3 -m tools.core test` builds or reuses
an up-to-date compiler and runs the focused gate. `python3 -m tools.core run
examples/sloppy_core/tour.dewy` runs the tour with the same cached toolchain.
The explicit `/tmp/dewy-core/bin/dewy-core` commands below also work with a
standalone build.

## Run, check and build

```sh
/tmp/dewy-core/bin/dewy-core new /tmp/hello-dewy program
/tmp/dewy-core/bin/dewy-core watch /tmp/hello-dewy/main.dewy
/tmp/dewy-core/bin/dewy-core check /tmp/hello-dewy/main.dewy
/tmp/dewy-core/bin/dewy-core build /tmp/hello-dewy/main.dewy --release -o /tmp/hello
/tmp/hello
```

`watch` reruns a terminal program after edits and retries failed builds when a
missing imported file or embedded asset appears. `check` reports errors without
emitting an executable. `build --time` reports compiler phase timings. Use
`--release` for optimized programs; development builds are the default.

The [VS Code extension](../dewy/vscode-dewy/README.md) supports unsaved diagnostics,
hover and definitions. Set `dewy.core.path` to the compiler executable.

## Functions and values

Arguments and array elements are separated by whitespace. Calls use adjacent
parentheses. A function's final expression is its result; `return` exits early.

```dewy
twice=(x)=>x+x
add=(a:int64 b:int64=2):>int64=>a+b
combine=(a b=a)=>a+b
main=()=>add(twice(20))
```

Types can be inferred, including generic functions. `:>` writes a result type;
use `:>void` for a function with no result. Named arguments such as `add(b=2 a=40)`
are supported. Explicit arguments evaluate in written order, then omitted
defaults in parameter order. An earlier parameter used in a default refers to
its captured value, so `combine(next())` calls `next()` once.

Use `let` to declare a local or deliberately shadow a name. Assignment updates a
visible variable; otherwise it can introduce a new variable. Parameters have
value semantics. Use `@` in both a parameter and its call to change the caller:

```dewy
bump=(@value:int64):>void=>{value+=1}
main=()=>{let value:int64=41 bump(@value) return value}
```

Integer types are `int8` through `int64` and `uint8` through `uint64`; floating
types are `float32` and `float64`. Ordinary integer literals default to `int64`
when they fit. Use `as` for numeric value conversion. Integer `//` is floor
division; floating-point `/` is available. Integer `/` and unbounded integers
are not implemented in this core yet.

Comparisons use `=?`, `<?`, `>?`, `<=?` and `>=?`. Boolean expressions use `and`,
`or` and `not`. Literal coefficients such as `2x` and `2(x+1)` multiply; use `*`
for general multiplication. A semicolon discards an expression's result.

## Records and collections

```dewy
Point:type=[x:int64 y:int64=22]
main=()=>{
    let point:Point=[x=20]
    let original=[values=[20 22]]
    let copy=original
    copy.values[0]=99
    let [y x]=point
    return x+y
}
```

`Point[20 22]` explicitly constructs a named record. `[x=20]` uses the expected
record type and its defaults. Without an expected type, named fields infer an
anonymous record. Anonymous record types agree by field names and types, even
when written in a different order. Their shape can also be written directly in
an annotation:

```dewy
sum=(point:[x:int64 y:int64]):>int64=>point.x+point.y
main=()=>{
    let point=[y=22 x=20]
    return sum(point)
}
```

Inline shapes work in parameters, returns, nested fields, collections, optional
values and function types. They share type identity with inferred anonymous
records. Named records remain distinct types; use a named declaration when fields
need defaults. Inline fields specify concrete value types.

Arrays and records retain independent values when copied, including nested
managed fields. Arrays support indexing, `.length`, and methods such as
`.push(value)`, `.pop()`, `.clear()` and `.truncate(count)`. `xs[1..3)` is an
exclusive-end slice; `xs[1..2]` includes index 2.

`let [a b] = xs` unpacks arrays or tuple results by position, with an exact array
length check. `_` discards an element. For records, targets select fields by
name, in any order. `[a b] = [b a]` swaps existing variables. Nested patterns
and `const` unpacking are not implemented yet.

```dewy
let values=[loop i in [0..10) i*i]
let selected=[loop value in values if value >? 20 value]
let lengths=[loop word in ["café" "🙂"] word->word.length]
```

Comprehensions are eager. Nested loops and block bodies work; a final block value
is collected, while `break`, `continue` and assignment statements do not emit a
value. `key -> value` creates dictionary entries; duplicate keys take the last
value. A dictionary can also be written directly as `["a"->20 "b"->22]`.

## Loops, text and optional values

`loop condition { ... }` repeats while the condition holds. Ranges such as
`[0..10)` exclude the upper bound. Combined headers walk iterables together:

```dewy
loop i in 0.. and character in "café 🙂" {
    printl"{i}: {character}"
}
```

String length, indexing, slicing and iteration use extended grapheme clusters.
`"é🙂".length` is 2. Interpolation uses `{expression}` inside a string.
Use `bytes(text)` for explicit UTF-8 bytes; binary literals such as `0x"ff00"`
also produce bytes. `$include_bytes(p"asset.png") as image` embeds an asset at
compile time, including for web builds.

`Type?` holds a value or `none`. `is?` narrows optional and union values:

```dewy
let lengths=["café"->4]
let found=lengths.get("café")
let size=match found {n:int64=>n <none>=>0}
printl"Length: {size}"
```

`match` supports typed bindings, literals and `_` as a fallback. A union is
written `int64|string`; union matches must cover its members or have a fallback.

## Modules and games

```dewy
import physics
import p"model.dewy" as model
from p"helpers.dewy" import advance, fresh
```

Bare names import bundled libraries; `p"..."` names a file. Both `.dewy` and the
inherited `.jo` library modules can be imported.

Start a game with the built-in template, then edit it while it runs:

```sh
/tmp/dewy-core/bin/dewy-core new /tmp/my-dewy-game
/tmp/dewy-core/bin/dewy-core watch /tmp/my-dewy-game/main.dewy
/tmp/dewy-core/bin/dewy-core build /tmp/my-dewy-game/main.dewy --target wasm -o /tmp/game
```

The web build produces `/tmp/game.html`. Games use `main()` for setup,
`update(dt:float64)` each frame, and `draw()` for rendering. The
[paddle game and physics playground](../examples/sloppy_core/README.md) show
input, drawing, simulation, module boundaries and live reload. Graphics, fonts,
audio, physics and other platform libraries come with the toolchain.

This remains a developing subset of Dewy. The earlier proof/effect system,
unbounded arithmetic, general structural conversions and every historical
juxtaposition form have not been recreated. See the
[implementation notes](../tools/sloppy_core/README.md) for current boundaries,
validation and measured performance.
