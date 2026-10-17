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
Development builds are the default and apply one local optimization pass per
function. `--release` adds cross-function inlining and further loop optimization.
Use `-g` without `--release` for native variable debugging; it preserves local
variable locations instead of running the default local optimization pass.

Native game reload keeps unrelated live state. Changed assets refresh globals
initialized from them, including through direct helper calls across modules.
Closures keep their captured state when assets used by their bodies change.
Dependency discovery cannot follow arbitrary calls through function values yet.

The [VS Code extension](../dewy/vscode-dewy/README.md) supports unsaved diagnostics,
completions, hover, definitions and Format Document. Set `dewy.core.path` to the compiler executable.

`python3 -m tools.core fmt file.dewy` formats declarations and indentation in
place. Add `--check` to report needed changes without writing, or pass a directory
to format its source files. `fmt -` reads Dewy from stdin and writes to stdout.
Formatting uses four spaces per nesting level and preserves line breaks, comments,
string contents and meaningful spacing such as `2x`, `f(x)` and `[1 -2 3]`.
Ordinary arithmetic spacing stays as written; invalid literals and unbalanced
delimiters leave the file unchanged with an error.

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

Array literals can spread other arrays: `[head... item tail...]`. Operands run
once, from left to right, and each spread appends its current elements before
the next operand runs. The result has independent value semantics, including
nested arrays and record fields. Expected array types flow into the literal,
so `let values:array<uint16>=[[]... 42]` works. Set spreading and spread call
arguments are not supported.

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
reads allocate the selected result. Contiguous slices accept the same assignments:
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
`set[values...]` also work. `push` adds a member; `add` returns whether it was
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
Bounded signed-word stepped ranges also work in combined headers. Open-ended
stepped ranges currently require a single header; stepped slicing is not implemented.

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

Dunes also defines vertex and fragment shaders as ordinary Dewy functions, with
typed input/output records and texture uniforms. The compiler generates GPU
shader code and the software renderer can execute the same shader functions.
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

This remains a developing subset of Dewy. The earlier proof/effect system,
automatic growth of machine integers on overflow, general structural conversions and every historical
juxtaposition form have not been recreated. See the
[implementation notes](../tools/sloppy_core/README.md) for current boundaries,
validation and measured performance.

An executable’s `main` returns `void` or an integer exit code. Other result types
are diagnosed rather than passed to the native/web entry wrapper.
