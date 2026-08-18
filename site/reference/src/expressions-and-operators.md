# Expressions and operators

Declarations, assignments, blocks, conditionals, and loops are expressions.
Declarations and ordinary assignments produce `void`.

Operator meaning is selected by type-directed dispatch. Implemented operators
cover fixed-width arithmetic, comparisons, shifts, Boolean operations,
membership/type tests, conversion, and assignment combinations.

Adjacent expressions create a juxtaposition whose meaning can depend on the
operand types. The parser preserves ambiguity between calls, indexing, and
future multiplication until semantic analysis can resolve it.

```dewy
function(argument)     # call in a callable context
values[index]          # indexing in an array context
value |> function      # pipe call
```

General juxtaposition multiplication and broadcasting remain planned.
