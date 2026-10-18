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
Spread last: 44
Record fields: 42
Record override: 42
Dependent default: 42
Specialized callback: 42
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
emitting an executable. `build --time` reports compiler phase timings.
Development builds are the default. Ordinary builds expand tiny functions that
call no other functions, then apply one local optimization pass per function.
`watch` and the interactive prompt retain calls so definitions can be replaced.
`--release` adds broader inlining and further loop optimization.
Use `-g` without `--release` for native variable debugging; it preserves local
variable locations instead of running the default local optimization pass.

`dewy-core new coin-race online` creates a playable two-player game in
`coin-race/coin-race.dewy`, with practice mode, rollback networking and invite
screens. The online template derives a safe source filename from the directory
name; keep it the same for native and web builds because it names saved data and
rooms. Other templates use `main.dewy`. Run `dewy-core watch coin-race/coin-race.dewy`
to start editing. Its generated README explains web links and the optional
matchmaking service; no public server is configured by default.

Native game reload keeps unrelated live state. Changed assets refresh globals
initialized from them, including through direct helper calls across modules.
Closures keep their captured state when assets used by their bodies change.
Dependency discovery cannot follow arbitrary calls through function values yet.

The [VS Code extension](../dewy/vscode-dewy/README.md) supports unsaved diagnostics,
completions, hover, definitions and Format Document. Set `dewy.core.path` to a
standalone compiler executable, or to the checkout's absolute `tools/dewy` path.
With the development launcher, restarting the language server picks up compiler
source changes without changing the editor setting.

`python3 -m tools.core fmt file.dewy` formats declarations and indentation in
place. Add `--check` to report needed changes without writing, or pass a directory
to format its source files. `fmt -` reads Dewy from stdin and writes to stdout.
Formatting uses four spaces per nesting level and preserves line breaks, comments,
string contents and meaningful spacing such as `2x`, `f(x)` and `[1 -2 3]`.
Ordinary arithmetic spacing stays as written; invalid literals and unbalanced
delimiters leave the file unchanged with an error.

### Interactive prompt

Run `python3 -m tools.core repl`, `tools/dewy repl`, or `dewy-core repl` to try
Dewy without creating a source file:

```text
>>> let score=20
>>> twice=(x)=>2x
>>> twice(score)+2
42
>>> score=21
>>> twice(score)
42
>>> :type score
int64
```

Variables, functions, types and imports persist for the session. Braces, brackets,
and quoted text may span input lines; the final expression's value is displayed.
`:type expression` checks its type without running it. `:help` lists commands,
`:quit` or Ctrl-D exits, and Ctrl-C cancels an input or interrupts running code.
Tab completes names; the arrow keys recall previous lines.

Assignment updates an existing binding. An explicit `let` redeclaration creates
a new binding; functions already defined retain the bindings they captured.
Compile errors, panics and interrupted inputs restore both session values and
new declarations. External effects such as printed output and file writes
remain. Imported modules initialize once, in dependency order.

Terminal history lives in `~/.dewy_history`. `DEWY_REPL_HISTORY` selects another
file; an empty value disables history persistence. The prompt is currently
validated on the Linux compiler host.

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

Parameters can unpack a single argument with the same patterns as `let` and
`loop`: arrays and tuple results use positions, records use field names, and
nested patterns can combine them.

```dewy
sum=([left right]:array<int64>)=>left+right
score=([damage armor]:[damage:int64 armor:int64])=>damage-armor
make_adder=(bias:int64)=>(([a b]:array<int64>)=>a+b+bias)
main=()=>sum([20 22])
```

The whole parameter can have a type or default, such as `([a b]=[20 22])`.
Untyped patterns infer the argument type, including when used as callbacks.
The argument evaluates once; array lengths are checked on entry and extracted
values remain independent of the caller. `_` discards array or tuple elements;
for records, leave unwanted fields out. Pattern bindings belong to the body,
so defaults on later parameters cannot refer to them. Pass the whole argument
positionally; other named parameters still work. Pattern names must be distinct
across the signature. Mutable `@` patterns and annotations on individual pattern
leaves are not supported; use a named parameter for those cases.

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
value semantics. Release builds can avoid a redundant entry copy when a
parameter is only read; this needs no annotation and preserves independent
values. Use `@` in both a parameter and its call to change the caller:

```dewy
bump=(@value:int64):>void=>{value+=1}
main=()=>{let value:int64=41 bump(@value) return value}
```

References can name a field or array element: `bump(@point.x)`,
`bump(@values[i])` or `bump(@points[i].x)`. An index expression evaluates once;
other copies of the record or array retain their independent values.

Integer types are `int8` through `int64` and `uint8` through `uint64`; floating
types are `float32` and `float64`. Ordinary integer literals default to `int64`
when they fit. Use `as` or a type call such as `uint8(value)` for numeric value
conversion. Integer types expose typed `.min` and `.max` constants, including
the full `uint64` range; these also work through type aliases and generic type
parameters. For example, `uint8.max` is 255 and `int64.min` is −9223372036854775808.
`string(value)` formats a value as text. Integer `//` is floor
division and `%` gives a remainder with the divisor’s sign (or zero). These
operators support signed `int64` and unsigned `uint64`, preserving the full
unsigned range; narrower operands retain the existing integer widening rules.
Integer `/` produces an exact fraction; `/` with a floating operand uses floating math.
Literals beyond a machine word automatically use the bundled exact `BigInt` type.

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
power as one.

