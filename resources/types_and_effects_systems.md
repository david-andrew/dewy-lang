> NOTE: some of this might not be valid dewy syntax. It's mainly to illustrate the design of the types and effects system

> NOTE: omitted from this discussion:
> - intersection types/errors, e.g. `A & B` or `SomeStruct & Error` to make a structural type into an error
> - what happens when you intersect nominal vs structural types
>    - `T = nominalT & structT` just makes `T is nominalT` true
>    - `T = nominalT1 & nominalT2` makes `T is nominalT1` true, and `T is nominalT2` true
>    - `T = structT1 & structT2` makes `T` contain all of the structural properties of `structT1` and `structT2` in a single type. TBD how to handle name conflicts, perhaps allow if they are compatible, taking the more specific one, and error if they are not compatible types

## Direct Union Errors and Forwarding Semantics

Functions return direct union types rather than wrapping results in a `Result<T, E>` container.

```dewy
let createInvoice = 
    (request: InvoiceRequest)
    :> Invoice | CreateInvoiceError
=> {
        # ...
}
```

`Invoice` and `CreateInvoiceError` are ordinary runtime values. The distinction is provided by the type system, with error types descending from a nominal base `Error` type.

```dewy
# TBD if this is a valid way to make a new error type
CreateInvoiceError: type<Error> = ...

# This should definitely be possible, but TBD if it will be the main approach
CreateInvoiceError: type = [#{some relevant type content}#] & Error
```

### Errors as Union Members

Expected failures are represented directly in the return type:

```dewy
let loadCustomer = (id: CustomerId)
    :> Customer | NotFoundError | DatabaseError
```

Error unions compose and flatten naturally:

```dewy
Customer | NotFoundError | DatabaseError
```

There are no nested error containers and no `Ok` or `Err` constructors.

Private functions may infer their error alternatives, while public functions should generally declare a stable return contract.

### Explicit Propagation

Error and absence propagation uses an explicit postfix construct:

```dewy
let customer = loadCustomer(id) or_return
```

Conceptually:

```dewy
let temporary = loadCustomer(id)

let customer = match temporary {
    Error error => return error
    value => value
}
```

`or_return` removes the forwarded alternatives from the local expression and returns them from the enclosing function.

It may also transform the propagated value:

```dewy
let customer =
    loadCustomer(id)
    or_return CustomerLookupError(id)
```

A callback form could expose the original value:

```dewy
let customer =
    loadCustomer(id)
    or_return error => CustomerLookupError(id, error)
```

The replacement must be compatible with the enclosing function’s return type.

### Forwarding Types

Some types belong to a special forwarding category:

```dewy
Forward
├── Error
└── Absent
```

Possible `Absent` members include:

```dewy
undefined
null
```

`Error` and `Absent` share navigation behavior, but they remain distinct categories so operators may handle them differently.

### Universal Safe Navigation

Member access automatically forwards designated forwarding values.

```dewy
user: User | UserError | undefined

user.profile.address.city
```

The inferred result might be:

```dewy
String | UserError | undefined
```

Conceptually, member access over:

```dewy
A | F
```

where `F` is forwarding behaves as:

```dewy
match value {
    A value => value.member
    F forwarded => forwarded
}
```

The forwarding alternatives pass through without invoking the member operation.

This removes the need for a separate `?.` safe-navigation operator.

### Union Member Lookup

For:

```dewy
value: A | B | F
```

where `F` is forwarding, member access succeeds only when every non-forwarding member supports the requested member.

```dewy
value.member
```

If:

```dewy
A.member : X
B.member : Y
```

then the result is:

```dewy
X | Y | F
```

If `B` does not support `member`, the expression is a type error. Ordinary union members are never silently skipped.

### Receiver Forwarding Only

Automatic forwarding applies to the receiver of navigation, not to function arguments.

```dewy
let amount: Money | ParseError = parseMoney(text)

invoice.setAmount(amount)
```

This is a type error because `setAmount` expects `Money`.

The caller must resolve or propagate the alternative explicitly:

```dewy
invoice.setAmount(amount or_return)
```

Likewise:

```dewy
receiver: Service | ServiceError
request: Request | ParseError

receiver.send(request)
```

The receiver may forward automatically, but the argument is invalid until explicitly narrowed:

```dewy
receiver.send(request or_return)
```

This avoids implicit branching at every call site and keeps argument evaluation and error precedence straightforward.

### Absence Fallback

> NOTE: TBD if `??` is just for absent values or if it also can handle Error values as well. It was suggested to have a separate `!?` operator which would do the same thing except for error values instead. TBD on the exact breakdown of which of these operators work only for Absent vs Error vs Forward

A fallback operator such as `??` should handle only absence:

```dewy
let address = user.address ?? defaultAddress
```

If:

```dewy
user.address: Address | undefined
```

the result is:

```dewy
Address
```

Errors are not silently discarded by `??`.

```dewy
Address | DatabaseError | undefined
```

after `?? defaultAddress` becomes:

```dewy
Address | DatabaseError
```

This avoids requiring a separate general error-fallback operator in the core language. Errors can instead be handled through matching, type-directed recovery, or explicit helper methods.

