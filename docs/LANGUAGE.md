# Try the compact Dewy core

This guide covers the current compiler. Build it from
the repository root with Python, a C compiler and `make` on Linux x86-64:

```sh
python3 -m tools.compiler.build --bootstrap --output /tmp/dewy-core
/tmp/dewy-core/bin/dewy-core examples/tour.dewy
```

The build directory must be new. The toolchain is standalone and does not replace
an installed Dewy compiler. A clean bootstrap currently takes about 18 seconds
on the development machine.

The [executable tour](../examples/tour.dewy) prints:

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
examples/tour.dewy` runs the tour with the same cached toolchain.
The explicit `/tmp/dewy-core/bin/dewy-core` commands below also work with a
standalone build.

## Test a project

Declare tests at the top level alongside your code, or import the code into a
separate test file:

```dewy
add = (a: int64 b: int64) => a+b

test "adds numbers" {
    assert(add(20 22) =? 42)
}
```

```sh
./tools/dewy test examples/paddle_tests.dewy
./tools/dewy test --release examples/paddle_tests.dewy bounce
./tools/dewy test --watch examples/paddle_tests.dewy bounce
```

The standalone compiler accepts the same `test` command. It compiles the selected
file once and runs its test blocks in declaration order. Optional words after the
filename select test names containing any of those words. A failed test, no tests,
or no matching names produces a nonzero exit status. Names must be constant strings.
The VS Code extension also provides **Dewy: Test Current File**, a release variant,
and **Run test** code lenses above each test. These save open files and show results in a
task terminal; the editor's task commands can stop or rerun them.

`test --watch` reruns the selected tests when the source, an imported module or
an embedded asset changes. It waits for another edit after failed tests or a
compile error. Each run starts from fresh program state and uses the ordinary
test build, including `--release` when requested. Enter `r` to rerun manually or
`q` to quit. **Dewy: Watch Tests in Current File** starts this workflow in
a VS Code task; save edits to trigger a rerun and terminate the task to stop it.

On native hosts, each test runs in a separate child process: assertions and
panics fail that test, later tests still run, and changes to globals stay local to
that test. Linux and macOS fork after top-level initialization. Windows starts
the executable again for each test, so top-level initialization repeats in each
child. Filesystem and
other external effects remain shared. Tests run natively, skip `main` and game
callbacks, and suppress windows opened through `window`. Only tests declared in
the selected file run; imported files supply code, not additional tests.

Normal runs and builds omit test bodies; `check` checks the selected file's tests
as well as its program. Test blocks do not accept `return`; put reusable logic in
ordinary functions. The compiler repository's Python validation gate remains
`python3 -m tools.core test`.

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
Read-only walks through recursive records avoid per-node copies in development
builds as well as release builds.
`watch` and the interactive prompt retain calls so definitions can be replaced.
`--release` adds broader inlining and further loop optimization.
Use `-g` without `--release` for native variable debugging; it preserves local
variable locations instead of running the default local optimization pass.

`dewy-core new coin-race online` creates a playable two-player game in
`coin-race/coin-race.dewy`, with practice mode, rollback networking and invite
screens. The online template derives a safe source filename from the directory
name; keep it the same for native and web builds because it names saved data and
rooms. The arcade and story templates also derive their filenames this way for saved data;
the other templates use `main.dewy`. Run `dewy-core watch coin-race/coin-race.dewy`
to start editing. Its generated README explains web links and the optional
matchmaking service; no public server is configured by default.

`dewy-core new gold-rush arcade` creates `gold-rush/gold-rush.dewy`, a complete
collect-and-dodge game with title, pause and game-over menus, particles, sound,
increasing difficulty and a saved high score. Arrows/WASD or a gamepad move;
Escape/Start or leaving the window pauses. Its `Game` includes an explicit random
generator, allowing saved states to replay deterministically. Two included
project tests cover replay and saved-value behavior.

`dewy-core new hillside platformer` creates a complete single-file platformer:
text-defined terrain, slopes, one-way platforms, coins, camera follow and generated
art/sound. Use arrows or A/D to move, Space/W/up to jump, and down to drop through
a platform; gamepads also work. The `tick` function takes player/input values,
so movement can be checked without live input. Run `dewy-core test
hillside/main.dewy` for its two starter tests. Edit `LEVEL` to change the terrain
and `RUN`, `JUMP` or `GRAVITY` to tune its feel.

`dewy-core new orb-yard 3d` creates a first-person game with a character controller,
movable crates, ray-cast shots, glowing targets, shadows and fog. Click to capture
the mouse, use WASD/Space to walk/jump, and click to shoot; Escape releases the
mouse. It also supports gamepad sticks, A and RB/right trigger. Its included test
checks shot selection. The yard, meshes and sounds are generated in the source.

`dewy-core new bell-tower story` creates `bell-tower/bell-tower.dewy`, a visual
novel with dialogue, branching choices, typewriter text and a saved reading place.
Space/Enter/click reveals a line, then advances; choices accept clicks or number
keys. A bookmark includes the background and characters and replays the displayed
step when reopened. Edit the embedded `SCRIPT` or use an embedded text asset.
The included tests cover choices and restoring a conversation.

Native game reload keeps unrelated live state. Changed assets refresh globals
initialized from them, including through direct helper calls across modules.
Closures keep their captured state when assets used by their bodies change.
Dependency discovery cannot follow arbitrary calls through function values yet.

The [VS Code extension](../editors/vscode/README.md) supports unsaved diagnostics,
completions, hover, navigation, rename, signature help, semantic highlighting, inlay hints,
quick fixes and Format Document. It uses a bundled or installed compiler, or the one
`dewy.core.path` names: a standalone compiler executable, or the checkout's absolute
`tools/dewy` path.
With the development launcher, restarting the language server picks up compiler
source changes without changing the editor setting.
For a rejected update to an ordinary loop binding, the editor can insert `@`
at that binding's declaration when it is a supported stored-array loop with a
block body. It follows resolved bindings through nested scopes and avoids
suggesting mutable iteration over constants, temporary results or slices.
Fixed arrays display as `array<Element length=N>`; constants are marked readonly.

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

Named arguments also work through function values, returned callbacks, record
fields and array elements. An inferred function value retains its declared
parameter names. A function-type annotation supplies the names at that boundary:
`let f:<(amount:int64):>int64> = (x)=>x*2` can be called as `f(amount=21)`.
These names do not change the runtime calling convention. The callee evaluates
first, then explicit arguments in written order. Parameters named `_` accept
positional arguments only. Function values require all arguments; default
arguments remain a direct-call feature.

A bare function name calls the function: `seven` is `seven()` when every
parameter of `seven` has a default, and a name whose function needs arguments
is an error. `@name` is the function itself, a value that can be passed,
stored and called later. This holds for named functions, function-valued
locals and parameters, and function-valued record fields (`w.on_event` calls
it; `@w.on_event` selects it):

```dewy
double=(x:int64):>int64=>x*2
apply=(f:<(x:int64):>int64> x:int64):>int64=>f(x)
main=()=>{
    let f=@double     # the function, not a call
    let g=@f          # copy a function value with `@` too
    printl(apply(@double 20)+g(1))   # 42
}
```

`@f(args)` partially evaluates `f`: the arguments are evaluated now, and the
result is a function of the remaining parameters. Every argument group in an
ungrouped `@` chain partially evaluates (`@sum(1)(2)`); parentheses end the
chain, after which an argument group calls (`(@sum(1))(2)`). A parameter left to
its default must have a literal default for now. An overloaded or generic
function partially evaluates too: the arguments choose the version, as in a
call, and an annotation such as `let f:<(b:int64):>int64>=@max(x)` chooses
among versions leaving different parameters open (without one, the version
leaving the fewest wins) and settles type parameters the arguments leave open.
`@text.split(" ")` saves the receiver with the arguments; built-in container
methods and methods that change their receiver are not supported yet. Inside a
generic function, a binding whose type is a type parameter stays a value even
when an instance makes it a function.

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
across the signature. Individual names can have types, such as
`([x:int64 y:float64])`; these check the extracted values inside the function,
while a type on the whole parameter guides call arguments and overloads.
Mutable `@` patterns are not supported; use a named parameter for those cases.

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
visible variable; otherwise it can introduce a new variable.

`const` initializes a binding once each time its declaration runs. Its initializer
may call ordinary runtime code. Reading it again retains that value, including
independent array/record snapshots; an unused initializer still runs. You cannot
reassign the binding, change its fields or elements, or pass it as an `@` argument.
Make a mutable copy with `let` when needed:

```dewy
let values=[20 22]
const saved=values
values[0]=99
let editable=saved
editable[0]=0
printl(saved) # [20, 22]
```

Constant expressions can also supply fixed-array lengths and `$assert`
conditions. In these contexts ordinary checked functions execute at compile
time, including recursion, local mutation, loops, records, arrays, strings,
and error values. A demanded module constant is materialized as a value:
its table-generation code does not run again at startup. A `const` initializer
otherwise retains its ordinary runtime behavior. Explicit `let` shadowing
remains available.

Parameters have
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

Closures capture snapshots of enclosing locals. Each closure can change its own
private captures; later changes to the enclosing locals do not change those
snapshots. Copying a closure copies its current private state:

```dewy
make_counter = () => {
    let count = 0
    return () => { count += 1; count }
}
main = () => {
    let a = make_counter()
    let b = @a
    printl(a()) # 1
    printl(b()) # 1
    printl(a()) # 2
}
```

Use `$capture @name` in the parameter list to share an enclosing local binding:

```dewy
main = () => {
    let count = 0
    let next = ($capture @count) => { count += 1; count }
    let other = @next
    printl(next()) # 1
    printl(other()) # 2
    printl(count) # 2
}
```

Captures can appear anywhere among ordinary parameters. `$capture` applies to
the following binding: `$capture name` takes a private snapshot and
`$capture @name` shares the enclosing binding. Both are bound when the closure
is created, so neither takes an argument when called:

```dewy
let update = (step:int64 $capture @count extra:int64) => {
    count += step + extra
}
update(2 3) # changes the enclosing count by 5
```

Each explicit capture names an enclosing local; capture and parameter names
must be distinct. Other referenced locals still become private snapshots.
Shared locals remain alive after the enclosing
call returns, and copies retain that deliberate sharing. A mutable parameter
or loop element place cannot escape through a shared capture; copy its value
into a local first. Shared cells that could hold functions are rejected to
avoid reference cycles. Module globals retain their module-wide identity.

Ordinary callback parameters receive independent values. To advance a caller's
counter, accept `@counter` and pass `@counter`, just as for other mutable values.
Records and collections containing closures also preserve independent copies.
Value-returning getters, including dictionary lookups, return independent
closures too. Calling `counters[key]()` advances that returned copy. To advance
the stored value, pass `@counters[key]` to a function with an `@` callback
parameter. Explicit shared captures retain their sharing through either path.
Calling a callable saved under `const` uses a temporary copy of its private
state; explicit shared captures still refer to their shared bindings. Captured
`const` locals remain read-only inside the closure.

A binary operator with its right operand can be used as a function:
`(* 2)` doubles its input, `(<? limit)` compares it, and `(.x)` reads a field.
Normal precedence applies: `(* 2 + 2)` means `x => x * 2 + 2`.
These functions use ordinary private captures and evaluate their bodies when
called. Function types use angle brackets, for example `<(x:int64):>int64>`;
parenthesized function type grouping is rejected. An inferred `@fn` handle
selects a single concrete user function ahead of prelude functions with the same
name; multiple concrete user overloads still require a callable type. Pass them to a typed callback
parameter or give a local a function type,
for example `let twice:<(value:int64):>int64> = (* 2)`. A module declaration such
as `twice = (* 2)` can infer its parameter type at calls, like other functions.
Operators with prefix meanings keep those meanings: `(-1)` is a negative value.

`int` is the mathematical integer type, distinct from `int64` in signatures,
containers and generic arguments. Unannotated integer literals default to `int`.
Arithmetic is arbitrary precision: word-sized values promote to a big integer
when their exact result exceeds the signed 64-bit range. `int` has no `.min` or `.max` members.

Explicit `int8` through `int64` and `uint8` through `uint64` retain wrapping
arithmetic. Floating types are `float32` and `float64`. Literals in an explicit
numeric context must fit that type exactly. A call parameter supplies that context
to `if` and `match` branch values, just as a binding annotation does. In `=?`
and `not=?`, array, record and dictionary literals take their element or field
types from the typed operand on either side. Mixed `int`/fixed-width arithmetic
uses `int`; a literal beside a fixed-width operand can take that operand's type.
Implicit conversions involving `int` preserve the value, checking narrowing at
runtime (or diagnosing known constant failures). `as` and type calls use those
same checks. Float-to-`int` truncates toward zero and rejects NaN and infinity;
exact decimal and fraction conversions to integers also truncate toward zero,
without rounding through a float. `int`-to-float retains the usual rounding. Existing conversions
between explicit fixed widths retain their behavior. Mutable arguments and
containers require matching element types: an `int` local is not an `@int64` place. Two mutable arguments in one call
must be disjoint: the same binding, a parent and its field/element, or possibly
equal indices of one array are rejected. Distinct fields and distinct constant
indices are accepted.

Lengths retain their current `int64` type. An `int` index uses the ordinary bounds
checks. `to_int(text)` returns `int | none`, parsing integers of arbitrary size.
`from_text<int>` and integer fields in parsed records and containers preserve
the same arbitrary precision. Printing, interpolation and
`string(value)` format `int` as decimal. Mathematical integers are not yet
supported in shaders; shader integer values need explicit fixed-width types.

Scalar integer annotations can carry checked refinements:

```dewy
positive = int64<i => i >? 0>
quotient = (n:int64 d:positive):>int64 => n//d
identity = (n:int64):>int64<r => r =? n> => n
```

The lambda binder is local to its predicate. A parameter may use its own name
(`d:int64<d >? 0>`); partial operators (`int64<(>? 0)>`), conjunctions,
one-direction comparison chains, scalar exclusion (`int64 & ~0`), and membership in literal ranges are also
supported. Bounds may use integer literals, fixed-width `.min`/`.max`, other
scalar value parameters of the same representation, or stable local bindings.
Predicates cannot contain calls or arbitrary arithmetic.

A refuted obligation is a compile error. An unproven obligation becomes an
ordinary runtime check that panics on failure; a proven obligation emits no
check. Annotated local initialization and replacement, arguments, and results
use these checks. Arguments are captured in evaluation order and checked before
invocation. A result's references to value parameters describe their entry
values, even when the function changes its private parameter copies. Generic
instances retain contracts. Callable conversion requires compatible
preconditions and guarantees; it cannot silently strengthen a result promise.
Fixed-width arithmetic still wraps before its result meets a refinement.

Scalar refinements do not yet support mutable place parameters, refined fields
or collection elements, length predicates, or captured lexical dependencies.
There is no public strict-lane spelling.

Fixed-width integer types expose typed `.min` and `.max` constants, including
the full `uint64` range; these also work through type aliases and generic type
parameters. For example, `uint8.max` is 255 and `int64.min` is −9223372036854775808.
`value transmute Type` reinterprets bits between equal-width machine integers
and floats; for example, `float64(1.0) transmute uint64` is `4607182418800017408`.
It evaluates the source once, preserving signed zero and NaN payloads. The
source has its own type: to reinterpret 32 bits, write a `uint32` or `float32`
source explicitly. The destination does not change the width of a literal.
This currently supports scalar native/web code; booleans, collections, records
and optional/union types cannot be reinterpreted this way.

`string(value)` formats a value as text. Integer `//` is floor
division and `%` gives a remainder with the divisor’s sign (or zero). These
operators support `int`, signed `int64` and unsigned `uint64`, preserving the full
unsigned range; narrower operands retain the existing integer widening rules.
Integer `/` produces an exact fraction; `/` with a floating operand uses floating math.
`int` division of the minimum stored word by −1 overflows; its remainder is zero.
Mathematical shifts reject negative counts. A right shift of at least 64 bits
returns the sign continuation (zero or −1); a left shift that cannot fit fails,
except that shifting zero by any nonnegative count remains zero.
Literals outside the checked `int` range need an explicit fixed-width context
that fits, or an explicit `BigInt` annotation.

