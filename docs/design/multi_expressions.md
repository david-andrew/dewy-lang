# Multi-expressions (decided 2026-10-23; restores the reference)

Dewy is expression-oriented: a construct is not a statement that happens to have a
value, it is an expression that may give one value, several, none, or never
finish. This note specifies how those values move. It restores the archived
reference (`git show archive/master-pre-restart:site/reference/src/expressions-and-operators.md`,
lines 3–21, and `site/learn/src/ch03/expressions-statements-blocks.md`, lines 29–75)
and fills the places it left open. Flagged items are natural extensions, not
reference text.

## The rule

An expression produces one value, several values for a surrounding collector,
`void`, or `never`. A block evaluates its expressions in source order and
**expresses each non-`void` result**. A context requiring one value rejects a
block that can produce an incompatible number of values.

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

A result that is `void` or an error (`void | E`, as from `sleep(1ms)`) is not
expressed in statement position either. Its error is forwarded or handled
through the error rules, not counted as a value. A `spawn` statement in a
`concurrent` block hands its task to the group and expresses nothing.
*Flagged: both keep today's behavior. The reference doesn't address either one.*

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

So `[f(); 7]` is `[7]` after calling `f`, never a matrix. Because
`[1 2; 3 4]` (attached) would silently discard `2`, an attached `;` that discards
a value with no effect (a literal, a name, arithmetic of them) inside an array
literal is a compile error. The message points to the standalone spelling.
*Flagged: this diagnostic is our addition. It's reversible.*

## Contexts

**Collectors take every value.**
- Array literals `[...]`: each element contributes what it expresses, in order.
  `[a {b c} d]` is `[a b c d]`, and `[if c x]` is `[x]` or `[]`.
- Loop capture `[loop ...]` collects every value of every iteration. A body that
  expresses two values per iteration contributes both:
  `[loop i in xs { i  i*10 }]`.
- Spread `xs...` inserts an array's elements. A call expressing several values in
  a collector needs no `...`, and `pair()...` means the same.
- Map, record and set literals are unchanged. Their entries are one value each.

**One-value contexts take exactly one.** These are bindings (`x = e`, `let`),
assignments, operands, conditions, call arguments, indexes, the result of a
function with a written return contract, and the arms of a value `if`/`match`
outside a collecting position. A block there expresses its last expression.
An earlier non-`void` value is an error with a fix-it to attach `;`:

```
x = { log(1)  5 }   # error at log(1): this gives a value, and here the block
                    # gives one, its last expression: attach `;` to discard it
```

Call argument lists are one-value contexts: the reference makes only collectors
spread, and its rest/spread forwarding for calls is still provisional.
*Flagged: once `...rest` forwarding lands, a call expressing several values may
supply several positional arguments; until then it's an error.*

**Statement contexts drop values.** Module-level code and the body of a function
whose contract is `:>void` or `:>void | E` drop what they express. The old
"value is not used" warning stays only here, for values that are discarded and
do nothing (`x == 6`, `speed + 1`).
*Flagged: the reference does not say whether a `:>void` body rejects or drops
expressed values. Dropping follows the contract ("gives nothing"). Rejecting
would be the stricter alternative.*

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
| `x = pair()`, `f(pair())`, `pair() + 1` | error: only one value is taken here. The fix-it is to collect them (`[pair()]`) or to discard the extras in its body |
| `[a b] = [pair()]` | unpacks through the collector |

`[a b] = pair()` (unpacking without the collector) is an error. The unpack
target takes one value apart, and `pair()` is not one value.
*Flagged: allowing it is a possible extension. It's reversible.*

Its type: the function's result is its element type, expressed a number of times
that may vary. Today it has no spelling, so such a function can't carry a written
contract. Diagnostics describe it as "gives several values".
*Provisional, needs David: a contract spelling for "several T". The recommended
form reuses loop capture's vocabulary rather than adding a keyword. Until then,
leave the contract off. It unblocks annotated generators. It's reversible.*

`return value` gives back that one value and ends the function. A function that
expresses values before its end and also uses `return value` is an error for
now, because the stream semantics of `return` after earlier values need a
decision. *Flagged: the natural extension is "earlier values, then the returned
one". Today it's rejected, which is the conservative choice.*

A function value (`@pair`) of a function expressing several values is not
checked yet. The compiler tracks the count on direct calls only, and a call
through such a value currently sees the collected array as one value. This is
a known gap: the fix is to reject `@pair` until function types can say
"several values".

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
  `:>void` bodies), one (one-value contexts and written contracts), body (an
  inferred function result), arm (an arm of the `if`/`match` ending a body, whose
  values belong to the body), and collector (loop capture and `[...]` with block
  or flow elements, which the frontend builds as an accumulator and pushes, as
  loop capture always was).
- A body sink creates its accumulator only when a second value, a value inside a
  loop, or a multi-valued call appears. Earlier pending values are then rewritten
  in place into pushes. A body expressing exactly one value, its last, checks
  exactly as before. Single-value code pays nothing per node: the sink
  bookkeeping runs per block and per expressed value.
- A multi-valued function returns its accumulator array. Its `FnInst.pack` marks
  it, and only a consumer that asked for several values (array element, spread,
  statement, final value of a collecting body) accepts the call. Any other use is
  the one-value error.
- `[1 2 ; 3 4]` row breaks are standalone `;` tokens. An attached `;` is
  `statement_end`, a discard. On a flow or loop statement it discards everything
  the statement expresses.
