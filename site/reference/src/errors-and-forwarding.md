# Errors, Exceptions, and Forwarding

Dewy models expected failures as values belonging to nominal error types. A function exposes those values directly as alternatives in its return type rather than wrapping its result in a runtime `Result<T, E>` object.

Automatic forwarding is defined by the broader nominal `exception` family. Errors are one kind of exception; `undefined` is another. The direct-union model, exception classification, receiver-forwarding rule, explicit treatment of arguments, and separation of errors from effects are settled semantic direction. The surface forms called out as provisional below are not yet normative.

## The `exception` Family

The built-in hierarchy contains:

```text
exception
├── error
└── undefined
```

Any value whose type descends from `exception` is a forwarding value. Programs may define additional exception types. A type that does not descend from `exception` remains an ordinary union alternative even if programmers conventionally use it as a sentinel.

“Exception” names a type category here. Exception values remain ordinary values; forwarding does not imply throwing, catching, or stack unwinding.

## Error Types and Return Unions

An error type descends from the nominal base type `error`, which itself descends from `exception`. The exact declaration syntax for introducing such a type is provisional; this page uses names such as `NotFoundError` without prescribing their definitions.

<!-- dewy-example: design-only -->
```dewy
let loadCustomer = (id:CustomerId)
    :> Customer | NotFoundError | DatabaseError
=> {
    # ...
}
```

`Customer`, `NotFoundError`, and `DatabaseError` are direct alternatives. Union normalization flattens errors in the same way as other alternatives, while nominal membership in `error` prevents an error from collapsing into a structurally similar success type. No `Ok` or `Err` constructor is implied.

An exposed function should ordinarily declare a stable error set. The compiler may infer error alternatives for an unexposed helper.

## Forwarding Member Access

Let a receiver have type:

```text
V1 | ... | Vn | X1 | ... | Xm
```

where each `Xi` descends from `exception` and no `Vi` does. For `receiver.member`:

1. Every ordinary alternative `Vi` must support `member`. Otherwise the expression is a type error.
2. When the runtime receiver is a `Vi`, the member operation is performed normally.
3. When the runtime receiver is an `Xi`, member lookup is not performed and that exception value is forwarded.
4. If the member results have types `R1` through `Rn`, the result type is `R1 | ... | Rn | X1 | ... | Xm`.

<!-- dewy-example: design-only -->
```dewy
let user:User | UserError | undefined = loadUser(id)
let city = user.profile.address.city

# city: string | UserError | undefined
```

Each successive route segment applies the rule again. This gives exception-bearing receivers safe navigation without a separate `?.` spelling. Ordinary union alternatives never forward merely because they lack the requested member.

Forwarding applies at the receiver's current type; it does not recursively search inside containers. An `array<int64 | ParseError>` is an array value, not a top-level `ParseError`. Code that wants to combine or reject exceptions among its elements must do so explicitly.

## Calls and Arguments

Selecting a member on an exception-bearing receiver follows the forwarding rule. Arguments to a call do not forward implicitly.

<!-- dewy-example: design-only -->
```dewy
let service:Service | ServiceError = connect()
let request:Request | ParseError = parseRequest(text)

service.send(request)            # type error: request is still a union
service.send(request or_return)  # explicit propagation
```

The first call is invalid unless `send` actually accepts `Request | ParseError`. Receiver forwarding does not change the argument contract.

## `or_return`

Postfix `or_return` is the intended spelling for passing exception alternatives out of the current function.

For an expression of type `V | X`, where `X` contains its `exception` alternatives, `expression or_return`:

- evaluates `expression` once;
- returns the encountered `X` value from the enclosing function; or
- produces the corresponding non-exception `V` value locally.

The enclosing return contract must accept every propagated exception alternative. This includes `undefined` and user-defined exception kinds as well as errors.

<!-- dewy-example: design-only -->
```dewy
let loadName = (id:UserId):>string | LookupError => {
    let user = loadUser(id) or_return
    return user.name
}
```

Forms that replace or transform the propagated exception are part of the design direction, but their exact syntax and evaluation rules remain provisional.

## Explicit Handling

Type tests narrow error unions through ordinary control flow:

<!-- dewy-example: design-only -->
```dewy
let result = loadUser(id)

if result is? NotFoundError
    useGuest()
else if result is? DatabaseError
    report(result)
else
    greet(result.name)
```

The general pattern-selection syntax and type-directed recovery helpers remain provisional. Any recovery operation must remove only the alternatives it actually handles and preserve every unhandled error in the result type.

Forwarded values do not become false in Boolean context. If `user.isAdmin` has type `bool | UserError | undefined`, it is not a valid `if` condition until every exception alternative is propagated, handled, or otherwise narrowed away.

The current fallback direction keeps absence and failure distinct: `??` would replace `undefined` while preserving any `error` alternative. Under that proposal, applying a default to `Address | DatabaseError | undefined` produces `Address | DatabaseError`, not just `Address`. The final operator split between absence and error recovery is still provisional.

## Mutation

Safe navigation is a read and receiver-selection rule. An assignment through an exception-bearing route must not silently become a no-op:

<!-- dewy-example: design-only -->
```dewy
user.profile.name = "Ada"  # invalid if user may be UserError or undefined
```

The program must first narrow or propagate every exception alternative so the destination is a definite place.

## Exceptions Versus Ordinary Sentinels

Only alternatives descended from `exception` receive forwarding behavior:

```text
User | Missing         ordinary domain alternatives
User | NotFoundError   value or propagatable failure
User | undefined       value or forwarding absence
```

Code should use an ordinary domain type when both outcomes are meant to participate normally in later operations. It should use an `error` subtype for a forwarding failure, `undefined` for ordinary forwarding absence, or another `exception` subtype when neither built-in category expresses the contract.

## Errors Versus Effects

Errors are return values. Effects describe observable behavior or requirements of evaluation. They occupy separate parts of a function contract and must not be mixed as alternatives of one union.

<!-- dewy-example: design-only -->
```dewy
let loadInvoice = (id:InvoiceId)
    :> (Invoice | NotFoundError | DatabaseError) & reads<database>
```

Here the union describes what the caller receives. `reads<database>` describes what evaluating the call does. General effect syntax remains provisional; see [Refinements, Effects, and Safety](refinements-and-effects.md).

## Provisional Boundaries

The following details remain open:

- the preferred declaration syntax for new nominal exception and error types and structural error payloads;
- pattern-selection and concise recovery syntax;
- transformed `or_return` forms;
- whether pipes automatically forward exceptions, and the exact rule for broadcast pipes whose elements may be exceptions;
- fallback operators for absence and errors; and
- runtime layouts for general heterogeneous unions.

Until those questions are settled, programs should not infer behavior for them from an experimental compiler lowering. See [Design Maturity and Open Questions](design-status.md) and [Implementation Compatibility](compatibility.md).