For fixed-width integers, shift counts are unsigned: a negative literal count
is an error, and a negative runtime count acts as a huge one. Shifting a
fixed-width integer by at least its width gives `0` for `<<` and unsigned `>>`,
and the sign (`0` or `-1`) for signed `>>`: `uint64(1) << 64` is `0` and
`int64(-2) >> 64` is `-1`.

Comparisons use `=?`, `<?`, `>?`, `<=?` and `>=?`. Boolean expressions use `and`,
`or` and `not`. Literal coefficients such as `2x` and `2(x+1)` multiply; use `*`
for general multiplication. A semicolon discards an expression's result.

`^` raises a value to a power and associates right: `2^3^2` is `2^(3^2)`.
It binds above multiplication, literal coefficients and unary minus, so `2x^2`
is `2*(x^2)` and `-2^2` is `-(2^2)`. Use `xor` for bitwise exclusive-or.
Integer powers use a nonnegative `int64` exponent. `int` powers check each
product; fixed-width powers retain wrapping multiplication; negative exponents panic with guidance
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

## Physical quantities

A quantity's dimension is part of its type and is erased at runtime. Time
units `s`, `ms`, `us`, `ns`, their written names, `minute`, and `hour` are in
the prelude. Import other units from `units`:

```dewy
from units import m, km, kg, deg, turn
Speed:type = float64 * Length / Time
Duration:type = <T>(T * Time)
travel=(speed:Speed elapsed:Duration<float64>):>(float64 * Length)=>speed*elapsed
let distance=travel(20m/s 300ms)
printl"{distance/m}"  # 6.0
```