Compound updates `//=`, `%=`, `/=` and `^=` use the same operations as their
ordinary forms. The destination keeps its type; fixed-width integer results wrap
back to that width. `let x=7; x//=2` stores `3`, while `let x=7/1; x/=2` stores
`7/2`. Integer `/=` cannot store a fraction in an integer variable: use `//=`
or start with a fractional value. Arrays, record fields, dictionary entries and
custom indexed values support these updates; indices evaluate once, before the
old value and right operand. Existing copies retain their independent values.

## Exact large integers

```dewy
from bigint import BigInt, bigint, parse_bigint
main=():>void=>{
    let value=123456789012345678901234567890
    printl"{value*value}"
    printl"{bigint(2)^256}"
    let parts=(-value).divmod(bigint(7))
    printl"{parts.quotient} {parts.remainder}"
}
```

Integer literals outside `int64`/`uint64` become `BigInt` values without an
explicit import. Decimal and all supported based literals work, including digit
separators. Their digits are converted at compilation, not parsed at runtime.
Small literals also adopt an expected `BigInt` type, for example
`let value:BigInt=42`, typed arguments, record fields and arrays. Import `BigInt`
when naming its type. Mixed arrays such as `[1 123456789012345678901234567890]`
infer `array<BigInt>`; ordinary word-only arrays keep their word element type.

`bigint` constructs from `int64`, `uint64`, `BigInt` or signed decimal text. `parse_bigint`
returns `BigInt|none` for text that may be invalid; the constructor panics on
invalid text. Parsing is strict: an optional leading `+`/`-` and ASCII decimal
digits, with no whitespace or separators. Leading zeros are accepted.

`BigInt` supports `+`, `-`, `*`, unary `-`, comparisons, `//` and `%`, including
mixed signed/unsigned machine-word operands in either order. Division rounds
down and the remainder has the divisor's sign. `.divmod(other)` computes both
results together. Parenthesize a negative numerator as `(-value)//other`:
Dewy's unary minus binds below multiplication and division.

`and`, `or`, `xor` and `not` operate on bits with infinite two's-complement sign
extension, including mixed signed/unsigned machine words. Thus `not bigint(0)`
is `-1`. `<<` and `>>` take a nonnegative `int64` count; right shift rounds down
for negative values, so `bigint(-3) >> 1` is `-2`. Shifting beyond all magnitude
bits yields `0` for nonnegative values or `-1` for negative ones. Negative shift
counts panic. Shift compound assignments (`<<=`, `>>=`) work too.

`^` (also `.pow(nonnegative_exponent)`), `.abs()` and `.gcd(other)` operate exactly;
`gcd(0, 0)` is zero and `0.pow(0)` is one. Division by zero and negative powers
panic. `.to_int64()` and `.to_uint64()` return an optional word, never silently
truncate. `.to_float32()` and `.to_float64()` round to the nearest floating
value, with ties to even; overflow produces signed infinity. Interpolation
formats decimal text. Values are independent copies and
can be dictionary keys; construct them through numeric literals or `bigint`, keeping `_sign` and
`_limbs` as internal representation details.

Ordinary fixed-width arithmetic does not automatically widen on overflow.
Convert a word variable with `bigint(word)` when exact arithmetic is needed.
The inherited `big` module is a separate approximate-number library for idle games.
[The exact-integer example](../examples/sloppy_core/exact_integers.dewy) computes
100!, a binomial coefficient and signed long division.

## Exact fractions

```dewy
from rational import Rational, rational, parse_rational
main=():>void=>{
    let half=1/2
    printl"{half+1/3}"  # 5/6
    printl"{(2/3)^(-3)}"  # 27/8
    printl"{rational("-7/3").floor()}"  # -3
}
```

Dividing two machine integers or `BigInt` values with `/` constructs a `Rational`
without an explicit import. This includes mixed signed/unsigned words, and the
full-width values are preserved. `4/2` is still a fraction value, formatted as
`2`. Use `//` for a whole-number quotient. Floating operands retain floating
division, so `1.0/2` is `float64`; a floating annotation alone does not convert
the exact result of `1/2`. Fraction support is loaded only when needed after
operand types are known. Import `Rational` when naming its type.

`rational(numerator denominator)` accepts machine integers, `BigInt` values, or
decimal integer text for its parts; the denominator defaults to one. A single string accepts an integer or `numerator/denominator`.
`parse_rational(text)` returns `Rational|none` for invalid input, including a zero
denominator. Decimal points and whitespace inside the string are not accepted.

Values keep a positive denominator and coprime `BigInt` parts. Zero is `0/1`.
Division and the constructor normalize signs and common factors. Use them to construct values;
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
keys.

`.to_float32()` and `.to_float64()` round the exact ratio once, to nearest with
ties to even. They handle very large parts without first rounding the numerator
and denominator separately. Overflow produces signed infinity; underflow can
produce signed zero. Conversion is explicit, for example when passing an exact
time step to a vector or rendering API:

```dewy
let step=(1/60).to_float32()
let movement=vec2(step 2.0*step)
```

Floating values cannot yet be converted back to `Rational` directly.

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
Generic constructors infer collection and record literals too: `Box([20 22])`
holds an integer array, and `Box([x=20 y=22])` holds an anonymous record. Other
fields can supply context for an empty collection or a callback's parameters.
Within a function, later writes can settle an initially empty container's element
type: `let box=Box([]); box.value.push(42)`. An empty container with no evidence
for its element type still needs an annotation, such as `Box<array<int64>>[[]]`.
Aliases also work as type values: a record alias can construct `Alias[42]`,
and an integer alias exposes `.min` and `.max`. The editor completes these
bounds and shows their integer type on hover; `end` inside brackets hovers as
`int64`.

