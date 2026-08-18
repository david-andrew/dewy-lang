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
representations. Type aliases are currently written with an explicit `:type`
annotation.