The base dimensions are `Time`, `Length`, `Mass`, `Current`, `Temperature`,
`Amount`, `Luminosity`, and `Angle`. Values use canonical seconds, metres,
kilograms, amperes, kelvins, moles, candelas, and whole turns. Unit scales are
exact: `3km =? 3000m`, `300ms =? 3s/10`, and `90deg =? turn/4`; `°` also
spells degrees. Fractions use `Rational`, and quantities also support machine
integers, checked `int`, `BigInt`, `float32`, and `float64`. A floating annotation rounds an
exact scale to that representation.

Addition, subtraction, and comparisons require identical dimensions.
Multiplication/division combine dimensions; powers require a constant integer
exponent. Divide by a unit to get a dimensionless count in that unit.
Annotations, generic functions, overloads, arrays, records, and conversions
preserve dimensions. Ordinary conversions cannot add or remove a dimension;
`transmute` can explicitly change it while preserving the numeric representation.
Formatting currently prints the canonical number without a unit suffix.
Display-unit selection, offset units such as Celsius, and calendar durations
remain open. `sleep` takes a time, `sleep(300ms)`, and waits whole nanoseconds;
a plain number is rejected. `sin`, `cos` and `tan` take an angle, `cos(45°)`, reduced
exactly in whole turns; until `fixed` exists they give a `float64` rounded to
fixed's 32 fraction bits (a plain number is still radians). The radian unit
remains unimplemented.

## Exact large integers

```dewy
from bigint import BigInt, bigint, parse_bigint
main=():>void=>{
    let value:BigInt=123456789012345678901234567890
    printl"{value*value}"
    printl"{bigint(2)^256}"
    let parts=(-value).divmod(bigint(7))
    printl"{parts.quotient} {parts.remainder}"
}
```

Oversized integer literals adopt an explicitly expected `BigInt` type. Decimal and all supported based literals work, including digit
separators. Their digits are converted at compilation, not parsed at runtime.
Small literals also adopt an expected `BigInt` type, for example
`let value:BigInt=42`, typed arguments, record fields and arrays. Import `BigInt`
when naming its type. Annotate mixed-size literal arrays as `array<BigInt>`;
unannotated ordinary integer arrays infer `array<int>`.

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
[The exact-integer example](../examples/exact_integers.dewy) computes
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
division. Decimal literals are exact fractions by default: `0.1 + 0.2 =? 0.3`
is true, `1.0/2` is `1/2`, and `1.25e2` is `125`. A float annotation or
floating operand gives literals a floating context (`let x:float64=0.1`).
Fraction support is loaded only when needed after
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
produce signed zero. A float annotation, parameter, or operand supplies a
floating context. An explicit conversion also works, for example when passing
an exact time step to a vector or rendering API:

```dewy
let step=(1/60).to_float32()
let movement=vec2(step 2.0*step)
```

Floating values cannot yet be converted back to `Rational` directly. Inferred
decimal bindings hold fractions; annotate an accumulator that will receive
floating values with `float32` or `float64`.

[The exact-fraction example](../examples/exact_rationals.dewy) computes
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

Records can contain optional values of their own type, including through other
records and unions. Lists and trees keep ordinary value semantics:

```dewy
Node:type=[value:int64 next:Node?]
sum=(node:Node?):>int64=>{
    let cur=node let total=0
    loop cur is?Node {total+=cur.value cur=cur.next}
    return total
}
main=()=>{
    let original=Node[20 Node[22]]
    let copy=original
    if copy.next is?Node {copy.next.value=100}
    printl(sum(original))  # 42
    printl(sum(copy))      # 120
}
```

Copies remain independent when nested values change. The compiler manages
recursive storage automatically; no pointer syntax or manual allocation is
needed. A recursive type must admit a finite value: `next:Node?` can end with
`none`, whereas `next:Node` alone cannot. Recursive values also support equality,
dictionary keys, formatting and JSON conversion. Private callback captures keep
their copy semantics inside these values; `$capture @name` still opts into sharing.
Recursive managed layouts cannot cross the C ABI; use an explicit C pointer
representation at that boundary.

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

Generic functions can also be specialized as values: `let convert=@identity<int64>`
stores a callable, including functions imported from Dewy or core modules.
Passing `@identity<int64>` directly as a callback works too. If several overloads
remain after specialization, give the value a callable type to select one.
Without explicit type arguments, an expected callable type can infer them.

Local closures use the same generic syntax and inference:

```dewy
main=()=>{
    let count=0
    let next=<T>(value:T)=>{count+=1; [value=value count=count]}
    let other=@next
    assert(next(20).count =? 1)
    assert(next("hello").count =? 2)
    assert(other(false).count =? 1)
}
```