Generic functions can also be specialized as values: `let convert=identity<int64>`
stores a callable, including functions imported from Dewy or core modules.
Passing `identity<int64>` directly as a callback works too. If several overloads
remain after specialization, give the value a callable type to select one.
Without explicit type arguments, an expected callable type can infer them.

This slice accepts plain type parameter names. Constraints such as `T of Bound`
and explicitly generic local closures remain unsupported.

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
| `and`, `or`, `not` | `__and__`, `__or__`, `__not__` |

Comparisons must return `bool`. When absent, `not=?` derives from `__eq__`,
and `<=?`, `>?`, `>=?` derive from `__lt__`. Derived comparisons preserve written
operand evaluation order. Arithmetic compound assignments reuse the corresponding
operator. Floor protocols receive the written divisor, including literal powers
of two; the built-in shift/mask optimizations do not change custom operands.
Record `and`/`or` operators are ordinary eager calls: both operands evaluate once
in written order. Built-in boolean `and`/`or` retain short-circuit evaluation;
machine integers use bit operations. Power uses `__pow__` and keeps bitwise
`xor`/`__xor__` separate.

Dictionary and set keys can define `hash` alongside their record type:

```dewy
Key:type=[id:int64 label:string]
__eq__=(a:Key b:Key):>bool=>a.id =? b.id
hash=(key:Key):>uint64=>(key.id as uint64).hash()
```

Equal keys must return the same hash; here both operations use `id` and ignore
`label`. Importing the type is enough for collection operations to find its hash
function, including generic keys. Ordinary keys without a custom hash use the
library's default hashing.

Equality and hashing defined in a named record's own module also apply when the
record is nested inside an array, another record, an optional or a union. Thus
`[Key[7 "first"]]=?[Key[7 "other"]]` is true with the definitions above, and the
two arrays hash alike. An outer record's own protocol takes precedence over
comparing or hashing its fields. Without a custom operation, that operation
continues to use the fields. A callback can change global state; the value being
compared or hashed stays independent throughout the operation.
Only the operation being used is instantiated: a generic record can be compared
even when its hash function does not support that particular payload type.

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

Custom read/edit/writeback retains value semantics and can copy a managed
collection. The bundled `Pool` has a faster path for scalar field/element writes
whose indices and right side are ordinary reads or scalar arithmetic/boolean
expressions, such as `pool[handle].inventory[slot+1] += damage*multiplier`.
It updates the stored item directly,
validating the handle and retaining array bounds and copy-on-write checks.
Snapshots remain independent. Calls, overloaded operators and custom indexers
keep read/edit/writeback; for a function result, calculating `let damage=...`
before the assignment makes the simple update available. For bulk iteration,
use `pool.items` when stable
handle lookup is unnecessary.

Arrays and records retain independent values when copied, including nested
managed fields. Arrays support indexing, `.length`, and methods such as
`.push(value)`, `.pop()`, `.clear()` and `.truncate(count)`. `xs[1..3)` is an
exclusive-end slice; `xs[1..2]` includes index 2.

Use `array<T length=N>` for a known, positive compile-time length:

```dewy
const WIDTH:int64=2
Pair:type=<T>(array<T length=WIDTH>)
let position:Pair<float64>=[10 20]
let copy=position
copy[0]=30
let [x y]=position
```

These arrays store their elements inline, including inside records and dictionary
values. Copies are independent; nested strings and growable arrays retain their
copy-on-write behavior. Indexing, `.length`, loops, equality and positional
unpacking work as usual. Fixed arrays cannot grow or shrink. The length can use
integer constants and constant arithmetic; zero-length inline arrays are not
currently supported.
In a fixed-array context, `[]` initializes every element to its zero value;
otherwise a literal must supply exactly the declared number of elements.

An ordinary `array<T>` remains growable. Assigning or passing one to a fixed-array
value checks its exact length at runtime and copies the elements. An empty
growable array therefore fails that check. Converting back creates a growable array.
Both conversions require the same element type and also support `as` casts.
Mutable arguments require the exact array type, so conversion cannot silently
redirect a mutation into a temporary copy.

Inline arrays also support read slices (`pair[..]`, `pair[1..]`), stepped
selections, index lists, masks and stored ranges. Their results are growable
arrays with independent values. Selection reads the inline storage directly
without first converting the entire source to a growable array. Bounds evaluate
after capturing the source value, so changing the source in a bound expression
does not change the value being selected.

Index lists and boolean masks can themselves be growable or inline arrays;
selection reads either directly. A bare `values[[]]` selects no elements.

The same selections support updates: `pair[..]=0`, `pair[0..1]=[20 22]`,
`values[0,2..]=42`, `values[indexes]=replacements` and `values[mask]=0`.
A scalar fills the selected elements; an array supplies exactly one replacement
per selected element. Updates preserve the fixed length and independent copies,
including nested managed values and overlapping source/destination selections.
They also work inside record fields, dictionaries and custom containers such as
`Pool`. As with ordinary arrays, compound assignment to a selection needs an
explicit loop.
Spreading inline arrays into ordinary arrays works, and a spread literal can
initialize a fixed array with a runtime length check: `let pair:Pair<int64>=[xs...]`.

