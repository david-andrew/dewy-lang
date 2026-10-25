# Multi-expressions (decided 2026-10-23; restores the reference)

Dewy is expression-oriented: a construct is not a statement that happens to have a
value, it is an expression that may give one value, several, none, or never
finish. This note specifies how those values move. It restores the archived
reference (`git show archive/master-pre-restart:site/reference/src/expressions-and-operators.md`,
lines 3–21, and `site/learn/src/ch03/expressions-statements-blocks.md`, lines 29–75)
and fills the places it left open. Flagged items are natural extensions, not
reference text.

## The rule

An expression produces one value, several values, `void`, or `never`. A block
evaluates its expressions in source order and **expresses each non-`void`
result**. A context requiring one value rejects a block that can produce an
incompatible number of values.

The same rule holds in every construct: blocks, function bodies, `if`/`match`
arms, loop bodies, loop capture and collectors. Values flow outward through
statement-level nesting until something collects them, takes exactly one of them,
or drops them:

```dewy
pair = () => { 1 2 }
printl([pair()])            # [1 2]
printl([{ 3 4 5 }])         # [3 4 5]
printl([0 if c { 1 2 } else { 3 } 9])
squares = (n:int64) => { loop i in 0..n i^2 }
printl([squares(3)])        # [0 1 4 9]
```

`void` results (declarations, assignments, `printl`, `xs.push(v)`) are never
expressed. A `never` result (`return`, `break`, `exit(...)`) ends its path, so it
contributes nothing either.

A result that is `void` or an error (`void | E`, as from `sleep(1ms)`) expresses
`E` when it fails and nothing when it succeeds (decided 2026-10-23). In statement
position that is a value that may appear, so the sink rules apply: the last
statement of a `:>void | E` body gives it as the result; anywhere else it is an
error naming the fixes (`or_throw` to propagate, `match`/`is?` to handle, an
attached `;` to discard). Module code still drops it. A `spawn` statement in a
`concurrent` block hands its task to the group and expresses nothing.
*Flagged: collecting failures (`[loop x in xs risky(x)]` giving the errors) is
not implemented; it is the same error for now.*

## Suppressing values: the attached `;`

A semicolon **attached** to an expression (no space before it) evaluates the
expression and discards everything it would express. It binds loosest of all
(the bottom row of the precedence table), so it applies to the whole expression
it ends:

```dewy
let selected = [
    load_primary();
    load_secondary()
]                                  # both run; only the second is collected
loop out.length >? 1 and out[out.length-1] =? 0 out.pop();   # the loop's values are dropped
```

A **standalone** `;` (with a space or a line break before it) is not statement
punctuation. Inside an array literal it selects the next dimension, standing in
for a row break (tensors.md): `[1 2 ; 3 4]` is a 2×2 matrix and `[1 2 ;; 3 4]`
starts a new 2-D block. Anywhere else a standalone `;` is an error.

So `[f(); 7]` is `[7]` after calling `f`, never a matrix, and `[1 2; 3 4]` is
`[1 3 4]`: the attached `;` discards `2` (decided 2026-10-23). Because that
usually means a row break, an attached `;` that discards a value with no effect
(a literal, a name, arithmetic of them) inside an array literal warns, with an
editor fix-it that makes it the standalone ` ;`. In a literal that has rows, an
attached `;` is an error, since rows hold only values.

## Contexts

**Collectors take every value.**
- Array literals `[...]`: each element contributes what it expresses, in order.
  `[a {b c} d]` is `[a b c d]`, and `[if c x]` is `[x]` or `[]`.
- Loop capture `[loop ...]` collects every value of every iteration. A body that
  expresses two values per iteration contributes both:
  `[loop i in xs { i  i*10 }]`.
- Spread `xs...` inserts an array's elements. Several values in a collector need
  no `...` (`[pair()]`, `[pair]`, `[(1 2) 3]`), and `pair()...` means the same.
- Map, record and set literals are unchanged. Their entries are one value each.

**Bindings, call arguments and unpacking take several values** (see
"Substitution invariance" below). A binding holds them (`pair = (1 2)`), a call
takes them as that many positional arguments (`add(pair)`), and a pattern takes
them apart (`(a b) = pair`).

**One-value contexts take exactly one.** These are operands, conditions,
indexes, named arguments, the result of a function with a written one-value
contract, and the arms of a value `if`/`match` outside a collecting position.
Several values there are never cut down to one: it is a compile error naming the
count (`'pair' holds 2 values, and only one is taken here`). A block in a
one-value context expresses its last expression. An