All specializations of one closure use its private captured state. Copying the
closure copies that state independently; `$capture @name` in its parameter list
keeps sharing explicit. A generic closure can be returned, stored in records or
collections, and forwarded through another generic function. Its concrete calls
use specialized code and the existing closure environment, without a runtime
type dictionary. `next<int64>` selects an ordinary callable value; assigning that
value follows the same independent-copy rules as other closures. An expected
callable type can select the specialization too. Defaults run against the
closure's captured state after explicitly supplied arguments, in parameter order.

This slice accepts plain type parameter names. Constraints such as `T of Bound`
remain unsupported.

Record types and record literals can declare methods: `name = (params) => body`
rows among the fields. Inside a method, a bare field or method name is that
member of the object the method was called on; there is no `self`. A parameter
or local of the same name hides the member.

```dewy
Span:type=[
    start:int64
    stop:int64
    width=()=>stop-start
    grow=(by:int64)=>{stop+=by}
]
counter=(start=0)=>[
    value=start
    increment=()=>(value+=1)
]
main=()=>{
    let s=Span(3 7)
    s.grow(2)                       # s is 3..9
    let c=counter(40)
    c.increment                     # a zero-argument method is called on access
    printl"{s.width} {c.value}"     # 6 41
}
```

A method that assigns or grows a member, places one with `@`, or calls a method
that does, changes its object, so it is called on a variable, field or element:
calling it on a const or a temporary value is an error. Other methods work on
any value. Copies of an object carry its methods and stay independent. A type's
methods are not stored in its values and are not constructor fields; methods of
a generic type use its type parameters, and imported types bring their methods.
A literal's methods keep what they capture from the enclosing function, as
closures do. A function written inside a method may read members but cannot
change them yet. Methods are not values yet (`@c.increment` is an error), and
types with methods are declared at module level.

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

[The bounded history example](../examples/history.dewy) uses a
[generic ring buffer written entirely in Dewy](../examples/ring.dewy),
including operator discovery through an imported type, nested edits and independent
rewind snapshots. A full ring replaces its oldest entry without shifting elements.

The bundled `Pool<T>` and `Heap<T>` are now available with ordinary Dewy type
annotations. A pool stores values under stable `Handle`s; removing an entry
invalidates its handle even when a later entry reuses the slot. A heap pops the
value with the lowest numeric priority. Both retain independent copies, like
arrays and dictionaries. [The entity-event example](../examples/entities.dewy)
uses them together:

```sh
python3 -m tools.core run examples/entities.dewy
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
`.push(value)`, `.pop()`, `.pop(i)` (removes and returns the element at `i`),
`.insert(value i)` (inserts before `i`), `.clear()` and `.truncate(count)`. `xs[1..3)` is an
exclusive-end slice; `xs[1..2]` includes index 2.

A member call that needs no other arguments may omit its parentheses: `xs.pop`,
`xs.sort`, `text.trim` and `shape.area` (for `area=(s:Shape)=>...`) call the
function, exactly as `xs.pop()` does. A record field of the same name wins and
is read, not called; a function with required arguments still needs them.

Low-level code can obtain an owned growable array's element pointer with
`.data()`. This first detaches shared storage, including containing arrays along
a field/index path, so existing value copies remain independent:

```dewy
Buffer:type=[values:array<int64>]
let original=Buffer[[20 22]]
let copy=original
let p=copy.values.data()
p[0]=42
# original.values is [20 22]; copy.values is [42 22]
```

The receiver's indices run once. A private closure capture keeps its independent
state when accessed this way; `$capture @name` still shares the binding explicitly.
The pointer is a low-level view: keep its owner alive and do not resize or replace
the array while using it. Ordinary read-only iteration bindings remain read-only;
make a local value copy before editing one, or use `loop @item` to edit storage.

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

`out.extend(source[lo..hi))` appends a contiguous slice directly from the
captured source, avoiding a temporary slice allocation when the source and
destination have different roots. Bounds are checked before evaluating the
destination; both arrays retain independent value semantics. Self-appends keep
the slice-copy path so appending a small selection does not force a copy of the
entire source. Matrix slice reads use the same bulk append path for each row.

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

Generic integer-array inference takes precedence over converting integer
elements to float: `sum([20 22])` returns an integer, just as summing a named
integer array does. This also applies when literals mix with integer variables
or function results, in either order. Adding more elements does not by itself
make an array-specific overload lose to a generic catch-all. Typed elements
supply context for earlier literals too,
including range checks. Concrete narrow overloads still accept
fitting literals, and floating arrays still select floating overloads. An
unconstrained array made solely of machine-integer literals infers `uint64` if
any literal exceeds `int64.max`; the remaining literals must fit that type.

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

A declaration can annotate the whole source value, including nested and fixed
arrays, records and dictionaries. The annotation supplies context for literals:

```dewy
let [red green blue]:array<uint8>=[255 128 0]
const [[left] [right]]:array<array<int64>>=[[20] [22]]
```

`const` patterns evaluate their source once and make every extracted binding
read-only, at local or module scope. Copies made with `let` remain mutable.
Individual names can also have types in declarations, parameter patterns and
loop patterns:

```dewy
let [x:int64 y:float64]=[20 22]
loop [key:string score:float64] in ["red"->20 "blue"->22] {printl(score)}
```

Each annotation uses ordinary assignment conversions on the extracted value;
it does not change the source container's element type. For example, an `int64`
element can widen to `float64`, while narrowing to `uint8` needs an explicit
conversion or a whole-source `array<uint8>` annotation. Types on discarded
`_` elements are checked too. Annotated patterns declare new bindings; use
unannotated patterns to assign existing variables. A nested bracket group
itself cannot have a type; annotate its names or the whole source instead.

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
These assignments retain the array's length. Dotted updates such as
`values[1..3) .+= 10` also work on slices, stepped ranges, index lists and masks.
Stepped string slicing is not implemented.

Comprehensions are eager. Nested loops and block bodies work; a final block value
is collected, while `break`, `continue` and assignment statements do not emit a
value. `key -> value` creates dictionary entries; duplicate keys take the last
value. A dictionary can also be written directly as `["a"->20 "b"->22]`.

Straight-line `[loop i in [0..n) expression]` comprehensions over an `int64`
bound and `[loop x in values expression]` over ordinary or fixed arrays reserve
their output once. Combined index/value loops and simple local declarations in
the body work too. Array loops use the input snapshot's length, including when
callbacks replace the source. Plain values with an unchanged control index are
written directly by index; managed values retain incremental initialization and
cleanup. General loop bodies, filters and early exits keep the ordinary
collection path. This needs no annotation or explicit allocation code in the
program.

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

`values.pop(key)` removes an entry and returns its value; a missing key fails
as `values[key]` does. `values.pop(key default=none)` returns the default for a
missing key instead. `values.remove(key)` returns whether it removed an entry.

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
if 7 not in? visited {visited.push(7) printl"first visit"}
```

`set<T>` supplies the element type for an empty literal or narrower numeric
members. Function parameters provide the same context. `set[loop ...]` and
`set[values...]` also work, with arrays or sets as spread operands. For example,
`set[existing... "new"]` preserves the first occurrence of each member, and
`[existing...]` collects a set's members into an array. `push` adds a member.
Adding an existing member leaves its position unchanged. `remove(value)`
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
let leaderboard=players.sorted_by(@by_score true)
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

## Numeric arrays and matrices

The bundled numeric library uses ordinary value semantics. Make a matrix with
`zeros(rows cols)`, `ones(rows cols)`, `eye(n)` or `reshape(values rows cols)`:

```dewy
let matrix = reshape([3.0 1.0 1.0 2.0] 2 2)
let saved = matrix
matrix[0 1] = 4.0
assert(saved[0 1] =? 1.0)
let solution = solve(saved [9.0 8.0])  # approximately [2.0 3.0]
let product = saved*eye(2)
assert(product.data =? saved.data)
```

