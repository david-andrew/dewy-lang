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
completions, hover and definitions. Set `dewy.core.path` to the compiler executable.

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

Module-level overload groups join function literals with `&`:

```dewy
measure = ((value:int64):>int64=>value)
        & ((text:string):>int64=>text.length)
main=()=>measure(40)+measure("ab")
```

Groups can be nested, and members may have different arities, defaults or generic
type parameters. They expand into ordinary function declarations, sharing the
same overload selection as repeated declarations of a function name. Selected
imports retain the whole group. When passing an overloaded function as a value,
its expected callable type selects a member. Grouping existing function values
or local closures is not yet supported; group members must be function literals
at module level. `main` must have one entry-point definition.

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
division and `%` gives a remainder with the divisor’s sign (or zero). These
operators support signed `int64` and unsigned `uint64`, preserving the full
unsigned range; narrower operands retain the existing integer widening rules.
Floating-point `/` is available; built-in integer `/` is not implemented yet.
Use the bundled `BigInt` library for exact integers beyond a machine word.

Comparisons use `=?`, `<?`, `>?`, `<=?` and `>=?`. Boolean expressions use `and`,
`or` and `not`. Literal coefficients such as `2x` and `2(x+1)` multiply; use `*`
for general multiplication. A semicolon discards an expression's result.

`^` raises a value to a power and associates right: `2^3^2` is `2^(3^2)`.
It binds above multiplication, literal coefficients and unary minus, so `2x^2`
is `2*(x^2)` and `-2^2` is `-(2^2)`. Use `xor` for bitwise exclusive-or.
Machine-integer powers use a nonnegative `int64` exponent and wrap at 64 bits,
like repeated fixed-width multiplication; negative exponents panic with guidance
to use an explicit rational or floating base. Float powers use the inherited
floating math library. `BigInt` powers remain exact for nonnegative exponents;
`Rational` supports signed exponents. All these types define zero to the zero
power as one. `^=` is not implemented yet.

## Exact large integers

```dewy
from bigint import BigInt, bigint, parse_bigint
main=():>void=>{
    let value=bigint("123456789012345678901234567890")
    printl"{value*value}"
    printl"{bigint(2)^256}"
    let parts=(-value).divmod(bigint(7))
    printl"{parts.quotient} {parts.remainder}"
}
```

`bigint` constructs from `int64`, `uint64` or signed decimal text. `parse_bigint`
returns `BigInt|none` for text that may be invalid; the constructor panics on
invalid text. Parsing is strict: an optional leading `+`/`-` and ASCII decimal
digits, with no whitespace or separators. Leading zeros are accepted.

`BigInt` supports `+`, `-`, `*`, unary `-`, comparisons, `//` and `%`, including
mixed signed/unsigned machine-word operands in either order. Division rounds
down and the remainder has the divisor's sign. `.divmod(other)` computes both
results together. Parenthesize a negative numerator as `(-value)//other`:
Dewy's unary minus binds below multiplication and division.

`^` (also `.pow(nonnegative_exponent)`), `.abs()` and `.gcd(other)` operate exactly;
`gcd(0, 0)` is zero and `0.pow(0)` is one. Division by zero and negative powers
panic. `.to_int64()` and `.to_uint64()` return an optional word, never silently
truncate. Interpolation formats decimal text. Values are independent copies and
can be dictionary keys; construct them through `bigint`, keeping `_sign` and
`_limbs` as internal representation details.

This is an explicit library type. Ordinary fixed-width arithmetic does not
automatically widen. Oversized numeric literals, automatic rational promotion and
bigint bitwise operations are not yet implemented. The inherited
`big` module is a separate approximate-number library for idle games.
[The exact-integer example](../examples/sloppy_core/exact_integers.dewy) computes
100!, a binomial coefficient and signed long division.

## Exact fractions

```dewy
from rational import Rational, rational, parse_rational
main=():>void=>{
    let half=rational(1 2)
    printl"{half+rational(1 3)}"  # 5/6
    printl"{rational(2 3)^(-3)}"  # 27/8
    printl"{rational("-7/3").floor()}"  # -3
}
```

`rational(numerator denominator)` accepts machine integers, `BigInt` values, or
decimal integer text for its parts; the denominator defaults to one. A single string accepts an integer or `numerator/denominator`.
`parse_rational(text)` returns `Rational|none` for invalid input, including a zero
denominator. Decimal points and whitespace inside the string are not accepted.

Values keep a positive denominator and coprime `BigInt` parts. Zero is `0/1`.
The constructor normalizes signs and common factors. Use it to construct values;
read `.numerator` and `.denominator` without assigning noncanonical parts directly.
`Rational[]` defaults to zero. Interpolation prints an integer when the denominator
is one, otherwise `numerator/denominator`.

