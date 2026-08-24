# Expressions and operators

Declarations, assignments, blocks, conditionals, and loops are expressions.
Declarations and ordinary assignments produce `void`.

Operator meaning is selected by type-directed dispatch. Implemented operators
cover fixed-width arithmetic, comparisons, shifts, Boolean operations,
membership/type tests, conversion, and assignment combinations.
Narrow fixed-width arithmetic and bitwise results roll over at their declared
width. Shift counts must be unsigned, so a negative count is a compile-time
error. A fixed-width shift evaluates each operand once. Once a count reaches
the value's width, a left shift or unsigned right shift is zero; a signed right
shift continues its sign bit, settling at `0` for nonnegative values and `-1`
for negative values.

Adjacent expressions create a juxtaposition whose meaning can depend on the
operand types. The parser preserves ambiguity between calls, indexing, and
future multiplication until semantic analysis can resolve it.

```dewy
function(argument)     # call in a callable context
values[index]          # indexing in an array context
value |> function      # pipe call
```

General juxtaposition multiplication and broadcasting remain planned.

## Place projection and precedence

The prefix `@` operator selects a place. Subsequent field and index operations project that place, so ordinary precedence gives these readings:

```dewy
@pair.left       # (@pair).left: the place occupied by left
@values[i]       # (@values)[i]: the place occupied by element i
@box.rows[i][j]  # (((@box).rows)[i])[j]
```

Parenthesizing the complete route, as in `@(pair.left)`, is equivalent. Dewy does not use a special `pair.@left` member-access form. See [Values, places, and containers](values.md#places-and-projected-routes) for call and aliasing rules.
