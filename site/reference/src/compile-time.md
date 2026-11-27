# Compile-Time Facilities and Metatags

> [Generated coverage](/status/#ref-compile-time) names related acceptance programs. Every example on this page compiles with the current compiler unless it is marked **Design only**.

Dewy has no separate macro, type or build language. Code that runs while compiling is ordinary Dewy, types are ordinary compile-time values, and `$name` metatags carry settings and directives.

## Compile-Time Evaluation

Constant expressions supply fixed-array lengths, `$assert` conditions, type arguments and literal checks. In these places ordinary checked functions run while compiling, including recursion, local mutation, loops, records, arrays, strings and error values. The library's text operations (`split`, `find`, `replace`, `join`, `upper`, `to_int`, …) run there too.

<!-- dewy-example: {"mode":"run","stdout":"6\n"} -->
```dewy
fib = (n:int):>int => if n <? 2 n else fib(n-1) + fib(n-2)
$assert fib(20) =? 6765

const N = 2 * 3
let xs:array<int64 length=N> = [1 2 3 4 5 6]
printl(xs.length)
```

A `const` initializer otherwise keeps its ordinary runtime behavior. A module constant that compile-time code demands is materialized as a value, so its table-building code does not run again at startup.

Compile-time execution has no step limit and no termination proof. It cannot read runtime locals or mutable globals, change global state, perform I/O, call external functions or reach host memory. Indirect and capturing calls, raw writes, generated declarations and host APIs are not supported yet. An unsupported operation is reported as an error, never silently deferred to run time.

## `$assert`

`$assert condition` or `$assert condition, "message"` must be proven while compiling; it never becomes a runtime check. A false condition is `assertion refuted`. An unknown one is `cannot prove assertion`, with the missing fact, the event that invalidated an earlier one, and possibly a witness consistent with the known bounds.

<!-- dewy-example: {"mode":"reject","diagnostic":"assertion refuted: N must be even"} -->
```dewy
const N = 7
is_even = (n:int):>bool => n % 2 =? 0
$assert is_even(N), "N must be even"
```

<!-- dewy-example: {"mode":"reject","diagnostic":"cannot prove assertion: missing lower bound"} -->
```dewy
positive = (x:int):>int => {
    $assert x >? 0
    x
}
printl(positive(3))
```

For runtime values, the proof uses constant facts, type tests, comparison guards, assignments and earlier `$runtime_assert` conditions. Calls forget facts about storage they may change, and loops forget values that change in them. See [Refinements, Effects, and Safety](refinements-and-effects.md#assertions) for `$runtime_assert` and the obligations the compiler proves.

## Types as Values

Types are compile-time values of type `type`. Aliases, generic type constructors, dimensions and refinements are ordinary bindings and expressions. See [Types and Conversions](types-and-conversions.md).

- `T.name` is a type's short name, a compile-time `string`.
- `members(U)` of a union of types yields its alternative types; a loop over it specializes its body for each.
- `size_of<T>` and `align_of<T>` are compile-time integers.

<!-- dewy-example: {"mode":"run","stdout":"Jpeg Png string\n"} -->
```dewy
Png:type = [w:int64]
Jpeg:type = [q:int64]
Img:type = Png | Jpeg
kind = (x:Img):>string => {
    loop t in members(Img) { if x is? t return t.name }
    "none"
}
describe = <T>(_x:T):>string => T.name
main = () => printl"{kind(Jpeg[2])} {describe(Png[1])} {describe("text")}"
```

## Record Fields at Compile Time

`fields(T)` is a compile-time sequence of a record type's field descriptors, each with `.name` (a constant string) and `.type`. A loop over it specializes its body for each field. `value.$field(name)` reads or writes the field named by a compile-time string; runtime names need a dictionary.

A loop inside a record literal expands into ordinary named fields. Constant arrays can supply the names, and compile-time interpolation builds them:

<!-- dewy-example: {"mode":"run","stdout":"[x=1 y=2]\n[x=0 y=0 z=0]\n[a1=true a2=true b1=true b2=true]\n"} -->
```dewy
Point:type = [x:int y:int]
copy_fields = <T>(value:T) =>
    [loop f in fields(T) $field(f.name) = value.$field(f.name)]
printl(copy_fields(Point[1 2]))
printl([loop name in ["x" "y" "z"] $field(name) = 0])
printl([loop r in ["a" "b"] loop c in ["1" "2"] $field("{r}{c}") = true])
```

Conditional record shapes are not supported. Field descriptors cannot escape into runtime storage.

## Embedding Files

`$include_bytes(p"file")` reads a file while compiling and gives its bytes as an `array<uint8>`, for native and web builds alike. The file is tracked as a dependency, so `watch` rebuilds when it changes. `$include_bytes(p"logo.png") as image` decodes an embedded image.

<!-- dewy-example: {"mode":"run","stdout":"5 true\n","fixtures":{"greeting.txt":"hello"}} -->
```dewy
let data = $include_bytes(p"greeting.txt")
printl(data.length (data as string?) =? "hello")
```

## Metatags

A word starting with `$` is a metatag. There are four kinds.

| Kind | Examples | Where it goes |
|---|---|---|
| Settings | `$runtime_checks`, `$explicit_copies`, `$time.zone = 'UTC'` | at the top of a file, function body or block; see [Settings and Safety Levels](settings.md) |
| Construct tags | `$extern`, `$export`, `$intrinsic`, `$test`, `$warn_if`, a loop label | immediately before the construct they mark |
| Directives | `$assert`, `$runtime_assert`, `$expect`, `$fail`, `$breakpoint`, `$include_bytes`, `$field`, `$allocator`, `$unsafe` | where an expression or statement goes, with their own argument grammar |
| Compile-time values | `$target`, `$build.mode`, `$dewy.version` | read as constant expressions |

### Loop labels

A label prefixes its loop. `break $name` and `continue $name` target the labelled loop from inside nested ones. A label does not cross a function boundary.

<!-- dewy-example: {"mode":"run","stdout":"23\n"} -->
```dewy
let found = 0
$rows loop r in [0..5) {
    loop c in [0..5) {
        if r * c =? 6 { found = r*10 + c  break $rows }
    }
}
printl(found)
```

A label on its own line at the top of a block names the loops directly in that block. A label before a `lazy` body ends the generator early (see [Generators](generators.md#ending-early)).

### Directive grammar

`$assert`, `$runtime_assert` and `$expect` take a condition and an optional message after a comma; the directive owns that comma, and `$assert(condition, "message")` is the same form. `$fail` takes only an optional message. `$breakpoint` takes nothing (see [Debugging](debugging.md#breakpoint)). `$test` and `$test(cases=…)` go on the line before a test function (see [Testing](testing.md)).

### Not built

Other directives of the design, such as `$no_prelude` and `$unsafe_assume`, are reported as not implemented where they appear. User-defined metatags beyond setting bundles, generated declarations and syntax extension are not part of the language yet.
