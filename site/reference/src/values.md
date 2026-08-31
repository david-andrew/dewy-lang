# Values, Copies, and Places

## Value Semantics

Assignment, argument passing, and return supply an independent value. Mutating the destination cannot change the source merely because an implementation reused backing storage.

```dewy
let original = [1 2 3]
let copy = original
copy[0] = 9                  # original remains [1 2 3]
```

The compiler may realize that semantic copy through physical copying, a move, ownership transfer, borrowed reading, shared immutable storage, or another representation whose differences are unobservable.

Scalar, array, object, string, and container values all follow this rule. A field whose own type has explicit handle semantics retains those semantics when its containing value is copied.

## Places

`@` explicitly selects the place occupied by a mutable value. A parameter that accepts a place also carries `@`, making caller-visible mutation explicit at both boundaries:

<!-- dewy-example: compiler -->
```dewy
let update = (@xs:array<int64 length=3>):>void => {
    xs[0] = 9
}

let values = [1 2 3]
update(@values)
```

Passing `values` without `@` supplies an ordinary value. Passing `@values` to a non-place parameter is likewise a type error.

## Projected Routes

A leading `@` selects the place at the end of the complete field-and-index route:

```dewy
set(@pair.left)
set(@values[i])
set(@box.rows[row][column])
```

The parser groups `@pair.left` as `(@pair).left`, but the language does not expose `@pair` as a separate reference value before applying `.left`. The whole expression refers to the place occupied by `left`. Putting the route inside the prefix, `@(pair.left)`, selects the same place. Grouping the completed selection, `(@pair.left)`, ends the `@` chain; this distinction matters when a following argument group calls a selected function. There is no `pair.@left` form. A computed index in a place route evaluates once before the call.

## Type and Aliasing Rules

A mutable place is invariant in its value type: a callee must not reinterpret the caller's storage through a broader or narrower place contract.

Two mutable place arguments in one call must be proven disjoint. Sibling object fields and distinct constant indices are disjoint. Prefix-related routes overlap. Dynamic indices are potentially overlapping unless analysis proves otherwise.

A `const` binding does not provide a mutable place.

## Escaping Places and Identity

Nonescaping place calls have settled semantics. Storing or returning a place, sharing it across concurrent work, and defining lifetime-bearing place types require the provisional ownership and escape design.

There is no place-identity test: places are borrows rather than first-class values, and the ownership model never exposes storage sharing between independent values, so the once-reserved `@?` was retired (see [Operators and Precedence](operators-and-precedence.md#retired-operators)).

Function handles build on the same root-and-route interpretation of `@`; see [Functions and Calls](functions-and-calls.md#function-handles).

## Provisional User-Managed Handles

The future systems escape hatch builds on, but does not change, the rules above. A library-defined shared-ownership type such as `Rc<T>` is intended to remain an ordinary Dewy value. Copying the handle retains its explicitly shared payload; copying an object containing such a handle does the same recursively. This does not make ordinary arrays or objects reference-semantic values.

`@rc` selects the place occupied by the handle, allowing a callee to replace that handle in the caller's binding. It does not select the allocation behind the handle. Payload access will instead use lifetime-bounded places supplied by the handle type: read-only while shared, and mutable only after unique ownership is established or through a separate checked-mutation abstraction.

The required userland lifecycle and allocation hooks are provisional and not implemented. The current design direction is recorded in the compiler's [`user_managed_storage.md`](https://github.com/david-andrew/dewy-lang/blob/main/dewy/semantic/user_managed_storage.md) note.

## Storage and Escape Copies

Where a value's bytes live is the implementation's business, but it is observable in one way: cost. A string may be static (a literal), arena-backed (decoded bytes, a `join`), owned by a container (an array element, an object field), frame-backed (an interpolation, or a call result copied into the calling frame), or a parameter's (the caller's, unknown to the callee). Storing a string where it outlives the current evaluation — into a growable array, an object field, a union cell — stores a static literal as it is, takes over a fresh arena string nobody else holds (a `join` or a decode stored directly), and copies everything else into the arena, so **every stored string has exactly one owner**. `dewy analyze file.dewy` lists every such *escape copy* with its reason, so the copies a program pays for are never a mystery; the ownership model's later steps (moves by liveness, borrowed parameters) will remove the ones that proofs can.

A transfer at a value's last use is a *move*: `return xs`, `[items = xs]`, `box.items = xs`, or `return box` for a local built here, when nothing uses the local afterwards (and the store is not inside a loop the local outlives), adopts the arena storage instead of copying it. Transfers of a value that is used again copy, as value semantics require. `dewy analyze` lists every transfer of an owned array as a move or a copy with its reason.

An array of strings owns its elements: when a local array's scope ends (or the binding is rebound), the element strings are released with the buffer — so building and dropping string arrays in a loop runs in constant memory. It follows that element strings never alias: reading an element out and storing or returning it copies it, and a copy of a string array (`let copy = parts`) gets its own element strings. `dewy analyze` reports each of these copies too.

Objects own their runtime-sized members the same way. When a local object's scope ends, its string fields, its array fields (with their elements), and the string payloads of its union cells are released; a copy of an object (`let two:Point = one`) owns copies of its own; assigning over a string field (`two.name = "changed"`) releases the value it held; and a literal or call result stored into an array or returned *moves* its members into the new owner rather than cloning them. Dictionaries are objects of arrays, so a local dictionary releases its keys and values too. Building and dropping objects, arrays of objects, and dictionaries in a loop runs in constant memory.

String storage that never leaves a function — slices, decoded bytes, joins that no `return` reaches (stores copy such strings into the arena as described above) — comes from the function's *frame region*, a scoped arena created on entry and released whole at every exit, so string work in a loop does not accumulate. Strings a `return` may hand out, and their sources, stay in the process arena.

A loop body gets a region of its own: a string it builds that stays within the iteration — no assignment carries it to a binding declared outside the loop — is given back at the end of every iteration (`continue` and `break` included), so string work inside a long loop runs in constant memory rather than accumulating until the function returns. A string assigned to an outer loop's variable lives in that loop's region; one assigned to a variable of the function lives in the function's. Stores into arrays, fields, and dictionaries copy, as before.

Runtime-sized storage is released when its owner is done with it. A growable array's old buffer is given back the moment growth relocates it, and a local that owns an array releases it at every exit of its scope — the end of the block, a `return` (after the returned value is computed; a returned array is copied out first), a `break` or `continue`. A loop that builds and drops a 1000-element array 10 000 times therefore runs in constant memory. Only storage the arena owns is released (a literal's static data and a borrowed parameter's are not); nothing is freed twice, because a released descriptor forgets that it owned anything.
