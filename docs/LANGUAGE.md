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

With no file, `dewy` starts the interactive prompt (below) when standard input is a
terminal. When it is piped or redirected, `dewy` reads the whole program from it and
runs it as `<stdin>.dewy` in the current directory: `echo 'printl"hi"' | dewy`,
`dewy --release < prog.dewy`. The program has then used up its standard input.

## Test a project

A test is an ordinary function marked `$test` on the line before it. `$expect
condition` (or `$expect condition, "message"`) states what it checks:

```dewy
add = (a: int64 b: int64) => a+b

$test
adds_numbers = () => $expect add(20 22) =? 42

$test(cases=(1 2 -3))
adds_zero = (x:int64) => $expect add(x 0) =? x, "{x} changed"

$test(cases=[[a=1 b=2] [a=(-3) b=4]])
commutes = (a:int64 b:int64) => $expect add(a b) =? add(b a)
```

```sh
./tools/dewy test examples/paddle_tests.dewy
./tools/dewy test --release examples/paddle_tests.dewy bounce
./tools/dewy test --watch examples/paddle_tests.dewy bounce
./tools/dewy test --json examples/paddle_tests.dewy
```

A failed expectation is reported on stderr (`expectation failed`, the source line
with the condition underlined, the message, and the value of each compared
operand that is not a literal, evaluated again) and returns from the function it is in; the code after an expectation
may assume it, so `$expect value is? int64` narrows `value`. Expectations belong
in functions that give no value: the test itself, or a helper it calls. A
helper's failure returns from the helper, the test goes on, and the test fails.
`$fail "message"` always fails. An expectation the compiler refutes is a warning;
the test fails when it runs.

`cases=` runs the test once per case, named `name[index]`: each value of a tuple
or array literal is the one argument, an object literal's fields are passed by
name, and a module constant array is looped over. A test with parameters needs
cases; one without parameters cannot have them.

`test` builds the selected file with a generated entry that calls each test (per
case) in declaration order; `main` and game callbacks do not run, and windows stay
closed. Each test prints `.` when it passes and `F` when it fails. What a test prints is
collected and shown only when it fails, under `--- FAIL name[case]`, then the
counts (`1 failed, 10 passed`). The exit status is the number of failed tests (at
most 100), 101 when a test aborted (a panic, a failed `$runtime_assert` or an
`exit`), and 102 when the file does not build. `--json` prints one JSON object
per test (`test`, `status`, and for a failure its `output` and `stdout`) and a
summary. Optional words after the filename select test names containing any of
them; no tests, or no matching names, is an error. Only tests declared in the
selected file run; imported files supply code, not additional tests. Given a
directory instead, `test` runs each `.dewy` file under it with a line starting
`$test` (skipping hidden directories and `__dewycache__`), one line of marks per
file, and adds up the results. With no path, `test` tests the current directory.

The VS Code extension also provides **Dewy: Test Current File**, a release variant,
and **Run test** code lenses above each `$test`. These save open files and show
results in a task terminal; the editor's task commands can stop or rerun them.

`test --watch` reruns the selected tests when the source, an imported module or
an embedded asset changes. It waits for another edit after failed tests or a
compile error. Each run starts from fresh program state and uses the ordinary
test build, including `--release` when requested. Enter `r` to rerun manually or
`q` to quit. **Dewy: Watch Tests in Current File** starts this workflow in
a VS Code task; save edits to trigger a rerun and terminate the task to stop it.