earlier non-`void` value is an error with a fix-it to attach `;`:

```
printl({ log(1)  5 })   # error at log(1): this gives a value, and here the block
                        # gives one, its last expression: attach `;` to discard it
```


A block as a binding's value gives every value it expresses, as a group would
(`x = { 1 2 }` holds both, `(int int)`; `x = { pair() 3 }` holds three). Each
must be a statement of the block's own level: a value in a loop or a branch has
no fixed count, and a binding holds a fixed number, so it is an error (collect
them, `x = [ … ]`). One value is held as before.

**Statement contexts drop values.** Module-level code drops what it expresses.
The old "value is not used" warning stays here, for values that are discarded and
do nothing (`x == 6`, `speed + 1`).

**A written `:>void` body expresses nothing** (decided 2026-10-23). A value its
body expresses (`xs.pop()`, `5`) is an error: attach `;` to discard it, or change
the result type. A `:>void | E` body is the same, except that its last statement
may give the `E`. A function whose result is `void` only by context (a callback
passed where `:>void` is expected, a game's `update`) still drops its values.
*Flagged: the context-typed exception keeps callbacks Python-like; reversible.*

## Functions

A function's result is what its body expresses.

- **Written contract `:>T`**: the body must express exactly one `T` on every path,
  its last expression or a `return`. More is an error, as in any one-value
  context.
- **Inferred result**: the body may express any number of values. With exactly
  one, the function gives that value, as before. With several, or a count that
  varies by path (a loop, an `if` without `else`), the function **expresses
  several values**.

How such a function is consumed (`pair = () => { 1 2 }`):

| Use | Meaning |
|---|---|
| `[pair()]` | `[1 2]`: the collector takes both |
| `[0 pair() 3]` | `[0 1 2 3]` |
| a statement in another inferred body | its values are expressed there too |
| `pair();` | runs it, drops both |
| `x = pair()` | `x` holds both, type `(int64 int64)` |
| `f(pair())`, `f(pair)` (the bare name calls) | both values, as `f`'s first two positional arguments |
| `[a b] = pair()`, `(a b) = pair()` | unpacks both |
| `pair() + 1`, `pair()[0]` | error: only one value is taken here, and `pair()` gives 2 |

Its type: the function's result is its element type, expressed a number of times.
That number is *static* when the result is written (`:>(int64 int64)`) or when
every value is a statement of the body's own block, outside loops and branches
(`() => (1 2)`, `() => { 1 2 }`): a call then gives exactly that many. Otherwise
(a loop, an `if` without `else`) it varies, and only a collector or an unpacking
takes it (the unpacking's length is then an obligation, as an array's).

**A written contract for several values** (decided 2026-10-23): `:>(int64 int64)`;
parentheses group several result values. The body must express exactly that
many, each of the written type, as statements of its own block: a value in a
loop or a branch, or from a call whose count is not written, has no fixed count
and is an error, as are more or fewer values. A call of such a function behaves
like a call of an inferred one (collected, `[pair()]`, or an error in a
one-value place). The values share one type for now; `(int64 string)` is an
error. Parenthesized values are a type only as a function's result or as a
binding's whole type, `let p:(int64 int64) = …` (where the types may differ,
`(int64 string)`, as a group's).
*Flagged: one type per group and the static count are conservative choices;
both are reversible.*

`return value` gives back that one value and ends the function. A function that
expresses values before its end and also uses `return value` is an error for
now, because the stream semantics of `return` after earlier values need a
decision. *Flagged: the natural extension is "earlier values, then the returned
one". Today it's rejected, which is the conservative choice.*

A function value (`@pair`) of a function expressing several values carries it in
its type, written `<():>(int64 int64)>`: a call through it gives several values,
under the same rules as a direct call. The count is part of the function type
(decided 2026-10-23, substitution invariance; reverses the provisional "count is
not part of a function type"): `f = @pair; add(f)` fills both parameters, as
`add(pair)` does, and `<():>(int64 int64 int64)>` does not hold `@pair`. A
function whose count varies (a loop, a branch) has the type `<():>(int64 ...)>`
in diagnostics, and a call through it is only collected. A function giving one
value does not fit a type giving several, nor the reverse. A lambda checked
against such a type expresses exactly its count, as a written result does.

## Substitution invariance (decided 2026-10-23)

If a literal works somewhere, anything producing the same values works there
unchanged. `(a b)` is not a container: it is the syntax for several values.
`[...]` arrays and records are containers, and a container is one value.

```dewy
add = (a b) => a + b
add(1 2)            # two values
fn = () => (1 2)
add(fn)             # the bare name calls; fn gives two values, filling both parameters
pair = (a b)
add(pair)           # a binding holds several values, type (int64 int64)
add([1 2]...)       # a container is spread, positionally, its length proven
fn2 = () => [1 2]
add(fn2...)         # a function giving a container: spread it
```

- **Several values are never cut down to one.** A place for exactly one value
  (operand, index, condition, named argument, single parameter) given several is
  a compile error naming the counts. `pair[0]` suggests `[pair][0]` or
  `(x y) = pair`.
- **`[...]` collects; `xs...` spreads a container.** In a call, a spread fills
  positional parameters in order. Its length must fit: a fixed array's and a
  `[T U]`'s are known; an array's must be exactly the positional parameters the
  other arguments leave (the function must have one version), proven from facts
  or, as any obligation, checked at run time where the scope allows one. A
  record does not spread into named arguments (deferred).
- **The count is static.** A call's count comes from its function's written or
  inferred result type, or from a function value's type; one that varies cannot
  fill parameters (collect it). The bare name of a function value taking no
  parameters calls it, as a function's does (`f = @pair; add(f)`). Overloads see
  the expanded shape: `show(pair())` picks the two-parameter `show`.
- **Order.** Arguments run in written order: an argument before a held one
  (a call giving several values, a spread container) that may have an effect is
  evaluated first, into a temporary.
- **Mitigation for shifted arguments.** The editor shows an inlay hint naming
  the parameters each multi-valued argument fills (`a b:`), and a warning marks
  a multi-valued argument whose count is not written at the call (a binding or a
  call) followed by more positional arguments.
- Groups flatten: `((1 2) 3)` is three values, `add((1 2))` is `add(1 2)`.
- A group's values may have different types: `(1 "a")` is `(int string)`. A
  function's written result `:>(T T)` still has one type (below).

A binding's type may be written with several values, `let p:(int64 int64) = …`
(each value converts to its place's type, as a group's does; another count is an
error naming both). It is the binding's whole type: `array<(int64 int64)>` or a
parameter typed so is an error.

## Unpacking (decided 2026-10-23)

`[...] =` and `(...) =` both unpack, in `let`, `const`, assignments and
parameters, whenever the right side provides a compatible number of values:
several values (a group, a binding holding them, a call giving them), an array,
a fixed array, a `[T U]`, a set, a dictionary (key/value pairs in insertion
order) or a record (by field name).

```dewy
let [a b] = pair()             # several values
let (c d) = (10 20)
let [x as px  y:int64 as py] = point         # `as` renames; the type goes on the source name
let [apple  banana as [carrot durian]] = o2  # a field taken apart further
let [first ...mid last] = xs   # `...rest` anywhere, once per level
let [head ...] = xs            # a bare `...` drops the rest
[a b] = [b a]                  # swap
```

- A rest takes what the other names leave: an array's slice, a fixed array's
  elements (an array), and several values' remainder (still several values).
  Names after it count from the end.
- `=` inside a pattern is reserved for defaults, which are deferred. The old
  `[local=field]` renaming is `[field as local]`, with no alias.
- **Patterns must be proven to fit (no traps).** Several values, fixed arrays
  and `[T U]` have static counts: a mismatch is a compile error. An array's
  length is an obligation (`exactly n`, or `at least n` with a rest): proven
  from facts it costs nothing; unproven it is a compile error, or a runtime
  check where `$runtime_checks` allows one, like an index. A literal of known
  length that does not fit is a compile error. Dictionary unpacking still checks
  its entry count at run time.
- Records: a rest is not decided (resources/discussion_points.md: "TBD"), so it
  is an error. Dictionaries: `[[k1 v1] [k2 v2] ...] = m` works; a dictionary's
  rest (`...rest` giving the remaining entries) is not implemented, nor is the
  notes' `m.['apple' 'banana']` key selection (marked "not sure" there).

**Parameter patterns.** Each parameter takes one argument and destructures it on
entry with the same patterns: `area = ([w h]:Size) => w*h`. `((a b)) =>` declares
one patterned parameter (taking one argument, a container); `(a b) =>` declares
two. Pattern names are not part of the function type (`area(w=1)` is an error).
The pattern's fit is an obligation in the body: give the parameter a fixed
length (`array<int64 length=2>`) to prove it statically. Deferred:
record-to-keyword spreading `f(opts...)`, place patterns `@[a b]`, pattern
defaults.

## `if` and `match` arms

Arms combine like branches of one expression:

- In a collector (or ending a function with an inferred result), arms may express
  different numbers of values. `[if c { 1 2 } else { 3 }]` is `[1 2]` or `[3]`, and
  a missing `else` expresses nothing.
- In a one-value context, every arm must express exactly one value (or `never`).
  An arm with two is an error at the extra value. The existing "an `if` without
  `else` gives nothing" error still applies.
- An exhaustive value `if`/`match` ending an inferred body whose arms each give one
  value stays one value. The function is not made multi-valued because two arms
  each give one.

## Loops

A loop expresses its body's values on each iteration. In a collector, that's loop
capture. Ending an inferred function body, it makes a generator-like function
whose values a collector takes (`[squares(3)]`). Elsewhere the values go to the
enclosing sink like any statement's. Filtering is an ordinary `if` without
`else`: `[loop n in xs if n % 2 =? 1 n]`.

## Effects, `void` and `never`

Expressing a value has no effect of its own. Every expression is evaluated
exactly once, in source order, whether its value is collected, taken or dropped.
The attached `;` changes only what is expressed, never what runs. `never`
expresses nothing and ends the path. Effect rows of a function expressing
several values are inferred from its body as usual. Collecting allocates the
collector's array, as loop capture always has.

## Implementation (compiler, 2026-10-23)

- Each block the checker checks has a *sink*. Its kinds: drop (module code and
  bodies void by context), void (written `:>void` and `:>void | E` bodies: a
  value is an error), one (one-value contexts and written contracts), body (an
  inferred function result), arm (an arm of the `if`/`match` ending a body, whose
  values belong to the body), and collector (loop capture and `[...]` with block
  or flow elements, which the frontend builds as an accumulator and pushes, as
  loop capture always was).
- A body sink creates its accumulator only when a second value, a value inside a
  loop, or a multi-valued call appears. Earlier pending values are then rewritten
  in place into pushes. A body expressing exactly one value, its last, checks
  exactly as before. Single-value code pays nothing per node: the sink
  bookkeeping runs per block and per expressed value.
- A multi-valued function with a static count returns `(T T)`, a values tuple,
  in place (a struct return, no allocation): a BODY sink holds each value in a
  local while the count stays static (`sink_hold`) and gives the group of them
  at its end; once a value in a loop or branch appears, the held values are
  pushed after all and the function returns its accumulator array. A BIND sink
  (a block as a binding's value) holds them the same way, and a value whose
  count is not static there is an error. Its `FnInst.pack` marks
  it (a written `:>(T T)` also sets `pack_n`, the count its BODY sink checks;
  `pack_k` is the static count, written or inferred, 0 when it varies; a
  function type marks it with its `sign` field, its result `(T T)` or the
  array), and only a consumer that asked
  for several values (array element, spread, statement, final value of a
  collecting body, binding, unpacking, call argument) accepts the call. Any other
  use is the one-value error.
- Several values as one thing (a group, a binding) have a tuple type marked
  with `sign` (`mk_values`), printed `(int64 int64)`; a `[T U]` is an unmarked
  tuple. A group is a `.tuple` node with `aux = TUPLE_VALUES`. Reading a binding
  of such a type, or checking a group, goes through `sink_values_use`, the same
  consumer test as a pack call. A binding of a pack call holds its array's
  elements, read in bounds (`values_init`).
- Call arguments are expanded before overload selection (`values_call`,
  `values_expand`): groups and spread array literals are spliced as written;
  other candidates are checked with no expected type first, as untyped
  arguments always were. The work runs only for Dewy calls with a call, name,
  group or spread argument; a call with nothing to expand is checked as before.
- Length obligations (an unpacking's or a spread's) are runtime `assert`
  intrinsics marked `UNPACK_OBLIGATION` and registered as fact requests: the
  facts erase a proven one, report an unproven one under `$runtime_checks =
  false` and keep it as a check otherwise (directives.jo).
- `[1 2 ; 3 4]` row breaks are standalone `;` tokens. An attached `;` is
  `statement_end`, a discard. On a flow or loop statement it discards everything
  the statement expresses.