### Type-Directed Handling

The language may expose generalized union operations rather than reproducing the full Rust `Result` API.

Useful type-level projections include:

```dewy
errorof<T>
absentof<T>
forwardof<T>
valueof<T>
```

For:

```dewy
T = Invoice | ValidationError | DatabaseError | undefined
```

they produce:

```dewy
errorof<T>
# ValidationError | DatabaseError

absentof<T>
# undefined

forwardof<T>
# ValidationError | DatabaseError | undefined

valueof<T>
# Invoice
```

Possible type-directed operations include:

```dewy
value.handle<NotFoundError>(...)
value.map<Error>(...)
value.recover<DatabaseError>(...)
```

Handling one member removes that member from the resulting union when the handler returns a nonmatching type.

```dewy
Invoice | NotFoundError | DatabaseError
```

after recovering `NotFoundError` with an `Invoice` becomes:

```dewy
Invoice | DatabaseError
```

Convenience methods such as `map`, `map_error`, `and_then`, or `or_else` may be provided as extensions over suitable union types, but they are not methods on a runtime `Result` wrapper.

### Error Identity

`Error` is a nominal type, though the language itself supports hybrid nominal and structural.

This prevents an error type from accidentally collapsing into or overlapping with a successful alternative during union normalization.

```dewy
User | ValidationError
```

must preserve both alternatives even when the types contain structurally similar fields.

A value intended to treat an error as ordinary data should use an explicit intersection between `Error` and the data/content to include with it:

```dewy
ValidationError = Error & [
    reason:str
    authLevel:Authority
    timestamp:Time
]
```

### Domain Alternatives Versus Errors

Not every unsuccessful-looking outcome needs to descend from `Error`.

```dewy
User | Missing
```

represents two ordinary domain outcomes.

```dewy
User | NotFoundError
```

represents a successful value or a propagatable failure.

> NOTE: TBD if this is actually true. may or may not let `or_return` and related syntax deal over any Forward type or may restrict to Error or Absent depending on what makes sense. I think most likely it will deal in both to provider a simpler language to users.

Only members classified as forwarding types participate in automatic navigation forwarding and `or_return`.

### Effects Remain Separate

Errors are return alternatives. Effects describe behavior, authority, or external requirements.

Examples include:

```dewy
reads<database>
writes<filesystem>
async
mutates<state>
```

A return annotation attaches a type expression to an effect expression with `&`. Parenthesize the type side (or both) so the `&` is not parsed as type intersection:

```dewy
let loadInvoice = (id: InvoiceId)
    :> (Invoice | NotFoundError | DatabaseError) & reads<database> & async
```

Several effects also combine with `&`. They are all part of the contract, not alternatives. `|` is only for value and error alternatives.

A convenience form may list several effects without `&` between them:

```dewy
:> (Invoice | NotFoundError | DatabaseError) & Effects<reads<database> async>
```

The type checker separates the terms by kind.

Internally, the signature should maintain distinct rows:

```text
Values:
    Invoice

Errors:
    NotFoundError
    DatabaseError

Effects:
    reads<database>
    async
```

The systems do not combine inside nested type expressions, and they do not share `|`.

```dewy
Array<Invoice | DatabaseError>
```

is a type expression.

```dewy
reads<database>
```

is an effect expression and cannot appear inside that union.

These are invalid:

```dewy
:> Invoice | NotFoundError | async
:> (Invoice | reads<database>) & (NotFoundError | async)
```

### Assignments and Boolean Contexts

Automatic forwarding should primarily apply to reads and receiver calls.

Conditional mutation such as:

```dewy
user.profile.name = "Alice"
```

should not silently become a no-op when `user` is absent or erroneous. Mutation should require explicit narrowing or propagation.

> TBD about this part here too. I think `if user.isAdmin {...}` would probably be a type error if the result weren't precisely of type `bool`. Honestly the simple way to handle something like this might be `if user.isAdmin =? true {...}` which would be redundant if `isAdmin` were always present, but makes more sense when `isAdmin` might be a more complex type like `bool | Missing`

Similarly, forwarding values should not be coerced to false in boolean contexts:

```dewy
if user.isAdmin {
    # ...
}
```

is invalid when `user.isAdmin` may be `Bool | UserError`.

The caller must handle it explicitly:

```dewy
if user.isAdmin or_return {
    # ...
}
```

or:

```dewy
if user.isAdmin ?? false {
    # ...
}
```

or:
```dewy
if user.isAdmin =? true {
    # ...
}
```


### Core Model

The central rules are:

```text
Navigation:
    Automatically forwards Error and Absent receiver alternatives.

Arguments:
    Never forward implicitly.

or_return:
    Explicitly propagates forwarding alternatives to the enclosing function.

??:
    Resolves absence only.

Matching and recovery:
    Handle selected error or union alternatives explicitly.

Effects:
    Remain a separate row. Surface syntax attaches them to a return
    type with `&`, never with `|`.
```

The resulting model treats failure propagation as type-directed forwarding through expressions rather than as unwrapping a result container.
