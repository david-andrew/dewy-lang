# Operators

Dewy operators are typed operations. The same spelling may select different overloads when the operand types give it a coherent meaning.

## Arithmetic

```dewy
left + right
left - right
left * right
left / right
left // right
left % right
base ^ exponent
```

Prefix `+` and `-` express sign. Prefix `/value` is reciprocal. Composite operator chains such as `value^/2` retain the first operator's precedence and can express roots compactly.

`/` on integers produces an exact rational (`1/3`), while `//` is floor division. `^` raises integers and rationals to integer powers; a negative constant exponent makes the result rational. On sets, `|`/`or`, `&`/`and`, `-`, and `xor` are union, intersection, difference, and symmetric difference, and `|` also merges dictionaries.

## Comparison and Tests

Dewy distinguishes tests from assignment:

```dewy
left =? right
left not =? right
left <? right
left <=? right
value in? range
value is? Type
value isnt? none
```

## Boolean and Bitwise Operations

The English operators `and`, `or`, `not`, `nand`, `nor`, `xor`, and `xnor` express Boolean composition and short-circuit where their truth rule permits it.

`&`, `|`, and `~` are the same operations as `and`, `or`, and `not` at a tighter precedence — above the comparisons, where the words sit below them. Use the symbols to compose things that are then compared or tested as a whole: types (`x is? int64|string`, `d:int64 & ~0`), overload sets (`@f & @g`), sets, and masks (`flags & MASK =? 0`). Use the words for logic over comparisons (`x >? 0 and y <? n`); `x >? 0 & y >? 0` would parse as `x >? (0 & y) >? 0`.

## Juxtaposition

Adjacent expressions reuse one syntactic relationship:

```dewy
function(argument)    # call
values[index]         # index
2distance             # multiplication
values...             # spread into a surrounding collector
```

The parser keeps meaningful alternatives until types and context select the operation. This is why function calls, indexing, and mathematical notation can share a consistent surface form without textual heuristics.

## Pipes and Conversion

```dewy
value |> @transform
@transform <| value
value as Destination
value transmute Representation
```

`as` performs a semantic conversion. `transmute` reinterprets a compatible representation and is not a substitute for conversion.

## Assignment

`=` updates a mutable binding or selected place. Most operations have a combined-assignment form:

```dewy
count += 1
flags xor= mask
```

Combined assignment has assignment precedence. When its right side is itself an assignment-like expression, grouping is required—for example, `() => (value += 1)`.

An attached postfix `;` suppresses an expression's produced value.

## Place and Function Selection

A leading `@` selects the place at the end of a complete field-and-index route, or selects a function binding as a handle. It appears only at the beginning of that route:

```dewy
@value
@pair.left
@items[index]
```

There is no operator asking whether two places are the same place: places are borrows, not values, and independent values never share observable storage (the once-reserved `@?` was retired for that reason).

For functions, an ungrouped `@` chain selects and partially evaluates without calling. Grouping ends that chain, so `(@worker.callback)(5)` calls the selected function. [Function Values and Composition](functional-programming.md) develops the complete rule after introducing places and objects.

## Elementwise and Vectorized Operations

> **Provisional design:** A leading `.` on an operator applies it elementwise, while `f.(values)` vectorizes a function call. Broadcasting and multidimensional shape rules must be specified together before edge cases are normative.

The complete and canonical precedence table lives in the [Reference](../../reference/operators-and-precedence.html). Use `()` or `{}` when the intended grouping is not represented directly by that table.
