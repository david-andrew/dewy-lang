# Errors, Exceptions, and Forwarding

> [Generated coverage](/status/#ref-errors-and-forwarding) names related acceptance programs. Every example on this page compiles with the current compiler unless it is marked **Design only**.

Expected failures are values. A function that can fail lists its failure types as alternatives of its result type, `int64 | ParseError`; there is no `Result` wrapper and no stack unwinding. A caller handles a failure, gives a fallback for it, or forwards it with `or_throw`.

Failures that the compiler can rule out are not values at all: an index, a divisor or a narrowing is proven before the program runs (see [Refinements, Effects, and Safety](refinements-and-effects.md)).

## The `exception` Family

```text
exception
├── error      file errors, ParseError, ValidationError, user errors, ...
├── none
└── Missing, Canceled, user exceptions, ...
```

A value whose type descends from `exception` is a *forwarding value*: member access forwards it, `??` replaces it and `or_throw` returns it. `is? error` and `is? exception` test the families. A type outside the family is an ordinary union alternative, even when used as a sentinel.

`Missing` is the prelude's exception for a search that found nothing (`text.find`, `xs.index_of`); it is neither `none` nor `-1`. `Canceled` reports a canceled wait (see [Concurrency](concurrency.md)).

## Declaring Error Types

`type of error` mints a new nominal error type. A unit error is written with its name. `& [fields]` adds a payload, constructed like a record. `type of exception` mints a non-error exception, and `type of Parent & [...]` mints a child that inherits the parent's fields. Two minted types are distinct even when their shapes agree. These declarations are module-level and nongeneric.

<!-- dewy-example: {"mode":"run","stdout":"42\nParseError[message=\"not a number: x\"]\nnot a number: x\n"} -->
```dewy
ParseError:type = type of error & [message:string]
parse = (text:string):>int|ParseError => {
    let n = to_int(text)
    if n is? error return ParseError["not a number: {text}"]
    return n
}
twice = (text:string):>int|ParseError => {
    let n = parse(text) or_throw
    return n * 2
}
printl(twice("21"))
let r = twice("x")
printl(r)
match r {
    e:ParseError => printl(e.message)
    v:int => printl(v)
}
```

A child keeps its identity where its parent is expected, so `match` and `is?` can select it:

<!-- dewy-example: {"mode":"run","stdout":"late by 5\n"} -->
```dewy
Ticket:type = type of error & [message:string code:int64=1]
Late:type = type of Ticket & [minutes:int64]
check = (k:int64):>int64|Ticket => if k =? 0 Late["late" 2 5] else k
match check(0) {
    l:Late => printl"late by {l.minutes}"
    t:Ticket => printl(t.message)
    n:int64 => printl(n)
}
```

## Error Return Unions

Errors are direct alternatives of a result union. A function that declares its result fixes the set of failures it may give. A function without a declared result infers it: each `return` of an error and each `or_throw` adds its kinds.

<!-- dewy-example: {"mode":"run","stdout":"Empty\n3\n"} -->
```dewy
Empty:type = type of error
measure = (text:string) => {
    if text =? "" return Empty
    return text.length
}
printl(measure(""))
printl(measure("abc"))
```

A function exposed to other modules should declare its failures.

## `or_throw`

Postfix `expression or_throw` evaluates the expression once. If the value is an exception, the enclosing function returns it; otherwise the expression gives the success value. It binds just below `as`, so it applies to the whole expression on its left. The enclosing function's result must accept every forwarded alternative:

<!-- dewy-example: {"mode":"reject","diagnostic":"or_throw cannot propagate NotFound"} -->
```dewy
NotFound:type = type of error
lookup = (id:int64):>int|NotFound => if id >? 100 NotFound else id * 2
use = (id:int64):>int => lookup(id) or_throw
printl(use(1))
```

`x or_throw<E>` forwards only the failures matched by `E` and leaves the others in the value. `E` may be a union or a family: `or_throw<error>` forwards errors and keeps `none`. The angle brackets select failures; they do not construct an `E`.

## Fallbacks with `??`

`value ?? fallback` gives the value when it is present, and otherwise runs the fallback. *Absent* means `none` or any exception value except `Canceled`. The left side runs once, and the fallback runs only when needed. Zero, `false` and empty collections are present values.

- The fallback may be `return x`, `break` or `continue`.
- `??<Missing | ParseError> fallback` covers only the listed kinds (and `none` only if listed); any other failure stays in the result. Listing a kind the value never holds is an error.
- Chains associate to the right: `first ?? second ?? default`.
- Arithmetic binds tighter than `??`; comparisons and boolean operators bind looser.
- `Canceled` is never replaced: it leaves the enclosing function as `or_throw` would. Only `??<Canceled>` handles it.

<!-- dewy-example: {"mode":"run","stdout":"42\n-1\n8080\n0\nBad\n"} -->
```dewy
total = (lines:array<string>):>int => {
    let sum = 0
    loop line in lines {
        let v = to_int(line) ?? continue
        sum += v
    }
    return sum
}
printl(total(["1" "x" "41"]))
first_num = (text:string):>int => to_int(text) ?? return -1
printl(first_num("q"))
printl(to_int("8080") ?? 80)

Bad:type = type of error
pick = (k:int64):>int64|Bad|Missing => if k =? 0 Bad else if k =? 1 Missing else k
printl(pick(1) ??<Missing> 0)
printl(pick(0) ??<Missing> 0)
```

## Explicit Handling

`is?`, `isnt?` and `match` narrow a result union through ordinary control flow. Each branch removes only the alternatives it tests; the rest stay in the type. A value that may hold a failure is not accepted where the success type is wanted:

<!-- dewy-example: {"mode":"reject","diagnostic":"it may hold a failure such as NotFound"} -->
```dewy
NotFound:type = type of error
lookup = (id:int64):>int64|NotFound => if id >? 100 NotFound else id
double = (n:int64):>int => n * 2
printl(double(lookup(3)))
```

## Forwarding Member Access

For a receiver of type `V1 | ... | Vn | X1 | ... | Xm`, where each `Xi` is an exception and no `Vi` is:

1. Every `Vi` must have the member; otherwise the access is an error.
2. When the receiver holds a `Vi`, the member is read (or the method called) normally.
3. When it holds an `Xi`, nothing is read and that exception is the result.
4. The result type is the union of the member types and `X1 | ... | Xm`.

Each step of a route applies the rule again, so a chain of reads is safe navigation without a separate `?.` operator. Method calls forward the same way: the receiver, then the arguments, are evaluated once.

<!-- dewy-example: {"mode":"run","stdout":"paris\nnone\nUserError\n"} -->
```dewy
UserError:type = type of error
Address:type = [city:string]
User:type = [name:string address:Address?]
load_user = (id:int64):>User|UserError|none => {
    if id <? 0 return UserError
    if id =? 0 return none
    return User["ada" Address["paris"]]
}
city_of = (id:int64) => load_user(id).address.city
printl(city_of(1))
printl(city_of(0))
printl(city_of(-1))
```

Without exception alternatives this is common-member access: when every alternative of a union has the member, the access reads it at the union of the member types. A member some alternative lacks is an error; narrow with `is?` first.

<!-- dewy-example: {"mode":"reject","diagnostic":"Org has no field 'id'"} -->
```dewy
Customer:type = [name:string id:int64]
Org:type = [name:string members:int64]
find = (id:int64):>Customer|Org => if id >? 0 Customer["ada" id] else Org["acme" 3]
printl(find(1).name)
printl(find(1).id)
```

Forwarding applies to the receiver's own type only. An `array<int64 | ParseError>` is an array, not a `ParseError`; arguments to a call do not forward either.

### Assignment

Forwarding is a read rule. Assigning through a route that may hold an exception is an error, so a write never silently does nothing:

<!-- dewy-example: {"mode":"reject","diagnostic":"cannot assign through a union receiver"} -->
```dewy
User:type = [name:string]
load = (id:int64):>User|none => if id >? 0 User["ada"] else none
let u = load(1)
u.name = "bea"
```

## `main` and Exit Codes

`main` is optional; without it a file runs top to bottom. With it, the top-level statements run first and then `main` runs once. `main` returns `void` or the errors that reach it, an ordinary `void | E` type, declared or inferred.

- Success exits with status 0. A program that needs another status calls `exit(n)` with a `uint8`.
- An error reaching `main` is printed on standard error as its kind and its `message` field, if it has one (`error: UsageError: usage: fetch HOST`). Other fields may hold secrets, so only a debug build (`-g`) prints the whole value.
- Each kind exits with its own status: 1, 2, 3, … in the order the kinds are declared (or as a declared result lists them), up to 100. Status 101 is a failed runtime check.
- An error type with an `exit_code` field pins its own status. The field is refined to 1–100, so an error can never report success.
- `dewy build --exit-codes file.dewy` prints the table.

<!-- dewy-example: {"mode":"run","stdout":"","exit":69,"args":["nowhere"]} -->
```dewy
UsageError:type = type of error & [message:string]
Offline:type = type of error & [exit_code:int64=69]
connect = (host:string):>void|Offline => {
    if host =? "nowhere" return Offline[]
    printl"connected to {host}"
}
main = ():>void|UsageError|Offline => {
    let argv = args
    if argv.length <? 2 return UsageError["usage: fetch HOST"]
    connect(argv[1]) or_throw
}
```

Run without arguments, this prints `error: UsageError: usage: fetch HOST` and exits 1; `fetch nowhere` prints `error: Offline` and exits 69.

## Errors Versus Effects

Errors are return values; effects describe what evaluating a call does. They are separate parts of a function's contract: `:>(Invoice | NotFound) & no allocates` has a result union and an effect row. A function's possible panic is the `panics` effect, not an error alternative. See [Effects](refinements-and-effects.md#effects).