Array literals can spread arrays and sets: `[head... item tail...]`. Operands run
once, from left to right, and each spread appends its current elements before
the next operand runs. The result has independent value semantics, including
nested arrays and record fields. Expected array types flow into the literal,
so `let values:array<uint16>=[[]... set[]... 42]` works. Sets contribute their
members in insertion order, skipping removed members. Arrays also accept sets
in `.extend(values)`. Spread call arguments are not supported.

Records compose similarly: `let tuned:Settings=[defaults... speed=12]`.
Later fields or record spreads replace earlier fields with the same name.
Every operand still runs once in source order, including overwritten values;
changes made by a later operand do not change an earlier captured record.
`[left... right...]` can combine records without any individually written fields.
The literal can infer an anonymous record shape, or take a named record type
from an annotation, function parameter, or return type, as other record literals do.

Inside an index or slice, `end` is the receiver's last index: `xs[end]`,
`xs[end-2..end]` and `xs[end,end-2..0]`. Nested brackets use their own receiver.
The receiver and its last index are evaluated once before the index expression;
strings count grapheme clusters. These forms also support array and custom
container updates. Ordinary array updates capture indices before the right-hand
side, then locate the destination again if that side resizes the array.

Array literals take their element type from a function parameter, including
nested arrays and optional array parameters. For example,
`sum_words=(xs:array<uint64>)=>xs[0]+xs[1]` accepts `sum_words([20 22])` without
element casts. Overloads compare element conversions and prefer the usual
integer or floating literal type when it fits. A literal outside a parameter's
element range is rejected. An already constructed array keeps its element type;
passing an `array<int64>` variable does not convert it to `array<uint64>`.

Equality and inequality also give an array literal the element type of the
value being compared, on either side. For example, `let words:array<uint8>=[0 42]`
can be followed by `words =? [0 42]` or `[0 42] =? words`. This includes nested
arrays, optional arrays, exact integers and record elements. Out-of-range
literals still fail, and separately constructed arrays keep their own types.
Integer and boolean array equality recognizes shared storage immediately and
compares narrow elements a machine word at a time. Floating-point arrays retain
element comparisons (`NaN` is unequal to itself and signed zeros compare equal),
and record arrays still call their value protocols even when storage is shared.
Binary operands evaluate left to right; changing a value while evaluating
the right operand does not change the left value already read.

`let [a b] = xs` unpacks arrays or tuple results by position, with an exact array
length check. `_` discards an element. For records, targets select fields by
name, in any order. `[a b] = [b a]` swaps existing variables. Nested patterns
work in declarations and assignments:

```dewy
let [[left top] [right bottom]]=[[10 20] [90 80]]
[[left] [right]]=[[right] [left]]
let [[x] [y]]=[[x=20 y=1] [x=2 y=22]]
let [[team score] [_ other]]=["red"->20 "blue"->22]
```

Each level follows its source type: arrays and tuples use positions, dictionaries
yield key/value pairs in insertion order, and records use field names. Dictionary
unpacking skips removed entries and requires exactly as many live entries as
targets. `_` can discard an entry or either member of a pair. The source evaluates
once, nested lengths are checked before destinations are written, and extracted
values keep ordinary value semantics.
A one-element loop pattern still unpacks: `loop [x] in [[20] [22]]` visits
20 and 22, while `loop x in [[20] [22]]` visits the two arrays. Every bracket
level is significant: `loop [[x y]] in [[[20 22]]]` unpacks a nested array.
This corrects the earlier behavior that discarded the outer brackets of a
one-element loop pattern. The same rule applies in comprehensions and combined
loop headers.

Annotated targets and `const` unpacking are not implemented yet.

```dewy
let values=[loop i in [0..10) i*i]
let selected=[loop value in values if value >? 20 value]
let lengths=[loop word in ["café" "🙂"] word->word.length]
```

Arrays can select elements with a stored `IntRange` or a stepped slice:

```dewy
let values=[10 20 30 40 50 60]
let evens=values[0,2..]       # [10 30 50]
let backwards=values[5,3..0] # [60 40 20]
let positions=[1,3..5]
values[positions]=42        # fill selected elements
values[0,2..]=[1 2 3]       # one replacement per selected element
```

A missing endpoint extends to the array's end in the step's direction. `]`
includes a written endpoint and `)` excludes it. Empty selections return empty
arrays; every selected index must be in bounds, and replacement arrays must have
exactly the selected length. A scalar replacement fills each selected element.
These operations preserve independent copies, including overlapping assignments
such as `values[5,4..0]=values`. They allocate no intermediate array of indices;
materializing a slice allocates the selected result. Read-only loops over a
contiguous array slice can iterate the selected range without that allocation.
Bounds still evaluate once, from left to right, and are checked before the body.
When the body can modify the source, iteration keeps the ordinary slice copy.
Contiguous slices accept the same assignments:
`values[1..3]=[10 20 30]`, `values[1..3)=[10 20]`, or `values[..]=42`.
These assignments retain the array's length. Compound updates of selections and
stepped string slicing are not implemented.

Comprehensions are eager. Nested loops and block bodies work; a final block value
is collected, while `break`, `continue` and assignment statements do not emit a
value. `key -> value` creates dictionary entries; duplicate keys take the last
value. A dictionary can also be written directly as `["a"->20 "b"->22]`.

`values.insert_if_absent(key value)` adds an entry only when the key is missing
and returns whether it was added. An existing value and its iteration position
stay unchanged. This combines the lookup and insertion, useful for graph visits,
deduplication and registering entities:

```dewy
let visited:dict<int64 int64>=[]
let queue:array<int64>=[]
if visited.insert_if_absent(7 1) {queue.push(7)}
```

