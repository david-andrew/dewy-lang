# Optional Values and Narrowing

`none` is a real value representing a missing alternative. It is not `void` or an uninitialized name.

An optional type is a union with `none`:

```dewy
let answer:int64 | none = lookup_answer()
```

## Checking an Optional

Use `is?` or `isnt?` to establish which alternative is present:

```dewy
if answer isnt? none
    printl"the next answer is {answer + 1}"
```

Inside the body, `answer` is known to be `int64`. An early exit can establish the same fact afterward:

```dewy
if answer is? none
    return

printl"answer is {answer}"
```

`value is? Type` tests membership in a type. Literal alternatives can be tested directly as well.

## Producing Optional Values

A function can return an optional explicitly:

```dewy
let choose = (enabled:bool):>int64 | none =>
    if enabled 42 else none
```

Any expression whose alternatives include a value and `none` can produce an optional.

## Absence Is an Exception, Not an Error

`none` says that a value is absent. An error says that an operation failed and carries its own error type. Both descend from Dewy's `exception` type family, so navigation forwards either one without trying to access a member on it. They nevertheless remain distinct contracts:

```dewy
User | none       # a user may simply be absent
```

<!-- dewy-example: design-only -->
```dewy
User | NotFoundError   # looking up the user may fail
```

[Exception values](errors-as-values.md#exception-values-forward) automatically forward when they are encountered as the receiver of a navigation route:

<!-- dewy-example: design-only -->
```dewy
let user:User | none = findUser(id)
let city = user.profile.address.city

# city has type string | none
```

If users want a non-forwarding sentinel, they can define an ordinary type that does not descend from `exception`. Every ordinary alternative must support a requested member or be narrowed away first.

This is ordinary typed value flow, not a hidden throw or stack unwind. The next chapter develops the exception family and propagation in full.

General unions with several unrelated runtime layouts use the same type-theoretic model, though their complete representation and narrowing support is still a [design and implementation frontier](../appendices/language-and-compiler.md).
