# Values, Copies, and Places

Dewy uses value semantics by default. Assigning, passing, or returning a value gives the destination an independent value:

```dewy
let original = [1 2 3]
let copy = original
copy[0] = 9

# original is still [1 2 3]
```

The compiler does not need to physically copy every byte. It may move storage, borrow it for reading, or share immutable backing data whenever the program cannot observe a difference.

## Asking a Function to Update Your Value

When mutation should be visible to the caller, pass a place with `@`. The parameter also carries `@`:

```dewy
let increment = (@value:int64):>void => value += 1

let count:int64 = 41
increment(@count)
printl"{count}"       # 42
```

Both sides advertise the mutation. `increment(count)` supplies a copy and does not satisfy a place parameter.

## A Place Can Follow a Route

`@` starts at a binding's storage. Fields and indices after it project the place to the final selected location:

```dewy
set(@point.x)
set(@values[i])
set(@grid.rows[row][column])
```

`@point.x` means `(@point).x`. Parenthesizing the complete expression, `@(point.x)`, is equivalent. There is no `point.@x` spelling.

A computed index evaluates once before the call.

## Whole-Value Replacement

A place can expose the entire selected value, not only its scalar fields:

```dewy
let replace_pair = (@pair:Pair):>void =>
    pair = [left=20 right=22]

replace_pair(@pairs[index])
```

For a recursively fixed aggregate, the caller can provide the complete destination storage. Runtime-sized replacements need the broader ownership and escape design described in the implementation appendix.

## Preventing Conflicting Mutation

A call cannot receive two mutable places that may overlap:

```dewy
set_both(@pair.left @pair.right)   # distinct fields
set_both(@values[0] @values[1])   # distinct constant indices
```

Prefix routes overlap, and dynamic indices are treated as potentially equal unless the compiler can prove otherwise.

`const` bindings do not provide mutable places. Place parameter types are invariant so a callee cannot reinterpret the caller's storage through a broader type.

## Escaping Places

> **Provisional design:** Nonescaping calls and projected routes have settled behavior. Storing or returning a place requires lifetime, ownership, and concurrency rules that are still being designed.

Function handles use the same `@` root-and-route idea; see [Functions and Calls](function-types.md#function-handles-and-partial-evaluation). The Reference contains the exact [value and aliasing rules](../../reference/values.html).
