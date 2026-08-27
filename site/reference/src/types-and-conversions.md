# Types and Conversions

Dewy statically checks values and expressions. Types describe semantic values; implementations may select any representation that preserves those semantics.

## Type Values and Aliases

A type is a compile-time value of type `type`. A binding may name it explicitly or infer a type-valued expression:

```dewy
const Name:type = string
const Index = <int64>
const MaybeIndex = <int64 | undefined>
```

`<>` groups a type-valued expression where ordinary expression context would otherwise treat it as a runtime value. Alternatives inside use the normal type operators: `<int64 | string>`, not whitespace-separated alternatives.

A type alias does not create nominal identity unless its defining construct explicitly requests generativity.

## Nominal Identity

`type of Parent` evaluates to a fresh nominal child of `Parent`:

<!-- dewy-example: design-only -->
```dewy
const UserId:type = type of int
const NotFoundError:type = type of error
```

Each evaluation of `type of` creates a distinct identity. Referring to or aliasing the resulting binding preserves that identity. `<T of Bound>` in a generic parameter is a bound declaration and is not this generative expression.

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
const T1:type = [a:int | bool b:string c:bool | undefined]
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

## Unions and Narrowing

`A | B` accepts a value belonging to either alternative. `T | undefined` is an optional value. Type and literal tests such as `is?` and `isnt?` narrow the tested value along control-flow paths.

General runtime unions are tag-and-payload cells; `undefined`, when present, is always member 0, so an optional is the two-member case of the same layout. A union whose members include several concrete types together with `undefined` (`Node | int64 | undefined`) is an ordinary union, including as a parameter or result.

Narrowing applies to member routes as well as bindings: after `if node.next is? Node`, `node.next` reads as `Node` until the field or its object is assigned. A store into a union field always accepts the field's declared type, and forgets any narrowing of that route.

### Recursive Types

A type alias may refer to itself, but only as a union member of one of its fields:

```dewy
let Node:type = [value:int64 next:Node|undefined]
let Tree:type = [value:int64 left:Tree|undefined right:Tree|undefined]
```

The recursive member is stored behind a handle, which is what makes the object finite. A field typed exactly `Node` (no union) is rejected as an infinite value, and an alias whose every union member is itself has no base case and is rejected too. Values keep value semantics: copying a `Node | undefined` deep-copies the chain it points to, and narrowing a recursive member (`cur.next is? Node`) yields the object itself, so `cur.next.value` reads and writes through the handle.

An alternative belonging to the nominal `exception` family receives special receiver-navigation behavior. Member access operates on every ordinary alternative that supports the member and forwards every exception alternative. Both `error` and `undefined` descend from `exception`; arbitrary union alternatives do not become skippable. See [Errors, Exceptions, and Forwarding](errors-and-forwarding.md).

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
let first = <T>(xs:array<T>):>T | undefined =>
    if xs.length >? 0 xs[0] else undefined

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

## Refined Types

Refinements attach facts that values must satisfy. The exact general refinement proposition language and proof interfaces remain provisional; length and supported range facts already use this model.

## `as`

`as` requests a meaning-preserving conversion defined for the source and destination types:

```dewy
value as string
text as array<uint8>
```

Conversions may change representation and may invoke overloadable conversion behavior. Lossy or fallible operations require an interface whose type exposes that possibility rather than silently discarding information.

## `transmute`

`transmute` reinterprets a compatible representation without performing a semantic conversion. It is valid only where source and destination layouts satisfy the transmute contract. It must not be used as an implicit substitute for numeric or textual conversion.

See [Numeric Types](numeric-types.md), [Strings](strings.md), and [Design Maturity](design-status.md).
