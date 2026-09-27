# Value semantics, copies, and places

Dewy primarily has value semantics. Ordinary rebinding behaves as an independent value, while the compiler may realize that with a copy, move, ownership transfer, or unobservable sharing. `@` explicitly requests a reference and is required at both the call site and in the signature.

Both compilers preserve independent values across ordinary bindings,
assignments, arguments and returns. The implementation combines proven
borrows and moves with a provisional copy-on-write fallback. Fixed local
storage may live in the frame when lifetime analysis proves it cannot escape.
Runtime arrays, nested records, dictionaries and tagged unions retain their
value semantics regardless of placement. This is not a promise that every
source assignment performs a physical copy.

Implementation coverage and remaining ownership restrictions are tracked in
[the Phase 1 checklist](../PHASE1_PROGRESS.md#current-completion-checklist-2026-09-27).
First-class escaping places and capturing function values remain unsupported.

A binding names a value. Assignment, argument passing, and return give you that value, not another name for the same cell. Element and field writes go through the binding you wrote. Sharing is either unobservable or spelled.

This matches the documented object rule: assigning, passing, and returning copy. Arrays follow the same rule. The Python-like experience is cheap literals, in-place writes on _this_ name, and no `clone()` in ordinary code. Moves, borrowing, ownership transfer, and unobservable sharing are how that can stay fast without making universal copy-on-write part of the language model.

```dewy
let a = [1 2 3]
let b = a
b[0] = 9          # a is still [1 2 3]

let original = [x = 10 y = 20]
let copy = original
copy.x = 32       # original.x is still 10

const snapshot = a
a[0] = 9          # snapshot is still the old value
```

`let` versus `const` is the mutability knob: `const` cannot be rebound and cannot take indexed or field writes. A `const` snapshot of a `let` value does not change when the `let` is written later.

Arrays, records, dictionaries, sets, and strings support an explicit `.copy()`:

```dewy
let snapshot = original.copy()
snapshot[0] = replacement     # original keeps its old value
```

The receiver is evaluated once. This requests an independent value, not a
particular allocation or an eager byte-for-byte clone: a dying fresh result
can transfer its storage, and the provisional copy-on-write implementation
can share storage until a write. Checked IR and copy reports retain the
explicit intent. A record's own `copy` field or method takes precedence over
the synthesized operation. Strings retain their contents independently of
the receiver's storage lifetime; unused temporary copies are released at the
end of their consuming statement. General unions and optional aggregates
support the same operation: only the active alternative is copied, and a
user-declared `copy` member is not silently replaced. Declared `$__copy__` hooks and synthesized component copies participate in
ordinary fact/effect checking. A `$__drop__` type without `$__copy__` is
move-only: a read may borrow, and a last use may transfer ownership, but a use
requiring two independent resources is rejected.

`$explicit_copies` opts a module into rejecting unproven runtime-sized copies.
Use `.copy()` when an independent value is intended, or `const view = @owner`
when stable borrowed storage is required. Without the directive, permitted
implicit copies remain visible in `dewy analyze`. Shared immutable strings,
including strings nested in fixed aggregates, are exempt from this policy;
mutable runtime-length payloads and strings copied out of an allocator scope
retain their copy obligations. Backend placement must not change acceptance.

Custom copy/move hooks may have effects. Their effects remain checked, but
elidable operations do not guarantee a particular hook invocation count.

Slices and nested elements are values too. `A[1]` on a multidimensional array, and `nested[1]` on an `array<array<T>>`, both produce a value. `A[1 0] = 9` mutates `A`. `row = A[1]  row[0] = 9` does not.

```dewy
myarr = update(myarr)
```

is the usual way to thread an updated array through a function. If `myarr` is unique, lowering elides the copy. `@` is for the cases a return cannot say cleanly: in-place algorithms, several outputs, reduce-into an accumulator, a buffer the callee must fill.

Default argument expressions run on every call that omits them, so `(a:array = []) => ...` already mints a fresh array per call.

## Places

The current compiler supports places rooted in named mutable scalar, array, or structural-object bindings, including routes through object fields and individual array elements. The caller and parameter storage contracts must match, a `const` root cannot be passed, and potentially overlapping routes cannot occupy two place arguments in one call. Nested calls may forward a place. A local `let cursor = @route` may retain a checked place through its last use;
`const view = @route` requests a read-only view. Both require the owner to
remain alive and its selected storage to remain stable. A place cannot be
returned or stored in an aggregate.

A nominal child may lend its parent portion when the inherited fields have
identical writable contracts. The callee's transitive access summary must
prove that it neither replaces nor exposes the whole parent place: the
complete value remains the child. Unknown callbacks cannot supply that
proof. Field-only updates through known helpers are valid; strengthening a
parent field in the child prevents lending it through a wider writable type.

`@x` is the place `x` lives. A bare name is the value (or, for a function, the call). That is already how `@` works on functions: `sum` calls, `@sum` is the handle. Arrays and objects use the same word as the opt-in hole in value semantics.

`@` on a parameter is a binding convention, not a type constructor. Inside the function body, the name still has type `T`. You write `a[10] = 42`, not `(@a)[10]`. That keeps `@T` from becoming a first-class identity type on day one.

Field and index selection form one place route. `@` occurs only at the beginning, and `@pair.left` selects the place occupied by `left` at the end of the complete route. The parser groups it as `(@pair).left`, but `@pair` is not an independently observable intermediate reference value. The same rule composes through `@matrix[row][column]` and mixed routes such as `@box.items[i]`. Parenthesized `@(pair.left)` selects the same final place. Every selector expression is evaluated once before the call.

Mark a place on both sides for ordinary values:

```dewy
some_fn = (@a:array<int64><length>?10> b:bool) => {
    a[10] = 42     # writes the caller's place
    b = false      # rebinds the local copy
}

myarr = [1 2 3 4 5 6 7 8 9 10 11 12 13]
some_fn(@myarr true)     # ok
some_fn(myarr true)      # error: expected a place

set_value(@record.count) # place of one field
set_value(@values[i])    # place of one element
```

Signature-only marking makes `some_fn(myarr)` look like a copy. Call-site-only marking makes every function a potential mutator. Both sides are required so ordinary calls stay copies and length refinements stay local.

Once `a` is a place, both element writes and rebinding write the caller:

```dewy
some_fn = (@a:array<int64>) => {
    if a.length >? 10 {a[10] = 42}   # update in place
    a = [0 0 0]  # replaces the whole thing in place
}

myarr = [1 2 3 4 5 6 7 8 9 10 11 12 13]
some_fn(@myarr)
# myarr = [0 0 0]
```

After `some_fn(@myarr)`, refinements on `myarr` are suspect. That invalidation is local to the `@` argument.

For now, a place cannot outlive the binding that roots its route. Legal today: pass `@myarr`, `@myarr[3]`, or `@obj.field`, write through the parameter, and return normally. A lifetime-bounded local such as `let c = @a` uses the same checked routes. Not legal: return `@a`, store `@a` in an object, or use `@[1 2 3]` (a temporary has no stable root to update).

`@?` (pronounced "is at?") means "is same place?", not residual copy-on-write sharing. Two copies are never the same place, even before anyone writes. If `@?` could see shared buffers, the optimization would leak into the semantics.

Overlapping places in one call are an error: `swap(@x @x)` is two mutable aliases of one cell. A `const` binding cannot be passed to a writing `@`. Read-only storage may be shared invisibly without `@` because that cannot change program behavior.

`__at__` is `@a`. `__is_at__` is `a @? b`. The spelling of an explicit function copy is still tdb.

## Functions

A bare function name calls it if that would be a valid call. There is therefore no `g = f` copy the way there is for arrays and objects. In the planned function-handle model, `@fn` selects the function binding's place as the handle used for passing and partial evaluation. The same whole-route rule makes `@obj.fn` select the function-valued place `fn` at the end of the route; the old interpreter spelling `obj.@fn` is not the current direction.

A leading `@` puts the complete ungrouped selector-and-application chain in place-selection mode and suppresses calls at every function-valued node in that chain. This does not materialize each intermediate node as a separately observable place; the place remains the endpoint of the whole route. Argument groups inside the `@` chain partially evaluate the selected function rather than invoking it. Grouping ends the `@` chain, after which an argument group is an ordinary call.

```dewy
@worker.callback.metadata     # `metadata` on the callback function value
worker.callback().metadata    # call callback, then read result.metadata
(@worker.callback)(5).metadata # select callback, call it, then read result.metadata
```

The ordinary call resolves its callee without first automatically calling it. `@sum(5)` saves an argument, whereas `(@sum)(5)` calls the selected function. Repeated argument groups remain inside the same `@` chain, so `@sum(1)(2)` performs two stages of partial evaluation. To call after the first stage, terminate the chain with grouping: `(@sum(1))(2)`.

An empty argument group inside the chain is an empty partial evaluation. It does not call the function or evaluate signature defaults. Thus `@worker.callback(5)()` is still a partially evaluated function; `(@worker.callback(5))()` invokes that function.

The selected function may be at the end of a member route. Partial evaluation applies to that endpoint and preserves the receiver captured by the function field:

```dewy
on_item = @worker.callback(5)   # save 5 in worker.callback; do not call it
```

If the function is a member of an object produced by another call, bind that result first and then select the inner function. `@` cannot begin a place route at a temporary, and `@make_worker()` is an empty partial evaluation of `make_worker` rather than a call.

```dewy
worker = make_worker()
on_item = @worker.callback(5)
```

```dewy
sum = (a b) => a + b
add5 = @sum(5)           # new function: freeze some arguments
reference = @sum         # handle / location of `sum`, not a copy
```

`@sum(5)` is intended to construct a new function value. `reference = @sum` instead names the original function place. Whether every escaping handle preserves that identity, and the spelling of an explicit function copy, remain to be finalized with function-handle lowering.

At a call site you already have to write `@fn` to pass a function rather than call it. Marking the parameter `@f` in the signature is therefore intended to be unnecessary; a function-typed parameter can request the handle directly.

```dewy
apply = (f:(int:>int) x:int) => f(x)
# same as
apply = (@f:(int:>int) x:int) => f(x)

apply(@sum 5)
```

The intended signatures are interchangeable because a function value cannot be passed without `@` anyway. The exact mutation and copy behavior of escaping callable handles remains planned rather than being inferred from the implemented nonescaping data-place ABI.

Ordinary values stay the opposite default: bare argument is a copy, `@` at both the signature and the call site is the place.

## Lowering

Representation stays use-dependent. Two values with the same Dewy type may use different machine layouts. Sharing a pointer for `let b = a` is an elided copy, not the language rule. If both names can be written, lowering must either give them independent storage or otherwise prove that sharing cannot be observed.

Proven cases already point this way: caller-owned recursively fixed array and object returns, borrowed read-only parameter adapters, `string as array<uint8>` copy-on-write, and fresh default arrays per call. Local raw-pointer alias chains for non-escaping exact arrays must be justified as unobservable copies, or replaced when both bindings can be written.

A descriptor, capacity, owner, or runtime stride appears only when some reachable use needs it. Places compile as a nonescaping borrow of the final storage selected by the root-and-route expression, with writeback of any rebinding.

## Performance

A possible slight deviation from the above, one of Dewy's goals is to be usable in systems programming contexts. So hidden, potentially unbounded copies are something to avoid. For example, if:

```dewy
b = a
```

could silently memcpy a 200 MB buffer at an unpredictable point, that would be unacceptable for many systems workloads.

A better rule:

Assignment has value behavior, but the implementation must be able to realize it through moves, ownership transfer, sharing of immutable storage, or explicit copy operations.

probably avoid making copy-on-write the universal mechanism. It is excellent for usability, but it can introduce hidden refcount traffic, branches, and latency spikes when mutation forces a copy. For systems work, move + borrow + explicit clone/copy is usually more predictable.

A good design probably would use different strategies by type:

- Small structs/scalars: just copy them.
- Large uniquely owned buffers: move them.
- Read-only/shared data: share storage.
- Strings/arrays: optionally use CoW where that tradeoff is good.
- Systems-facing types: expose explicit ownership/borrowing so there are no surprise CoW copies.
- User-defined types: perhaps let library authors choose whether a value type is plain-copy, move-only, or CoW-backed.

Dewy doesn't necessarily need to use exactly this breakdown, but the goal is for consistent/predictable performance suitable for low level work

## Explicit managed handles

A user-defined shared-ownership type such as `Rc<T>` remains compatible with value semantics: the value being copied is an explicit handle, whose copy operation retains its shared payload. `@rc` selects the caller's storage for that handle; it does not mean "the payload behind this handle" and is not the mechanism that makes the payload escape.

Supporting such types requires deterministic copy/transfer/release hooks, typed allocation capabilities, and lifetime-bounded payload places. The provisional substrate and its relationship to `@` are recorded in [`user_managed_storage.md`](user_managed_storage.md).

## Resource iteration

An iterator keeps its source alive until the loop no longer needs it. This
also applies to a temporary returned by a factory. Normal completion and
early exits release owned elements through their lifecycle hooks before
releasing their storage. Dictionary key/value iteration evaluates the
dictionary once; multiple iterator sources retain their evaluation order.

The loop binding is a read-only loan of the current element. Creating an
independent, mutable local from it uses the type's ordinary copy operation.
The compiler can borrow a stable source or transfer an owner at its last use;
otherwise it needs a valid copy. Move-only elements can therefore be read
without requiring a copy hook. Dictionary mutation during iteration remains
rejected by the existing container-stability check.


## Scoped raw storage

`$lend(bytes) { ... }` lends a named byte array's storage for one expression.
The existing `__load_i64__(bytes)` operation obtains the element address, and
`bytes.length` remains readable. The owner stays alive through the expression;
the checked extraction does not permanently pin its storage.

```dewy
let written = $lend(bytes) {
    let address = __load_i64__(bytes)
    __syscall3__(1 fd address bytes.length)
}
```

The initial implementation accepts scalar local work, raw word reads, and
Linux x86-64 synchronous `write` (also through the C backend). An address or
anything derived from it cannot escape through a result, outer assignment,
aggregate, closure or unmodeled call. Assignments and loop backedges propagate
address origins to a fixed point. The owner cannot be mutated, replaced or
passed elsewhere inside the expression. Unknown operations are rejected;
the compiler grants unpinned access only after checking the whole body.
The Linux x86-64/C stdout, stderr and file-writing library paths use these
loans. File reads use writable loans to fill array storage in bulk.
Unscoped raw exposure retains the existing pinning rule.

Writable `$lend(@bytes reserve=n)` accepts a named, growable array of
unrestricted `uint8`. It evaluates `n` once, reserves that many **additional**
bytes and detaches existing shared snapshots before lending the address.
Omitting `reserve` means zero additional bytes. Byte stores and synchronous
Linux x86-64/C reads may write through the scoped address.

```dewy
$lend(@bytes reserve=4096) {
    let address = __load_i64__(bytes)
    let count = __syscall3__(0 fd address + bytes.length 4096)
    if count >? 0 and count <=? 4096 {
        bytes.set_length(bytes.length + count)
    }
}
```

`set_length` is available only on the active writable owner. Every commit
must prove a nonnegative length no greater than the captured entry length
plus reservation; the compiler inserts no implicit runtime check. Raw writes
invalidate element facts. Ordinary owner reads, alias creation, growth and
replacement remain forbidden inside the scope. Raw address arithmetic is
still low-level code: this lifetime permission does not prove each byte
store's offset or initialization of every committed byte. Allocation failure
policy remains open, as for ordinary array reservation.

Strings and arbitrary aggregate owners are outside this initial subset.


Resource array sorting preserves the stored owners while permuting their
handles. An owning by-value key callback receives an independent value
through the checked copy operation and drops that argument normally. Those
copies obey `$explicit_copies` and contribute hook effects; an unknown or
mutating hook cannot invalidate the sort receiver. Move-only elements cannot
be supplied to an owning key while the array retains them. Borrowed key
parameter syntax is not introduced by this implementation.
