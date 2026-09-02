# Errors, Exceptions, and Forwarding

Dewy models expected failures as values belonging to nominal error types. A function exposes those values directly as alternatives in its return type rather than wrapping its result in a runtime `Result<T, E>` object.

Automatic forwarding is defined by the broader nominal `exception` family. Errors are one kind of exception; `none` is another. The direct-union model, exception classification, receiver-forwarding rule, explicit treatment of arguments, and separation of errors from effects are settled semantic direction. The surface forms called out as provisional below are not yet normative.

Implemented today: error types minted with `type of error`, unit-like or carrying fields, error alternatives in return unions and other unions, `is?` handling (including `is? error` for the whole family), postfix `or_throw`, and forwarding member access (safe navigation, reads only). Not yet implemented: forwarding through method calls and the fallback operators. Examples marked as compiler examples below compile with the current compiler; the rest are design.

Errors are the second half of Dewy's no-trap rule (see [No Traps](refinements-and-effects.md#no-traps)): what cannot be proven safe at compile time is returned as a value, never raised, never aborted.

## The `exception` Family

The built-in hierarchy contains:

```text
exception
├── error
└── none
```

Any value whose type descends from `exception` is a forwarding value. Programs may define additional exception types. A type that does not descend from `exception` remains an ordinary union alternative even if programmers conventionally use it as a sentinel.

“Exception” names a type category here. Exception values remain ordinary values; forwarding does not imply stack unwinding.

## Declaring Error Types

An error type descends from the nominal base type `error`, which itself descends from `exception`. `type of error` creates a fresh nominal error type:

<!-- dewy-example: design-only -->
```dewy
const MyCustomError:type = type of error
```

A unit-like nominal error has one canonical inhabitant, written with the type's name. The question of whether that inhabitant is literally the type value itself remains open, but there is no separate `MyCustomError()` spelling:

<!-- dewy-example: compiler -->

```dewy
let MyCustomError:type = type of error

let maybeNumber = (flag:bool):>int64 | MyCustomError => {
    if flag { return MyCustomError }
    return 42
}
```

Minted names are nominal: two `type of error` aliases are distinct types even though both descend from `error`, and a value of one is never a value of the other.