`NDArray<T>` stores a flat, row-major `data` array and a `shape` array. Use
`matrix[i j]` for a two-dimensional element; three- and four-dimensional
indexing work too. `zeros<int64>(rows cols)` chooses integer elements instead of
the default `float64`. Dimensions must be nonnegative and their product must
fit the supported array size. A zero dimension produces an empty array.

`reshape` checks the number of elements; `flatten`, `row` and `col` return
independent array values. `transpose` reverses the axes. `size(matrix)` counts
all elements; `rows` and `cols` inspect a two-dimensional shape. Use these
constructors rather than changing `shape` independently of `data`.

For matrices, `a*b` is the matrix product; `a*values` multiplies a matrix by a
column vector. `a+b` and `a-b` require matching shapes. `sum`, `mean`, `min` and
`max` reduce the elements. `solve(matrix values)`, `inverse(matrix)` and
`det(matrix)` provide linear algebra on square `float64` matrices; a singular
matrix raises an error in `solve` and `inverse`.

`dot(a b)` computes a dot product. `norm(values)` computes the Euclidean length
of a `float64` array; `hypot(x y)` computes the length of two coordinates.
They rescale extreme values so that squaring a large or tiny coordinate does
not unnecessarily overflow or underflow: both `norm([3e200 4e200])` and
`hypot(3e200 4e200)` give approximately `5e200`, and the same works at `1e-200`
scale. An empty or all-zero array has positive zero length. `norm` propagates
any NaN; `hypot` returns infinity if either coordinate is infinite, even when
the other is NaN. Floating `abs(-0.0)` returns positive zero.

GPU `hypot` uses the shader's `float32` arithmetic and a corresponding scaled
implementation. Shader precision and handling of subnormal values still depend
on the graphics driver; the CPU and WebAssembly routines use `float64`.

Dotted operators apply scalar arithmetic to each element. Adjacent dotted
operations and calls fuse into one traversal without intermediate result arrays:

```dewy
let xs = [1.0 4.0 9.0]
let shifted = sqrt.(xs) .* 2.0 .+ 1.0       # [3.0 5.0 7.0]
let mask = shifted .>=? 5.0                # [false true true]
let grid = reshape([10 20] 2 1) .+ [1 2 3] # shape [2 3]
```

`.+`, `.-`, `.*`, `./`, `.//`, `.%`, `.^` and dotted numeric comparisons use
the corresponding scalar operation. In particular, integer `./` produces exact
rationals, `.//` rounds down, and integer `.%` has the divisor's sign. Floating
`//` and `%` have the same current limitations as their scalar forms.
`f.(values other)` applies a function elementwise; scalar arguments are repeated.
Array operands are evaluated once, left to right. CPU callbacks run in row-major
order and may return managed values such as strings and arrays.

Shapes align at the last dimension. Equal dimensions match; a dimension of one
stretches to the other operand's size, and missing leading dimensions behave as
one. A one-dimensional array therefore acts as a row when combined with a
matrix. Empty dimensions produce empty results when the other dimension is
zero or one; incompatible shapes raise an error. Fixed-size array operands are
accepted and produce ordinary dynamic arrays. Results are independent values.
`xs .+= amount` is the update form of `xs = xs .+ amount`; `.-=`, `.*=`, `./=`,
`.//=`, `.%=` and `.^=` work the same way. Indexed destinations are evaluated
once, before the right side, and saved copies keep their previous values:

```dewy
let positions = [1.0 2.0 3.0]
let saved = positions
positions .+= [0.5 1.0 1.5] .* 0.25
assert(saved =? [1.0 2.0 3.0])
```

Updates retain the destination's type; their result must fit it. Broadcasting
may change a dynamic matrix's shape, while fixed-size arrays check the resulting
length. Ordinary and fixed arrays also support dotted selection updates:

```dewy
positions[1..end] .+= 0.5
positions[[true false true]] .*= 2.0
```

Receiver indices and selectors evaluate once before the right side. Selected
values come from the original array; writeback reacquires the destination if the
right side resizes it. Open range endpoints are fixed before that right side
runs, and the result must have exactly the selected length. Repeated indices
read the same original value and write in selection order, with the last write
winning. Saved copies remain independent. These operations allocate the selected
values and result; an otherwise unique destination does not need a full-array
copy merely to keep the temporary input snapshot alive.

`.-values` negates each element; `.+values` applies unary plus. These forms
accept ordinary arrays, fixed arrays, matrices and GPU arrays, and fuse with
surrounding dotted expressions and calls: `.-(positions .+ offset) .* scale`.
They use the scalar operators' precedence and behavior, including custom
negation and floating-point signed zero. Results are independent values;
fixed arrays produce dynamic arrays. Other dotted prefix operators remain
unsupported.

Put a range in its own brackets when selecting axes:

```dewy
let matrix = reshape([1 2 3 4 5 6] 2 3)
let column = matrix[[..] 1]           # shape [2], values [2 5]
let row = matrix[1 [..]]              # shape [3], values [4 5 6]
let block = matrix[[0..2) [1..3)]     # shape [2 2], values [2 3 5 6]
matrix[[..] 1] = [20 50]
matrix[0 [1..3)] = 99                # fill each selected element
matrix[[..] 1] .*= 2                 # update a column elementwise
assert(column.data =? [2 5])
```

A scalar index removes that axis; a range keeps it, and omitted trailing axes
are selected in full. A selection is an independent `NDArray` value. Assign a
scalar to fill it, or an array/matrix with the same number of elements to replace
it in row-major order. Bounds and replacement lengths are checked. The explicit
inner brackets matter: `matrix[.. 1]` is one range ending at 1, while
`matrix[[..] 1]` selects column 1. Each axis accepts contiguous or stepped
ranges, forward or backward, inclusive or exclusive endpoints, and stored
`IntRange` values:

```dewy
let selected_rows = [0,2..rows(matrix))
let sample = matrix[selected_rows [..]]
let flipped = matrix[[..] [end,end-1..]]
matrix[selected_rows [0,2..end]] .+= 10
```

The first two values define a step, as they do in ordinary array ranges. A
range keeps its axis even when it selects zero or one element. An empty range
selects no cells; a nonempty range must select only in-bounds coordinates.
Stored ranges remain small values; selecting a matrix materializes the selected
data. Scalar, array and matrix replacements work with stepped and stored
selectors too.

Dotted updates work on matrix slices too, using the selected shape for
broadcasting. Axis indices and bounds evaluate once. Open endpoints and omitted
trailing axes are fixed from the original shape before evaluating the right
side; if that side reshapes the destination, writeback uses those same
coordinates with the new shape's strides. The destination must still contain
those coordinates, and the result must have exactly the selected element count.
Saved matrices remain independent, including when selected elements are managed
values such as strings.

`end` refers to the last index of its own axis: `matrix[end end]` selects the
bottom-right element, and `matrix[[..] end]` selects the last column, including
on non-square matrices. The receiver is evaluated once. In a zero-length axis,
`end` is -1; an element read fails its bounds check, while `[0..end+1)` selects
the empty axis.

[`trajectory_fit.dewy`](../examples/trajectory_fit.dewy) fits a
quadratic to sampled heights, predicts another height, and includes native test
blocks. Its normal-equation example uses small, well-scaled times; it is not a
general numerical fitting package.

[`reaction_field.dewy`](../examples/reaction_field.dewy) combines
matrix slices, fused dotted arithmetic and slice updates in a paintable
reaction/diffusion simulation. Its separate
[model](../examples/reaction_model.dewy) keeps the previous field
values while computing both updates, preserves a fixed outer boundary, and
includes tests that run without opening a window.

