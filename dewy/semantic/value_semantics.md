# Value semantics, copies, and places

BLUF: basically matlab style, assignments copy (with COW under the hood), `@` is used for references (needed on both both sides, call site and in signatures)

Intended language rule. Not implemented. Lowering may share storage only when that sharing is unobservable or the program asked for a place with `@`.

A binding names a value. Assignment, argument passing, and return give you that value, not another name for the same cell. Element and field writes go through the binding you wrote. Sharing is either unobservable or spelled.

This matches the documented object rule: assigning, passing, and returning copy. Arrays follow the same rule. The Python-like experience is cheap literals, in-place writes on _this_ name, and no `clone()` in ordinary code. Copy-on-write and uniqueness proofs are how that stays fast.

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

Slices and nested elements are values too. `A[1]` on a multidimensional array, and `nested[1]` on an `array<array<T>>`, both produce a value. `A[1 0] = 9` mutates `A`. `row = A[1]  row[0] = 9` does not.

```dewy
myarr = update(myarr)
```

is the usual way to thread an updated array through a function. If `myarr` is unique, lowering elides the copy. `@` is for the cases a return cannot say cleanly: in-place algorithms, several outputs, reduce-into an accumulator, a buffer the callee must fill.

Default argument expressions run on every call that omits them, so `(a:array = []) => ...` already mints a fresh array per call.

## Places

`@x` is the place `x` lives. A bare name is the value (or, for a function, the call). That is already how `@` works on functions: `sum` calls, `@sum` is the handle. Arrays and objects use the same word as the opt-in hole in value semantics.

`@` on a parameter is a binding convention, not a type constructor. Inside the function body, the name still has type `T`. You write `a[10] = 42`, not `(@a)[10]`. That keeps `@T` from becoming a first-class identity type on day one.

Mark a place on both sides for ordinary values:

```dewy
some_fn = (@a:array<int length>?10> b:bool) => {
    a[10] = 42     # writes the caller's place
    b = false      # rebinds the local copy
}

myarr = [1 2 3 4 5 6 7 8 9 10 11 12 13]
some_fn(@myarr true)     # ok
some_fn(myarr true)      # error: expected a place
```

Signature-only marking makes `some_fn(myarr)` look like a copy. Call-site-only marking makes every function a potential mutator. Both sides are required so ordinary calls stay copies and length refinements stay local.

Once `a` is a place, both element writes and rebinding write the caller:

```dewy
some_fn = (@a:array<int length>?10>) => {
    a[10] = 42   # update in place
    a = [0 0 0]  # replaces the whole thing in place
}

myarr = [1 2 3 4 5 6 7 8 9 10 11 12 13]
some_fn(@a)
# a = [0 0 0]
```

After `some_fn(@myarr)`, refinements on `myarr` are suspect. That invalidation is local to the `@` argument.

For now: A place cannot outlive the binding it names. Legal: pass `@myarr`, write it, return normally; later, local `let c = @a` for the lifetime of `a`, and places of parts such as `@myarr[3]` or `@obj.field`. Not legal at first: return `@a`, store `@a` in an object, or `@[1 2 3]` (a temporary has nowhere to write back).

`@?` (pronounced "is at?") means "is same place?", not residual copy-on-write sharing. Two copies are never the same place, even before anyone writes. If `@?` could see shared buffers, the optimization would leak into the semantics.

Overlapping places in one call are an error: `swap(@x @x)` is two mutable aliases of one cell. A `const` binding cannot be passed to a writing `@`. Read-only sharing does not need `@`; that is what copy-on-write is for.

`__at__` is `@a`. `__is_at__` is `a @? b`. The spelling of an explicit function copy is still tdb.

## Functions

A bare function name calls it if that would be a valid call. There is therefore no `g = f` copy the way there is for arrays and objects. `@fn` is both the handle used for passing and partial evaluation, and the location of the original function binding.

```dewy
sum = (a b) => a + b
add5 = @sum(5)           # new function: freeze some arguments
reference = @sum         # handle / location of `sum`, not a copy
```

`@sum(5)` constructs a new function value. `reference = @sum` does not. Writes through that handle, including `reference &= other`, affect `sum`. Copying a function needs an explicit operation (TBD syntax); until that spelling exists, functions are not copied by assignment.

At a call site you already have to write `@fn` to pass a function rather than call it. Marking the parameter `@f` in the signature is therefore unnecessary and the sugared version can be to allow ommitting it

```dewy
apply = (f:(int:>int) x:int) => f(x)
# same as
apply = (@f:(int:>int) x:int) => f(x)

apply(@sum 5)
```

The two signatures are interchangeable. The call is unambiguous because a function value cannot be passed without `@` anyway. Consequence: function parameters are places by default. Local `f &= other` writes the caller's function binding. To overload or replace a function without touching the caller, copy first, then write the copy.

Ordinary values stay the opposite default: bare argument is a copy, `@` at both the signature and the call site is the place.

## Lowering

Representation stays use-dependent. Two values with the same Dewy type may use different machine layouts. Sharing a pointer for `let b = a` is an elided copy, not the language rule. If both names can be written, the first write unique-ifies.

Proven cases already point this way: caller-owned exact-length array returns, borrowed read-only parameter adapters, `string as array<uint8>` copy-on-write, and fresh default arrays per call. Local raw-pointer alias chains for non-escaping exact arrays must be justified as unobservable copies, or replaced when both bindings can be written.

A descriptor, capacity, owner, or runtime stride appears only when some reachable use needs it. Places compile as a borrow of the named binding's storage, with writeback of any rebinding.
