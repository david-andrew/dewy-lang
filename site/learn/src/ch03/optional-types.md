# Optional Values and Narrowing

`undefined` is a real value representing a missing alternative. It is not `void`, an uninitialized name, or a hidden exception.

An optional type is a union with `undefined`:

```dewy
let answer:int64 | undefined = lookup_answer()
```

## Checking an Optional

Use `is?` or `isnt?` to establish which alternative is present:

```dewy
if answer isnt? undefined
    printl"the next answer is {answer + 1}"
```

Inside the body, `answer` is known to be `int64`. An early exit can establish the same fact afterward:

```dewy
if answer is? undefined
    return

printl"answer is {answer}"
```

`value is? Type` tests membership in a type. Literal alternatives can be tested directly as well.

## Producing Optional Values

A function can return an optional explicitly:

```dewy
let choose = (enabled:bool):>int64 | undefined =>
    if enabled 42 else undefined
```

Any expression whose alternatives include a value and `undefined` can produce an optional.

## Optionals in Multiiterators

An `or` multiiterator can continue after one source is exhausted. During those later iterations, the exhausted source's bound value is optional:

```dewy
loop short in short_items or long in long_items {
    if short isnt? undefined
        process_short(short)

    if long isnt? undefined
        process_long(long)
}
```

By contrast, `and` stops before a required source's missing value reaches the body.

General unions with several unrelated runtime layouts use the same type-theoretic model, though their complete representation and narrowing support is still a [design and implementation frontier](../appendices/language-and-compiler.md).
