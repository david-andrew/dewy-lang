# Expressions and Evaluation

> [Generated coverage](/status/#ref-expressions-and-operators) names related acceptance programs. Every example on this page compiles with the current compiler unless it is marked **Design only**.

Every executable construct in Dewy is an expression. An expression expresses zero or more values, or `never` when it cannot complete (`exit(…)`, a call to a `:>never` function, an endless loop). Declarations and assignments express nothing (`void`).

## Blocks

`{ … }` is a scoped block and `( … )` an unscoped one; names declared inside parentheses stay visible after them (see [Scopes](bindings-and-scope.md#scopes)). A block expresses each non-`void` value its expressions give, in order, including values from nested `if`/`match` arms and loops.

A collector takes every value: `[{1 2} 3]` is `[1 2 3]`, `[if c 1]` is `[1]` or `[]`, and a loop inside a collector collects every value of every iteration. A place for one value (an operand, an index, a condition, a `:>T` result) takes a block's last expression; an earlier value there is an error.

<!-- dewy-example: {"mode":"run","stdout":"27\n[1 2 3]\n[]\n[1 4 9]\n"} -->
```dewy
main = () => {
    let radius = 3
    let area = {
        let r2 = radius * radius     # void: expresses nothing
        3 * r2
    }
    printl(area)
    printl([{1 2} 3])
    let c = false
    printl([if c 1])
    printl([loop i in [1..3] i * i])
}
```

## Several Values

`(1 2)` is two values, not a container; `[1 2]` is an array, one value. Several values work wherever the same values written out would. A function may express several values, and `:>(int64 int64)` writes that result type. A binding can hold several values, a call takes them as that many positional arguments, a collector takes them all, and a pattern takes them apart. A fixed number of values is returned in place, with no array.

<!-- dewy-example: {"mode":"run","stdout":"3 [1 2]\n3\n"} -->
```dewy
pair = ():>(int64 int64) => (1 2)
add = (a:int b:int) => a + b
main = () => {
    let p = pair
    printl"{add(p)} {[p]}"
    let (a b) = p
    printl(a + b)
}
```

A place for one value given several is an error naming the count, never the last value:

<!-- dewy-example: {"mode":"reject","diagnostic":"'pair' gives 2 values, and only one is taken here"} -->
```dewy
pair = () => (1 2)
printl(pair + 1)
```

## Discarding Values

A postfix `;` evaluates the expression before it and discards what it expresses, whatever the spacing: `f();` and `f() ;` are the same. Module top-level code discards what it expresses. A body written `:>void` expresses nothing, so a value there is an error: discard it with `;` or change the result type.

<!-- dewy-example: {"mode":"reject","diagnostic":"attach `;` to discard the value"} -->
```dewy
drop_last = (@xs:array<int64>):>void => {
    if xs.length >? 0 xs.pop()
}
```

<!-- dewy-example: {"mode":"check"} -->
```dewy
drop_last = (@xs:array<int64>):>void => {
    if xs.length >? 0 xs.pop();
}
```

Directly inside an array literal, `;` separates rows instead. To discard inside an array, use a group: `[(f();) 7]` runs `f` and keeps only `7`. A result that is `void | E` must be used: as the last statement of a `:>void | E` body it is the result; elsewhere propagate it with `or_throw`, handle it, or discard it with `;`.

## Evaluation Order

Within the tree that grouping and precedence establish, operands and arguments evaluate left to right. A call evaluates the callee first, then its explicit arguments in written order, then omitted defaults in parameter order. An argument list may declare names between its values (`add(let w = 3; w 4)`); declarations and arguments run in written order, and `w` stays visible after the call.

`and` and `or` evaluate their right operand only when it can change the result. A comparison chain evaluates each operand at most once. `if`, `match` and loops evaluate their conditions in order and run only the selected body.

<!-- dewy-example: {"mode":"run","stdout":"first\nsecond\ndefault\n3\nfalse\n"} -->
```dewy
note = (s:string):>int => {
    printl(s)
    1
}
show = (a:int b:int c:int=note("default")) => a + b + c
main = () => {
    printl(show(note("first") note("second")))
    let ok = false and note("skipped") =? 1
    printl(ok)
}
```

## Assignment

Assignment evaluates its destination route and its source, stores the value into the binding, field, element or entry, and expresses nothing. A compound assignment (`+=`, `//=`, `and=`) evaluates the destination route once, before the old value and the right operand, and keeps the destination's type. See [Operators and Precedence](operators-and-precedence.md#operator-families).

## Place Projection

A prefix `@` selects the place at the end of a whole field-and-index route: `@pair.left`, `@values[i]`, `@box.rows[r][c]`. `@(pair.left)` selects the same place; there is no `pair.@left` form. See [Values, Copies, and Places](values.md#place-routes).

A leading `@` on a function selects the function rather than calling it; see [Function Handles](functions-and-calls.md#function-handles).