Both arguments evaluate once, in order, even if the key already exists; the value
argument is not lazy. Copies of the dictionary and inserted values remain
independent. `values.reserve(count)` reserves capacity for a known entry count
without adding entries or changing their order; arrays have `reserve` too.

When `values.get(key)` is immediately tested against `none`, the compiler uses
a presence lookup without constructing the optional value. `is?`, `isnt?`,
`=?` and `not=?` keep their usual meaning, argument order and custom key callbacks.
Calls that use the returned value or supply a default still retrieve it.

For a dictionary whose values are optional, `get` adds an outer optional: a
missing key returns outer `none`, while a present key can hold inner `none`.
After checking the lookup result, bind its payload to check the stored value:

```dewy
let settings:dict<string int64?>=["limit"->none]
let found=settings.get("limit")
if found isnt? none {
    let limit=found
    if limit is? none printl("limit is present but unset")
}
```

This also works for generic functions returning `T?` when `T` is optional.
A bare `none` means the outer optional is absent; wrapping an already-typed
optional value preserves it as a present payload.

`values.keys()` and `values.values()` return arrays in insertion order, skipping
removed entries. The arrays retain independent values: editing a returned array
or one of its nested elements does not change the dictionary, and later dictionary
edits do not change an earlier result.

Dictionary loops and unpacking retain an insertion-ordered snapshot of the live
keys and values. Changing the source dictionary while iterating does not change
that input. With no removed entries, the snapshot shares the existing arrays;
after removals it collects only live keys and values, without copying or rebuilding
the dictionary's hash table. Combined and counted loops use the same ordering.

Dictionaries compare by their key/value associations, ignoring insertion order,
capacity and removed entries. This also holds when they are nested inside other
values. Their hashes follow the same rule, so dictionaries can be set members
or dictionary keys; changing a copy leaves an already-inserted key independent.

Sets retain distinct members in insertion order:

```dewy
let tags=set["visible" "moving" "visible"]
tags.push("selected")
if "moving" in? tags {printl"moving entity"}
let active=tags & set["visible" "selected"]
let names=[loop tag in active tag]
let [first second]=active
let visited:set<int64>=set[]
if visited.add(7) {printl"first visit"}
```

`set<T>` supplies the element type for an empty literal or narrower numeric
members. Function parameters provide the same context. `set[loop ...]` and
`set[values...]` also work, with arrays or sets as spread operands. For example,
`set[existing... "new"]` preserves the first occurrence of each member, and
`[existing...]` collects a set's members into an array. `push` adds a member;
`add` returns whether it was
new. Adding an existing member leaves its position unchanged. `remove(value)`
returns whether it removed a member, while `clear()` and `reserve(count)` work
like their dictionary counterparts. `.length`, `has`, `contains` and `is_empty`
inspect the set.

`a | b`, `a & b`, `a-b` and `a xor b` compute union, intersection, difference and
symmetric difference. Results keep surviving members from the left in order,
then any new members from the right. Equality and hashing ignore insertion
order, so sets can themselves be dictionary keys or set members. Copies remain
independent, including managed members and iteration snapshots. Counted/zipped
loops, comprehensions and unpacking use the same members and skip removed ones.

`pop(value)` removes and returns that member; `pop()` removes and returns a
member from a nonempty set. A missing member or empty set causes a checked
runtime failure. Use `pop(value default=none)` or `pop(default=none)` to receive
an optional value instead.

Repeated `pop()` calls use a retained tail cursor instead of collecting the set's
members each time. Arbitrary removals and internal compaction keep the cursor
valid, and copied sets retain independent cursor and member values.

`values.sorted()` returns an independent sorted array; `values.sort()` updates
the receiver. Use `sorted_by(key)` or `sort_by(key)` for records:

```dewy
Player:type=[name:string score:int64]
by_score=(p:Player)=>p.score
let players=[Player["Ada" 20] Player["Bea" 42] Player["Cal" 42]]
let leaderboard=players.sorted_by(by_score true)
```

The optional `true` requests descending order. Equal keys retain their original
order, so Bea stays ahead of Cal. The key is computed once per element when
sorting is needed, then cached while integer positions are sorted. Records and
their managed fields keep ordinary independent-value behavior; modifying a
record in `leaderboard` leaves `players` unchanged.

`values.sort_with(less)` takes a comparison function with two arguments for
orderings that depend on both values. It is stable too: values for which neither
argument compares less than the other retain their order. A comparator should
define a consistent ordering; use `sort_by` when a cached key expresses it.

`values.min_by(key)` and `values.max_by(key)` select one value without sorting.
They evaluate the key once per element and choose the first of equal keys.
The scan does not allocate a copy of the array tail, and the returned value
remains independent of the source. An empty input raises an error.

## Settings and JSON

`to_json(value)` writes a typed value directly to JSON. `from_json<T>(text)`
reads it into a type and returns either that value or a `TextError` with a message,
line and column. Record fields may arrive in any order; missing fields keep their
declared defaults and unknown fields are skipped:

```dewy
Settings:type=[player:uint64 volume:float64=0.5 fullscreen:bool=false]
main=()=>{
    let loaded=from_json<Settings>(r'{"player":18446744073709551615}')
    if loaded is? TextError {printl(loaded.message) return 1}
    let updated:Settings=[loaded... fullscreen=true]
    printl(to_json(updated 2))
    return 0
}
```

