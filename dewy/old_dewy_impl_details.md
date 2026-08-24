# Old Dewy interpreter notes

Historical behavior from `src/backend/python.py`. This is not a ratified spec
and several paths were unfinished (`pdb.set_trace()`, `NotImplementedError`).
Use it when reimplementing the same surface in cleanparse. The example programs
below are often clearer than the code.

> **Current syntax note:** this interpreter used member-handle spellings such as
> `obj.@fn`. The current language direction uses one compositional place route:
> `@obj.fn` is parsed as `(@obj).fn`, selecting the place or callable field at
> the end of the route. The older spellings below are retained only as a record
> of that implementation.

Related examples: `examples/closure.dewy`, `examples/partial_functions.dewy`,
`examples/unpack_array.dewy`, `examples/unpack_dict.dewy`, `examples/objects.dewy`,
`examples/hello_name.dewy`.

---

## Closures and object fields

A function literal is never a bare callable. Evaluating it wraps it:

```
Closure(fn=FunctionLiteral, scope=<scope at evaluation time>)
```

Calling a closure:

1. Child of the *captured* scope is the body scope.
2. Child of the *caller* scope is used only to evaluate the call's arguments.
3. Call args/kwargs are stashed on `scope.meta[closure].call_args` by `evaluate_call`, then read by `evaluate_closure`.
4. `resolve_calling_args` binds every parameter into the body scope, then the body runs there.

So free names see the definition environment. Parameters shadow those names for that call only. The captured scope is shared across calls (later assignments in an enclosing `let` are visible).

A `{...}` block is a fresh child scope. Returning `@fn` from a block is how a nested function escapes with its locals:

```dewy
my_closure = {
    b = 10
    fn = c => a + b + c
    @fn
}
```

Without `@`, expressing `fn` would *call* it (see `@` below).

### Objects are scopes

`evaluate_object_literal` makes a child of the current scope, evaluates the field declarations in that child, and wraps the child as `Object(scope=...)`.

Field function literals therefore capture the object scope, so `obj.fn` can read sibling fields `a` and `b`. Member lookup uses `search_parents=False`: only the object's own bindings, not the surrounding module.

```dewy
obj = [
    let a = 5
    let b = 10
    let fn = () => a + b
]
printl(obj.fn)   # calls fn, prints 15
printl(obj.@fn)  # the function value itself
```

`obj.B` vs `obj.@B`: `evaluate_access` on a plain identifier evaluates the field value (a zero-arg closure fires). `obj.@name` looks up the same binding and returns it uncalled.

---

## `@`, expressing, and partial application

`@` is prefix `AtHandle`. On an identifier it is a lookup that does **not** evaluate the stored value:

```
evaluate_at_handle(@name) = scope.get(name).value
```

Bare use of a name is `Express`. That looks up the value and then `evaluate`s it. A stored `Closure` or zero-arg `Builtin` therefore runs. `@name` is the way to talk about the function instead of calling it.

```dewy
printl(@printl)     # handle
printl              # would call printl with its default
```

Implemented `@` operand: identifier only.

### Partial application is `@` plus a call

`evaluate_call` has a special case: if the callee *is* an `AtHandle`, it does not invoke. It calls `apply_partial_eval(operand, args, caller_scope)` and returns a new `Closure` or `Builtin` with an updated signature. The captured scope of the original closure is kept.

```dewy
let add = (a b) => a + b
let add5 = @add(5)       # remaining: (b) effectively, with a bound
let add7 = @add(a=7)
```

`update_signature` (used by partial apply):

- Collect call args/kwargs (often still ASTs, not values).
- A keyword that fills a keyword-only slot replaces that slot's default with a *suspended* value.
- A keyword that fills a positional-or-keyword slot *moves* that slot into keyword-only, with a suspended value. Once you bind a pkwarg, it is no longer positional.
- Positional args fill leftover positional-only slots first, then leftover pkwargs. Each filled slot is removed from the positional side and appended as keyword-only with a suspended value.
- Too many positionals is an error.

`suspend(ast, scope)` is `Closure(fn=(() => ast), scope=scope)` — a deferred
zero-argument expression carrying the partial-application scope. In this old
implementation, saved expressions were therefore re-evaluated when the
*resulting* function was later called, rather than when `@fn(...)` ran. The
current language design instead evaluates explicitly supplied partial values
immediately.

`resolve_calling_args` (used by a real call):

- Evaluate the call's positional/keyword args in the *caller* scope.
- Keyword args from the call win; those names are removed from the remaining signature.
- Leftover keyword-only defaults evaluate in the *closure* scope.
- Remaining positional/pkwarg slots pair with leftover positionals; anything still unbound must be an `Assign` default, also evaluated in the closure scope.
- Too many positionals is an error. A leftover required parameter (not an `Assign`) is an error.