On native hosts, each test runs in a separate child process, so a test that aborts
does not stop the others, and changes to globals stay local to that test. Linux
and macOS fork after top-level initialization. Windows starts the executable
again for each test, so top-level initialization repeats in each child (and a
test's stderr is not collected there). Filesystem and other external effects
remain shared.

Test functions are checked and compiled like any other function, and an ordinary
run or build keeps the module's own `main`. `check` checks the selected file's
tests as well as its program. The compiler repository's Python validation gate
remains `python3 -m tools.core test`.

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
Types carry their Dewy spellings, and `lib/debug/dewy_gdb.py` (gdb `source`) or
`dewy_lldb.py` (lldb `command script import`) show values as `"{[value]}"`
prints them: `int` as its number, strings quoted, arrays, records, optionals,
unions and dictionaries as their literals.

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

Run `tools/dewy` or `dewy-core` with no file, at a terminal, to try Dewy without
creating a source file:

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

A decimal binding declared and written a float in the same input is a `float64`
(`let acc=0.0; acc+=dt`). One declared in an earlier input already ran as an
exact fraction, so writing it a float later is a type error; annotate it instead.

Terminal history lives in `~/.dewy_history`. `DEWY_REPL_HISTORY` selects another
file; an empty value disables history persistence. The prompt is currently
validated on the Linux compiler host.

## Functions and values

Arguments and array elements are separated by whitespace. Calls use adjacent
parentheses. A function's final expression is its result; `return` exits early.
A function declared `:>never` never returns: every path ends in `exit(...)`, a
panic or an endless loop, and a call to it ends its branch like `exit` does.

```dewy
twice=(x)=>x+x
add=(a:int64 b:int64=2):>int64=>a+b
combine=(a b=a)=>a+b
main=()=>add(twice(20))
```

One bare parameter name may omit the parentheses: `x=>x+1`, as in
`apply(x=>x*2 21)`, where the lambda ends at the next argument. The name is
always the parameter, even when a type has that spelling; annotated parameters
and result types need the parenthesized form, `(x:int64):>int64=>x+1`.

Unannotated string bindings retain the finite domain of all their literal
writes, including later writes, loop iterations and shared closure writes.
A conditional of literals (`if loud "loud" else "quiet"`) writes each of them.
A match without `else` must cover that entire domain, even when it precedes
some writes. Shadowed bindings and private closure writes have separate domains.
A nonliteral write or writable escape conservatively widens the domain to
`string`. An annotation fixes the type: `let mode:string="fast"` stays general.
String operations and character iteration work normally. A conversion to a
literal union (including a dictionary key) rejects a known domain containing
values outside that union. `members(mode)` returns an `array<string>` containing
the distinct values in an inferred finite domain, in first checked-write order;
later writes participate. Type-based `members(U)` retains its compile-time
specialization. Value domains settle after checking, so `members(mode)` cannot
supply compile-time record field names while the enclosing code is checked.

Integers follow the same rule as ranges: an unannotated `int` binding's type
covers every value written to it, so `let n=1` then `n=2` holds `1..2`
(the same as `1|2`). Literal writes, conditionals of literals, shared closure
writes and a `+=`/`-=` of a literal that runs at most once (in the declaring
function, outside any loop the declaration is not in) each widen the set; a
match without `else` must cover it, and a conversion to a literal union such as
`1|2|3` is proven when the set fits. Any other write (`count+=1` in a loop,
`n=m`, passing `@n`) leaves the set unbounded, which is plain `int`. Storage
stays mathematical `int` either way: `let count=0; count+=1` and
`let value=5; value=300` keep ordinary integer behavior.

Types can be inferred, including generic functions. `:>` writes a result type;
use `:>void` for a function with no result. Named arguments such as `add(b=2 a=40)`
are supported. Explicit arguments evaluate in written order, then omitted
defaults in parameter order. An earlier parameter used in a default refers to
its captured value, so `combine(next())` calls `next()` once.

`...` after a parameter ends the positional run: in
`offset=(value:int64 ... amount:int64)=>value+amount`, `amount` must be named,
`offset(40 amount=2)`; a leading bare `...`, as in `(... width:int64)`, makes
every parameter keyword-only. A parameter wrapped in `<>` is position-only: it keeps its
local name, but `increment=(<value:int64>)=>value+1` rejects `increment(value=41)`.
These kinds apply to direct calls of declared functions.

Named arguments also work through function values, returned callbacks, record
fields and array elements. An inferred function value retains its declared
parameter names. A function-type annotation supplies the names at that boundary:
`let f:<(amount:int64):>int64> = (x)=>x*2` can be called as `f(amount=21)`.
These names do not change the runtime calling convention. The callee evaluates
first, then explicit arguments in written order. Parameters named `_` accept
positional arguments only. A handle keeps its function's defaults: after
`f=(a:int64 b:int64=2)=>a+b` and `g=@f`, `g(1)` is `f(1)`, with the default
evaluated at each call. A function-type annotation states only the contract, so
a value stored under one, or chosen between two such functions, takes every
argument.

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

`$shadowable const` at module top level declares a const that inner scopes and
importing modules may shadow: there a plain `name = ...` declares a new binding
instead of being an error. The prelude is declared this way. Shadowing replaces
the whole overload family: with `max = (a:int64 b:int64 c:int64):>int64 => ...`
in a module, a bare `max(1 2)` there is an error, since none of the prelude's
`max` overloads join the module's. Members are found through their value, so
`(2.5).max(1.0)` and `xs.hash()` still reach the prelude's. To extend an
operation for your own type, use its protocol (`hash`, `len`, `__add__`, …) or a
method; a function selected by `from m import f` can be shadowed only if `m`
declared it `$shadowable`, otherwise import it under another name.

```dewy
$shadowable const limit = 10
main = () => {
    limit = 3     # a new binding in this scope
    printl(limit) # 3
}
```

Use `let` to declare a local or deliberately shadow a name. Assignment updates a
visible variable; otherwise it can introduce a new variable. Assigning to a
visible const or module function that is not `$shadowable` is an error that
suggests `let`.

`let x:T` without a value declares a local that has none yet: every path must
assign it before it is read, so `let x:int64` then `if c {x=1} else {x=2}` is
fine, while reading it after only one arm, after a loop that might not run, or
from a closure made before the assignment is an error. There is no zero value to
read: write `let xs:array<int64> = []` or `let n:int64 = 0`. Paths that return,
break or continue do not count. At module level, `let config:Config` without a
value must be given one by the top-level statements or by `main` before any
read, including reads in the functions `main` calls (or takes a handle to)
before the assignment; a function `main` calls may make the assignment.

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
printl(saved) # [20 22]
```

`const view = @route` (`@xs`, `@boxes[0]`, `@r.a`) is a read-only view of the
stored value: writing the route's variable while the view is still to be used
(later in the function, or again around a loop begun after the view) is an
error at the write. Write after the view's last use, or use `.copy`.

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
main=()=>{let value:int64=41 bump(@value) printl(value)}
```

References can name a field or array element: `bump(@point.x)`,
`bump(@values[i])` or `bump(@points[i].x)`. An index expression evaluates once;
other copies of the record or array retain their independent values. `@value`
for a parameter without `@` is an error (`@f` of a function is its handle).

Closures capture snapshots of enclosing locals; later changes to the enclosing
locals do not change those snapshots. A closure that changes a local must
capture it explicitly: `$capture name` makes it the closure's own private state,
kept between calls, and `$capture @name` shares the enclosing binding. Changing
an implicitly captured local is an error naming both fixes. Copying a closure
copies its current private state:

```dewy
make_counter = () => {
    let count = 0
    return ($capture count) => { count += 1; count }
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
must be distinct. Other referenced locals become private, read-only snapshots.
Shared locals remain alive after the enclosing
call returns, and copies retain that deliberate sharing. A mutable parameter
or loop element place cannot escape through a shared capture; copy its value
into a local first. Shared cells that could hold functions are rejected to
avoid reference cycles. Module globals retain their module-wide identity.

Inside a method, a closure reads the object's members as a snapshot and
changes one only through an explicit capture of that member:
`let hit = ($capture @hits) => { hits += 1 }` changes the object's `hits`,
while writing a member it did not capture is an error naming the fix. Such a
closure holds the caller's object, so it stays in the method: it is bound with
`let` and called there (`@hit` and returning it are errors).

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
parenthesized function type grouping is rejected. A function's handle also fits
a function type whose parameters it accepts and whose result accepts its result:
`@f` with `f=(x:int64|string):>uint64?` fits `<(x:int64):>uint64?|E>` (through a
wrapper; refined and `@` parameters still need an exact match). A function value
held in a variable adapts the same way (`apply(@h)`, `let g:<(x:int64):>int64> = @wide`). An inferred `@fn` handle
names the visible family, so a module's own function shadows the prelude's;
multiple concrete overloads still require a callable type. Pass them to a typed callback
parameter or give a local a function type,
for example `let twice:<(value:int64):>int64> = (* 2)`. A module declaration such
as `twice = (* 2)` can infer its parameter type at calls, like other functions.
Operators with prefix meanings keep those meanings: `(-1)` is a negative value.

Pipes call a callable expression: `x |> @f` is `f(x)` and chains left to right
(`3 |> @square |> @inc`), while `@f <| x` chains right to left
(`@inc <| @square <| 3`). The callable side is an ordinary expression, so a named
function is written `@name`, and a function literal or a function-valued binding
pipes as written. Pipes bind more loosely than `=>` and arithmetic.

Function signatures can bound direct place effects with `reads<place>`,
`mutates<place>`, and `no_effects`:

```dewy
read = (@x:int64):>int64 & reads<x> => x
write = (@x:int64 value:int64):>void & mutates<x> => { x=value }
quiet = (x:int64):>int64 & no_effects => x*2
```

A positive row is a closed upper bound, and it is the contract callers see: a
caller is checked against what the callee declares, not the narrower row its body
would infer, so a `reads<y>` or `no mutates<Filesystem>` caller of a function
declared `mutates<...>` on that place is rejected even if the body only reads.
Negative-only rows bound nothing from above; their callers see the inferred row.
Field permissions such as
`mutates<pair.left>` cover that field and its descendants, not a sibling or
replacement of the parent. Calls translate permissions by argument position and
actual place, including through recursive helpers. Private scalar locals and
value parameters do not export place effects. Existing disjointness rules for
mutable arguments still apply. Omitted rows are inferred when a checked contract
needs them; an unannotated or external function is never assumed pure.

Callable types retain rows through variables, containers, results and checked
conversions. Parameters are contravariant and results covariant. Omitted callback
rows are inferred on demand; reassignment joins every possible source, including
later assignments. Losing provenance or exceeding the bounded analysis keeps
behavior unknown. Recovering a forgotten guarantee requires another checked conversion; an
unconstrained callback parameter alone cannot establish one.

Row parameters have kind `Effect`, separate from value types. Aliases can mix
type and row binders and preserve them across imports:

```dewy
Action:type=<E:Effect>(<(x:int64):>int64 & E>)
apply=<E:Effect>(f:Action<E> x:int64):>int64 & E=>f(x)
```

`E` carries only the nonlocal remainder. Callback-place permissions remain
explicit: `mutates<x>` on a callback can become `mutates<y>` when invoked with
`@y`, but cannot be inferred into `E`. Negative-only rows such as
`no mutates<Filesystem>` remain open while excluding the named nominal resource.
`allocates` is bare; `allocates<Resource>` is invalid. `blocks` is inferred and
only ever excluded: `& no blocks` rejects I/O and any operation the inventory
cannot classify (waits, sleeps, foreign calls). In a row `no` reaches to the next
`&`, so `& no allocates & no blocks` excludes both.

`panics` is inferred the same way: a function may panic when its body keeps a
runtime check (an unproven obligation in a `$runtime_checks`, `$prototype` or
default scope), panics explicitly (`panic`, `$runtime_assert`), or calls or
takes a handle to a function that may panic. A scope without runtime checks
(`$runtime_checks=false`, and so `$no_hidden_costs`) cannot call such code: the
error names the chain to the panic and offers both repairs, proving what the
callee checks first or opting in with `$runtime_checks`. So a function built
with `$runtime_checks` cannot fail inside a caller that did not opt in.
`& no panics` forbids it outright, whatever the scope. A library function's
precondition is the caller's obligation where the library states it: `xs.first`
and `xs.last` take an array with `length >? 0`, and `xs.swap(i j)` and
`xs.insert(value i)` need their positions in bounds, so a guarded call cannot
panic. Other library failures (a missing dictionary key with `d[k]`, a bad
format specification) still make the call panic; their value-returning forms
(`d.get(k)`) do not. Running out of memory is not a panic. The editor's hover
shows `& panics` on a function that may panic, and `dewy check --obligations`
lists each library call that may panic where runtime checks are allowed.

The implementation-cost inventory supports wrapping fixed-width scalar work
(including shifts), inline scalar records and unions of them (`:>(int64 | Oops) &
no_effects`; the parentheses are required), bare handles, capture-free lambdas,
read-only array parameter borrowing, length/capacity inspection and scalar array
iteration, fixed arrays of such values (literals built in place, literal constant
tables), counted loops over word ranges, and element reads and stores whose index
is proven in bounds (a constant into a fixed array, or the function's own facts:
`loop i in [0..16)`, a guard on `xs.length`). An unproven index is a possible
failure. Reading a mutable parameter's elements reads that formal. Library bodies receive the same analysis as user functions. Intrinsic
costs use resolved compiler identities. Dynamic growth, formatting, managed
copies, closure construction and recursive boxes retain allocation costs;
unknown storage conditions remain conservative. Defaults, defers and known drop
hooks contribute effects even on early exits. Allocation diagnostics preserve
the transitive allocating operation as a witness.

An allocation permission alone does not certify absence of failure or other
unproved costs. Declarations and inferred callback conversions are verified after
helper discovery, including unreachable checked declarations. Lowering checks
introduced intrinsic costs against demanded summaries. Broader storage proofs,
unsupported lifecycle facilities and the public strict profile remain
unimplemented.

`int` is the mathematical integer type, distinct from `int64` in signatures,
containers and generic arguments. Unannotated integer literals default to `int`.
Arithmetic is arbitrary precision: word-sized values promote to a big integer
when their exact result exceeds the signed 64-bit range. `int` has no `.min` or `.max` members.

Explicit `int8` through `int64` and `uint8` through `uint64` retain wrapping
arithmetic. Floating types are `float32` and `float64`; text is `string`. The
implementation's short names (`i64`, `u8`, `f64`, `str`, `byte`) are rejected. Literals in an explicit
numeric context must fit that type exactly. A call parameter supplies that context
to `if` and `match` branch values, just as a binding annotation does. In `=?`
and `not=?`, array, record and dictionary literals take their element or field
types from the typed operand on either side. Mixed `int`/fixed-width arithmetic
uses `int`; a literal beside a fixed-width operand can take that operand's type.
Implicit conversions involving `int` preserve the value, checking narrowing at
runtime (or diagnosing known constant failures). `as` and type calls use those
same checks. Float-to-integer conversions (`int(f)`, `int64(f)`, `f as uint8`)
truncate toward zero and keep the value: NaN, an infinity or a value outside the
target's range fails a check (`the float is above the int64 range`; a constant one is a
compile error) and never saturates;
exact decimal and fraction conversions to integers also truncate toward zero,
without rounding through a float. `int`-to-float retains the usual rounding. Conversions keep the value:
a narrowing between fixed widths, explicit (`uint64(x)`, `x as uint8`) or implicit
(`let n:uint64 = xs.length`, `let b:int8 = w` after `if -128 <=? w <=? 127`, a
`uint64` index or slice bound, an argument or result), is a proven conversion: the facts that
prove a refinement prove it, an unproven one is checked when it runs (`value does not fit int8`),
and a refuted one is a compile error (`w does not fit uint64`). Keeping the bits has its own
spelling: `wrap<uint8>(x)` is the integer modulo 2^8 (two's complement for a signed target, and
the low bits of an `int`), so `wrap<uint64>(int64(-1))` is `18446744073709551615`;
`x transmute float64` reads the bits of an integer or float as another type of the same width. Among overloads, a narrowing is
the last resort. A comparison between two widths (`i:uint64 <? s.length`) compares in the left
operand's width, the right operand taking the same proven conversion. Mutable arguments and
containers require matching element types: an `int` local is not an `@int64` place. Two mutable arguments in one call
must be disjoint: the same binding, a parent and its field/element, or possibly
equal indices of one array are rejected. Distinct fields and distinct constant
indices are accepted. An `@` parameter may be its caller's global or captured
variable, so passing it together with one is rejected too; distinct `@`
parameters of one function are disjoint, and writing one keeps what is known
of the others.

Floats are strict IEEE 754 binary32 and binary64. NaN, the infinities, signed
zero and subnormals are ordinary values, not traps: `1.0/0.0` is `inf`, `0.0/0.0`
is NaN, `-0.0 =? 0.0` is true while `1.0/-0.0` is `-inf`, and NaN is unequal to
everything, itself included. Results round to nearest, ties to even, and
arithmetic is never reassociated or contracted into fused multiply-adds, so a
float expression gives the same result on every CPU target and optimization
level (only the sign and payload of a NaN may differ).
Reductions run in a fixed order: `sum` of a float array adds pairwise halves,
`loop` accumulations add left to right, matrix products add each element's
products in order, and parallel work never reassociates (see "Parallel CPU
work"). Sorting floats (`sort`, `sorted`, float `key=`, tuple keys with
float parts, `min_by`/`max_by` keys) uses IEEE totalOrder: −NaN, −∞, the
negative numbers, −0.0, 0.0, the positive numbers, ∞, NaN. `min` and `max` of
floats are IEEE 754-2019 minimum and maximum in either argument order: a NaN
gives NaN, and −0.0 is below 0.0; an array's `min` and `max` give NaN when any
element is NaN. `floor`, `ceil`, `trunc` and `round` keep the sign of a zero result
(`ceil(-0.5)` is `-0.0`), and `sign` returns a zero or NaN unchanged.

Four settings (see "Directives") change the float policy of a scope.
`$fast_math` permits reassociation and contraction (the backends do neither
yet, so it currently changes no result). `$no_nan` makes every float operation
in its scope that could produce a NaN (`∞-∞`, `0*∞`, `0/0`, `∞/∞`, `sqrt` or
`log` of a negative number, `sin` of an infinity, `pow`) an obligation, and
`$no_inf` does the same for infinities (an overflowing `+`, `-`, `*` or `/`, a
possibly zero divisor, `log(0)`, `exp`, `pow`, a `float32` narrowing, a large
`int` converted). `$finite_floats` (lib/directives.dewy) is both. Values that
enter the scope (parameters, fields, elements, call results) are taken to obey
it. Guards on locals and constant operands prove most obligations:

```dewy
$finite_floats
ratio=(a:float64 b:float64):>float64=>{
    if 1.0 <=? b and -1e300 <? a <? 1e300 return a/b   # proven: no check
    return 0.0
}
average=(total:float64 n:float64):>float64=>total/n   # unproven
```

An unproven one follows the obligation settings like any other: a runtime
check of the result (“produced an infinity under `$no_inf`”, exit 101) under
`$runtime_checks` and today's default, a compile error under
`$runtime_checks=false`.

`let cursor = @xs[i]` declares a local place: reads and writes of `cursor` read
and write `xs[i]`, with `i` evaluated once at the declaration. A local place can
name a whole variable (`let p = @xs`: `p.push(4)` changes `xs`), or an element,
a dictionary entry (`@table[k]`) or a field (`@r.a`) of a local variable; each
access checks the index or key at run time. Deeper routes
go to an `@` parameter instead. `@` of a function value is still its handle.
A function gives back a value: `return @a` is an error.

Lengths retain their current `int64` type. An `int` index uses the ordinary bounds
checks. `to_int(text)` returns `int | none`, parsing integers of arbitrary size: an
optional sign, then decimal digits (spaces, `_` and `0x` give `none`). More
decimal digits than `max_digits=` allows (a million unless given; zero: no
limit) also give `none`, since converting them takes time that grows faster than
their length (CVE-2020-10735). Decimal text converts both ways by divide and
conquer, in about the time of a few multiplications of that size.
`from_text<int>` and integer fields in parsed records and containers preserve
the same arbitrary precision. Printing, interpolation and
`string(value)` format `int` as decimal. Mathematical integers are not yet
supported in shaders; shader integer values need explicit fixed-width types.

Scalar integer annotations can carry checked refinements:

```dewy
positive = int64<(>? 0)>
quotient = (n:int64 d:positive):>int64 => n//d
identity = (n:int64):>int64<(=? n)> => n
```

Where the refinement is a single comparison or test of the value, write the
partial operator (`int64<(>? 0)>`, `int64<(>=? a)>`); keep a lambda
(`int64<i => i >=? 0 and i <=? 4>`) for several conditions. A lambda binder is
local to its predicate. A parameter may use its own name
(`d:int64<d >? 0>`); conjunctions,
one-direction comparison chains, scalar exclusion (`int64 & ~0`), and membership in literal ranges are also
supported. Bounds may use integer literals, fixed-width `.min`/`.max`, other
scalar value parameters of the same representation, an array or string
parameter's length (`i:uint64<(<? b.length)>`, `n:uint64<(<=? text.length)>`), or
stable local bindings, and on a signed integer each may add or subtract a
constant (`at:int64<0 <=? at and at+4 <=? b.length>`). A string is refined by its length in graphemes
(`nonempty = string<length >? 0>`); an ASCII literal's length is known when compiling.
Predicates cannot contain calls or other arithmetic.

An integer literal in a type position is its singleton type, and a union of
integer singletons is an `int64` whose value set is its invariant: `s:-1|1`,
`:>-1|0|1`, `Sign:type = <-1|1>`, `answer:42`. Storing into one is the same
obligation as any refinement. On an integer, `s is? 1` is the comparison
`s =? 1`, `s is? -1|1` tests each member, and `n is? int64<(<? 100)>` tests the
refinement. At most 24 values may be missing between a union's least and
greatest members.

A string literal in a type position is likewise its singleton, and a union of
them is an enumeration: `BasePrefix:type = '0b' | '0t' | '0x'`. Its value is one
word at run time, so `p =? '0x'`, `p is? '0x'` and `match` compare words, and
its text appears only where it meets a string (printing, interpolation, a
`string` parameter, string methods such as `p.upper()`). A member literal stores
as it is, another literal is a compile error, and any other string is checked
when the program runs. On a string, `head is? BasePrefix` compares it with each
member. Literal unions mix with each other and with other types
(`<1 | 2 | "fast" | "slow">`, `'auto' | int64`): `m is? 1` and `m is? "fast"`
test the member and its value. A literal-typed parameter specializes an overload: `((n:int64 d:0):>DivZero => ...)
& ((n:int64 d:int64 & ~0):>int64 => n // d)` sends a literal argument to the method
whose values hold it, ahead of a plain integer method, and the call has that
method's result type; `(mode:'loud' ...)` and `(mode:'quiet' ...)` do the same for
strings. `loop m in members(U)` unrolls over a literal
union's members in the order the union was written, each typed as its own
singleton, so `if text =? m return m` returns a `U`. Literal unions are
ordinary type arguments: `Box<'tokens'|'ast'>`, `array<'a'|'b'>`.

A refuted obligation is a compile error. An unproven obligation becomes an
ordinary runtime check that panics on failure; a proven obligation emits no
check. Annotated local initialization and replacement, arguments, and results
use these checks. Arguments are captured in evaluation order and checked before
invocation. A result's references to value parameters describe their entry
values, even when the function changes its private parameter copies. Generic
instances retain contracts. Callable conversion requires compatible
preconditions and guarantees; it cannot silently strengthen a result promise.
Fixed-width arithmetic still wraps before its result meets a refinement.

Refinements also apply to record fields and array elements. Constructors,
defaults, structural record conversions and stores check the declared contracts.
A field may depend on a sibling, as in `[low:int64 high:int64<(>=? low)>]`;
a field's (or a `let`'s) own name in its refinement is its value, `high:int64<high >=? low>`;
a dependent write checks a private candidate before replacing the record.
Missing initialization must satisfy the contract too. Fixed-width increments
retain runtime checks when overflow cannot be ruled out. `xs.swap(i j)` keeps an
element refinement without a proof per element.

`array<int64 length <? 10>` is a dynamic array with a checked length contract;
`array<int64 length=10>` remains a fixed-size array. Length-changing operations
check a private candidate before publishing it. `addr` is a nonnegative index
below `2^48` on native targets and `2^32` on WebAssembly. Arithmetic does not
automatically preserve this range. A returned refinement may
project a mutable parameter's final length, for example
`append=(@xs:array<int64> x:int64):>addr<(<? xs.length)>=>{...}`.
References to by-value parameters still describe their captured entry values.

Mutable `@` access requires an equivalent storage contract. A dependent record
must be passed as a whole so its field updates retain invariant authority.
Raw mutable access cannot expose refined storage; changing a container's element
contract through an alias is rejected. Captured lexical dependencies remain
unsupported. Parameter-dependent contracts nested inside element types, and
projected mutable postconditions with deferred cleanup, are conservatively
rejected. There is no public strict-lane spelling.

Static evidence can follow transitive integer comparisons, constant-offset
addition, subtraction and literal scaling when their intermediates fit, and facts supported by
both sides of a branch. Range loops use their captured endpoints. While-loop
invariants are validated across entry, condition effects, continues and exits;
bounded widening and narrowing fall back to unknown when analysis exhausts its
budget. Assertions never supply assumed loop invariants. Calls preserve facts
only when a settled effect summary rules out interference.

`$proof` marks an erased procedure. Its fact-only result is checked at every
normal exit, including bare returns:

```dewy
$proof
ordered=(a:int64 b:int64<(>=? a)> c:int64<(>=? b)>):><a <=? c>=>{
    $assert a <=? b
    $assert b <=? c
}
```

Proofs may contain static assertions, branches, bare returns and direct calls
to other proofs; dependencies must be acyclic. Only direct statement calls are
allowed, including imported and generic proofs. Arguments and conditions must
be pure fact terms. Runtime calls, globals, loops, defaults, place parameters
and unsafe assumptions are rejected. Preconditions and exit propositions must
be statically proven; there is no runtime fallback. Definitions and calls erase
after checking, while callers retain facts about the evaluated arguments.

Result arms can attach facts to value parameters, for example
`positive=(a:int64):>true & <a >? 0> | false & <a <=? 0>=>a >? 0`.
Nominal union arms and optional arms support the same `T & <facts>` spelling;
`void & <facts>` publishes an unconditional postcondition. Each normal exit
must establish its arm's propositions. This initial subset requires static
exit evidence and rejects place parameters and deferred cleanup. Facts become
available when the caller tests the result's arm. Reassigning the result or a
dependent argument cannot transfer old facts to the replacement. Joining paths
retains only common evidence. `$prototype` remains unsupported.

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
`//` and `%` reject floating operands; `(a / b).floor()` floors a float quotient.
`mod(a b kind='trunc')` gives the remainder with the dividend's sign (C's `%`)
and `kind='euclid'` a remainder that is never negative; `kind='floor'`, the
default, is `%`. It takes `int` and `int64` operands, and a divisor proven
nonzero, as `%` does; `mod(x y)` of floats is floored.
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

