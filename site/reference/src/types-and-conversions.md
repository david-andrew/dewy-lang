# Types and Conversions

Dewy statically checks values and expressions. Types describe semantic values; implementations may select any representation that preserves those semantics.

## Type Values and Aliases

A type is a compile-time value of type `type`. A binding may name it explicitly or infer a type-valued expression:

```dewy
const Name:type = string
const Index = <int64>
const MaybeIndex = <int64 | none>
```

`<>` groups a type-valued expression where ordinary expression context would otherwise treat it as a runtime value. Alternatives inside use the normal type operators: `<int64 | string>`, not whitespace-separated alternatives.

A type alias does not create nominal identity unless its defining construct explicitly requests generativity.

## Nominal Identity

`type of Parent` evaluates to a fresh nominal child of `Parent`. Implemented today: error types (`type of error`) and object types, where the operand may be an object type, `any` alone (an empty marker type), or an intersection of `any` with object types (`&` contributes structure, never identity):

<!-- dewy-example: compiler -->
```dewy
let NotFoundError:type = type of error
let Name:type = type of any & [text:string]
Punct = type of any & [text:string]     # same structure, distinct type
let Vec = type of [x:int64 y:int64  length_squared = ():>int64 => x*x + y*y]
```

`type of Parent` where `Parent` is itself a minted type mints a nominal *child*: a subtype of the parent (a `Whitespace` value satisfies a `Token` parameter, and `t is? Token` holds for every child in a union), distinct from the parent and from its siblings. The parent's fields lead the child's, and the operand may add more (`type of Token & [text:string]`); one nominal parent per mint. A minted type with no fields is both the type and its single inhabitant — written with its name where a value is wanted, as an error type is: `[Whitespace Name(text='x')]`, `return Whitespace`, `let w = Whitespace` (`Whitespace()` constructs the same value).

<!-- dewy-example: compiler -->
```dewy
let Token = type of any
let Whitespace = type of Token
let Name = type of Token & [text:string]
```

A minted object type is structurally its operand but distinct from every other type, including a structurally identical one: `Name | Punct` is a two-member union that `match` distinguishes, and a `Name` value does not satisfy a `Punct` annotation. The type prints by its name. Values are constructed by calling the type (`Name(text='hi')`, positionally `Vec(3 4)`) or by an object literal in the minted type's context (`let n:Name = [text='hi']`); methods and `&=` constructor overloads work as on any object type. Numeric parents such as `type of int` are not implemented yet:

<!-- dewy-example: design-only -->
```dewy
const UserId:type = type of int
```

Each evaluation of `type of` creates a distinct identity. Referring to or aliasing the resulting binding preserves that identity. `<T of Bound>` in a generic parameter is a bound declaration and is not this generative expression.

An alias is declared by any of `Name = <type expr>`, `let Name = <type expr>`, `Name:type = <type expr>`, or `let Name:type = <type expr>`. Intersecting object types strengthens structure without minting: `Root = Context & [tag:string='root']` has `Context`'s fields plus `tag` (and stays `Context`'s nominal kind when `Context` is minted — a `Root` satisfies a `Context` parameter); a same-name field must fit the inherited one and replaces it, so a mint may narrow an inherited default (`type of Report & [severity='error']`). A field written `name = value` takes the default's widened type; construction is by calling the type (defaults fill omitted fields).

`type of` is the only generative type operation. Intersection does not mint nominal identity:

<!-- dewy-example: design-only -->
```dewy
const ContextError:type =
    (type of error) & [context:string code:int64]

const DetailedContextError:type =
    ContextError & [source:string]
```

`ContextError` has one fresh identity beneath `error`. `DetailedContextError` is the same nominal kind with a stronger structural requirement; it does not add another node to the nominal tree. Consequently, `ContextError | DetailedContextError` simplifies to `ContextError`.

## Intersections

`A & B` requires both operand types and is non-generative, including when an operand carries nominal ancestry. Re-evaluating equal intersections produces equal types.

Structural-object intersections merge requirements by field name. A field found on only one side is retained. Matching fields intersect their required types:

<!-- dewy-example: design-only -->
```dewy
const T1:type = [a:int | bool b:string c:bool | none]
const T2:type = [a:bool b:int]

# a requires (int | bool) & bool, which simplifies to bool
# b requires string & int, which simplifies to never
const Impossible:type = T1 & T2  # compile-time error
```

A required `never` field makes the complete object intersection uninhabited; presenting that result as a constructible declared type is a compile-time error. Matching fields must also agree on mutability. A mutable requirement and a const requirement are incompatible because neither contract can safely stand in for the other.

These rules keep `&` associative, commutative, idempotent, and independent of declaration identity. Because object field order otherwise participates in structural types, normalization of a merged intersection must choose the same semantic field order independently of operand order; the exact canonical ordering and layout remain representation-design work.