Matrix multiplication uses contiguous rows and shares large products among the
native worker pool. Native x86-64 default builds vectorize short float kernels,
including array comprehensions and fused dotted expressions; release builds
apply broader optimization. Bounds and overlap guards select a scalar fallback
when a whole loop cannot safely use SIMD; tail elements also use scalar code.
Web builds use the same scalar
operations. `SLOPPY_THREADS=1` restricts native execution to the
calling thread.

## GPU arrays

`gpu(values)` uploads a numeric array or `NDArray`; `cpu(value)` downloads an
independent `NDArray` with the same shape. Floating inputs become `float32`,
integer inputs become `int32`, and arrays may have up to four dimensions:

```dewy
let xs = gpu([1.0 2.0 3.0])
let shifted = xs .* 2.0 .+ 1.0
assert(cpu(shifted).data =? [3.0 5.0 7.0])
assert(cpu(xs).data =? [1.0 2.0 3.0])
```

Adjacent dotted operations fuse into one GPU program, including calls to named
functions written in Dewy. Shapes broadcast as on the CPU. `sum`, `min`, `max`
and `mean` also accept GPU arrays. Comparisons produce `float32` masks containing
zero or one. The uploaded value and saved copies remain unchanged when another
binding receives the next result. Upload reusable inputs once and download at
the point where CPU code needs the result.

Native Linux programs try Vulkan, then offscreen GLES; browser builds use
WebGL 2 where available. `gpu_available()` reports whether the driver path is
active. Otherwise—including Node and `SLOPPY_SOFTWARE=1`—the same expression runs
on the CPU. GPU functions must use shader-compatible numeric values and cannot
capture closures or allocate managed collections. These restrictions are checked
at compilation even if execution will use the CPU fallback. Exact rational
integer division is therefore a CPU-array operation; use floating GPU inputs
for `./`. Single-precision GPU math can differ slightly from CPU results.

[`terrain_array.dewy`](../examples/terrain_array.dewy) broadcasts two
axes into a height field using a Dewy function, then compares the downloaded
field with its CPU reference. Regression checks exercise native/web CPU fallback
and offscreen Mesa GLES/Vulkan execution. Those software-driver checks validate
the generated programs; they are not hardware GPU performance measurements.

## Parallel CPU work

The bundled worker pool provides `parallel_map`, `parallel_range` and
`parallel_update`. They wait for completion and keep results in input order:

```dewy
let squares = parallel_range(1000 (i:int64) => i*i)
let shifted = parallel_map(squares (x) => x+1)
let saved = shifted
parallel_update(@shifted (x) => x*2)
assert(saved[0] =? 1 and shifted[0] =? 2)
```

Callbacks may read captured values and change their own local values. They return
results instead of writing shared globals or captured variables; the compiler
checks direct callbacks and functions they call for those writes. Pass a named
function or a function literal so it can inspect the code. Arrays, strings and
records retain ordinary independent value semantics, including snapshots held
across `parallel_update`. No explicit memory management is needed.

Native programs use a persistent worker pool. `SLOPPY_THREADS=2` limits it to two
threads including the caller; `SLOPPY_THREADS=1` runs on the caller. Nested parallel
operations run on the current thread. Web builds currently run these operations
serially with the same result order and copy semantics.

Use parallel work for substantial independent calculations; scheduling and atomic
reference counts can cost more than a small callback saves. Keep drawing and
window/input operations on the main thread. The
[particle example](../examples/parallel_particles.dewy) computes each
particle's forces from a shared previous-frame snapshot and checks the result
against the serial calculation. Run it on two threads:

```sh
SLOPPY_THREADS=2 ./tools/dewy --release examples/parallel_particles.dewy
```

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

See [the settings example](../examples/settings.dewy) for defaults,
record updates and an exact large-ID round trip.

## Errors as values

`type of error` mints a distinct nominal error type. A unit error is written
with its name; add `& [fields...]` for a payload, constructed like a record.
`type of exception` and children of minted exception types are also supported,
including inherited fields. These declarations are currently module-level and
nongeneric; other nominal parents and general intersections are not yet supported.

```dewy
Missing:type=type of error
ParseError:type=type of error & [message:string]
parse=(text:string):>int64|ParseError=>{
    let n=to_int(text)
    if n is? none return ParseError["invalid integer"]
    return n
}
twice=(text:string):>int64|ParseError=>{
    let n=parse(text) or_throw
    return n*2
}
```

Errors are direct union alternatives. Postfix `or_throw` evaluates its operand
once, returns an encountered exception, or yields its success value. It binds
just below `as`. The enclosing function must declare a result type accepting
every propagated alternative. Early returns clean up pending expressions and
enclosing scopes. `none` also belongs to `exception`, alongside `error` and
user-defined descendants. `is? error`, `is? exception`, and tests of individual
types select family members; parent-typed storage preserves the child's identity
and payload. Errors use the ordinary named-record formatting.
A family test on an optional union does not yet narrow an optional exception
subset in its true branch; handle `none` separately before narrowing that subset.

Member reads on unions forward exception alternatives unchanged, including
`none`: `person.address.city` has the successful field types plus the encountered
exceptions. Every ordinary alternative must provide the requested member. A
narrowed concrete error exposes its payload normally. Arguments do not forward
implicitly, and assignments through union routes require narrowing first.
Forwarding method calls are not yet implemented.

`TextError` and `JsonError` belong to `error`, as do the file errors and
`SpawnError` below. `main` still returns void or an integer exit code: handle
exceptions there explicitly.

## Files, paths and processes

`p"dir/file.txt"` is a path literal and `p(text)` builds a path at run time.
Both make a `Path`, which holds its text in `.path`. A path interpolates as its
text, and `path as string` is that text too, so paths are joined by
interpolation: `p"{root}/{name}.csv"`. There is no `join` method.

```dewy
main=():>int64=>{
    let source=p"project/src/main.dewy"
    match source.read_text {
        text:string => printl(text)
        <FileNotFound> => printl"no such file: {source}"
        _ => printl"cannot read {source}"
    }
    printl(source.with_suffix(".udewy"))   # project/src/main.udewy
    printl(source.parent.name)             # src
    return 0
}
```

The methods follow Python's `pathlib`. The lexical ones read only the text:
`name`, `stem`, `suffix` (with its dot; `.bashrc` has none), `parent`, `parts` (a
leading `/` is the root part), `is_absolute`, `with_name(name)`,
`with_stem(stem)` and `with_suffix(suffix)`. The file-system ones give every
outcome as a value:

- `exists`, `is_file` and `is_dir` give a `bool`;
- `read_text` gives a `string`, `read_bytes` an `array<uint8>`, and `list` the
  directory's entry names;
- `write_text(text)` and `write_bytes(bytes)` replace the file and give the byte
  count;
- `mkdir`, `rmdir` and `unlink` give `true`.

A failure is `FileNotFound`, `FileAccessDenied`, `IsDirectory`, `FileExists` or
`FileError` (any other failure), and `read_text` adds `InvalidUtf8`. All are
`error`s, so `is? error`, `or_throw` and `match` handle them.

The same operations exist as functions of a path's text: `read_text(path)`,
`read_bytes`, `write_text(path text)`, `write_bytes`, `file_exists`, `is_file`,
`is_directory`, `list_directory`, `make_directory`, `remove_directory` and
`remove_file`. `append_file(path text)` adds to the end of a file, making it if
it is not there, and gives the byte count or a file error, as `write_text` does. The
implementation language's spellings (`read_file`, `write_file`, `mkdir`,
`delete_file`, `list_dir`, `file_name`, `join_path`, `run_program` and the like)
are rejected in Dewy with the Dewy spelling to use instead.