The optional second argument indents by that many spaces. Records become JSON
objects, arrays and tuples become arrays, dictionaries become objects with string
keys, and `none` becomes `null`. Typed writing preserves all signed and unsigned
integer values through 64 bits, plus round-tripping finite float representations
including negative zero. Readers in other languages must also support the number
range if they need to preserve large IDs exactly.

`parse_json(text)` and `json_value(value)` instead produce the dynamic `Json`
tree, whose numbers are `float64`; conversion to that tree can round large integers.
Use `from_json<T>` directly for typed settings or save data. Embedded `Json` values
write their JSON contents. The inherited non-finite float spellings (`NaN` and
`Infinity`) are also supported, though they are outside standard JSON.

See [the settings example](../examples/sloppy_core/settings.dewy) for defaults,
record updates and an exact large-ID round trip.

## Loops, text and optional values

Optional types use `T?`, including generic types such as `array<uint16>?`
and nested `array<array<uint16>?>?`. `none` represents an absent value.

Use `value ?? fallback` to unwrap an optional or provide a default. The left side
runs once; the fallback runs only when it is `none`. Zero, `false` and empty
collections are present values. Chains associate right, so
`first ?? second ?? default` picks the first present value. A final optional
fallback keeps the result optional. Arithmetic binds more tightly than `??`,
while comparisons and boolean operators bind less tightly:
`to_int(text) ?? 0 >? 10` compares the selected number with 10.

```dewy
let address = env("JOIN") ?? "localhost"
let port = to_int(env("PORT") ?? "47200") ?? 47200
```

The left operand must be optional; use `mapping.get(key) ?? fallback` for an
optional dictionary lookup. Direct indexing returns the stored element itself.

Loop bindings can unpack structured values, including nested groups:

```dewy
let scores=["red"->[20 22] "blue"->[4 8]]
loop [team [home away]] in scores {printl"{team}: {home+away}"}
loop [x y z] in [[1 2 3] [4 5 6]] {printl(x+y+z)}
```

With two bindings, dictionaries yield keys and values. Several bindings over an array unpack
each element by position for arrays/tuples or by field name for records. Nested
values follow the same declaration rules and keep independent value semantics.
A dictionary binder may be followed by `and` conditions, and `else` runs if its
body never enters. Nested groups also work in indexed-sequence `and` headers;
`or` headers yield optional values and do not support unpacking groups.

Dictionaries also work in counted and zipped headers:

```dewy
loop i in 0.. and team in scores {printl"{i}: {team}"}
loop [team [home away]] in scores and factor in [2 3] {
    printl"{team}: {(home+away)*factor}"
}
```

The counter is a position starting at zero, independent of dictionary keys.
Dictionary iteration follows insertion order, skips removed entries and retains
a snapshot of its input. Combined sources evaluate once in source order. An
`and` header stops at the shortest input; an `or` header keeps going until all
inputs finish, yielding `none` for exhausted inputs.

Records with `len(container)` and `__index__(container index)` work as finite
indexed sequences in loops and comprehensions. Length describes integer positions
from zero through `len(container)-1`. For example:

```dewy
Series:type=[first:int64 count:int64]
len=(s:Series)=>s.count
__index__=(s:Series index:int64)=>s.first+index
let values=[loop value in Series[40 3] value] # [40 41 42]
```

The source expression evaluates once and iteration retains its value; modifying
the original container leaves that input intact. Ordinary loops, counters,
combined `and`/`or` headers, destructuring, labels and fallback arms work with
these sequences. To edit the original container, use its indexed assignments.
The [Ring example](../examples/sloppy_core/ring.dewy) and
[history program](../examples/sloppy_core/history.dewy) use this interface across
module imports without a separate iterator allocation.

`loop condition { ... }` repeats while the condition holds. Ranges such as
`[0..10)` exclude the upper bound. Give the first two values for a stepped range:

```dewy
loop x in [0,16..width) {printl(x)}
loop y in [10,8..0] {printl(y)}
let odd_squares=[loop i in [1,3..10] i*i]
```

The step is the second value minus the first; it can ascend or descend but must
be nonzero. `]` includes the endpoint and `)` excludes it. Starting values and
the endpoint evaluate once in source order. Iteration uses counters without
building an intermediate array. Bounded integer loops terminate safely at the integer type's limits, including
an inclusive maximum endpoint. Open-ended ranges such as `[0..]` or `[1,3..]` panic if they exhaust their fixed-width
integer type; `break` and `continue` work normally.
Signed-word stepped ranges, including open-ended counters, also work in combined
headers: `loop i in [0,2..] and item in items { ... }`. A condition can bound the
counter, and comprehensions use the same forms. `or` headers expose optional
values as usual; the open counter continues after a finite partner ends, until
the body exits or another requested counter value would overflow. Combined
stepped counters use `int64`, as stored ranges do; single-header loops retain
their inferred integer width. Arrays support stepped slicing as described above;
strings support contiguous grapheme slices.

Store a bounded range to reuse it, pass it to functions or return it:

```dewy
evens = [0,2..100)
sum = (r:IntRange):>int64 => {
    let total:int64=0
    loop value in r {total+=value}
    return total
}
printl(sum(evens))
printl(42 in? evens)
```

`IntRange` is a small lazy value with signed `int64` endpoints. It captures its
bounds once, retains no array, and each loop gets an independent cursor. Copies,
arrays, record fields, `and`/`or` loops and membership work normally. Ordinary
loops keep their counters in scalar locals. A default-initialized `IntRange` is
empty. Even an interval covering the full signed-word domain takes constant
storage; use `break` to consume a prefix. Use a comprehension to materialize an
array when needed. Stored ranges currently require both endpoints; open ranges
remain available directly in loops and unit-range membership.

