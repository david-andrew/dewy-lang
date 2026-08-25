# Errors as Values

Dewy represents an expected failure as an ordinary value. A function lists its successful result and its possible errors directly in one union:

<!-- dewy-example: design-only -->
```dewy
let loadCustomer = (id:CustomerId)
    :> Customer | NotFoundError | DatabaseError
=> {
    # ...
}
```

Calling `loadCustomer` produces one of those three values. There is no `Result` container to unwrap and no `Ok` or `Err` constructor around either outcome. Error types belong to Dewy's nominal `error` family, which lets the language distinguish failures from ordinary domain alternatives.

Public functions should normally state a stable set of errors in their return contract. A private helper may allow the compiler to infer them.

## Exception Values Forward

Safe navigation is governed by a broader `exception` type family. Both `error` and `undefined` descend from `exception`, and programmers can define other exception types. Any alternative in this family forwards through navigation.

Here, “exception” describes an ordinary value's type. It does not imply throwing, catching, or stack unwinding.

## Defining Exceptions

`type of Parent` creates a fresh nominal child. A unit-like error has one canonical inhabitant written with the type's own name:

<!-- dewy-example: design-only -->
```dewy
const MyCustomError:type = type of error

let maybeNumber = ():>int64 | MyCustomError => {
    if random.coinflip
        return MyCustomError
    return 42
}
```

There is currently no separate `MyCustomError()` spelling. Whether the canonical inhabitant and its type value are literally the same semantic object is left open.

An error that carries context combines its fresh nominal identity with a structural type:

<!-- dewy-example: design-only -->
```dewy
const MyComplexError:type =
    (type of error) & [extra:string fields:int64]

let problem = MyComplexError[
    extra='some extra context'
    fields=42
]
```

Only `type of error` creates identity. A later alias such as `MyComplexError & [metadata:string]` adds a structural requirement while remaining the same nominal error kind.

## Safe Navigation

When a receiver might be an exception, Dewy applies a member operation to every ordinary alternative and forwards the exception unchanged:

<!-- dewy-example: design-only -->
```dewy
let customer:Customer | DatabaseError | undefined = findCustomer(id)
let city = customer.profile.address.city

# city has type string | DatabaseError | undefined
```

If `customer` is a `Customer`, the route reads its `profile`, `address`, and `city`. If it is a `DatabaseError` or `undefined`, none of those accesses run; that exception becomes the value of `city`. Every later access in the route follows the same rule, so Dewy does not need a separate `?.` operator.

This behavior is type checked rather than based on whether a value happens to be truthy. Every non-exception alternative must support the requested member:

<!-- dewy-example: design-only -->
```dewy
let subject:Customer | Organization | DatabaseError = findSubject(id)
let name = subject.name
```

This is valid only if both `Customer` and `Organization` have a usable `name`. An ordinary union member is never silently skipped.

If a program needs a sentinel that does not forward, it defines an ordinary type that does not descend from `exception`. Such a sentinel must be narrowed explicitly before accessing members that it does not support.

## Propagating an Exception

Use `or_return` when the current function should pass an exception back to its caller:

<!-- dewy-example: design-only -->
```dewy
let loadGreeting = (id:CustomerId)
    :> string | NotFoundError | DatabaseError
=> {
    let customer = loadCustomer(id) or_return
    return "Hello, {customer.name}!"
}
```

The expression evaluates `loadCustomer(id)` once. A `Customer` becomes the local `customer`; an exception returns immediately from `loadGreeting`. The enclosing return contract must accept every exception alternative that can be forwarded this way. This applies to `undefined` and user-defined exceptions as well as errors.

Unlike navigation on a receiver, arguments do not forward implicitly:

<!-- dewy-example: design-only -->
```dewy
let amount:Money | ParseError = parseMoney(text)

invoice.setAmount(amount)            # type error
invoice.setAmount(amount or_return)  # passes Money or returns ParseError
```

Keeping arguments explicit prevents a call from acquiring hidden early exits for any exception-bearing expression supplied to it.

## Inspecting and Recovering

An error is still a value, so ordinary type tests can narrow it:

<!-- dewy-example: design-only -->
```dewy
let customer = loadCustomer(id)

if customer is? NotFoundError
    return guestCustomer
else if customer is? DatabaseError
    return customer

printl"Welcome back, {customer.name}!"
```

After both error alternatives have left the flow, `customer` is known to be a `Customer`. General pattern selection and concise type-directed recovery helpers are planned, but their final syntax is not yet fixed.

Not every alternative that describes an unsuccessful search should be an exception. `User | Missing` contains two ordinary domain outcomes and does not gain forwarding. `User | NotFoundError` says that the second alternative is an error intended to participate in propagation.

## Errors, Absence, and Effects

`undefined` represents absence. It is not an `error`, but it is an `exception`, so optional navigation forwards it automatically. This makes `T | undefined` the common option-like form: use the `T` normally, or carry its exceptional absence through the route. [Optional Values and Narrowing](optional-types.md) covers explicit tests and fallbacks.

Errors are also separate from [effects](effects.md). An error appears in the returned union because it is a value the caller receives. Effects describe behavior such as I/O, blocking, or mutation even when a call succeeds.

> **Design boundary:** Direct error unions, nominal exception creation, the `exception` forwarding family, safe receiver navigation, explicit argument handling, and the separation of errors from effects are the intended model. Transforming an exception during `or_return`, pattern matching, recovery helpers, and extending automatic forwarding to pipelines remain provisional.

The [Errors and Forwarding reference](../../reference/errors-and-forwarding.html) gives the exact type rules and collects the remaining open points.
