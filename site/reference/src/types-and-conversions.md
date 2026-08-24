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

## Inference and Context

Literals retain exact information until context requires a broader type. An unannotated mutable integer binding widens from its literal singleton to `int`; a fixed-width annotation accepts the literal only when it fits.

Function parameters, returns, container elements, object fields, assignments, and operator overloads all provide type context.

## Unions and Narrowing

`A | B` accepts a value belonging to either alternative. `T | undefined` is an optional value. Type and literal tests such as `is?` and `isnt?` narrow the tested value along control-flow paths.

General heterogeneous runtime-union layout remains provisional. Optional values with one concrete payload have a settled semantic model.

An alternative belonging to the nominal `exception` family receives special receiver-navigation behavior. Member access operates on every ordinary alternative that supports the member and forwards every exception alternative. Both `error` and `undefined` descend from `exception`; arbitrary union alternatives do not become skippable. See [Errors, Exceptions, and Forwarding](errors-and-forwarding.md).

## Parameterized and Refined Types

Parameterized types apply compile-time arguments:

```dewy
array<string>
array<int64 length=3>
Duration<uint64>
```

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