`run(program args)` runs a child process and gives its status: the exit code, or
`128 + n` when signal `n` ended it. `SpawnError` means no child could be started.
`program` is a path: there is no `PATH` search (`run("/usr/bin/env" ["python3"
"tool.py"])` does one), and a program that cannot be run ends with `127`, as in a
shell. The child shares the standard streams. `run_silent` sends its stdout and
stderr to `/dev/null`. `spawn(program args)` gives a `Child` whose `wait` gives
the status. `capture(program args)` waits and gives an `Output`: `status`,
`stdout` and `stderr` bytes (both drained as they fill), and `stdout_text` and
`stderr_text` (`string | none`).

In a web build, files live in the page's memory, and directories exist as the
paths of its files and those made with `mkdir`. Processes are `SpawnError` there.
On Windows, `run` works and `run_silent`, `spawn` and `capture` are not available
yet (`SpawnError`).

## Loops, text and optional values

`printl(x)` writes a value and a line break; `print(x)` writes it without one.

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
The [Ring example](../examples/ring.dewy) and
[history program](../examples/history.dewy) use this interface across
module imports without a separate iterator allocation.

Use an explicit place binding to update stored array elements:

```dewy
let values = [20 21]
let saved = values
loop @value in values { value += 1 }
# values is [21 22]; saved is still [20 21]

loop @rock in game.rocks {
    rock.pos += rock.vel*dt
    rock.angle += rock.spin*dt
}
```

`@item` names the current element. Assigning it, changing its fields, calling a
mutating method, or passing `@item` to a function updates the array. Copies of
the array or element remain independent, including copies made inside the loop.
Ordinary function parameters still hold independent values: a mutable loop over
a value parameter changes that function's copy; an `@` parameter reaches the caller.

This form accepts dynamic or fixed arrays named by a binding or field path
(`items`, `game.rocks`). Indexed sources, slices, temporary expressions, custom
sequences, mutable destructuring and combined headers are not supported yet.
Nested mutable loops work, as do comprehensions, labels, early exits and fallback
arms. A fallback runs only when the body never ran, as for ordinary loops.
Keep the source array's length and storage intact during iteration: collect
removals/additions separately and apply them afterwards. The compiler rejects
visible resizing or replacement; indirect changes through callbacks still have
runtime bounds checks. An escaping callback captures an independent snapshot
of the element. The mutable place itself cannot be kept through an explicit
shared capture for later changes.

Read-only helpers may inspect the source during a mutable loop, including through
method syntax such as `values.first()`. The resolved parameter types determine
whether a call can mutate its arguments. Calls that can resize the source through
an `@` parameter or a global still cannot run inside that loop.

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

Assertions are directives with their own argument grammar:
`$runtime_assert condition` or `$runtime_assert condition, "message"` checks
the condition when the program runs; a failure reports the condition (or the
message, which may interpolate values) and exits with status 101.
`$assert condition [, "message"]` must be proven while compiling. The compiler
uses constant facts and settled type tests, then executes ordinary checked code
for closed compile-time requests. For runtime scalar values, it also uses
builtin comparison guards, interval/nonzero facts, assignments, snapshots and
successful `$runtime_assert` conditions. Early returns remove unreachable
paths; joins retain only evidence shared by every incoming path. Calls forget
facts about mutable or exposed storage, and loops forget changing values.
Symbolic operands must be pure scalar fact terms; calls, fields and nonlinear
inference are not supported by this pilot. An erased assertion cannot introduce
a new implicit closure capture; existing runtime captures remain usable.
An unknown assertion reports the
missing evidence or its invalidation witness. A false condition reports
`assertion refuted`; failed closed evaluation reports the source operation and
compile-time call chain. Ordinary division and bounds checks remain runtime
checks; these facts do not change their optimization.
It never becomes a runtime check. The directive owns the comma
after its condition, and `$assert(condition, "message")` is the same form.
General compile-time execution has no mandatory step limit or termination proof.
It cannot read runtime locals or mutable globals, mutate global state, perform
I/O, call external functions, or access host memory. Bounded read-only views of
evaluator-owned integer buffers support ordinary library scanners, including
Unicode string length. Existing `$include_bytes` inputs retain their tracked
file dependencies. Indirect/capturing calls, raw writes, generated declarations
and general artifact/host APIs are not yet supported; unsupported operations
are diagnosed, never silently deferred to runtime.
`fields(T)` is a compile-time sequence of a record type's field descriptors.
Each descriptor has `.name` (a constant string) and `.type`. A loop over
`fields(T)` specializes its body for each field when the enclosing function is
instantiated. `value.$field(name)` reads or writes the ordinary field selected
by a compile-time string; runtime names require a dictionary. For example:

```dewy
copy_fields = <T>(value:T) =>
    [loop f in fields(T) $field(f.name) = value.$field(f.name)]
```

A loop in a record literal expands into ordinary named fields, whose types are
inferred independently. Constant arrays can also supply these iterations:
`[loop name in ["x" "y"] $field(name) = 0]`. Nested record loops are supported;
conditional record shapes and general generated declarations are not. Field
descriptors themselves cannot escape into runtime storage. Compile-time string
operations include concatenation, slicing and ordinary checked string-library
calls; interpolation and indirect/capturing calls remain unsupported.

Other directives of the design (`$no_prelude`, `$lend`,
`$allocator`, `$expect`, `$unsafe_assume`, `$target`, …) are reported as not
implemented yet where they appear.

`value.copy` requests an independent value. It evaluates the receiver once
and supports arrays, records, dictionaries, sets, strings, closures and
optional/union values. Parentheses are also accepted (`value.copy()`).
Declared `copy` members take precedence. The operation preserves ordinary
value semantics, including private closure state, and may share COW storage
until a write or transfer a fresh result instead of duplicating it.

`$explicit_copies` at file scope rejects unproven implicit costly copies in
that module, including imported modules and unused checked function bodies.
It can be set once; `$explicit_copies = false` keeps the ordinary COW policy.
Costly values include dynamic arrays, records/containers with mutable heap
payloads, and closure environments. Scalars, fixed inline storage and shared
immutable strings are exempt. Stable read-only record snapshots can share
their payloads. A slice or repeated heap-bearing element also has a copy
obligation.

Write `.copy` for an independent snapshot, borrow a stable value for reading,
or arrange a last-use transfer. The compiler transfers dead local values and
unboxed record fields, distinguishes conditional return paths, borrows
read-only arguments and iteration sources, and infers owning parameters for
closed direct calls. Moves clear their old storage before cleanup. Loops,
captured or exposed owners, live readers, and indirect calls retain conservative
checks when these proofs do not apply. This directive does not forbid fresh
allocation or panics, and is not a separate no-detach guarantee.

String length, indexing, slicing and iteration use extended grapheme clusters.
`"é🙂".length` is 2. String loops stream from an independent input snapshot;
changing the source variable does not change the remaining input. They create
one independent string per visited grapheme, so `break` and `return` avoid
collecting or scanning the remaining text. `graphemes(text)` explicitly collects
all graphemes into an array. Foreign malformed UTF-8 panics when examined,
including the lookahead needed to find a boundary; an unvisited tail is not
validated. Indexing scans from the beginning; use string iteration to visit
every grapheme in one pass.

`upper(text)` and `lower(text)` (also `text.upper()` and `text.lower()`)
return independent strings using the core's current simple mappings for ASCII
and supported Latin, Greek and Cyrillic letters. For example, `upper("café")`
is `"CAFÉ"`. Unmapped characters and malformed UTF-8 bytes are preserved;
these byte-oriented transformations do not perform grapheme validation.
`text.startswith(prefix)` and `text.endswith(suffix)` test the ends of a string.

