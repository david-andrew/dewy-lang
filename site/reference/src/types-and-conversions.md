# Types and conversions

Dewy performs static type checking and contextual inference. Implemented value
types include `bool`, `void`, `never`, `undefined`, fixed-width integers,
strings, homogeneous arrays, structural objects, functions, ranges, and
supported optionals.

Integer literals begin as exact singleton types and may inhabit a compatible
fixed-width context. An unannotated integer binding widens to abstract `int`,
whose semantic contract is arbitrary precision. Bigint lowering is not yet
implemented.

```dewy
let byte:uint8 = 255
let count = 10             # int semantics
let optional:int64 | undefined = undefined
```

`as` performs a checked representation-changing conversion supported by the
compiler. `transmute` preserves bits and requires compatible implemented
representations.

A standalone `<>` block contains one type expression and produces a
compile-time type value. This lets an ordinary inferred declaration introduce
an alias; the explicit `:type` spelling remains available too.

```dewy
const Index = <int64>
const Result = <int64 | undefined>
const Name:type = string

let offset:Index = 42
```

Separate alternatives inside `<>` use the ordinary type operator rather than
whitespace: write `<int64 | string>`, not `<int64 string>`.