Comparisons use `=?`, `<?`, `>?`, `<=?` and `>=?`. Comparisons chain in one
direction: `0 <? x <? 10` is `0 <? x and x <? 10`, each operand evaluated once
and later ones only while the chain holds. A chain rises (`<?`, `<=?`) or falls
(`>?`, `>=?`), and `=?` fits either; mixing directions, or chaining `not =?`,
`is?` or `in?`, is an error. A parenthesized comparison is a bool:
`(a =? b) =? c` compares it with `c`. Boolean expressions use `and`,
`or` and `not`; `a nand b` is `not (a and b)`, and `nor` and `xnor` negate `or`
and `xor` the same way, at their precedence. A literal coefficient multiplies the name or parenthesized
expression after it (`2x`, `2(x+1)`); an identifier followed by parentheses is a
call. Other juxtaposition is not defined here. A semicolon attached to an expression, `f();`, discards its result; an unattached
`;` (after a space or on its own line) is an error.

`^` raises a value to a power and associates right: `2^3^2` is `2^(3^2)`.
It binds above multiplication, literal coefficients and unary minus, so `2x^2`
is `2*(x^2)` and `-2^2` is `-(2^2)`. Use `xor` for bitwise exclusive-or.
Integer powers use a nonnegative `int64` exponent. `int` powers check each
product; fixed-width powers retain wrapping multiplication. A negative constant
exponent gives a `rational`, `2^(-2)` is `1/4`; a negative runtime exponent panics
with guidance to use an explicit rational or floating base. Float powers use the inherited
floating math library. `BigInt` powers remain exact for nonnegative exponents;
`rational` supports signed exponents. All these types define zero to the zero
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
spells degrees. Fractions use `rational`, and quantities also support machine
integers, checked `int`, `BigInt`, `float32`, and `float64`. A floating annotation rounds an
exact scale to that representation.

Addition, subtraction, and comparisons require identical dimensions.
Multiplication/division combine dimensions; powers require a constant integer
exponent, and `sqrt` halves powers. Powers may be fractions: `sqrt(Hz)` has
`Time^(1/2)`, so a noise density is `V/sqrt(Hz)`, and types can say
`Time^(1/2)`. Divide by a unit to get a dimensionless count in that unit.
Annotations, generic functions, overloads, arrays, records, and conversions
preserve dimensions. Ordinary conversions cannot add or remove a dimension;
`transmute` can explicitly change it while preserving the numeric representation.

A quantity prints with a unit chosen from its dimension and magnitude:

```dewy
from units import m, kg, J
printl"{1500m} {3000m} {300ms} {4500J} {20m/s} {2kg*m/s}"  # 1500 m 3 km 300 ms 4500 J 20 m/s 2 N*s
let d:float64 * Length=1500m
printl"{d} {d/1000}"  # 1.5 km 1.5 m
```

Each kind has a list of candidate units: time `ns µs ms s min h`, length
`nm µm mm m km`, mass `mg g kg`, and SI prefixes `n` to `G` for amperes,
moles and the named units `Hz N Pa J W C V Ω`; temperatures print in `K`,
angles in `°` and luminosity in `cd`. A float prints in the largest candidate
not above its magnitude. An exact value prints in the largest such candidate
that keeps a whole count (`2.5m` is `2500 mm`), and otherwise in the candidate
with the simplest fraction (`m/3` is `1/3 m`). Zero prints in the kind's own
unit (`0 s`). Other dimensions print in canonical units, using one named unit
where that needs fewer factors (`m/s^2`, `N*s`, `kg/m^3`, `V/Hz^(1/2)`,
`°/s`). Text from `string(x)` is the same. A format spec such as `{x:.2f}`
formats the canonical number alone.

`x as unit` converts a quantity to a constant unit of the same dimension:
`30cm as inches` prints `1500/127 inches` and `25m/s as km/hour` prints
`90 km/hour`. It changes only how the value prints: comparisons and counts are
unaffected. The unit stays through scaling and sums (`(l as mm)*2`), but not
through products of quantities.

Temperatures in `°C` and `°F` (from `units`, beside `K`) count from an offset
zero:

```dewy
from units import K, °C, °F
let start=20°C
let later=start+15°C       # 35°C: a literal added to a point is a difference
let rise=later-start       # 15°C: point - point is a difference
printl"{rise as °F} {later as °F} {start*2} {start/°F}"  # 27°F 95°F 40°C 68
```

A temperature is a point unless it is the difference of two points. Where a
difference is needed, a point is read as one in the unit it was written in:
`start + 20°C`, `t += 5°C`, and the right side of `-` when it is a literal
(`start - 5°C` is `15°C`). Subtracting a temperature that is not a literal
gives a difference, also for plain kelvins (`a - b`); the difference prints in
the first point's unit. A product or quotient with a plain number scales the
reading in the value's own unit (`20°C*2` is `40°C`). With other quantities a
temperature counts as its difference, and dividing by a temperature unit gives
the reading in that unit (`t/°C`, `t/K`). Comparisons compare points. `as` keeps
the scale a value was written in: `(20°C as °F)` prints `68°F`, but read as a
difference it is still 20 K (`36°F`), so `start + (20°C as °F)` is `40°C`.
A plain `float64 * Temperature` annotation holds kelvins and drops the offset
scale. Calendar durations remain open. `sleep` takes a time, `sleep(300ms)`, and waits whole nanoseconds;
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
is `-1`. Prefix `~` is `not` binding as tightly as unary minus: `~flags & 3`
is `(not flags) & 3`. `<<` and `>>` take a nonnegative `int64` count; right shift rounds down
for negative values, so `bigint(-3) >> 1` is `-2`. Shifting beyond all magnitude
bits yields `0` for nonnegative values or `-1` for negative ones. Negative shift
counts panic. Shift compound assignments (`<<=`, `>>=`) work too, as do
`&=`, `|=`, `and=`, `or=` and `xor=` (on integers, booleans and sets).
`a and= f()` means `a = a and f()`, so on booleans `and=`/`or=` short-circuit:
`f()` runs only when it can change `a`.

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
from rational import parse_rational
kelvin=(celsius:rational):>rational=>celsius+273.15
main=():>void=>{
    let half=1/2
    printl"{half+1/3}"  # 5/6
    printl"{(2/3)^(-3)}"  # 27/8
    printl"{kelvin(20)}"  # 293.15
    printl"{0.1/3} {1/3+0.5}"  # 0.0(3) 5/6
    printl"{rational("-7/3").floor()}"  # -3
}
```

`rational` is the exact fraction type, built in like `int`. Dividing two
integers or `BigInt` values with `/` gives a `rational`, including mixed
signed/unsigned words, and the full-width values are preserved. `4/2` is still
a fraction value, formatted as `2`. Use `//` for a whole-number quotient.
Floating operands retain floating division. Decimal literals are exact
fractions unless their context is floating: `0.1 + 0.2 =? 0.3` is true, `1.0/2`
equals `1/2`, and `1.25e2` is `125`. A float annotation, a floating operand beside the
literal, a `float64` parameter or field, or a later float written to the
unannotated binding the literal initializes makes it a `float64` when compiling:
`let acc=0.0` followed by `acc+=dt` with `dt:float64` declares a `float64`,
inside a lambda too.
Among overloads, a decimal literal takes an exact parameter before a float one.
An integer promotes to `rational` wherever one is
expected: arguments, results, record fields and container elements.
Constant fractions and decimal literals are reduced at compilation; a constant
zero divisor of `/` is a compile error.

`rational(numerator denominator)` accepts integers, `BigInt` values, or
decimal integer text for its parts; the denominator defaults to one. A single
string accepts an integer or `numerator/denominator`. `parse_rational(text)`
(imported from `rational`) returns `rational|none` for invalid input, including
a zero denominator. Decimal points and whitespace inside the string are not
accepted.

Values keep a positive denominator and coprime `int` parts. Zero is `0/1`.
A part is a machine word while it fits and grows into a big integer beyond, so
arithmetic never overflows. Division and the constructor normalize signs and
common factors. Read `.numerator` and `.denominator` without assigning
noncanonical parts directly.

Values print the way they were written. A whole number prints as an integer. A
value made from decimal literals (and integers) prints as a decimal: `0.1+0.2`
is `0.3`, `kelvin(20)` above `293.15`. When its digits never end, the repeating
block goes in parentheses: `0.1/3` is `0.0(3)`, `2.5/7` is `0.3(571428)`; a block
longer than 64 digits prints as a fraction instead (`0.1/97` is `1/970`). A
value made from written fractions (`1/3`, `rational(1 4)`) prints as
`numerator/denominator`. Where both take part, it prints as a decimal when the
digits end, otherwise as a fraction: `19.99*(8/100)` is `1.5992`, `1/3+0.5` is
`5/6`. How a value prints never changes the value: `0.5 =? 1/2`, and both are
the same dictionary key. `rational<int64>` prints the same way.