For bounded signed-word ranges, `(` excludes the first specified value:
`(0..3]` yields `1, 2, 3`, `(0..3)` yields `1, 2`, and `(0,3..10]` yields
`3, 6, 9`. This works in ordinary/combined loops, stored values and membership.
Excluding a single-element interval makes it empty, even at an integer limit.
An exclusive-first range also selects array elements: `values[(0..3]]` selects
indices 1, 2 and 3. Open-ended left-exclusive ranges are not implemented.

Combined headers walk supported iterables together:

```dewy
loop i in 0.. and character in "café 🙂" {
    printl"{i}: {character}"
}
```

`and` stops when an input ends or a condition fails. `or` keeps going until
all its inputs end; each exhausted input supplies `none`:

```dewy
loop left in [10 20] or right in [1 2 3] {
    if left isnt? none {printl(left)}
    if right isnt? none {printl(right)}
}
```

Inputs and range bounds are evaluated once, in source order. Conditions run
from left to right and can refer to earlier bindings. An `or` group accepts
iterator bindings; ordinary boolean `or` still works in a condition.

An `else` after a loop runs only if its body never enters:

```dewy
head_or=<T>(values:array<T> fallback:T):>T=>{
    loop value in values {return value}
    else {return fallback}
}
```

After any body iteration, including one that ends with `break` or `continue`,
the fallback is skipped. Conditions and iterator exhaustion both determine
whether the body enters. Chains can mix `if`, `loop`, `else if`, and `else loop`.
Each loop's bindings and label belong to that arm; they are unavailable in its
fallback. A comprehension can collect fallback elements for an empty loop.
Loops themselves remain statements; use `return` or a comprehension for values.

Place `$name` before a loop to target it from nested loops:

```dewy
$rows
loop row in [0..height) {
    loop column in [0..width) {
        if skip_row(row) {continue $rows}
        if finished(row, column) {break $rows}
    }
}
```

`continue $rows` advances that loop; `break $rows` exits it. Both release values
from the scopes they leave. Labels work with ordinary and combined headers,
stored ranges and strings. Active labels must be unique within a function;
a label can be reused after its loop ends. A closure cannot exit its caller's
loop. Unlabeled exits still target the nearest loop.

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

`format(value spec)` formats machine numbers or text, including inside an
interpolation. The specification is an ordinary string and may be computed:

```dewy
printl(format(3.14159 ".2f"))        # 3.14
printl(format(255 "#06x"))          # 0x00ff
printl(format(1234567 ","))         # 1,234,567
printl(format("θ" "^5"))           # two spaces on each side
let angle=12.25
printl("θ = {format(angle ".1f")}°")
```

The shape is `[[fill]align][+][#][0][width][,|_][.precision][type]`.
Alignment is `<`, `>` or `^`, with an optional ASCII fill character. Floating
formats are `f`, `e`/`E`, `g`/`G` and `%`; integer bases are `d`, `x`/`X`, `b`
and `o`. `#` adds a radix prefix; grouping applies to decimal formats. An omitted
type keeps ordinary value formatting, or fixed decimals when precision is given.
Decimal/radix integer formats retain every bit. Floating formats on integers
convert to `float64`; exact library numbers require an explicit `.to_float64()`
for this kind of formatting. Fixed decimal rounding uses ties to even.

Text takes alignment, fill and minimum width, optionally ending in `s`. Its
width counts grapheme clusters; it does not truncate. Use a string slice to
truncate explicitly. Invalid specs or options for the wrong value type panic.

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
Literal arms also work directly on unions:

```dewy
classify=(value:int64|string):>string=>match value {
    <0>=>"zero"
    <"quit">=>"exit"
    n:int64=>"number {n}"
    text:string=>text
}
```

An arm such as `text:"quit"=>text` binds the matched member's value; the original
variable or field is also narrowed inside that arm. Literals use the same member
type selection as assignment: with `int64|uint8`, `<42>` selects `int64`, while a
`uint8` value needs a `uint8` arm. A literal covers only its value, so other values
of that type still need an arm. `<true>` and `<false>` together cover `bool`.

A type arm can group a subset of the union's members. For a value of type
`int64|string|bool`, `part:int64|string=>...` binds an independent `int64|string`
value and narrows the original variable or field to the same subset. The remaining
`_` arm knows the value is `bool`. `<int64|string>=>...` performs the same test
without introducing a binding. Subset aliases and generic type parameters work
too. Arms run in source order, including when their subsets overlap.

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
comparison is false. Bounded signed-word stepped literals and stored `IntRange`
values check the stride as well as the bounds, without constructing an array.
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
[paddle game, physics playground, forest and Dunes](../examples/sloppy_core/README.md) show
input, 2D/3D drawing, simulation, module boundaries and live reload. Graphics, fonts,
audio, physics and other platform libraries come with the toolchain.

Landscape games show a turn-sideways hint on portrait browser displays whose
primary pointer is touch. The game continues underneath; rotating to landscape
removes the hint. Call `sideways_hint(false)` for a layout that supports either
orientation, using `visible_rect()` to position content in the available space.
Native windows and browser displays with a fine primary pointer show no hint.