`regex(pattern)` prepares a reusable regular expression. `text.find(pattern)`
returns `Match|none`; `find_all` returns nonoverlapping matches, `contains` tests
for any match, and `matches` requires the whole string to match. A `Match` has
`text`, `groups`, `start` and `end`. **Match offsets and the optional `find`
starting offset are UTF-8 byte offsets**, while regex atoms consume code points.
They are not Dewy's ordinary grapheme indices; use the returned `text` directly.

```dewy
let date = regex(r"(\d{4})-(\d\d)-(\d\d)")
let found = "due 2026-10-19!".find(date)
if found isnt? none {printl(found.groups[0])}
let rewritten = "due 2026-10-19!".replace(date "$3/$2/$1")
let fields = "a, b;c".split(regex(r"[,;]\s*"))
```

Patterns support character classes, alternatives, captured and `(?:...)`
uncaptured groups, greedy/lazy repetitions, line anchors `^`/`$`, and word
boundaries. `(?i)` at the start folds ASCII case. Use `regex_error(pattern)`
to check user-supplied patterns before preparing them. An empty match advances
one code point before the next search; unmatched capture groups contain `""`.
`replace` accepts `$0` for the match, `$1` onward for captures, `$$` for a dollar,
or a `(Match):>string` callback. `split` returns the text between matches.

Matching uses compact tables and skips impossible starting positions. Long
inputs can use bounded lazy DFAs, with the Pike VM retained for anchors, captures
and fallback. Prepare a pattern once when matching many strings. This bounds
the matching strategy without exponential backtracking; the precise performance
depends on the pattern, input and whether preparation is included.

Interpolation uses `{expression}` inside a string.
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
strings, blocks and comments.

`#` begins a line comment; `#{` and `}#` delimit a block comment, which nests and
may span lines. Comment markers inside strings are string contents.

```dewy
#{ outer
   #{ nested }#
}#
let total = 1 #{ inline }# + 2
```

Printing, interpolation and `string(value)` show a present optional as its payload:
an optional string prints bare on its own and quoted inside a container or record.
An absent optional prints `none`.

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

Assigning another type invalidates a narrowed local. Sibling `if` and `match`
arms are checked independently: an assignment in one arm does not change the
type assumptions used to check another arm. A guard carries forward only
refinements still valid on its continuing path. Replacing a parent value
invalidates refinements of its fields, including across block boundaries.
An arm that returns does not invalidate refinements on paths that continue;
writes on `break` and `continue` paths remain in effect at their destinations.
Assigning a known member to an optional or union field establishes that member's
type for subsequent accesses. `??` also works after an optional has been narrowed
to its value, and its fallback remains lazy.

`match` supports typed bindings, literals and `_` as a fallback. An optional
payload arm such as `n:int64` also narrows the original variable or field to
`int64` inside that arm; the binding `n` is an independent value. A union is
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
a path literal `p"..."` names a file explicitly. Within each folder, a Dewy importer prefers
`.dewy` and falls back to `.jo`; a Jo importer prefers `.jo`. The importing file
itself is skipped, so `physics.dewy` can import the bundled `physics` library.
Watch mode notices creation/removal of a preferred local module and reloads it.
Use `import p"@lib/physics.jo" as physics` to select a bundled library explicitly,
even when a neighboring file has the same name. `@lib/` resolves inside the
active toolchain's library directory and also works with selected imports.

Import cycles containing a Dewy (`.dewy`) module are rejected, with the import
path through the cycle in the diagnostic. This includes cycles that pass through
Jo implementation libraries; cycles made entirely of Jo modules remain allowed.

Start a game with the built-in template, then edit it while it runs:

```sh
/tmp/dewy-core/bin/dewy-core new /tmp/my-dewy-game
/tmp/dewy-core/bin/dewy-core watch /tmp/my-dewy-game/main.dewy
/tmp/dewy-core/bin/dewy-core build /tmp/my-dewy-game/main.dewy --target wasm -o /tmp/game
```

The web build produces `/tmp/game.html`. Games use `main()` for setup,
`update(dt:float64)` each frame, and `draw()` for rendering. The
[paddle game, physics playground, forest and Dunes](../examples/README.md) show
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
The [camera-roll example](../examples/camera_roll.dewy) combines this
with cursor picking and a settings menu. Menu rows expand for long labels and
choice values, sharing the widest row's width on the next frame.

`ui_slider(label value step=0.1 low=0.0 high=1.0)` supports ranges, keyboard
steps, and mouse/touch dragging. Once pressed, a slider keeps its drag until
release even outside its bounds; crossing another control does not transfer it.
`hud_slider(rect value low high step=0.0 label="")` places the same kind of
control directly in a HUD. A zero step gives continuous dragging, and descending
ranges work too. `ui_style=ui_light_style()` supplies a light-background theme.
The [pendulum example](../examples/controls.dewy) combines these
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
[charts example](../examples/charts.dewy).

`polyline(points thickness color closed=true)` joins the segments into one band,
including the closing edge. Consecutive repeated points are ignored and sharp
joins are capped to prevent long spikes. Open paths leave their ends flat.
`rect_rounded_outline` uses the same joins. See the
[outlines example](../examples/outlines.dewy) for these shapes and a
dense plot that spans several drawing batches.

Dunes also defines vertex and fragment shaders as ordinary Dewy functions, with
typed input/output records and texture uniforms. The compiler generates GPU
shader code and the software renderer can execute the same shader functions.
The CPU fallback uses a smaller shadow map and four samples for built-in 3D
lighting; GPU lighting keeps nine samples. Custom shadow shaders should derive
texel spacing from the actual shadow texture size rather than a fixed resolution.
See [its model module](../examples/dunes_model.dewy) for terrain,
animated meshes and custom sand/shadow and beacon shaders.
Native `watch` refreshes shaders after edits, including imported shader functions,
while preserving unrelated game state.

[`netpong.dewy`](../examples/netpong.dewy) adds native/browser
multiplayer using `import net`. `net.listen(port)` hosts natively,
`net.connect(address port)` joins, `net.receive()` supplies joined/message/left
events, and `net.send(peer value)` sends strings or byte arrays. Browser builds
can connect to a native host or use direct invite codes through `import invite`.
See the [multiplayer run instructions](../examples/README.md#multiplayer).
For short room codes and links, configure `invite.server(url)` and run the
bundled rendezvous server. The same invite screens exchange offers automatically;
`invite.arrivals()` supports additional lobby members. See
[short-code rooms](../examples/README.md#short-code-rooms) for setup
and native/browser endpoint details. `net.listen(port largest=4096)` can bound
incoming message size for a small signaling service; ordinary games retain the
16 MiB default. Fragmented WebSocket messages retain their bytes across polls.

For native TCP, `net.tcp_listen(0)` lets the operating system choose an available
port. `net.tcp_port(socket)` returns the bound local port, or `-1` on failure
(including in a browser).

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

The [rollback lab](../examples/rollback_lab.dewy) runs two peers on a
simulated link with adjustable latency, jitter and loss. Its
[model](../examples/rollback_model.dewy) shows session construction,
`play`, outgoing packets and delivery using Dewy records and COW arrays.

This remains a developing subset of Dewy. The earlier proof/effect system,
automatic growth of machine integers on overflow, general structural conversions and every historical
juxtaposition form have not been recreated.

An executable’s `main` returns `void` or an integer exit code. Other result types
are diagnosed rather than passed to the native/web entry wrapper.
