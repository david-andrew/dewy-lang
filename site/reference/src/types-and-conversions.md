# Types and Conversions

> [Generated coverage](/status/#ref-types-and-conversions) names related acceptance programs. Every example on this page compiles with the current compiler unless it is marked **Design only**.

Dewy checks every value and expression statically. Types describe values; the compiler chooses any representation that preserves their meaning.

## Types as Values

A type is a compile-time value of type `type`. A type alias is declared as `Name:type = T`, `let Name:type = T` or `const Name:type = T`. An alias is the same type as its right side; it does not create a new identity.

`<…>` is a type block: inside it, the contents are read as types. Union alternatives use `|`, not whitespace. An annotation position (`name:T`, `:>T`) and the right side of `name:type =` are already type positions.

Where a value is needed, a type converts to its spelling, so types can be printed while debugging. `T.name` is a type's short name, a compile-time `string`.

<!-- dewy-example: {"mode":"run","stdout":"2 1 | 2\nint64 | float64\nPoint Point int64\n"} -->
```dewy
let Mode:type = <1 | 2>
let m:Mode = 2
printl"{m} {Mode}"
const Num:type = int64 | float64
printl(Num)
Point:type = [x:int64 y:int64]
printl"{Point} {Point.name} {int64 as string}"
```

A method that reads no field of its type, and calls no method that does, is static: it is called on the type's name as well as on an instance (`Span.unit` for a member `unit = ():>Span => Span(0 1)`).

A type cannot be held in an ordinary runtime binding:

<!-- dewy-example: {"mode":"reject","diagnostic":"'T' cannot hold a type"} -->
```dewy
let T = int64
```

## Minted Types

`type of Parent` mints a fresh nominal type: a child of `Parent` that is distinct from every other type, including a structurally identical one. Each evaluation of `type of` creates a new identity; aliasing the result keeps it. The parent is `error` (see [Errors](errors-and-forwarding.md)), `exception`, `any`, or another minted type. `type of any` starts a family of its own. `& [fields…]` adds fields.

<!-- dewy-example: {"mode":"run","stdout":"name x\npunct ;\nName[line=3 text=\"y\"]\nNotFound\ntrue\n"} -->
```dewy
NotFound:type = type of error
Token:type = type of any & [line:int64]
Name:type = type of Token & [text:string]
Punct:type = type of Token & [text:string]   # same structure, distinct type

describe = (t:Token):>string => match t {
    n:Name => "name {n.text}"
    p:Punct => "punct {p.text}"
    _ => "token"
}

main = () => {
    printl(describe(Name(1 "x")))
    printl(describe(Punct(line=2 text=";")))
    let n:Name = [line=3 text="y"]
    printl(n)
    printl(NotFound)
    printl(n is? Token)
}
```

- A child is a subtype of its parent: a `Name` satisfies a `Token` parameter and keeps its identity there, for `is?` and `match`.
- The parent's fields lead the child's. One nominal parent per mint.
- A minted value carries its brand at run time, so a value seen through its parent still says which child it is. A parent-typed slot stores the whole child.
- A minted type prints by its name. A minted type with no fields, or with defaults for every field, is also its own value: `NotFound` and `NotFound()` are the same.
- Values are constructed by calling the type (`Name(1 "x")`, `Punct(line=2 text=";")`) or by an object literal in the type's context.

A minted type does not satisfy a sibling's annotation:

<!-- dewy-example: {"mode":"reject","diagnostic":"argument 'n' expects Name, found Punct"} -->
```dewy
Token:type = type of any & [line:int64]
Name:type = type of Token & [text:string]
Punct:type = type of Token & [text:string]
f = (n:Name):>int64 => n.line
printl(f(Punct(1 ";")))
```

Minting is currently module-level and nongeneric. Other nominal parents, such as `type of int64`, are not supported. `$abstract` mints (a parent with no values of its own) and type-valued families (`type<Token>`) are decided but not built yet.

## Intersections

`A & B` requires both operand types. It never mints: intersecting record types gives a record with the fields of both, and stays a subtype of each. A field on both sides takes the intersection of its types; an empty intersection is an error. A later default replaces an earlier one.

<!-- dewy-example: {"mode":"run","stdout":"[depth=2 tag=\"root\"] 2\n[a=true b=\"x\" c=3]\n"} -->
```dewy
Root:type = [depth:int64]
Tagged:type = Root & [tag:string = "root"]
T1:type = [a:int64 | bool b:string]
T2:type = [a:bool c:int64]
Both:type = T1 & T2          # a is bool

takes = (r:Root):>int64 => r.depth

main = () => {
    let t = Tagged(depth=2)
    printl"{t} {takes(t)}"
    printl(Both(a=true b="x" c=3))
}
```

<!-- dewy-example: {"mode":"reject","diagnostic":"this intersection has no values: field 'b' would be string & int64"} -->
```dewy
T1:type = [b:string]
T2:type = [b:int64]
Impossible:type = T1 & T2
```

On types, `&` and `|` are the same operators as `and` and `or`; see [Symbolic and Word Composition](operators-and-precedence.md#symbolic-and-word-composition).

## Unions, Optionals and Narrowing

`A | B` holds a value of either alternative. `T?` is `T | none`. `is?` and `isnt?` test the alternative and narrow the tested value on the paths where the test holds; `match` selects by alternative.

<!-- dewy-example: {"mode":"run","stdout":"2\n5\ntext hi\n"} -->
```dewy
let v:int64 | string = "hi"
if v is? string printl(v.length)
let o:int64? = 4
if o isnt? none printl(o + 1)
match v {
    s:string => printl"text {s}"
    n:int64 => printl"number {n}"
}
```

Narrowing also applies to field routes: after `if node.next is? Node`, `node.next` reads as `Node` until it or its object is assigned. Assigning another type to a narrowed binding ends the narrowing.

`members(U)` lists a union's alternatives. In `loop t in members(U)` each `t` is a type, so `x is? t` works:

<!-- dewy-example: {"mode":"run","stdout":"Jpeg Img\n"} -->
```dewy
Png:type = [w:int64]
Jpeg:type = [q:int64]
Img:type = Png | Jpeg
kind = (x:Img):>string => {
    loop t in members(Img) { if x is? t return t.name }
    "none"
}
main = () => printl"{kind(Jpeg[2])} {Img.name}"
```

### Recursive Types

A record type may refer to itself through an optional or union field. The recursive member is stored behind a handle, which keeps the value finite; values keep value semantics.

<!-- dewy-example: {"mode":"run","stdout":"6\n"} -->
```dewy
Node:type = [value:int64 next:Node?]
total = (n:Node):>int => {
    let t:int = n.value
    let cur = n
    loop cur.next is? Node {
        cur = cur.next
        t += cur.value
    }
    t
}
main = () => printl(total(Node(1 Node(2 Node(3 none)))))
```

<!-- dewy-example: {"mode":"reject","diagnostic":"recursive type 'Bad' has no finite value"} -->
```dewy
Bad:type = [value:int64 next:Bad]
```

## Parameterized Types and Generics

Parameterized types take compile-time arguments in `<…>`: `array<string>`, `array<int64 length=3>`, `dict<string int64>`. A user type alias takes parameters before its body: `Box:type = <T>[value:T]`, then `Box<int64>`.

A generic function declares its type parameters before its parameter list. Type arguments are inferred from the arguments, through arrays, records and function types. Each distinct instantiation is checked and compiled as an ordinary function.

<!-- dewy-example: {"mode":"run","stdout":"hi none\n[x=\"one\" y=1]\nx [value=3]\n"} -->
```dewy
Box:type = <T>[value:T]
first = <T>(xs:array<T>):>T? => if xs.length >? 0 xs[0] else none
swap = <T U>(a:T b:U):>[x:U y:T] => [x=b y=a]
unbox = <T>(b:Box<T>):>T => b.value

main = () => {
    let words:array<string> = ["hi"]
    let empty:array<string> = []
    printl"{first(words)} {first(empty)}"
    printl(swap(1 "one"))
    let b:Box<string> = [value="x"]
    printl"{unbox(b)} {Box<int64>(3)}"
}
```

Bounded type parameters (`<T of Bound>`) are not supported yet.

## Literal Types

In a type position a literal is its singleton type: `d:0` admits only `0`, `s:"fast"` only `"fast"`. A union of literals is an enumeration and mixes freely with other types. On a value, `m is? 1` tests the member.

<!-- dewy-example: {"mode":"run","stdout":"60\n"} -->
```dewy
Mode:type = <1 | 2 | "fast" | "slow">
describe = (m:Mode):>int64 =>
    if m is? 1 10 else if m is? 2 20 else if m is? "fast" 30 else 40
main = () => {
    let m:Mode = "slow"
    printl(describe(m) + describe(2))
}
```

Storing into a literal type is an obligation: a member literal stores as it is, another literal is an error, and a runtime value must be proven a member (`if s is? BasePrefix`). For a string, `is?` against a union of string literals compares with each member:

<!-- dewy-example: {"mode":"run","stdout":"0x none\n"} -->
```dewy
BasePrefix:type = '0b' | '0t' | '0x'
classify = (text:string):>string => {
    if text.length >=? 2 {
        let head = text[..2)
        if head is? BasePrefix return head
    }
    "none"
}
main = () => printl"{classify("0x1f")} {classify("12")}"
```

<!-- dewy-example: {"mode":"reject","diagnostic":"argument 's' expects 1 | 2 | 3, found int"} -->
```dewy
Small:type = 1 | 2 | 3
f = (s:Small):>int64 => s
printl(f(4))
```

A literal-typed parameter specializes an overload: a call with that literal selects the most specific method, and has that method's result type. `int64 & ~0` is `int64` without `0`:

<!-- dewy-example: {"mode":"run","stdout":"2\nDivZero\n"} -->
```dewy
DivZero:type = type of error
safe_div = ((_n:int64 _d:0):>DivZero => DivZero)
         & ((n:int64 d:int64 & ~0):>int => n // d)
main = () => {
    printl(safe_div(6 3))
    printl(safe_div(6 0))
}
```

## Refined Types

A refinement attaches a fact to a type: `int64<(>? 0)>`, `d:int64<d not=? 0>`, `string<length >? 0>`, `array<int64 length=3>`. On a binding the fact is proven at the declaration; on a parameter at every call and assumed in the body. See [Refinements, Effects, and Safety](refinements-and-effects.md).

## Conversions

Implicit conversions never lose information. A narrower integer widens freely. A narrowing (an `int` or `int64` stored into `uint8`, say) is a *proven conversion*: free when facts prove the value fits, a compile error otherwise (a runtime check under `$runtime_checks`). See [Meeting Another Width](numeric-types.md#meeting-another-width).

### `as`

`x as T` requests a conversion that keeps the value. It uses the same proofs as an annotated binding, so an unproven narrowing is an error, not a truncation:

<!-- dewy-example: {"mode":"run","stdout":"200 none\n42\nhi\n"} -->
```dewy
byte = (n:int):>uint8? => {
    if 0 <=? n <=? 255 return n as uint8
    none
}
main = () => {
    printl"{byte(200)} {byte(300)}"
    printl(42 as string)
    let bytes:array<uint8> = [104 105]
    printl(bytes as string | none)
}
```

<!-- dewy-example: {"mode":"reject","diagnostic":"w does not fit uint8"} -->
```dewy
let w:int64 = 300
printl(w as uint8)
```

A conversion that can fail names the failure in its target: `bytes as string | none` decodes UTF-8 and gives `none` for invalid input, and `bytes as string ?? fallback` falls back. Plain `bytes as string` is an error, since nothing proves the bytes valid.

`as` binds below `|`, so `x as string | none` converts to the union; write `(x as int64) + 1` to convert before arithmetic.

### Type Calls

Calling a type converts or constructs: `int64(x)` and `uint8(x)` are the same proven conversions as `as`; `string(value)` formats a value; `int(f)` truncates a float toward zero. A literal union read from text, `BasePrefix(s)`, gives `BasePrefix | ValidationError`:

<!-- dewy-example: {"mode":"run","stdout":"0x\nValidationError[message=\"must be one of '0b' | '0t' | '0x'\" input=\"0q\"]\n42 7 3.0 -2\n"} -->
```dewy
BasePrefix:type = '0b' | '0t' | '0x'
main = () => {
    printl(BasePrefix("0x"))
    printl(BasePrefix("0q"))
    printl"{string(42)} {int64(7)} {float64(3)} {int(-2.7)}"
}
```

### Conversion Methods

A record type says how its values convert with a conversion method, `__as__ = ():>T => …`. It serves `x as T` and, for `T` = `string`, printing and interpolation. A minted child without its own uses its nearest ancestor's. Without one, a container or record converts to `string` as its literal syntax (`[1 2 3]`, `[x=1 y=2]`).

<!-- dewy-example: {"mode":"run","stdout":"(3, 4) 6\n"} -->
```dewy
Point:type = [
    x:int64
    y:int64
    __as__ = ():>string => "({x}, {y})"
]
main = () => {
    let pt = Point(3 4)
    let text = pt as string
    printl"{pt} {text.length}"
}
```

## `transmute`

`x transmute T` reinterprets the bits of a machine integer or float as another type of the same width. It is not a numeric conversion. Booleans, collections, records and unions cannot be transmuted.

<!-- dewy-example: {"mode":"run","stdout":"4607182418800017408\n"} -->
```dewy
printl(float64(1.0) transmute uint64)
```

See [Numeric Types](numeric-types.md) and [Strings](strings.md).