A `rational` binding without an annotation that a loop carries through `*`, `/`
or `^` gets a warning: its parts can grow every iteration (`balance*=1.05`,
Newton's `x=(x+2/x)/2`, `step/=2`), so a long loop slows down and prints a huge
number. The value stays exact; annotate `float64` (or another explicit
representation) where it is declared if an approximate result is fine (the
editor offers the fix). Sums (`total+=0.1`), whole-number factors (`n*3`),
lone reciprocals (`1/x`) and annotated bindings (`let q:rational=...`) do not
warn.

Arithmetic `+`, `-`, `*`, `/`, comparisons, and unary minus work with fractions,
`BigInt`, and integers in either order. `//` returns an `int` floor quotient;
`%` returns a `rational` remainder with the divisor's sign. `.divmod(other)`
returns both. `.floor()`, `.ceil()` and `.round()` return `int`, and `int(q)`
truncates toward zero. Exact numbers round as people do, a half away from zero:
`round(5/2)` and `round(2.5)` are 3, `round(-2.5)` is −3. Floats follow IEEE
754 instead, a half to the even neighbour: `round(f)` is `2.0` for
`f:float64=2.5`. Both take `ties=` to choose the rule: `'away'`, `'even'`,
`'zero'` (toward zero), `'up'` (toward +∞) or `'down'` (toward −∞), as in
`round(f ties='away')`. `.abs()`, `.reciprocal()` and `.pow(signed_exponent)` return
fractions. Runtime division by zero, a zero denominator and negative powers of
zero panic. Zero to the zeroth power is one. Copies are independent, and
normalized values can be dictionary keys.

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

`rational(x)` of a `float32` or `float64` is the float's exact binary value
(`rational(f)` with `f:float64=0.1` is `3602879701896397/36028797018963968`);
NaN and infinity panic. Floats never become fractions implicitly. Inferred
decimal bindings hold fractions unless a float is written to them later, which
makes them `float64` from the start; annotate `float32` explicitly.

`rational<int64>` is the explicit fixed-width form: normalized `int64` parts.
Its `+`, `-`, `*`, `/`, `^` and negation return `rational<int64> | Overflow`,
`Overflow` when the exact result does not fit the parts; handle it with `is?`
or `match`. Comparisons and printing work as for `rational`. A word integer or a
constant fraction initializes it (`let third:rational<int64>=1/3`), and it
widens to `rational` or a float wherever one is expected. A runtime `rational`
narrows explicitly: `rational<int64>(q)`, or `rational<int64>(numerator
denominator)` like `rational(...)`, returns `rational<int64> | Overflow`.

```dewy
main=():>void=>{
    let total:rational<int64>=0
    loop i in [0..30) {
        let next=total+1/3
        if next is? Overflow exit(1)
        total=next
    }
    exit((if total =? 10 42 else 2))
}
```

[The exact-fraction example](../examples/exact_rationals.dewy) computes
harmonic sums, dice probabilities and exact time steps.

## Records and collections

A scalar nominal record can declare a compiler-only `$__drop__` method with
no explicit parameters and a `void` result:

```dewy
let released:int64=0
Ticket=type of [id:int64
    $__drop__
    release=():>void=>{released+=id}
]
```

Without a copy hook, such a record is move-only. Fresh construction creates an owner; a whole local
can transfer at a proven last use, including into a direct function parameter
or return value. A later read, an alias or a loop backedge can prevent that
proof. `.copy()` cannot duplicate a drop-only owner. Every initialized owner
runs its hook once at lifetime end, including replacement, return, loop exits,
compiler-controlled panic and process termination through `exit`. A construction
that fails before completion does not run the incomplete value's hook.

Inline records may contain other owning records. Cleanup runs the outer hook
first, then fields in reverse order. During construction, only completed fields
are cleaned up on failure; the incomplete outer hook does not run. Structural
copyability includes every field; synthesized moves recursively transfer fields.
An unboxed field of a structural owner can transfer at its own proven last use.
Sibling fields remain usable and are cleaned up on the path that retains them,
including panic and early exits. A later read of the moved field or the whole
record prevents a move-only transfer. Fields beneath an outer lifecycle hook
cannot transfer independently, because the hook may read them.

Optional owner fields use their presence tag: `none` drops nothing, and a
present value transfers or copies through its payload's lifecycle. Recursive
records use owning boxes with exactly-once cleanup. Copyable recursive records
copy their boxes eagerly; completed children remain protected if a later box
allocation fails. Move-only payloads make their recursive container move-only.

Fixed arrays of owners copy eagerly through element hooks and transfer elements
through move hooks. Cleanup runs in reverse element order, including only the
completed prefix when construction fails. Stable readonly iteration borrows the
elements in both default and release builds. A move-only element makes its array
move-only; nonempty owner arrays require explicit element construction.

Growable arrays and dictionaries can also own inline resource elements. They
copy live elements eagerly; copied dictionary keys are hashed and inserted again.
Move-only elements make their container move-only. Growing a buffer and compacting dictionary entries relocate storage without
calling copy or move hooks. `pop` transfers its result; replacement, removal and
`clear` drop removed values exactly once. Vacant dictionary slots are not live
values, even if their bytes are zero. Array cleanup visits live elements in
reverse order. Stable readonly iteration borrows elements without copying.
Resource arrays must construct new elements with `push` or `insert`, rather
than expose uninitialized elements with `resize`.

The current implementation requires inline record/scalar/fixed-array resource
elements and a proven no-failure drop summary. Scalar mutation and literal-string logging are supported; unknown calls
and potentially failing formatting are rejected. Hooks cannot be called or
referenced directly. `$__copy__` and `$__move__` methods also take no explicit
parameters and return the same nominal type. An explicit `.copy()` runs its
hook even on a fresh temporary, which is then cleaned up separately.
Copy borrows a readonly receiver;
move consumes the source and skips its outer drop. Both currently require a
proven no-failure summary. Hooks may change the abstract value: the compiler does
not assume their results equal their inputs. Inherited roles run once on the
parent portion, composing the child's added fields; a declared child
role overrides that role. Generic records instantiate their declared hooks for
each concrete type; structural generic records compose their fields' hooks.
Generic functions cannot implicitly duplicate a move-only type argument.
Global owners and foreign entry points with owners remain unsupported.
Ordinary records and collections keep their existing value and copy-on-write behavior.

A snapshot closure capture copies its value or transfers it at a proven last
use. A move-only capture makes the closure move-only, including when stored in
a record or array or passed through a generic function. Copying a copyable
closure runs its captures' copy hooks; cleanup drops owned captures once, in
reverse order. Callable conversions cannot erase these ownership restrictions.
An explicit `$capture @owner` borrows the owner's place without taking ownership.
Borrowed owner captures currently require a local closure used only by direct
calls; copying or escaping such a closure is conservatively rejected. Generic
closure literals with owner captures and partial application of owners remain
unsupported; ordinary generic functions and nongeneric closure literals work.

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
record type and its defaults, and so does a positional `[20]`, which gives the
fields in order, as `Point(20)` would: in an annotation, an element of
`array<Point>`, a dictionary value or an argument. A field without a default must
be given, except an optional one (`next:Node?`), which defaults to `none`; leaving
out a required field is an error naming the field. When every field has a default, the type's
bare name where a value goes constructs it, as `Origin()` would: `let p=Origin`.
The name stays the type in `Origin[...]`, `Origin.member` and `is? Origin`.
Without an expected type, named fields infer an anonymous record. Anonymous record types agree by field names and types, even
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
need defaults. A default may use earlier fields, as in
`Span:type=[start:int64 stop:int64=start]`: given values are evaluated first,
in written order, then the defaults in field order. Inline fields may also refer to a generic function's type parameters.

Records can contain optional values of their own type, including through other
records and unions. Lists and trees keep ordinary value semantics:

```dewy
Node:type=[value:int64 next:Node?=none]
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
    let next=<T>(value:T $capture count)=>{count+=1; [value=value count=count]}
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
any value. A type's method that reaches no member, nor calls one that does, is
static: it is also called on the type, as `Span.unit` for a row
`unit=():>Span=>Span(0 1)`. Copies of an object carry its methods and stay
independent. Printing an object shows its fields, not its methods. A type's
methods are not stored in its values and are not constructor fields; methods of
a generic type use its type parameters, and imported types bring their methods.
A literal's methods keep what they capture from the enclosing function, as
closures do. A function written inside a method may read members but cannot
change them yet. Methods are not values yet (`@c.increment` is an error), and
types with methods are declared at module level. Minted types such as `type of
error & [...]` take methods too, which also reach the members the type inherits,
from a parent in any module;
a method of a type with minted children cannot change its object yet.

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
library's default hashing. `hash` gives the same value in every run, but a
dictionary places its keys by a hash keyed with a secret drawn from the operating
system once per process (a custom hash's result is mixed under it), so keys
crafted to collide cannot slow it down; iteration follows insertion order
regardless.

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
`.insert(value i)` (inserts before `i`), `.clear()` and `.truncate(count)` (a
negative count panics). `fill(value count)` makes an array of `count` copies of
`value`: `fill(false n)`, `fill(uint8(0) 512)`, and with an annotation choosing
the element type, `let row:array<int64>=fill(0 n)`. `xs[1..3)` is an
exclusive-end slice; `xs[1..2]` includes index 2. A slice's bounds are proven
like an index (or checked under `$runtime_checks`). `xs[$clamp a..b)` instead
truncates them to the receiver, as Python's slices do: each bound is clamped
to `0..xs.length` and the end to at least the start, so `xs[$clamp 1..10)` of
three elements is `xs[1..3)` and `xs[$clamp 5..9)` is empty.

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

`[int64 string]` is a fixed-length array with a type per position, Dewy's form
of a tuple: `let entry:[int64 string]=[7 "seven"]`. A constant index reads that
position with its own type (`entry[0]` is an `int64`, `entry[1]` a `string`);
any other index gives the union of the element types (`int64|string`) and is
proven in bounds like an array index. `.length` is the number of positions,
and `let [n name]=entry` unpacks it. It prints as an array, `[7 "seven"]`, and
is how implementation-language tuples such as `(str, u8[])` appear in Dewy.

A literal of sibling records (types minted in one family) keeps their
positions: with `Circle` and `Square` minted from `Shape`,
`let shapes=[Circle[r=1] Square[s=2]]` is a `[Circle Square]`, so `shapes[0].r`
reads a `Circle`, and it is accepted where an `array<Shape>` is expected. When
the rest of its block writes the binding (a push, an element store, `@shapes`,
any method call on it), its type is instead the union of its elements,
`array<Circle|Square>`. Straight-line code still knows its contents: after
`shapes.push(Circle[r=3])` in the same block, `shapes[2]` is a `Circle`. That
knowledge ends at any other write, inside loops and closures, after a push in a
branch, and past eight positions.

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

`+` never joins arrays: `[xs... ys...]` combines them, `xs.extend(ys)` appends
in place and `xs.push(y)` adds one element. On arrays `+` is reserved for
elementwise math; the dotted `.+` adds element by element today.

`out.extend(source[lo..hi))` appends a contiguous slice directly from the
captured source, avoiding a temporary slice allocation when the source and
destination have different roots. Bounds are checked before evaluating the
destination; both arrays retain independent value semantics. Self-appends keep
the slice-copy path so appending a small selection does not force a copy of the
entire source. Matrix slice reads use the same bulk append path for each row.

`xs.is_empty` tests for no elements, `xs.count(value)` counts the elements equal
to a value and `xs.count(f)` those a predicate accepts; `xs.any(f)` and
`xs.all(f)` test a predicate. Without a predicate, `any` and `all` apply only to
an array of bools (`all(flags)`; the idiom for numbers is a comparison per
element, `all(xs .>? 0)`, part of the planned elementwise operators). There is no
`zip` or `enumerate`: a compound loop walks several sources in step,
`loop x in xs and y in ys {...}`, and `loop i in 0.. and x in xs {...}` counts
alongside (`[loop x in xs and y in ys [x y]]` collects pairs).

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
strings count grapheme clusters, and a custom container's `end` is its `len` minus one.
`xs[end]` compiles exactly as `xs[xs.length - 1]`, so whatever proves one proves
the other. These forms also support array and custom
container updates. Ordinary array updates capture indices before the right-hand
side, then locate the destination again if that side resizes the array.

`new` inside brackets inserts an axis of length one, as NumPy's `newaxis` does,
on arrays, nested arrays and strings: `xs[new]` (or `xs[new ..]`) is `[xs]`,
and `xs[.. new]` wraps each element, `[[x0] [x1] ...]`. With more axes, spell
a whole axis `[..]` and place `new` where the axis goes: for `m = [[1 2] [3 4]]`,
`m[.. new]` is `[[[1 2]] [[3 4]]]` and `m[[..] [..] new]` is
`[[[1] [2]] [[3] [4]]]`. Indices and slices can sit beside it, `m[end new]` is
`[[3 4]]` and `m[[..] 0 new]` is `[[1] [3]]`, each `end` counting its own
axis. Axes after the last entry are kept whole. The result is a new nested
array; `new` on an NDArray is not supported yet, and the selection cannot be
assigned to.

`end`, `new`, `none` and `void` are reserved: none of them can name a
variable, function, parameter, field, method, loop or pattern binding, or import
alias. (`extern` and `intrinsic` are ordinary names; the forms are the `$extern`
and `$intrinsic` metatags, under "Foreign functions".)

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

A direct call can borrow an exclusive-end mutable slice, such as
`swap(@values[..mid) @values[mid..])`. Its callee must only inspect lengths and
read or write scalar elements, including through other checked direct calls;
it cannot resize, copy or retain the borrowed array. Bounds are checked, and
multiple mutable arguments from one array must have provably disjoint ranges.
Stable matching endpoints and ordered constant endpoints establish that proof.
Ordinary slice reads still produce values.

A scoped binary `parallel_range(2 ...)` can pass such disjoint slices to its
two branches. Each branch must be a single direct call selected by the index
being zero, followed by `return 0`. Mutable array captures stay borrowed until
both branches finish; they cannot escape into a stored or returned closure.
Read-only array inputs may be shared between branches without copying. The
checked callee must not mutate, copy or retain those inputs, and their ranges
must not overlap a writable range. Unknown footprints and overlapping writable
ranges are rejected.

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
A float key is never NaN, which equals nothing, so its entry could never be
found again: each float key given to a dictionary (stored, looked up, removed or
written in a literal) is an obligation. Literals, converted integers and keys
under `$no_nan` are proven; any other follows the obligation settings.

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

An in-place update such as `values[key] += 1`, `values[key].x = 5` or
`values[key].push(v)` changes an existing entry; a missing key fails as
`values[key]` does, and nothing is inserted. Count with
`if key in? counts counts[key] += 1 else counts[key] = 1`.

`values.pop(key)` removes an entry and returns its value; a missing key fails
as `values[key]` does. `values.pop(key default=none)` returns the default for a
missing key instead. `values.remove(key)` returns whether it removed an entry.

`totaldict<K V>` is a dictionary with an entry for every value of a finite key
type (a union of literals). Its literal must list every key, and the error names
the missing ones; it has no `pop` or `clear`. A `totaldict` parameter takes a
literal, another `totaldict`, or a `const` dictionary whose literal has every
key; a `dict<K V>` that may be partial does not pass:

```dewy
BasePrefix:type = '0b' | '0o' | '0x'
const RADIX:totaldict<BasePrefix int64> = ['0b' -> 2 '0o' -> 8 '0x' -> 16]
radix_of = (base:BasePrefix):>int64 => RADIX[base]
```

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

`values.keys` returns the keys as a set and `values.values` the values as an
array, both in insertion order, skipping removed entries. A set has no positions:
`[values.keys...]` collects the keys into an array to index or sort, and
`loop key in values.keys` visits them without making the set. Both results are
independent values: editing one does not change the dictionary, and later
dictionary edits do not change an earlier result.

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
`set[existing... "new"]` preserves the first occurrence of each member,
`set(values)` makes the set of an array's elements, `set"0123"` the set of a
string's graphemes, and
`[existing...]` collects a set's members into an array. `push` adds a member.
Adding an existing member leaves its position unchanged. `remove(value)`
returns whether it removed a member, while `clear()` and `reserve(count)` work
like their dictionary counterparts. `.length`, `has`, `contains` and `is_empty`
inspect the set.

`a | b`, `a & b`, `a-b` and `a xor b` compute union, intersection, difference and
symmetric difference. Results keep surviving members from the left in order,
then any new members from the right. `s.values` is a fresh array of the members,
and `s.sorted` (with `reverse=` and `key=` as for arrays) an array of them in order.
For dictionaries, `d1 | d2` (or `d1 or d2`) keeps every entry of `d1` and adds
`d2`'s new keys; a shared key keeps its position and takes `d2`'s value. Equality and hashing ignore insertion
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
the receiver. `reverse=true` sorts largest first, and `key=` sorts by a key
function, such as a function handle, a closure or a partial operator:

```dewy
Player:type=[name:string score:int64]
by_score=(p:Player)=>p.score
let players=[Player["Ada" 20] Player["Bea" 42] Player["Cal" 42]]
let leaderboard=players.sorted(key=@by_score reverse=true)
players.sort(key=(p:Player)=>p.name.length)
```

Both orders are stable: equal keys retain their original order, so Bea stays
ahead of Cal. The key is computed once per element when
sorting is needed, then cached while integer positions are sorted. Records and
their managed fields keep ordinary independent-value behavior; modifying a
record in `leaderboard` leaves `players` unchanged.

`values.sort_with(less)` takes a comparison function with two arguments for
orderings that depend on both values. It is stable too: values for which neither
argument compares less than the other retain their order. A comparator should
define a consistent ordering; use `key=` when a cached key expresses it.

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

Write a matrix literal with `;` between rows, either standalone or attached to
the element before it, and `;;` between 2-D blocks: `[1 2; 3 4]` has shape
`[2 2]`, `[1 2; 3 4;; 5 6; 7 8]` shape `[2 2 2]` and `[1 2 3;]` shape `[1 3]`.
Rows must have the same length. `[xs; ys]` stacks two arrays as rows.

The shape belongs in the type: `array<float64 length=[m n]>` is a 2-D array,
`array<float64 length=[n]>` a 1-D one. In a parameter, a dimension named by a
word not yet bound binds it, and later mentions check it; an annotated `let`
checks its value's shape. Shapes are compared where values enter: a literal of
the wrong shape is a compile-time error, other values are checked at run time:

```dewy
product=(a:array<float64 length=[m n]> b:array<float64 length=[n p]>)=>a*b
width=(rows:array<int64 length=[r 2]>):>int64=>r   # r is rows' first dimension
```

An n-dimensional array's `.length` is its shape, `[2 3]` for a matrix; there
is no `.shape` member in Dewy code. Internally it is an `NDArray<T>` holding a
flat, row-major `data` array and a `shape` array. Use
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

A `vec2`, `vec3` or `vec4` has its magnitude as the method `v.norm`;
`v.norm(p=1)` is the p-norm (`p` at least 1; shaders have only the default
`p=2`). `.length` always means element count, so a vector has none.

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
matrix; `xs[new ..]` makes it an explicit `[1 n]` row and `xs[.. new]` an
`[n 1]` column, and `m[new ..]` inserts a leading axis into a matrix. Nested
rows of numbers, such as `[[1 2] [3 4]]`, combine as a 2-D operand. In an
elementwise product a `bool` counts as 1 or 0, so `xs .* (xs .>? 0.0)` keeps
the positive elements. Empty dimensions produce empty results when the other dimension is
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

An array of indexes selects those positions of an axis, in order:
`matrix[[2 0] [..]]` takes rows 2 and 0, and assigning to it writes them.
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

`value.to(device)` places a value's arrays on a device, and computation
follows the data. This build has one device: `'cpu'`, which `'best'` chooses,
so placement currently returns the value unchanged.

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

`parallel` visits an array or bounded integer range, and `[parallel ...]`
collects its results in input order:

```dewy
let squares = [parallel i in [0..1000) i*i]
let shifted = [parallel x in squares x+1]
let saved = shifted
parallel @x in shifted {x*=2}
parallel x in shifted {assert(x >=? 2)}
assert(saved[0] =? 1 and shifted[0] =? 2)
```

An ordinary binding is read-only, as in `loop`. A mutable `@x` binding owns one
array element for the body, including its managed fields. Saved copies keep their original values. Other captured variables and
globals may be read but cannot be changed, including through called functions.
Indexed writes to a captured array are currently rejected; use the mutable
element binding. The first implementation accepts one named binding over an
array or bounded range; combined headers, destructuring and filtered parallel
collectors are not yet supported. `return`, `break` and `continue` cannot leave
a parallel body.

The existing `parallel_map`, `parallel_range` and `parallel_update` functions
remain available. Callbacks must be named functions or function literals so the
compiler can check their writes. Arrays, strings and records retain ordinary
independent value semantics. Collection preserves source order, so a subsequent
`sum` uses the same reduction order as the sequential collection. Scheduling
does not reassociate reductions.

Native programs use a persistent worker pool. `SLOPPY_THREADS=2` limits it to
two threads including the caller; `SLOPPY_THREADS=1` runs on the caller. Nested
operations share the same pool, and a caller waiting at a join helps run ready
work. Forks stay local until a heartbeat exposes work to another worker; small
scoped joins use direct calls on the sequential path. Web builds run serially with
the same result order and copy semantics. Parallel work may always execute
sequentially. Its body must be proven nonblocking: sleeps, blocking I/O,
waiting joins, and unclassified foreign calls are rejected, including through
called functions. Use the waiting lane for these operations. This conservative
rule prevents waiting for a sibling that the scheduler may run inline.

`blocks` is inferred; a function can exclude it with `:>T & no blocks`.
`Send` and `Sync` are structural compiler facts. Scalars, arrays, records and
unions compose automatically; raw-storage handles and escaping places do not.
A proven disjoint scoped partition is checked separately. Atomic handles have
shared identity and can cross tasks.

A type opts out with a row: `Counter:type=[n:int64 $send=false]` cannot be
moved into a task (captured, bound or returned), and `$sync=false` keeps it out
of storage that tasks share, such as a module-level binding a `parallel` body
reads. A bare `$send` or `$sync` row claims the property. A claim the structure
already gives needs nothing; one the compiler cannot verify (a raw `ptr<T>`
field, say) needs the unsafe boundary: `$unsafe` on a line of its own before the
type, or as another of its rows.

`atomic(0)` makes an `Atomic<int64>` shared counter. Payloads are fixed-width
integers; `atomic<T>(value)` selects another width. `load`, `store`, `add`,
`compare_swap`, and the existing `get`, `set`, and `set_max` operations accept an
optional compile-time `MemoryOrder` literal: `'relaxed'`, `'acquire'`,
`'release'`, `'acq_rel'`, or `'seq_cst'` (the default). Loads reject release
orders; stores reject acquire orders. `add` returns the new value. The current
native backend implements every order with sequentially consistent instructions,
which is stronger than requested. For example:

```dewy
let hits=atomic(0)
parallel i in [0..1000) {hits.add(1 'relaxed')}
assert(hits.load'acquire' =? 1000)
```

Private synchronized handles need explicit factory values: `atomic(...)`,
`concurrent`, or `spawn`. Zero-filled fixed arrays, omitted fields, and array
growth cannot manufacture these handles; empty containers remain valid.

`CachePadded<T>` has a `value:T` payload and a padded representation: its stride
includes a spare cache line and rounds to 128 bytes. The payload keeps its
natural alignment. Padding a handle pads the handle, not its separate allocation.

Waiting work uses a structured task group on the Linux threads backend:

```dewy
work=(n:int64)=>n*2
concurrent {
    let a=spawn work(21)
    let b=spawn work(20)
}
# a and b are available here: their results, or Canceled / OutOfMemory.
```

The closing brace joins every child. As an expression, `concurrent { ... }`
returns `true` on success or the first exception returned by a child. The first
failure cancels its siblings; joining still waits for their cleanup. Returning
early from the body cancels and joins its children. `concurrent g { ... }` names
a `TaskGroup`; pass it explicitly to helpers that use `spawn(g) expression`.
`cancel(g)` cancels that group and its descendants. Captures and results must
satisfy inferred transfer properties. A task cannot read an unsynchronized
mutable global while its parent runs; capture a value or use an atomic handle.

`Canceled` is an exception value, with US spelling (`Cancelled` produces a
fix-it diagnostic). Cancellation is level-triggered: every later blocking
operation in that scope returns `Canceled`. `sleep`, file and stdin operations,
and process waits include it in their result type; console output (`print`,
`printl`, `console.*`) is not a cancellation point. Use `or_throw` to
propagate it, or handle it explicitly. For optional streaming results, check
`none` (EOF) before checking `Canceled`. Owned process helpers cancel and reap
their child; cancellation of `child.wait` leaves that child owned by its caller.

`within(2s @get(url))` establishes a deadline scope and returns `Timeout` when
its own deadline expires; parent cancellation remains `Canceled`.
`race(@first_lookup(key) @second_lookup(key))` returns the first completed result
and cancels and joins the other task. Neither helper leaves a task detached.
Backend state, cancellation, and deadlines travel implicitly through calls.
CPU work cooperates with cancellation by checking a blocking operation such as
`sleep(0ns)`; an arbitrary computation is not forcibly terminated. Cleanup
(`defer` and drop hooks) is shielded, with a 100 ms grace deadline.

Thread/slot admission failure returns `OutOfMemory`. Ordinary heap allocation
retains the language's environmental resource-failure policy. Other targets
currently diagnose waiting-lane tasks; portable `parallel` remains available.
`Canceled` reaching `main` is an error like any other: it is reported and exits
with its kind's code.

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
declared defaults (`none` for an optional field) and unknown fields are skipped.
A field named twice in one object, and a `\u` escape of half a surrogate pair
without its other half, are errors here and in `parse_json`. A missing field
without a default is a `TextError` naming it:

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
including inherited fields. `type of any` (alone, or `& [fields...]`) mints the
root of a family of its own, which is not an error: `Token:type=type of any &
[line:int64]`, then `Name:type=type of Token & [text:string]`. A `Name` satisfies
a `Token` parameter and keeps its identity there, for `is?` and `match`; a
same-shaped type minted separately is a different type. These declarations are
currently module-level and nongeneric; other nominal parents (`type of int64`)
are not yet supported.

`Name:type = A & B` intersects record types without minting: `Name` has the
fields of both (and of any `& [fields...]`), a field on both sides takes the
intersection of its types (`int64 | bool` and `bool` give `bool`; `string` and
`int64` make the declaration an error), and a later default replaces an earlier
one. A `Name` value passes where an `A` or a `B` is wanted, as those fields.
Intersections are module-level declarations of plain (not minted) records.

```dewy
Empty:type=type of error
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
Method calls forward the same way: `lookup(id).scaled(2)` evaluates the receiver
and then the arguments once, and gives the exception (or `none`) unchanged, or
the call's result.

`TextError` and `JsonError` belong to `error`, as do the file errors and
`SpawnError` below.

A function without a declared result type infers the kinds it throws: each
`return` of an error and each `or_throw` adds its kinds to the result, so
`parse=(text:string)=>{... return ParseError[...] ... return n}` gives
`int64 | ParseError`. A declared result fixes the set instead.

`main` is optional: without it a file runs top to bottom as a script. With it,
the top-level statements run first and then `main` runs by itself, exactly once;
calling `main()` at the top level is an error (recursion inside `main` is fine).

`main` returns `void` or the errors that reach it, an ordinary `void | E` type,
declared or inferred. It gives no exit code: success exits 0, and a script that
needs a particular code calls `exit(n)`. An error reaching `main` is printed on
standard error as its kind and its `message` text field, if it has one
(`error: ParseError: ...`; the rest of a payload may hold secrets, so only a
debug build, `-g`, prints it whole: `error: ParseError[message="..."]`) and ends
the program with
its kind's exit code: 1, 2, 3, … in the order the kinds are declared, or as a
declared result lists them, up to 100 (101 is a failed runtime check). An error type with an `exit_code` field
pins its own code (its default, 1 to 100). The field is an integer refined to
1–100, so a value written to it, as in `Offline[exit_code=code]`, is an
obligation like any other: proven, checked at run time under `$runtime_checks`,
or an error. An error can never report success. `dewy build --exit-codes file.dewy`
prints the table without building.

```dewy
UsageError:type=type of error & [message:string]
Offline:type=type of error & [exit_code:int64=69]
connect=(host:string):>void|Offline=>{
    if host =? "nowhere" return Offline[]
    printl"connected to {host}"
}
main=():>void|UsageError|Offline=>{
    let argv=args()
    if argv.length <? 2 return UsageError["usage: fetch HOST"]
    connect(argv[1]) or_throw
}
```

Without arguments this prints `error: UsageError[message="usage: fetch HOST"]`
and exits 1; `fetch nowhere` exits 69.

## Files, paths and processes

`p"dir/file.txt"` is a path literal and `p(text)` builds a path at run time.
Both make a `Path`, which holds its text in `.path`. A path interpolates as its
text, and `path as string` is that text too, so paths are joined by
interpolation: `p"{root}/{name}.csv"`. There is no `join` method.

```dewy
main=():>void=>{
    let source=p"project/src/main.dewy"
    match source.read_text {
        text:string => printl(text)
        <FileNotFound> => printl"no such file: {source}"
        _ => printl"cannot read {source}"
    }
    printl(source.with_suffix(".udewy"))   # project/src/main.udewy
    printl(source.parent.name)             # src
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
  count. The new contents go to a file beside it, reach the disk, and are renamed
  over it, so a reader or a crash sees the old file or the new one, and its
  permissions are kept. A symbolic link there is refused (`FileError`), not
  followed;
- `mkdir`, `rmdir` and `unlink` give `true`;
- `copy_to(target)` copies the file's bytes and gives the byte count,
  `rename(target)` moves a file or directory in one step, `make_dirs` makes the
  directory and any missing ones above it, and `chmod(0o644)` sets permission
  bits, the last three giving `true`;
- `size` gives the file's byte count, `modified` the `Date` it last changed,
  `walk` every file under a directory (sorted paths, links to directories not
  followed), and `glob"*.dewy"` the sorted paths under it matching a pattern
  (`*` any part of a name, `?` one character, `**` any number of directories).

A failure is `FileNotFound`, `FileAccessDenied`, `IsDirectory`, `FileExists` or
`FileError` (any other failure), and `read_text` adds `InvalidUtf8`. All are
`error`s, so `is? error`, `or_throw` and `match` handle them.

Provisional path methods for durable stores (spellings unsettled): `sync`, `replace(target)` (atomic rename), `append_bytes(bytes)` and `read_at(offset count)`.

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
`stdout` and `stderr` bytes (both drained as they fill, at most 64 MiB each), and
`stdout_text` and `stderr_text` (`string | none`). A child that writes more, or a
pipe that cannot be read, ends the child and gives a `FileError`.

In a web build, files live in the page's memory, and directories exist as the
paths of its files and those made with `mkdir`. Processes are `SpawnError` there.
On Windows, `run` works and `run_silent`, `spawn` and `capture` are not available
yet (`SpawnError`).

## Networking

`import net` gives blocking TCP sockets. Each call waits for its result and
gives a `NetError` (an `error` with a `message`) when the system refuses, or
`Canceled` when its task is canceled: a task waiting in `tcp_accept`,
`tcp_connect`, `tcp_receive` or `tcp_send` wakes up when its group is canceled
or its `within` deadline passes.

```dewy
import net
main=():>void | net.NetError | Canceled=>{
    let server=net.tcp_listen(0) or_throw           # 0: a free port, on loopback
    let client=net.tcp_connect("127.0.0.1" server.port) or_throw
    let peer=net.tcp_accept(server) or_throw
    net.tcp_send(client "hello") or_throw
    let got=net.tcp_receive(peer)
    if got is? none return                           # the client closed
    printl((got or_throw) as string | none)
    loop stream in [client peer] net.tcp_close(stream)
    net.tcp_close(server)
}
```

- `tcp_listen(port host="127.0.0.1" backlog=128)` gives a `TcpListener`, whose
  `port` is the one bound (the system's choice for port 0). `host` is a numeric
  IPv4 or IPv6 address; the default admits only this machine.
- `tcp_accept(listener)` waits for the next connection, a `TcpStream`.
- `tcp_connect(host port)` connects to a numeric address or `localhost`.
- `tcp_send(stream data)` sends all of a string or `array<uint8>`, waiting while
  the other side is slow to take it.
- `tcp_receive(stream largest=65536)` waits for some bytes and gives what has
  arrived, at most `largest`; `none` once the other side has closed and
  everything it sent has been read. Check `none` before handling the errors, as
  for other streaming reads.
- `tcp_close` closes a stream or a listener.

Cancellation reaches the group's own thread as well: a server can accept on the
thread that opened the group while a spawned client cancels the group when it
is done. Tasks run on Linux for now; elsewhere the calls simply block. Native
targets use the system's C library (Winsock on Windows); a web page has no TCP
sockets. The game library's WebSocket messages (`net.listen`, `net.connect`,
`net.receive`, `net.send`, below) come with the same import.

## Foreign functions

A function whose body is the metatag `$extern` is a C function. Its signature is
the C one: fixed-width numbers, `bool`, raw pointers `ptr<T>`, and as
parameters also strings (passed as a zero-terminated `char *`) and function types
(C function pointers). `int` is rejected, since its size is not fixed. Optional
keyword arguments give the C name and the library:

```dewy
strlen=(s:ptr<uint8>):>uint64 => $extern
getenv=(name:string):>ptr<uint8>? => $extern
sleep_ms=(ms:uint32):>void => $extern(name='Sleep' lib='kernel32')
```

Without `lib=`, or with `lib='c'`, the function is in the C library
(`libc.so.6`, `libSystem` or `msvcrt.dll`); `lib='m'` is the math library. Another
bare name is the system's usual file for it (`kernel32.dll`, `libz.so`,
`libz.dylib`), and a name with a dot or a slash is used as written
(`lib='libsqlite3.so.0'`). The library is loaded when the function is first
called. A web build imports it from the page under its Dewy name; Dewy has no
spelling yet for the JavaScript that supplies it.

`ptr<T>` is a raw pointer, never null; `ptr<T>?` may be null, which is `none` on
the Dewy side. `p[i]` reads and writes the `i`th `T` from `p`, `p + n` is `n`
elements on, and `p as ptr<U>` reinterprets it. A C function's result is the
claim of its declaration: one declared `ptr<T>` must not return null.
`xs.ptr` (provisional spelling) is the pointer to an array's elements, for C to
read or fill; it is valid until the array next changes length or is replaced.

A pointer at the C boundary points to data with C's layout: fixed-width
numbers, bools, pointers, and records of them. Such a record is a C struct: its
fields in order, each at its natural alignment, so C fills one in place:

```dewy
TimeVal:type=[seconds:int64 microseconds:int64]
gettimeofday=(now:ptr<TimeVal> zone:ptr<uint8>?):>int32 => $extern
main=():>void=>{
    $unsafe
    let now:array<TimeVal>=[TimeVal[0 0]]
    gettimeofday(now.ptr none)
    printl(now[0].seconds)
}
```

A record holding a string, an array or another managed value has no C layout,
and a pointer to one is rejected in an `$extern` signature.

Calling a `$extern` function, or naming it as a value, and reading or writing
through a `ptr<T>` need an unsafe boundary: the setting `$unsafe` on a line of
its own in an enclosing block, function body or module. The compiler cannot
check what foreign code does, so the boundary marks where a person must. No
bundle may hold `$unsafe`. A safe wrapper confines it:

```dewy
getpid=():>int32 => $extern
pid=():>int32 => {
    $unsafe
    getpid()
}
```

A foreign call is opaque to effect rows: a function declared `& no_effects`, or
any closed row, cannot call one. It may block, so a `parallel` body cannot call
one either; tasks can. On Linux, a program with tasks that calls C loads C's
library on its main thread before its first task. A row written on the `$extern` declaration
itself (`labs=(x:int64):>int64 & no_effects => $extern`) is trusted instead, as
part of the unsafe claim.

`$export` on the line before a module function gives it the C calling
convention, so C can call it through a function pointer; `$export(name='sym')`
names its symbol where the target exports one (WebAssembly builds export it to
the page). `@f` passes it where a C function type is expected:

```dewy
qsort=(base:ptr<int32> count:uint64 size:uint64 compare:<(a:ptr<int32> b:ptr<int32>):>int32>):>void => $extern

$export
ascending=(a:ptr<int32> b:ptr<int32>):>int32 => {
    $unsafe
    return if a[0] <? b[0] -1 else if a[0] >? b[0] 1 else 0
}
```

An exported function takes and returns the same kinds of values, but not yet
`ptr<T>?`. Native executables do not export symbols yet, so C reaches an
exported function only through a pointer that Dewy gives it.

A function whose body is `$intrinsic` states one the compiler provides
(`sqrt=(x:float64):>float64 => $intrinsic`); any other name is an error.

## Loops, text and optional values

`printl(x)` writes a value and a line break; `print(x)` writes it without one.
They are the prelude's shadowable names for `console.printl` and `console.print`.
`print(x file=stderr)` (and `printl`) writes to another stream: `stdout` and
`stderr` are in the prelude. The prelude `console` also has `info` (as
`printl`), `warn` and `error` (standard error, yellow and red on a terminal) and
`debug` (standard error; left out of release builds, its arguments unevaluated):

```dewy
console.info("loaded {3} files")
console.warn("cache is stale")
printl("plain text on standard error" file=stderr)
console.debug("only in debug builds")
```

Colour is used only when the stream is a terminal. `NO_COLOR` (set and nonempty)
turns it off; otherwise `FORCE_COLOR` or `CLICOLOR_FORCE` (nonempty, not `0`)
turns it on. A program overrides both with `console.color='always'`, `'never'`
or `'auto'` (the default).

Optional types use `T?`, including generic types such as `array<uint16>?`
and nested `array<array<uint16>?>?`. `none` represents an absent value.

Use `value ?? fallback` to unwrap an optional or provide a default. The left side
runs once; the fallback runs only when it is `none`. Zero, `false` and empty
collections are present values. Chains associate right, so
`first ?? second ?? default` picks the first present value. A final optional
fallback keeps the result optional. Arithmetic binds more tightly than `??`,
while comparisons and boolean operators bind less tightly:
`to_int(text) ?? 0 >? 10` compares the selected number with 10. Since
`count ?? 0 + 1` is `count ?? (0 + 1)`, a literal fallback followed by
arithmetic draws a warning; parenthesize either way to say which is meant.

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

*Provisional:* a value whose type has a `next` method, giving the next element
or `none`, is an iterator; a loop calls `next` until it gives `none`.
`loop x in it` steps a copy of the iterator. To steer the traversal, bind the
iterator and loop over its place: `loop x in @it` steps the bound iterator
itself, so the body can call its other methods (`it.seek(i)`, say). The bundled
`tree` module's walk visits a tree depth first, each node before its children,
and its `skip_children` leaves out the children of the node it gave last:

```dewy
from tree import Tree
let files:Tree<string> = []
let home = files.add("home")
files.add("old.txt" files.add("drafts" home))
let w = files.walk
loop name in @w {
    if name =? "drafts" { w.skip_children }
    printl(name)   # home, drafts
}
```

An iterator loop binds one value (unpack it in the body) and is not part of a
combined header yet.

`loop x in xs` iterates the value `xs` has at loop entry. The body may change
`xs`; the iteration does not see it, and no copy is made unless the body writes
`xs`. `loop x in @xs` iterates the place live instead: each step reads the
current length and element, so pushes and edits made by the body are seen. This
is the worklist idiom:

```dewy
let order:array<int64> = [start]
loop node in @order {
    loop next in edges[node] {
        if not seen[next] { seen[next] = true  order.push(next) }
    }
}
```

Changing the length of an array that a loop iterates by value (`push`, `pop`,
`insert`, `remove`, `clear`, `extend`, `resize`, `truncate` on the same binding
or field path in the body) is a compile error with both fixes: iterate `@xs` to
see the changes, or bind a snapshot first (`let snapshot = xs` then
`loop x in snapshot`). A live loop binds one name over a growable array named by
a binding or field path, and cannot be part of a combined header.

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

A conversion ending a header converts the last source, since a header itself
has no type: `loop byte in text as array<uint8> { ... }` iterates
`text as array<uint8>`, as does `loop i in 0.. and byte in text as array<uint8>`.

`loop { ... }` with nothing after the block on its line runs until `break` or
`return` leaves it, like `loop true { ... }`. A block followed on the same line
by a body is that loop's condition instead, evaluated before each pass:
`loop {calls+=1; calls <? 4} {total+=1}`.

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

`$breakpoint` is a statement that prints `── breakpoint at file.dewy:LINE ──` and
the function's live bindings (`name = value`, strings quoted; functions, types,
ranges and hidden bindings are left out) to standard error, then reads commands
from standard input at a `>>> ` prompt: `\c` or an empty line continues, `\q`
quits with status 130, `\h` lists the commands, and anything else is refused (a
compiled program cannot evaluate an expression yet). The end of input continues.
At the top level it shows only local bindings, and it does not yet trap into an
attached debugger.

Assertions are directives with their own argument grammar:
`$runtime_assert condition` or `$runtime_assert condition, "message"` checks
the condition when the program runs; a failure reports the condition (or the
message, which may interpolate values) and exits with status 101. Its type
tests narrow for the rest of the block, as after `if not condition return`:
after `$runtime_assert r isnt? Oops`, `r` is its other members.
`$assert condition [, "message"]` must be proven while compiling. The compiler
uses constant facts and settled type tests, then executes ordinary checked code
for closed compile-time requests. For runtime scalar values, it also uses
builtin comparison guards, interval/nonzero facts, assignments, snapshots and
successful `$runtime_assert` conditions. Early returns remove unreachable
paths; joins retain only evidence shared by every incoming path. Calls forget
facts about mutable or exposed storage, and loops forget changing values.
Symbolic operands may use pure scalar terms, record fields, array lengths, and
array elements whose indices are proven in bounds. Copies retain captured value
facts; parent replacement and possibly overlapping element stores invalidate the
corresponding current projections. Reserve and element replacement preserve the
containing length. Calls and nonlinear inference remain unsupported in erased
symbolic operands. An erased assertion cannot introduce
a new implicit closure capture; existing runtime captures remain usable.
An unknown assertion reports `cannot prove assertion` with its reason
(a missing bound, an invalidating call, assignment, resize or loop, a path
lacking evidence, possible wrap, an unsupported operation or an exhausted
budget). Notes point at the invalidating event and at the earlier guard whose
fact described the replaced value, and may show a *possible* witness: values
consistent with the known bounds, never a claim about a real execution. A false
condition reports `assertion refuted`; failed closed evaluation reports the source operation and
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
operations include interpolation of text, machine integers and booleans
(`$field("{row}{col}")`), slicing and ordinary checked string-library calls;
indirect/capturing calls remain unsupported.

`$lend(bytes) expression` lends a named `array<uint8>` read-only;
`$lend(@bytes reserve=n) expression` lends it writable and reserves **n additional
bytes**. Reservation is evaluated once, checked for negative values and length
overflow, and writable storage detaches from COW snapshots before access.
Inside the expression, `__load_i64__(bytes)` gives the unpinned storage address,
`__load_u8__(address)` reads a byte, and `__store_u8__(value address)` writes one.
`bytes.set_length(n)` requires a writable loan and checks `0 <= n <= entry_length
+ reservation`, regardless of spare geometric capacity. Known violations are
rejected; otherwise the bound is checked at runtime, including release builds.
Raw byte initialization and address bounds remain the caller's responsibility.

Loan addresses and derived integers cannot escape through results, returns,
stores, captures, aggregates or unreviewed calls. The owner cannot be copied,
aliased, replaced or resized during the loan, except by `set_length`. Nested
loans on different owners work; conflicting loans and exposed/shared owner
views and mutable parameter owners are rejected. Address-controlled branches and closure construction inside
loans currently reject conservatively. Raw writes require a writable address origin. Ordinary scalar results and early exits are supported; after
the expression the owner is an ordinary value and is freed normally.

`$allocator(@scratch) expression` makes an `Arena` the context allocator for
the whole next expression (braces group statements): everything the expression
allocates, in it and in the functions it calls, bumps the arena's cursor.
`scratch.reset()` gives all of it back at once:

```dewy
let scratch=Arena[]
loop request in requests {
    let summary=$allocator(@scratch) build_summary(request)
    send(summary)
    scratch.reset()
}
```

The expression's value leaves with independent storage of the enclosing
allocator (the heap, or the arena of an enclosing `$allocator`): it is copied
out, so a reset never invalidates it. Static data such as string literals is
not copied. Separate arenas nest; the inner value is copied into the outer
arena. Everything else the expression allocates must die inside it, which the
compiler proves rather than checks at run time. Inside the expression:

- a variable declared outside it may only be given plain data (numbers, flags,
  records of them), and not through an array or string; a call may not change
  such a variable through an `@` argument, and a function it calls may not
  change a global that holds managed values or a shared capture;
- `return`, and `break`/`continue` to a loop outside it, are errors;
- the lent arena cannot be used, reset or lent again;
- closures made in it capture snapshots only, and function values made
  outside it cannot be called from it;
- its value cannot hold closures, resource owners or raw pointers.

Under `$explicit_copies` the copy out is a costly copy like any other, strings
included: end the expression with `.copy()` to ask for it
(`$allocator(@scratch) build_summary(request).copy()`).

The bundled library's raw-memory code (output, the allocator, system calls) is
trusted not to keep what it is given; starting threads or tasks is not. An `Arena` is a value: a copy is another
arena, and dropping one gives its memory back. Debug builds fill reset storage
with `0xdb`.

`arena(bytes)` makes an arena with its whole capacity acquired at once; it
gives `Arena | OutOfMemory`, the latter when the system refuses the memory. It
never takes more: an allocation past its capacity is refused. A fixed arena
starts every `$allocator` expression empty. Under `$no_hidden_costs` this is
how allocation is made explicit: inside `$allocator(@a) expression`, where `a`
is a local made by `arena(n)` with a constant `n`, allocation is allowed when
the compiler proves it fits `n` bytes (array literals of known length, in loops
over constant ranges); anything else is reported with the reason.

```dewy
$no_hidden_costs
count=():>int64 | OutOfMemory=>{
    let a=arena(4096) or_throw
    let n=$allocator(@a) {
        let xs:array<int64>=[1 2 3]
        xs.length
    }
    n
}
```

Ordinary allocation is infallible: when the system refuses memory the program
ends with a report. `$explicit_allocation_failure`, written alone at the top of
a module, makes each of its functions that may allocate return
`T | OutOfMemory` (functions over fixed-width numbers only keep their result).
A refusal while such a function runs, from the system or from a fixed arena,
drops the resource owners made since it began and makes it return
`OutOfMemory`; memory the interrupted work held is not freed. An `OutOfMemory`
reaching `main` prints `error: OutOfMemory`. WebAssembly cannot return to the
function, so a refusal there still ends the program.

Other directives of the design (`$no_prelude`,
`$expect`, `$unsafe_assume`, …) are reported as not implemented yet where they
appear.

`value.copy` requests an independent value. It evaluates the receiver once
and supports arrays, records, dictionaries, sets, strings, closures and
optional/union values. Parentheses are also accepted (`value.copy()`).
Declared `copy` members take precedence. The operation preserves ordinary
value semantics, including private closure state, and may share COW storage
until a write or transfer a fresh result instead of duplicating it.

`$explicit_copies` rejects unproven implicit costly copies in the module,
function or block it is written in (see "Directives"), including unused checked
function bodies; `$explicit_copies = false` keeps the ordinary COW policy.
Costly values include dynamic arrays, records/containers with mutable heap
payloads, and closure environments. Scalars, fixed inline storage and shared
immutable strings are exempt. Stable read-only record snapshots can share
their payloads. A slice or repeated heap-bearing element also has a copy
obligation.

Write `.copy` for an independent snapshot, borrow a stable value for reading,
or arrange a last-use transfer. The compiler transfers dead local values and
unboxed record fields, distinguishes conditional return paths, borrows
read-only arguments and iteration sources (including a method's own field when
the call can change only other fields), reads `extend` and spread sources
without copying them, and infers owning parameters for closed direct calls. Moves clear their old storage before cleanup. Loops,
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
`text.startswith(prefix)` and `text.endswith(suffix)` test the ends of a string;
`text.remove_prefix(prefix)` and `text.remove_suffix(suffix)` give the text without
that end when it has it (once), and the text unchanged otherwise.
`text.trim_start` and `text.trim_end` drop whitespace from one end (`trim` both),
`text.lines` gives the lines without their breaks (a final break adds no empty
line), `text.chars` its graphemes (as `graphemes(text)`), `text.count(part)` the
nonoverlapping occurrences and `text.is_empty` whether it has none.
`text.find(part)` and `text.rfind(part)` give the grapheme position of the first or
last occurrence, as indexing counts, or `Missing`; `text.find(part start)` searches from
grapheme `start`. `xs.index_of(x)` gives the first position of `x` in an array, or
`Missing`. `Missing` is the prelude's exception for a search that found nothing:
it is neither `none` nor -1, so `??` does not apply; test it with `is? Missing`,
forward it with `or_throw`, or `match` it.

```dewy
let at="key=value".find("=")
if at isnt? Missing {printl(at)}       # 3
printl([3 1 4].index_of(9))            # Missing
```

`regex(pattern)` prepares a reusable regular expression. `text.find(pattern)`
returns `Match|Missing`; `find_all` returns nonoverlapping matches, `contains` tests
for any match, and `matches` requires the whole string to match. A `Match` has
`text`, `groups`, `start` and `end`. **Match offsets and the optional `find`
starting offset are UTF-8 byte offsets**, while regex atoms consume code points.
They are not Dewy's ordinary grapheme indices; use the returned `text` directly.

```dewy
let date = regex(r"(\d{4})-(\d\d)-(\d\d)")
let found = "due 2026-10-19!".find(date)
if found isnt? Missing {printl(found.groups[0])}
let rewritten = "due 2026-10-19!".replace(date "$3/$2/$1")
let fields = "a, b;c".split(regex(r"[,;]\s*"))
```

Patterns support character classes, alternatives, captured and `(?:...)`
uncaptured groups, greedy/lazy repetitions, line anchors `^`/`$`, and word
boundaries. `(?i)` at the start folds ASCII case. Use `regex_error(pattern)`
to check user-supplied patterns before preparing them. A pattern whose repeats
written out exceed 50,000 instructions (`(a{1000}){1000}`), or that nests groups
or repeats over 200 deep, is refused like one that cannot be read. An empty match advances
one code point before the next search; unmatched capture groups contain `""`.
`replace` accepts `$0` for the match, `$1` onward for captures, `$$` for a dollar,
or a `(Match):>string` callback. `split` returns the text between matches.

Matching uses compact tables and skips impossible starting positions. Long
inputs can use bounded lazy DFAs, with the Pike VM retained for anchors, captures
and fallback. Prepare a pattern once when matching many strings. This bounds
the matching strategy without exponential backtracking; the precise performance
depends on the pattern, input and whether preparation is included.

Interpolation uses `{expression}` inside a string.
Single or double quotes support escapes and interpolation.
`+` never joins text: two strings combine by interpolation, `"{left}{right}"`,
and many pieces collect in an `array<string>` and `join` (`pieces.join` or
`pieces.join(", ")`). `s = "{s}more"` on a local string appends in place, so
building text in a loop stays linear; `s += x` is an error. Unicode escapes use
four hexadecimal digits (`"\u00E9"`) or one to six inside braces
(`"\u{1F642}"`); both name Unicode scalar values. Surrogates and values above
`10FFFF` are errors. Braced escapes currently accept hex literals, not expressions.
The letter escapes are `\n`, `\r`, `\t`, `\a`, `\b`, `\v` and `\f`, plus `\0`;
any ASCII punctuation escapes to itself (`\{`, `\}`, `\'`, `\"`, `\\`, `\%`), and
an unknown escape of a letter or digit (`\N`) is an error.

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
may span lines. Comment markers inside strings are string contents. A
documentation string is an ordinary call of the prelude's `doc` with a string,
usually a `"""` block at the top of a module or a function body:
`doc"""Tokenizer framework."""`. Nothing is kept from it yet, so the call does
nothing.

A name has one spelling however it is written: subscript digits are `_` and the
digits (`x₁₂`, `x₁_2` and `x_12` are one name), superscript digits are `‾` and the
digits (`x¹²` is `x‾12`), and the micro sign `µ` is Greek `μ`. Letter
decorations (`xᵢ`) stay distinct from `x_i`.

```dewy
#{ outer
   #{ nested }#
}#
let total = 1 #{ inline }# + 2
```

Printing, interpolation, `string(value)` and `value as string` show a value as
its literal syntax: `[1 2 3]`, `set["a" "b"]`, `["a" -> 1]`, a range as `[0..2]`
or `[1,3..9]`, and an object field by field, `[x=1 name="q"]`. A minted type
adds its name, `Fault[code=7]`, or is just `Unit` without fields. A type that
declares `__as__ = ():>string` shows that text instead (a minted child without
its own uses its nearest ancestor's, as `as string` does), and function fields are
left out. A string prints bare on its own and quoted, with its escapes, inside a
structure (`["a\tb"]`). A present optional or a union shows its member; an
absent optional prints `none`. A function handle shows its type's spelling,
`"{@f}"` as `<(x:int64):>int64>`, and so does a type: `printl(Point)`,
`"{int64}"` and `int64 as string`.

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
also produce bytes. Byte literals spell them directly: `b'a'` is the `uint8` 97
(one byte, escapes allowed: `b'\n'`, `b'\{'`) and works as a constant and a
`match` arm, and `b"abc"` is an `array<uint8>` of the text's UTF-8 bytes,
without interpolation. `bytes as string | none` decodes UTF-8, giving `none` for
invalid input; plain `bytes as string` is an error, since nothing proves the
bytes valid. `bytes as string ?? ""` decodes or falls back: no type has a
fallback, so a conversion to `T ?? fallback` is `(bytes as T?) ?? fallback`. `$include_bytes(p"asset.png") as image` embeds an asset at
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
type for subsequent accesses. A literal builds the one union member it fits: a
record literal the record whose fields it names (`return [name="ada"]` for
`Customer|NotFound`), a dictionary literal the dictionary, an array literal the
array. In `if flag xs else []`, a container literal in the `else` branch takes
the type of the first branch; in `if flag [42] else xs`, a then-branch literal made
of literals takes the `else` branch's. `??` also works after an optional has been narrowed
to its value, and its fallback remains lazy.

`match` supports typed bindings, literals and `_` as a fallback. Any other bare
name arm also matches every value and binds it, with a warning: `limit => ...`
shadows `limit` rather than comparing with it. An optional
payload arm such as `n:int64` also narrows the original variable or field to
`int64` inside that arm; the binding `n` is an independent value. A union is
written `int64|string`; union matches must cover its members or have a fallback.
An arm after a catch-all, or one whose member earlier arms already cover, is
unreachable and an error. An `if`/`else if` chain of `is?` tests that names every
member is a value without a final `else`:
`if v is? int64 "int" else if v is? string "str"` for `v:int64|string`.
A union compares with one of its members directly: `v =? 3` is true only when
`v` holds that `int64` and it equals 3, and false while it holds a `string`.
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

On a fixed-width integer, a refined type arm is a guard: `small:int64<small <? 100>`
binds `small` when the refinement holds, and `<-1|1>` matches either value.
Coverage is computed on value sets, so `a:int64<a <? 0>` and `b:int64<b >=? 0>`
cover `int64`, while over `-1|0|1` the same guards with `>? 0` report
`this match has no arm for 0`; an arm whose values earlier arms already match is
unreachable. String literal arms work the same way: over `'n' | 's' | 'e'`,
`<'n'>` and `other:'s'|'e'` cover it, and over a mixed literal union the arms
cover a literal member once each of its values has an arm.

An object pattern matches the record (or the union member) with the fields it
names and binds them: `[sign:1 limbs] => limbs.length` and
`[sign:-1 limbs] => -limbs.length` together cover `[sign:-1|1 limbs:array<int64>]`.
A sequence scrutinee is read once per value, `match (x y) (a:int64 <string>) => a`,
and a sequence pattern on an array tests its length and each element:
`(a <7> c) => ...`; object and sequence patterns nest inside it. Over a sequence
scrutinee, arms that cover each member of one value while matching the others
whole cover the match. An object or sequence arm whose member or field values
earlier arms already match is unreachable. On an `int` (a variable or any
expression), a guard arm such as `small:int<small <? 100>` compares the value
itself. A guard arm's bounds are facts in its body.

A type arm can group a subset of the union's members. For a value of type
`int64|string|bool`, `part:int64|string=>...` binds an independent `int64|string`
value and narrows the original variable or field to the same subset. The remaining
`_` arm knows the value is `bool`. `<int64|string>=>...` performs the same test
without introducing a binding. Subset aliases and generic type parameters work
too. Arms run in source order, including when their subsets overlap.

Membership uses `in?`; negate it with `not in?`:

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

Random numbers: `random()` gives a float in `[0, 1)`, `random_int(lo hi)` a
whole number in `[lo..hi)`, and `rng(seed)` a generator of its own whose
`next_int(lo hi)`, `next_float()` and friends repeat for the same seed. The
shared generator is seeded once per process from the operating system's random
source; `seed_random(n)` (or an `Rng`) makes a run repeatable. An empty range has
no number to give, so `hi >? lo` is an obligation of `random_int` and
`next_int`: a refuted one (`random_int(10 3)`) is a compile error, and an
unproven one follows the obligation settings. These generators are predictable
from their state and are not for secrets: keys, tokens and nonces come from
`crypto.random_bytes(n)` (`import crypto`), which reads the operating system's
secure random source (getrandom, getentropy, RtlGenRandom, or
`crypto.getRandomValues` on the web).

## Directives

A setting is a metatag on a line of its own: `$name` or `$name=true` turns it
on and `$name=false` turns it off. It holds throughout the scope it is written
in, wherever in that scope: the module at file level, a function in its body,
or any other block. An inner scope may change it again. A scope sets each
setting at most once, and the value must be a literal `true` or `false`.

An obligation is a fact an operation needs: an index or slice in bounds (a
string's counted in graphemes, as `text.length` counts), a nonzero divisor, a value that fits a narrower integer, an argument meeting a refined
parameter. A proven obligation has no runtime check. These settings decide what
an unproven one does:

- `$runtime_checks=false`: it is a compile error with the reason and a fix
  (no hidden traps). This becomes the default in a later release; until then
  the default is a runtime check.
- `$runtime_checks`: it compiles to a runtime check, with no warning. A failing
  check names the requirement and the values it saw, as
  ``refinement failed: `d not=? 0` (observed: d was 0)`` or
  `index 5 out of bounds (length 3)`, and exits with status 101. Proven checks
  still vanish.
- `$prototype`: as `$runtime_checks`, with a `prototype: …` warning at each
  site while compiling, for development. `$prototype_warnings=false` silences
  the warnings. Obligations of `$proof` functions and `$assert` are never
  deferred.

`dewy check --obligations file.dewy` lists every unproven obligation that
compiles to a runtime check, one per line, with the setting responsible
(`$runtime_checks`, `$prototype`, or `default`), and each library call that may
panic (``may panic: indexing with `[]` ``). Without runtime checks, calling code
that may panic is an error too (the `panics` effect, "Functions and values"). The editor shows sites in
`$runtime_checks` scopes as information hints.

`$explicit_copies` (described with `.copy` above) is a setting like these, for
a module, a function or a block. So are the float settings `$fast_math`,
`$no_nan` and `$no_inf`, and the library bundle `$finite_floats` (both of the
latter), described with the numeric types. `$unsafe`, the unsafe boundary, is one too
(see "Foreign functions"), though no bundle may hold it.

A bundle is one metatag for several settings, defined at module level:

```dewy
$careful = {
    $explicit_copies
    $runtime_checks=false
}
```

Writing `$careful` holds every setting in the bundle throughout that scope.
Inside it, a setting that contradicts the bundle is an error; `$careful=false`
opts a nested scope out of the whole bundle first. `$default_row = <effect row>`
in a bundle gives each function declared in its scope without an effect row
of its own that row (see "Functions and values").

The library defines `$no_hidden_costs`, the strict lane (lib/directives.dewy):
`$explicit_copies`, `$runtime_checks=false`, `$prototype=false` and
`$default_row = no allocates & no panics`. Code in it has no hidden allocation
(a detach allocates), no implicit costly copy, no runtime check and no call of
code that may panic (the `panics` effect, "Functions and values"), and it
cannot use `$runtime_checks` or `$prototype`. A function that needs more opts out with
`$no_hidden_costs=false` in its body, or declares a row of its own. The effect
inventory is still partial (see "Functions and values"): an operation it does
not classify is rejected there. `$realtime` is reserved for a stronger future bundle.

## Modules and games

```dewy
import physics
import p"model.dewy" as model
import p"shapes.dewy"
from p"helpers.dewy" import advance, fresh
```

`import p"shapes.dewy"` with no selection and no name binds each of the module's
top-level declarations here, as if every one were selected (names starting with
`_` stay in it, and its own imports are not passed on). `as model` keeps a module
behind a namespace instead (`model.step()`), and a bare library name such as
`physics` is its namespace. Two imports binding different declarations under one
name are an error naming both modules; import one under a name or select what you
need. A module's own declaration may shadow an imported `$shadowable` one, an
import may shadow the prelude's, and a non-`$shadowable` import outranks a
`$shadowable` one.

A selection lists names with commas or in parentheses, each optionally renamed
(`import (advance fresh as new)`, `import advance as step, fresh` after `from
p"helpers.dewy"`). The other order works too: `import (advance fresh) from
p"helpers.dewy"`.

Bare names search beside the importing file, then the bundled library folders;
a path literal `p"..."` names a file explicitly. Within each folder, a Dewy importer prefers
`.dewy` and falls back to `.jo`; a Sloppy importer prefers `.jo`. The importing file
itself is skipped, so `physics.dewy` can import the bundled `physics` library.
Watch mode notices creation/removal of a preferred local module and reloads it.
Use `import p"@lib/physics.jo" as physics` to select a bundled library explicitly,
even when a neighboring file has the same name. `@lib/` resolves inside the
active toolchain's library directory and also works with selected imports.

Import cycles containing a Dewy (`.dewy`) module are rejected, with the import
path through the cycle in the diagnostic. This includes cycles that pass through
Sloppy implementation libraries; cycles made entirely of Sloppy modules remain allowed.

`--target` and `$target` use the design's target names. A name has only the
fields it needs: the processor, then the system.

| Names | Target |
|---|---|
| `x86_64`, `aarch64`, `riscv64`, `c` | this machine's system on that processor |
| `x86_64-linux`, `aarch64-linux`, `riscv64-linux`, `c-linux` | Linux |
| `x86_64-mac`, `aarch64-mac` | macOS |
| `x86_64-windows`, `aarch64-windows`, `riscv64-windows`, `c-windows` | Windows |
| `x86_64-freestanding`, `aarch64-freestanding`, `riscv64-freestanding`, `c-freestanding` | bare metal |
| `c-posix`, `c89`, `wasm32` | portable C, and WebAssembly in the browser |

This compiler builds `x86_64-linux`, `aarch64-linux`, `aarch64-mac`,
`x86_64-windows` and `wasm32`; the default is this machine. `--target` with
another of the names is an error saying it is not supported yet.

`$target` is the full name of the target being compiled for (`x86_64-linux`,
`wasm32`, …), never a processor alone. `$target.arch` is its processor (`x86_64`,
`aarch64`, `riscv64`, `c` or `wasm32`) and `$target.os` its system (`linux`,
`mac`, `windows`, `freestanding`, `posix`, or `none` for `wasm32` and `c89`). A
condition made only of these compared with string literals (`=?`, `not =?`,
`in?` and `not in?` a literal list, joined by `not`, `and` and `or`) is decided
while compiling. Its `if` compiles only the live arm and splices that arm's body
into the enclosing scope, so imports and declarations there bind as if written
outside. The other arms are never checked, so they may name modules or functions
that exist only for another target. A misspelled name is an error. Elsewhere
these are ordinary strings.

```dewy
$supported_targets = ["x86_64-linux" "aarch64-mac" "wasm32"]
if $target =? "wasm32" {
    import p"web_audio.dewy" as audio
} else if $target.os =? "mac" {
    import p"mac_audio.dewy" as audio
} else {
    import p"native_audio.dewy" as audio
}
```

`$supported_targets` lists the full target names a module accepts, once at file
scope; compiling it for any other target is an error.

`$build` is the compile-time record of how the program is built: `$build.mode`
is `"release"` or `"debug"`, and `$build.debug` is `true` in a debug build.
Conditions on them fold like `$target` tests (`if $build.debug {...}` compiles
only the live arm). Project flags are ordinary constants in a build module the
entry module overrides; there are no command-line `-D` flags.

Start a game with the built-in template, then edit it while it runs:

```sh
/tmp/dewy-core/bin/dewy-core new /tmp/my-dewy-game
/tmp/dewy-core/bin/dewy-core watch /tmp/my-dewy-game/main.dewy
/tmp/dewy-core/bin/dewy-core build /tmp/my-dewy-game/main.dewy --target wasm32 -o /tmp/game
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

For TCP streams of your own protocol, see [Networking](#networking).

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

An executable’s `main` returns `void` or the errors that reach it (see
[Errors as values](#errors-as-values)); other result types are diagnosed.
