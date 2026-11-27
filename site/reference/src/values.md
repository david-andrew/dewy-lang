# Values, Copies, and Places

> [Generated coverage](/status/#ref-values) names related acceptance programs. Every example on this page compiles with the current compiler unless it is marked **Design only**.

## Value Semantics

Assignment, argument passing and return supply an independent value. Changing the destination never changes the source.

<!-- dewy-example: {"mode":"run","stdout":"[1 2 3] [9 2 3]\n"} -->
```dewy
let original = [1 2 3]
let copy = original
copy[0] = 9
printl"{original} {copy}"
```

Scalars, strings, arrays, objects, dictionaries, sets and closures all follow this rule. The compiler realizes the semantic copy however it likes: a physical copy, a move at a last use, a borrow of read-only data, or sharing of immutable storage. Strings and `int` values are immutable shares, so keeping, passing or returning one never duplicates it.

## Places

`@` selects the place a mutable value occupies. A parameter that accepts a place carries `@`, and so does the argument, so caller-visible mutation is explicit at both ends:

<!-- dewy-example: {"mode":"run","stdout":"[9 2 3]\n"} -->
```dewy
set_first = (@xs:array<int64 length=3>):>void => {
    xs[0] = 9
}

let values:array<int64 length=3> = [1 2 3]
set_first(@values)
printl(values)
```

Passing a value to an `@` parameter, or `@x` to a value parameter, is an error:

<!-- dewy-example: {"mode":"reject","diagnostic":"a mutable argument needs `@` at the call site"} -->
```dewy
set_first = (@xs:array<int64 length=3>):>void => { xs[0] = 9 }
let values:array<int64 length=3> = [1 2 3]
set_first(values)
```

<!-- dewy-example: {"mode":"reject","diagnostic":"this parameter takes a value: drop the `@`"} -->
```dewy
show = (xs:array<int64>):>void => printl(xs)
let values:array<int64> = [1]
show(@values)
```

`@` of a function is its handle, not a place; see [Function Handles](functions-and-calls.md#function-handles).

## Place Routes

A leading `@` selects the place at the end of the whole field-and-index route: `@pair.left`, `@values[i]`, `@box.rows[r][c]`. `@(pair.left)` selects the same place. There is no `pair.@left` form. An index in a route evaluates once, before the call.

<!-- dewy-example: {"mode":"run","stdout":"[left=2 right=3] [10 21 30]\n"} -->
```dewy
bump = (@value:int64):>void => { value += 1 }
Pair:type = [left:int64 right:int64]

main = () => {
    let pair = Pair(1 2)
    let values:array<int64> = [10 20 30]
    let i = 1
    bump(@pair.left)
    bump(@values[i])
    bump(@(pair.right))
    printl"{pair} {values}"
}
```

## Aliasing Rules

A mutable place is invariant in its type: an `int` local is not an `@int64` place. A `const` binding provides no mutable place.

Two mutable place arguments in one call must be disjoint. Distinct fields and distinct constant indices are disjoint. The same binding, a parent and its field or element, and possibly equal indices of one array overlap:

<!-- dewy-example: {"mode":"reject","diagnostic":"mutable arguments 1 and 2 overlap"} -->
```dewy
swap2 = (@a:int64 @b:int64):>void => {
    let t = a
    a = b
    b = t
}
main = () => {
    let xs:array<int64> = [1 2]
    swap2(@xs[0] @xs[0])
}
```

## Local Places

Inside a function, `let name = @route` declares a local place: reads and writes of `name` read and write the route, and an index in it evaluates once at the declaration. A local place can name a whole variable, an element, a dictionary entry or a field of a local variable. A top-level local place is not supported.

<!-- dewy-example: {"mode":"run","stdout":"42\n[1 2 4]\n"} -->
```dewy
main = () => {
    let xs:array<int64> = [40]
    let cursor = @xs[0]
    cursor += 2
    printl(xs[0])
    let ys:array<int64> = [1 2]
    let p = @ys
    p.push(4)
    printl(ys)
}
```

## Read-Only Views

`const name = @route` is a read-only view of stored data. The compiler proves the storage stays valid and unchanged while the view is in use; it never silently replaces the view with a copy. A write to the route before the view's last use is an error at the write.

<!-- dewy-example: {"mode":"run","stdout":"5\n"} -->
```dewy
Box:type = [value:int64]
read = (boxes:array<Box length=1>):>int64 => {
    const box = @boxes[0]
    return box.value
}
printl(read([Box(5)]))
```

<!-- dewy-example: {"mode":"reject","diagnostic":"this write conflicts with const view 'view'"} -->
```dewy
main = () => {
    let xs:array<int64> = [1 2]
    const view = @xs
    xs.push(3)
    printl(view.length)
}
```

A view introduces no allocation: a function that only reads its by-value input through views can state `no_effects`. Ordinary read-only locals already borrow when the compiler can prove it safe; the explicit form demands it.

## Requiring Explicit Copies

The `$explicit_copies` setting rejects an implicit copy of runtime-sized storage that the compiler cannot turn into a move or a borrow. It applies to the module, function or block it is written in. Only costly copies count: sharing an immutable string is not a copy. Use `.copy()` when an independent value is intended, or `const view = @source` for a borrow. `$explicit_copies = false` turns it off.

<!-- dewy-example: {"mode":"reject","diagnostic":"implicit costly copy of array<int64>"} -->
```dewy
$explicit_copies
main = () => {
    let a:array<int64> = [1 2]
    a.push(3)
    let b = a
    b.push(4)
    printl"{a} {b}"
}
```

<!-- dewy-example: {"mode":"run","stdout":"[1 2 3] [1 2 3 4]\n"} -->
```dewy
$explicit_copies
main = () => {
    let a:array<int64> = [1 2]
    a.push(3)
    let b = a.copy()
    b.push(4)
    printl"{a} {b}"
}
```

## Scoped Allocators

`$allocator(@scratch) expression` allocates from an `Arena` for the whole next expression; braces group several statements under one request. Results leave the scope with independent storage, so resetting the arena does not invalidate them. The arena cannot be used while it is lent.

<!-- dewy-example: {"mode":"run","stdout":"n=3\n"} -->
```dewy
build_summary = (n:int64):>string => "n={n}"
main = () => {
    let scratch = Arena[]
    let summary = $allocator(@scratch) build_summary(3)
    scratch.reset()
    printl(summary)
}
```

## Resource Types

A nominal record can declare a compiler-only `$__drop__` hook, a function with no parameters and a `void` result. It runs once when each owner's lifetime ends: at scope exit, replacement, return, loop exit, a panic or `exit`. A parent's hook runs before its fields are cleaned up in reverse order; arrays clean up their elements in reverse order.

<!-- dewy-example: {"mode":"run","stdout":"7\n"} -->
```dewy
let released:int64 = 0
Ticket = type of [id:int64
    $__drop__ = ():>void => { released += id }
]
main = () => {
    {
        let _a = Ticket(3)
        let _b = Ticket(4)
    }
    printl(released)
}
```

Without a `$__copy__` hook such a record is move-only: a proven last use transfers it, a read-only use borrows it, and `.copy()` cannot duplicate it. `$__copy__` and `$__move__` hooks return the same type.

## Storage

Where bytes live is the implementation's choice, observable only as cost. Every stored string, array and object has exactly one owner. A transfer at a value's last use (`return xs`, `box.items = xs`) is a move. Runtime-sized storage is released when its owner's scope ends, when it is overwritten, or at each iteration of a loop that built it, so building and dropping strings, arrays, objects and dictionaries in a loop runs in constant memory.

There is no place-identity test and no first-class reference: places are borrows, and storing or returning a place is an error.