Arithmetic `+`, `-`, `*`, `/`, comparisons, and unary minus work with fractions,
`BigInt`, and signed/unsigned machine words in either order. `//` returns a
`BigInt` floor quotient; `%` returns a `Rational` remainder with the divisor's
sign. `.divmod(other)` returns both. `.floor()` and `.ceil()` return `BigInt`;
`.abs()`, `.reciprocal()` and `.pow(signed_exponent)` return fractions. Division
by zero, a zero denominator and negative powers of zero panic. Zero to the zeroth
power is one. Copies are independent, and normalized values can be dictionary
keys. Floating conversion and automatic promotion of built-in integer `/` are
not yet supplied.

[The exact-fraction example](../examples/sloppy_core/exact_rationals.dewy) computes
harmonic sums, dice probabilities and exact time steps.

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
need defaults. Inline fields may also refer to a generic function's type parameters.

Declare type parameters before a function's parameters or a record's fields:

```dewy
first=<T>(items:array<T>):>T|none=>if items.length >? 0 items[0] else none
Box:type=<T>[value:T]
Values:type=<T>(array<T>)
main=()=>{
    let words:Values<string>=["hello" "world"]
    let box=Box<string>["Dewy"]
    printl(first(words))
    printl(box.value)
}
```

Calls normally infer the type arguments; `first<string>(words)` supplies them
explicitly. Type applications nest, as in `Pool<Box<int64>>`, and work on imported
names such as `models.Box<string>`. Generic type aliases wrap their definition in
parentheses. Each concrete function/type is specialized by the compact compiler;
this adds no universal boxed-value representation. Defaults can use the bound
type parameters, and generic functions can return closures or structural records.

This slice accepts plain type parameter names. Constraints such as `T of Bound`
and explicitly generic local closures remain unsupported. To pass a generic
function as a value, provide its expected callable type; explicit type arguments
currently apply to calls and type construction.

Custom records can define arithmetic and indexing with ordinary functions:

```dewy
Point:type=[x:int64 y:int64]
__add__=(a:Point b:Point):>Point=>Point[a.x+b.x a.y+b.y]

Store:type=<T>[values:array<T>]
__index__=<T>(store:Store<T> index:int64):>T=>store.values[index]
__setindex__=<T>(@store:Store<T> index:int64 value:T):>void=>{
    store.values[index]=value
}
```

`a+b` uses `__add__`; `store[i]` uses `__index__`; indexed assignment uses
`__setindex__`. The setter is the compact core's mutation counterpart to the
index getter. These are normal generic functions, and explicit calls still work.
Operators find declarations in either operand's defining module, so importing a
record type is sufficient. Built-in scalar operations keep their built-in behavior.

| Operation | Record protocol |
| --- | --- |
| `+`, binary `-`, `*`, `/` | `__add__`, `__sub__`, `__mul__`, `__truediv__` |
| `//`, `%` | `__floordiv__`, `__mod__` |
| `^` | `__pow__` |
| unary `-` | `__unary_sub__` |
| `=?`, `not=?` | `__eq__`, `__ne__` |
| `<?`, `<=?`, `>?`, `>=?` | `__lt__`, `__le__`, `__gt__`, `__ge__` |
| `<<`, `>>`, `xor` | `__lshift__`, `__rshift__`, `__xor__` |

Comparisons must return `bool`. When absent, `not=?` derives from `__eq__`,
and `<=?`, `>?`, `>=?` derive from `__lt__`. Derived comparisons preserve written
operand evaluation order. Arithmetic compound assignments reuse the corresponding
operator. Floor protocols receive the written divisor, including literal powers
of two; the built-in shift/mask optimizations do not change custom operands.
Logical `and`/`or`/`not` do not yet have custom record protocols. Power uses
`__pow__` and keeps bitwise `xor`/`__xor__` separate.

[The bounded history example](../examples/sloppy_core/history.dewy) uses a
[generic ring buffer written entirely in Dewy](../examples/sloppy_core/ring.dewy),
including operator discovery through an imported type, nested edits and independent
rewind snapshots. A full ring replaces its oldest entry without shifting elements.

The bundled `Pool<T>` and `Heap<T>` are now available with ordinary Dewy type
annotations. A pool stores values under stable `Handle`s; removing an entry
invalidates its handle even when a later entry reuses the slot. A heap pops the
value with the lowest numeric priority. Both retain independent copies, like
arrays and dictionaries. [The entity-event example](../examples/sloppy_core/entities.dewy)
uses them together:

```sh
python3 -m tools.core run examples/sloppy_core/entities.dewy
```