Intersect the fresh nominal type with an object type when an error carries fields. The result is constructed, matched, and read like any minted object (`Report`'s methods included when the structure is `Report`), sits in the `error` family for `is? error`, `or_throw`, and forwarding, and — being a fresh nominal child of its structure — satisfies a parameter of that structure:

<!-- dewy-example: compiler -->
```dewy
let TokenError:type = type of error & [message:string offset:int64 = 0]

let count = (src:string):>int64 | TokenError => {
    if src.length =? 0 return TokenError(message='empty input')
    return src.length
}

describe = (n:int64):>string => match count("abc") {
    e:TokenError => e.message
    v:int64 => "{v} characters"
}
```

`type of error` mints the identity; `&` only adds the structural requirement. Further structural extension therefore reuses the existing nominal ancestry:

<!-- dewy-example: design-only -->
```dewy
const MyMoreComplexError:type =
    MyComplexError & [metadata:string]
```

`MyMoreComplexError` is structurally stronger but is not a separate nominal error variant. See [Nominal Identity](types-and-conversions.md#nominal-identity).

## Error Return Unions

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

<!-- dewy-example: compiler -->

```dewy
let UserError:type = type of error
let Address:type = [city:string]
let User:type = [name:string address:Address|none]

let load_user = (id:int64):>User | UserError | none =>
    if id >? 0 [name="ada" address=[city="paris"]] else UserError

let city_of = (id:int64):>string | UserError | none => {
    let user = load_user(id)
    let city = user.address.city      # city: string | UserError | none
    return city
}
```

Each successive route segment applies the rule again. This gives exception-bearing receivers safe navigation without a separate `?.` spelling. Ordinary union alternatives never forward merely because they lack the requested member.

The rule with no exception alternatives is plain common-member access: when every alternative of an ordinary union has the member, the access reads it without narrowing, at the union of the member types (one type when they agree):

<!-- dewy-example: compiler -->

```dewy
let Customer:type = [name:string id:int64]
let Organization:type = [name:string members:int64]

let find = (id:int64):>Customer | Organization =>
    if id >? 0 [name="ada" id=id] else [name="acme" members=3]

let who = (id:int64):>string => find(id).name    # both alternatives have `name`
```

`find(id).id` is a type error there — `Organization` has no `id` — and so is assigning through any union route; narrow with `is?` first.

Forwarding applies at the receiver's current type; it does not recursively search inside containers. An `array<int64 | ParseError>` is an array value, not a top-level `ParseError`. Code that wants to combine or reject exceptions among its elements must do so explicitly.

## Calls and Arguments

Selecting a member on an exception-bearing receiver follows the forwarding rule. Arguments to a call do not forward implicitly.

<!-- dewy-example: design-only -->
```dewy
let service:Service | ServiceError = connect()
let request:Request | ParseError = parseRequest(text)

service.send(request)            # type error: request is still a union
service.send(request or_throw)  # explicit propagation
```

The first call is invalid unless `send` actually accepts `Request | ParseError`. Receiver forwarding does not change the argument contract.

## `or_throw`

Postfix `or_throw` is the intended spelling for passing exception alternatives out of the current function.

For an expression of type `V | X`, where `X` contains its `exception` alternatives, `expression or_throw`:

- evaluates `expression` once;
- returns the encountered `X` value from the enclosing function; or
- produces the corresponding non-exception `V` value locally.

The enclosing return contract must accept every propagated exception alternative. This includes `none` and user-defined exception kinds as well as errors.

<!-- dewy-example: compiler -->

```dewy
let NotFound:type = type of error

let lookup = (id:int64):>int64 | NotFound => {
    if id >? 100 { return NotFound }
    return id * 2
}

let twice = (id:int64):>int64 | NotFound | none => {
    let first = lookup(id) or_throw      # first: int64
    let second = lookup(first) or_throw
    if second =? 8 { return none }
    return second
}
```

`or_throw` is a postfix just below `as` in precedence, so it applies to the whole expression on its left: `lookup(id) or_throw` propagates the call's result, and `f(x) * 2 or_throw` propagates from the product (see [operators and precedence](operators-and-precedence.md)). The propagated alternatives must each be accepted by the enclosing function's declared result type; a function without a declared result type cannot use it. Forms that replace or transform the propagated exception are part of the design direction, but their exact syntax and evaluation rules remain provisional.

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

Forwarded values do not become false in Boolean context. If `user.isAdmin` has type `bool | UserError | none`, it is not a valid `if` condition until every exception alternative is propagated, handled, or otherwise narrowed away.

The current fallback direction keeps absence and failure distinct: `??` would replace `none` while preserving any `error` alternative. Under that proposal, applying a default to `Address | DatabaseError | none` produces `Address | DatabaseError`, not just `Address`. The final operator split between absence and error recovery is still provisional.

## Mutation

Safe navigation is a read and receiver-selection rule. An assignment through an exception-bearing route must not silently become a no-op:

<!-- dewy-example: design-only -->
```dewy
user.profile.name = "Ada"  # invalid if user may be UserError or none
```

The program must first narrow or propagate every exception alternative so the destination is a definite place.

## Exceptions Versus Ordinary Sentinels

Only alternatives descended from `exception` receive forwarding behavior:

```text
User | Missing         ordinary domain alternatives
User | NotFoundError   value or propagatable failure
User | none       value or forwarding absence
```

Code should use an ordinary domain type when both outcomes are meant to participate normally in later operations. It should use an `error` subtype for a forwarding failure, `none` for ordinary forwarding absence, or another `exception` subtype when neither built-in category expresses the contract.

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

- pattern-selection and concise recovery syntax;
- transformed `or_throw` forms;
- whether pipes automatically forward exceptions, and the exact rule for broadcast pipes whose elements may be exceptions;
- fallback operators for absence and errors; and
- runtime layouts for general heterogeneous unions.

Until those questions are settled, programs should not infer behavior for them from an experimental compiler lowering. See [Design Maturity and Open Questions](design-status.md) and [Implementation Compatibility](compatibility.md).