`camera3d(position target up=direction)` rolls a 3D camera by changing its up
vector. Rendering, `world_to_screen`, `screen_ray`, particles and positional audio
use that orientation together; omitting `up` restores the usual world-up view.
The up vector should be nonzero and not parallel to the viewing direction.
The [camera-roll example](../examples/sloppy_core/camera_roll.dewy) combines this
with cursor picking and a settings menu. Menu rows expand for long labels and
choice values, sharing the widest row's width on the next frame.

`ui_slider(label value step=0.1 low=0.0 high=1.0)` supports ranges, keyboard
steps, and mouse/touch dragging. Once pressed, a slider keeps its drag until
release even outside its bounds; crossing another control does not transfer it.
`hud_slider(rect value low high step=0.0 label="")` places the same kind of
control directly in a HUD. A zero step gives continuous dragging, and descending
ranges work too. `ui_style=ui_light_style()` supplies a light-background theme.
The [pendulum example](../examples/sloppy_core/controls.dewy) combines these
controls with Greek letters, superscripts and mathematical symbols from the
bundled font, including `θ`, `π`, `√`, `≈`, `≤`, `∞`, `x₀` and `m/s²`.

`Chart` holds line, scatter, bar and histogram series. `draw_chart(chart rect)`
draws a live panel; `chart_image(chart width height)` makes an image without a
window, ready for `save_png(image path)`. Lines, points and bars accept arrays of
`int64`, `float32` or `float64`; both coordinate arrays use the same numeric type.
A line can omit its x array to use sample indices. For example:

```dewy
let chart=Chart[title="Measurements" equal_axes=true
    legend_at=LegendAt.bottom_left]
chart.line([0 1 2] [0 2 0] "trial" dash=6.0)
chart.annotate(1.0 2.0 "peak")
let picture=chart_image(chart 800 500)
save_png(picture "measurements.png")
```

`dash` measures pixels per dash and gap; zero draws a solid line, and positive
values below one use one pixel. The pattern continues through segment boundaries.
Annotations do not affect automatic bounds or appear in the legend. Series with
explicit colors and annotations leave the automatic color palette unchanged.
`LegendAt` selects any of the four plot corners. `equal_axes` expands automatic
upper bounds to give x and y units the same screen length; explicit upper bounds
can prevent that adjustment, and categorical bar charts ignore it. See the
[charts example](../examples/sloppy_core/charts.dewy).

`polyline(points thickness color closed=true)` joins the segments into one band,
including the closing edge. Consecutive repeated points are ignored and sharp
joins are capped to prevent long spikes. Open paths leave their ends flat.
`rect_rounded_outline` uses the same joins. See the
[outlines example](../examples/sloppy_core/outlines.dewy) for these shapes and a
dense plot that spans several drawing batches.

Dunes also defines vertex and fragment shaders as ordinary Dewy functions, with
typed input/output records and texture uniforms. The compiler generates GPU
shader code and the software renderer can execute the same shader functions.
The CPU fallback uses a smaller shadow map and four samples for built-in 3D
lighting; GPU lighting keeps nine samples. Custom shadow shaders should derive
texel spacing from the actual shadow texture size rather than a fixed resolution.
See [its model module](../examples/sloppy_core/dunes_model.dewy) for terrain,
animated meshes and custom sand/shadow and beacon shaders.
Native `watch` refreshes shaders after edits, including imported shader functions,
while preserving unrelated game state.

[`netpong.dewy`](../examples/sloppy_core/netpong.dewy) adds native/browser
multiplayer using `import net`. `net.listen(port)` hosts natively,
`net.connect(address port)` joins, `net.receive()` supplies joined/message/left
events, and `net.send(peer value)` sends strings or byte arrays. Browser builds
can connect to a native host or use direct invite codes through `import invite`.
See the [multiplayer run instructions](../examples/sloppy_core/README.md#multiplayer).
For short room codes and links, configure `invite.server(url)` and run the
bundled rendezvous server. The same invite screens exchange offers automatically;
`invite.arrivals()` supports additional lobby members. See
[short-code rooms](../examples/sloppy_core/README.md#short-code-rooms) for setup
and native/browser endpoint details. `net.listen(port largest=4096)` can bound
incoming message size for a small signaling service; ordinary games retain the
16 MiB default. Fragmented WebSocket messages retain their bytes across polls.

`import netplay` adds rollback sessions: each peer runs the game from ordinary
value snapshots, predicts remote input, then rewinds and replays when late input
differs. The tick callback must be deterministic for its state and inputs; keep
random seeds in the state and leave clocks and rendering outside that callback.
The compiler warns about known clock, unseeded random and live-input calls,
and writes to globals, in a directly supplied named or inline tick callback
and the user functions it calls. These warnings appear during `check` and native
or web builds. An `Rng` carried in the game state supplies reproducible random
numbers; `unix_time(date)` is a value conversion and does not trigger the clock
warning. This is an advisory scan, not a determinism guarantee: indirect function
values, external calls and captured state can still need care.

The [rollback lab](../examples/sloppy_core/rollback_lab.dewy) runs two peers on a
simulated link with adjustable latency, jitter and loss. Its
[model](../examples/sloppy_core/rollback_model.dewy) shows session construction,
`play`, outgoing packets and delivery using Dewy records and COW arrays.

This remains a developing subset of Dewy. The earlier proof/effect system,
automatic growth of machine integers on overflow, general structural conversions and every historical
juxtaposition form have not been recreated. See the
[implementation notes](../tools/sloppy_core/README.md) for current boundaries,
validation and measured performance.

An executable’s `main` returns `void` or an integer exit code. Other result types
are diagnosed rather than passed to the native/web entry wrapper.