Use `pool.has(handle)` or `pool.get(handle)` when an entity may have been removed.
`pool[handle].health -= damage` and `pool[handle].inventory[i].amount += 1`
update fields and nested collections. Custom indexed assignments read the selected
value, edit it, then write it back through the container’s setter. This also
composes through nested pools. Receiver indices and the custom key are evaluated
once and retained for writeback, even if the right side changes an index variable.
A selected import of a container type makes its indexing operators available.

Read/edit/writeback retains value semantics; it is not a zero-copy borrow. Updating
a managed collection inside a custom getter can copy that collection, as an
explicit read/edit/writeback would. For bulk pool iteration, use its `items` array
when stable-handle lookup is unnecessary.

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
`"é🙂".length` is 2. String loops stream from an independent input snapshot;
changing the source variable does not change the remaining input. They create
one independent string per visited grapheme, so `break` and `return` avoid
collecting or scanning the remaining text. `graphemes(text)` explicitly collects
all graphemes into an array. Foreign malformed UTF-8 panics when examined,
including the lookahead needed to find a boundary; an unvisited tail is not
validated. Interpolation uses `{expression}` inside a string.
Single or double quotes support escapes and interpolation. Unicode escapes use
four hexadecimal digits (`"\u00E9"`) or one to six inside braces
(`"\u{1F642}"`); both name Unicode scalar values. Surrogates and values above
`10FFFF` are errors. Braced escapes currently accept hex literals, not expressions.

Prefix a string with `r` to keep backslashes and braces literally. Three matching
quotes allow embedded single quotes and multiline text; whitespace is preserved,
including leading/trailing newlines. Raw triple-quoted strings combine both:

```dewy
let path = r"assets\textures\{name}.png"
let caption = """He said "go".
Next frame: {42}"""
let pattern = r'''\w+\{item\}'''
printl(caption)
```

Standard escapes include `\n`, `\r`, `\t`, `\0`, `\a`, `\b`, `\v`, `\f`,
backslash, quotes and braces. A backslash immediately followed by a newline
continues the string without that newline. Interpolations can contain nested
strings, blocks and line comments.

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

Membership uses `in?`; negate it with `not in?` or `notin?`:

```dewy
let names=["apple" "pear"]
let counts=["apple"->3 "pear"->5]
printl("pear" in? names)
printl("apple" in? counts)
printl("fé" in? "café")
printl(42 in? [0..100))
```

Arrays compare elements, dictionaries check keys, and strings check substrings.
Integer range literals use bound comparisons without building an array; `[a..b]`
includes the end, `[a..b)` excludes it, and either endpoint can be omitted. The
needle and then the container evaluate once in source order. For a range, both
specified endpoints evaluate once after the needle, even if the lower-bound
comparison is false. Stepped and stored range membership are not implemented.
Custom containers can provide a `contains(container, needle):>bool` overload;
a callable field named `contains` is not used by membership.

## Modules and games

```dewy
import physics
import p"model.dewy" as model
from p"helpers.dewy" import advance, fresh
```

Bare names search beside the importing file, then the bundled library folders;
`p"..."` names a file explicitly. Within each folder, a Dewy importer prefers
`.dewy` and falls back to `.jo`; a Jo importer prefers `.jo`. The importing file
itself is skipped, so `physics.dewy` can import the bundled `physics` library.
Watch mode notices creation/removal of a preferred local module and reloads it.
Use `import p"@lib/physics.jo" as physics` to select a bundled library explicitly,
even when a neighboring file has the same name. `@lib/` resolves inside the
active toolchain's library directory and also works with selected imports.

Start a game with the built-in template, then edit it while it runs:

```sh
/tmp/dewy-core/bin/dewy-core new /tmp/my-dewy-game
/tmp/dewy-core/bin/dewy-core watch /tmp/my-dewy-game/main.dewy
/tmp/dewy-core/bin/dewy-core build /tmp/my-dewy-game/main.dewy --target wasm -o /tmp/game
```

The web build produces `/tmp/game.html`. Games use `main()` for setup,
`update(dt:float64)` each frame, and `draw()` for rendering. The
[paddle game, physics playground and 3D forest](../examples/sloppy_core/README.md) show
input, 2D/3D drawing, simulation, module boundaries and live reload. Graphics, fonts,
audio, physics and other platform libraries come with the toolchain.

This remains a developing subset of Dewy. The earlier proof/effect system,
automatic numeric widening, general structural conversions and every historical
juxtaposition form have not been recreated. See the
[implementation notes](../tools/sloppy_core/README.md) for current boundaries,
validation and measured performance.

An executable’s `main` returns `void` or an integer exit code. Other result types
are diagnosed rather than passed to the native/web entry wrapper.
