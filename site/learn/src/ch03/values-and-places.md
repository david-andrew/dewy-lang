# Values, Copies, and Places

Dewy uses value semantics by default. Giving a value another name, passing it to a function, or returning it does not silently give someone else permission to mutate your original.

```dewy
let original = [10 20]
let copy = original

copy[0] = 99
printl"{original[0]}"  # 10
```

The compiler does not have to perform a literal copy every time. It can move storage, transfer ownership, or share immutable backing data as long as the program behaves as though the two values are independent.

## Asking a function to write your value

Use `@` when a function should receive the actual place where a value lives. Mark that intent in both the parameter and the call:

```dewy
let increment = (@value:int64):>void => {
    value += 1
}

let count:int64 = 41
increment(@count)
printl"{count}"       # 42
```

Without `@` on either side, the call is rejected rather than silently changing between copy and mutation behavior.

## A place can follow a route

Think of `@` as starting at a named storage location. Every field or index after it follows the route to a more specific location:

```dewy
set(@point.x)
set(@values[i])
set(@grid.rows[row][column])
```

For example, `@point.x` follows these steps:

1. `@point` selects the place occupied by `point`.
2. `.x` projects that place to the storage occupied by its `x` field.

That is why ordinary precedence reads `@point.x` as `(@point).x`. Writing `@(point.x)` is equivalent if the grouping makes the intent easier to see. There is no separate `point.@x` syntax.

The same rule composes through any supported mixture of fields and individual array indices. An index expression is evaluated once when preparing the call.

## Safety rules

A place parameter has an explicit type, and the argument must have exactly that type. The root must be mutable: neither a `const` value nor a field beneath one can become a writing place.

Dewy also rejects mutable routes that could overlap in one call:

```dewy
swap(@value @value)          # error: same place twice
update(@record @record.x)    # error: whole value overlaps its field

update(@record.x @record.y)  # okay: distinct fields
update(@items[0] @items[1])  # okay: distinct constant indices
```

Runtime-computed indices are currently treated conservatively because two different expressions might select the same element.

## Current boundary

The compiler supports nonescaping places rooted in named mutable fixed-width scalars, Booleans, arrays, and structural objects. Routes may select mutable object fields or individual array elements, including nested mixed routes. Whole-value replacement through a route works too, such as replacing `@matrix[0]` with another row.

Places can currently be passed and forwarded through calls, but cannot be saved in a local, stored in an object, or returned. Function handles share the `@` idea but are still planned; see [Function Types](function-types.md).
