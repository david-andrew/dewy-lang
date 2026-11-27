# Types and Numbers

Types are inferred, and an annotation after a colon states one when you want to. The everyday types are `int`, `rational`, `float64`, `bool` and `string`.

<!-- dewy-example: {"mode": "run", "stdout": "42 true\n1267650600228229401496703205376\n7/2 3\n"} -->
```dewy
let count:int = 40
let ready = true
printl"{count + 2} {ready}"

printl(2^100)            # int never overflows
printl"{7 / 2} {7 // 2}" # exact division, floor division
```

`int` is the mathematical integer. It is stored in a machine word while the value fits and grows when it does not, so ordinary arithmetic is both fast and exact. Dividing two integers with `/` gives an exact `rational`, and `//` is floor division. A decimal literal such as `0.1` is exact too, unless a float is wanted.

`float64` and `float32` are IEEE floating point, used when you ask for them:

<!-- dewy-example: {"mode": "run", "stdout": "0.30000000000000004\ntrue\n"} -->
```dewy
let x:float64 = 0.1
printl(x + 0.2)
printl(0.1 + 0.2 =? 0.3)
```

Fixed-width integers (`int8` to `int64`, `uint8` to `uint64`) fix how a value is stored, for dense data and interop. Arithmetic on them is exact; storing a result that might not fit the width is a compile error, unless the type says it wraps or saturates (`uint32<overflow='wrap'>`).

The [reference](/reference/numeric-types.html) has the complete rules.