Because suspended bindings are themselves closures, evaluating a deferred
default also evaluates its saved expression at bind time.

### `@` vs not-`@` on a passed function

From `examples/closure.dewy`:

```dewy
B = () => '@Blueberry'
A = () => '@Apricot'
@fn(b=B)     # B is looked up now; the saved expression calls B when fn is called; parameter `b` is already a string
@fn(a=@A)    # `@A` stays a handle; parameter `a` is the function; the body IString calls it while interpolating
```

`collect_calling_args` treats a bare identifier as an immediate lookup (`scope.get(name).value`) and an `AtHandle` as an unevaluated AST. That is why the two forms differ.

Unfinished: spreading arguments into a call (`...xs`), unpack targets as call args, `@` of a raw function literal (the code assumed you parenthesize so it is already a `Closure`).

---

## Interpolated strings

`IString` is a list of parts (literal `String` chunks and embedded expressions).

```
evaluate_istring = String(join(py_stringify(part) for part in parts))
```

`py_stringify` evaluates its argument unless it is already a `Closure` or `Builtin`. `Express` / other ASTs therefore run in the *current* scope — the closure body that is evaluating the string, not the scope where the IString node was parsed.

Consequences:

- `s = 'x={x}'` inside a nested function sees that function's `x` when the string is evaluated, even if `s` was built in an inner block and returned (`examples/closure.dewy`).
- Interpolating a name whose value is a `Closure` goes `Express` → `evaluate(closure)` → a zero-arg call, then stringifies the result. That is the `@A` / IString interaction above.
- Stringifying a `Closure` that is *already* a value (not re-evaluated) prints the function literal text, not a call result.

`printl'Hello {name}!'` is juxtaposition of `printl` with an `IString` (resolved as a call). `readl` is a zero-arg builtin that becomes `input()` and returns a `String`.

This is a dynamic interpreter. It does not model compile-time vs runtime interpolation, grapheme strings, or encoding.

---

## Unpack assignment

`a, ...b, c = value` is `Assign(left=UnpackTarget, right=value)`. The right-hand side is evaluated first, then `unpack_assign`.

Also used as the binder for `name in iterable` when the left side is an unpack target (`evaluate_iter_in`).

### Sources

Implemented: `Array`, `Dict`, `PointsTo`, `BidirDict`, `BidirPointsTo`, `Undefined`.

`String` is a hack: it becomes an array of one-character `String`s, then unpacks as an array.

Object-field unpack (`{a, b}` / rename) was not implemented. `let a, b = ...` (declare + unpack) hits a breakpoint.

### Cardinality

- At most one `...` collect (`CollectInto`) in the target list.
- `undefined` becomes `N` undefineds, where `N` is the number of *non-spread* targets. A spread in that case collects an empty array (`spread_size = 0`).
- `spread_size = num_values - num_targets + 1` (the extras plus the one slot the `...` occupies).
- Too few values: `num_targets - num_spread > num_values`.
- Too many values: leftover items after walking the targets. A spread absorbs leftovers, so this only fires when there is no `...`.

### Target walk (left to right)

| Target | Action |
|---|---|
| `Identifier` | assign the next value |
| nested `UnpackTarget` | recurse on the next value |
| `...name` | assign an `Array` of the next `spread_size` values |
| `...[nested]` | collect those values into an array, then recurse unpack |

Examples from `examples/unpack_array.dewy`:

```dewy
s = ['Hello' ['World' '!'] 5 10]
a, b, c, d = s          # exact
a, ...b = s             # b = rest
...a, b = s             # a = all but last
a, [b c], ...d = s      # nested unpack of the second element
a, ...b, c, d, e = s    # spread in the middle
```

Commented errors there: too many targets, too few targets, spread that still leaves the fixed slots larger than the source.

Dict unpack iterates the dict's children (pairs), not keys-only. That is whatever `__iter_asts__` produced for `Dict` / `PointsTo`, not a designed key/value protocol.

---

## Call / express recap

```
name            Express: lookup, then evaluate (zero-arg callables fire)
@name           AtHandle: lookup only
name(args)      call
@name(args)     partial application, new Closure/Builtin
obj.name        lookup in object scope, then evaluate
obj.@name       lookup in object scope, return uncalled
```

`evaluate_call` on a group first evaluates the group (so `(fn)(x)` works). On an identifier it looks up, then calls or partial-applies.

---

## Known holes in this interpreter

- No capturing-local lowering story; everything is a Python scope pointer.
- No rest/spread *into* calls (`fn(...xs)`).
- No object unpack, no declare-and-unpack.
- `@` only on identifiers.
- IString evaluation is eager and untyped.
- `printl` / `readl` are host builtins, not `library/io.dewy`.
- Iterator `iter_next` is a separate, incomplete range/array walker; cleanparse already has a stricter iterator model.