## Inference and Context

Literals retain exact information until context requires a broader type. An unannotated mutable integer binding widens from its literal singleton to `int`; a fixed-width annotation accepts the literal only when it fits.

Function parameters, returns, container elements, object fields, assignments, and operator overloads all provide type context.

## Optional Sugar

`T?` in a type position is `T | none`: `let word:string? = none`, a parameter `(v:string?)`, a result `:>int64?`, an element `dict<string int64?>`. `?` does not appear in value positions; narrowing an optional is the ordinary `is?`.

## Unions and Narrowing

`A | B` accepts a value belonging to either alternative. `T | none` is an optional value. Type and literal tests such as `is?` and `isnt?` narrow the tested value along control-flow paths.

General runtime unions are tag-and-payload cells; `none`, when present, is always member 0, so an optional is the two-member case of the same layout. A union whose members include several concrete types together with `none` (`Node | int64 | none`) is an ordinary union, including as a parameter or result.

Narrowing applies to member routes as well as bindings: after `if node.next is? Node`, `node.next` reads as `Node` until the field or its object is assigned. A store into a union field always accepts the field's declared type, and forgets any narrowing of that route.

A type test against a union of string literals is a membership test when the value is a runtime string: `head is? BasePrefix` with `BasePrefix:type = '0b' | '0t' | '0x'` compares `head` with each member, and narrows it to the union where the test passes. A test the static types settle is decided while checking (a three-grapheme string is never a two-grapheme member; see [Generic Functions](#generic-functions)).

<!-- dewy-example: compiler -->

```dewy
let BasePrefix:type = '0b' | '0t' | '0x'

let classify = (text:string):>string => {
    if text.length >=? 2 {
        let head = text[..2)
        if head is? BasePrefix { return head }
    }
    return "none"
}

let main = ():>int64 => classify("0x1f").length     # 2
```

### Recursive Types

A type alias may refer to itself, but only as a union member of one of its fields:

```dewy
let Node:type = [value:int64 next:Node|none]
let Tree:type = [value:int64 left:Tree|none right:Tree|none]
```

The recursive member is stored behind a handle, which is what makes the object finite. A field typed exactly `Node` (no union) is rejected as an infinite value, and an alias whose every union member is itself has no base case and is rejected too. Values keep value semantics: copying a `Node | none` deep-copies the chain it points to, and narrowing a recursive member (`cur.next is? Node`) yields the object itself, so `cur.next.value` reads and writes through the handle.

An alternative belonging to the nominal `exception` family receives special receiver-navigation behavior. Member access operates on every ordinary alternative that supports the member and forwards every exception alternative. Both `error` and `none` descend from `exception`; arbitrary union alternatives do not become skippable. See [Errors, Exceptions, and Forwarding](errors-and-forwarding.md).

## Parameterized Types

Parameterized types apply compile-time arguments:

```dewy
array<string>
array<int64 length=3>
Duration<uint64>
```

User type aliases take parameters the same way: `let Box:type = <T>[value:T]`, then `Box<int64>`.

### Generic Functions

A generic function declares its type parameters before the parameter list and must declare its result type:

<!-- dewy-example: compiler -->

```dewy
let first = <T>(xs:array<T>):>T | none =>
    if xs.length >? 0 xs[0] else none

let swap = <T U>(a:T b:U):>[x:U y:T] => [x=b y=a]

let total = <T of int>(a:T b:T):>T => a + b

let main = ():>int64 => {
    let words:array<string> = ["hi"]
    let w = first(words)          # T = string
    let s = swap(1 "one")         # T = int64, U = string
    return total(20 22) + s.y     # 43
}
```

Type arguments are inferred from the arguments (and a contextual result type), structurally through arrays, objects, and function types; a literal argument binds its ordinary type (`1` is `int64`, `"one"` is `string`). `T of Bound` restricts the arguments a call may supply. The body is checked per instantiation with the type parameters bound to the inferred types — an operation the instance's types do not support is reported at that use, as it would be in a plain function — and each distinct instantiation is compiled as an ordinary function (`first__string`). A generic function is declared with `let` at module level, is called by name, and cannot be used as a value. Generic type aliases that refer to themselves, and generic *local* functions, are not implemented yet.

A type test the static types settle is decided while checking — `v is? string` is true when `v`'s type is `string` and false when it cannot be — and only the live arm of an `if` on it is checked. In a generic, that is how a body varies by type parameter: each instance keeps the arm written for its type, which may use members the other arm's type lacks.

<!-- dewy-example: compiler -->

```dewy
let size = <T>(v:T):>int64 => if v is? string v.length else 1

let main = ():>int64 => size("abc") + size(true)   # 4
```

## Literal Types

In a type context a literal denotes its singleton type: `x:5` admits only `5`, `d:0` only `0`, `s:"one"` only `"one"`, and a packed literal `0x"6869"` only those bytes. Type contexts are annotation positions (`name:T`, `:>T`), the right-hand side of `name:type = …`, and an explicit type block `<…>`; anywhere else a literal is a value, and `<…>` is the way to write a type expression where the context alone would read it as values (`<1 | 2 | 3>` is a type — as values `1 | 2 | 3` would be `or` between numbers).

Unions of literals are enumerations, mixed freely with other types, and `is?` narrows them:

<!-- dewy-example: compiler -->

```dewy
let Mode:type = <1 | 2 | "fast" | "slow">

let describe = (m:Mode):>int64 =>
    if m is? 1 10 else if m is? 2 20 else if m is? "fast" 30 else 40

let main = ():>int64 => {
    let m:Mode = "slow"
    return describe(m) + describe(2)    # 60
}
```

A literal-typed parameter specializes an overload — dispatch picks the most specific applicable method, and each call has the selected method's result type:

<!-- dewy-example: compiler -->

```dewy
let DivZero:type = type of error
let safe_div = ((n:int64 d:0):>DivZero => DivZero)
             & ((n:int64 d:int64 & ~0):>int64 => n // d)

let main = ():>int64 => {
    let q = safe_div(6 3)             # int64
    let e = safe_div(6 0)             # DivZero
    if e is? DivZero { return q }     # 2
    return 0
}
```

The literal method wins exactly when the divisor is the literal `0`; `int64 & ~0` — the intersection of `int64` with the negation of the literal type `0` — is the structural spelling of the refinement `int64<d not=? 0>`, so the two methods partition `int64`, the general method's `n // d` is proven, and a call with a runtime divisor must establish `d not=? 0` first (a guard, or a `$runtime_assert`). Boolean literal types (`true`, `false`) are not implemented; use `bool`.

## Refined Types

Refinements attach facts that values must satisfy. On a named declaration the declared name is the value — `d:int64<d not=? 0>`, `xs:array<int64 xs.length >? 0>` — while the lambda form names it where there is no name (`Positive = int64<i => i >? 0>`), and `length>?0` alone still means the sequence's length. An object value can be refined by an integer field (`r:Ratio<bottom >? 0>`), and `length` on an array is the same idea for the one measure arrays expose today. Excluding literals has a structural spelling: `int64 & ~0` and `int64 & ~(0 | 1)` are `int64<d not=? 0>` and `int64<d not=? 0 and d not=? 1>`. On a binding they are proven at the declaration; on a parameter at every call site and assumed inside the body (see [Refined Parameters](refinements-and-effects.md#refined-parameters)). The exact general refinement proposition language and proof interfaces remain provisional; value comparisons against constants and length facts use this model today.

## `as`

`as` requests a meaning-preserving conversion defined for the source and destination types:

```dewy
value as string
text as array<uint8>
```

Conversions may change representation and may invoke overloadable conversion behavior. Lossy or fallible operations require an interface whose type exposes that possibility rather than silently discarding information.

A declared type says how its values convert with a conversion method: `__as__ = ():>T => …` serves `x as T`, and — for `T` = `string` — string interpolation (`"{x}"`). The target type is the method's result type; nothing about a type's name or shape is special to the compiler. The prelude's `Path` converts to its text this way, which is why `p"{root}/{name}"` joins paths:

<!-- dewy-example: compiler -->

```dewy
let Point:type = [
    x:int64
    y:int64
    __as__ = ():>string => "({x}, {y})"
]

let main = ():>int64 => {
    let pt = Point(3 4)
    let text:string = pt as string      # "(3, 4)"
    printl"{pt} and {p"a/b.c".parent}"  # (3, 4) and a
    return text.length
}
```

A type, a function, or an overload set has no runtime representation; where a value is needed — `T as string`, an interpolation field `"{T}"`, `printl(T)`, a generic's value parameter — it is its spelling (`'0b' | '0t'`, `<(a:int64):>int64>`), which makes such things printable while debugging. A container, or an object whose type declares no `__as__` to `string`, converts to `string` as its literal syntax (`[1 2 3]`, `[x=1 y=2]`; see [Printing](strings.md#printing)). Any other value whose type has no fitting `__as__` is an error where it is converted (`unsupported value conversion`, or `no string conversion for this value`). A type converts to several targets by adding conversions with `&=` — `__as__ &= ():>int64 => x * 100 + y` after the first — and `x as T` picks the one whose result fits `T`.

## `transmute`

`transmute` reinterprets a compatible representation without performing a semantic conversion. It is valid only where source and destination layouts satisfy the transmute contract. It must not be used as an implicit substitute for numeric or textual conversion.

See [Numeric Types](numeric-types.md), [Strings](strings.md), and [Design Maturity](design-status.md).
