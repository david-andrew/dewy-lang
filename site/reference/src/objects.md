# Records and Objects

> [Generated coverage](/status/#ref-objects) names related acceptance programs. Every example on this page compiles with the current compiler unless it is marked **Design only**.

A record is a value with named fields. `Name:type = [field:Type ...]` declares a named record type; a literal with `name=value` fields and no expected type makes an anonymous record.

<!-- dewy-example: {"mode":"run","stdout":"42\n[x=1 y=2]\n[x=5 y=22]\n[x=3 y=22]\n"} -->
```dewy
Point:type = [x:int64 y:int64=22]
let p:Point = [x=20]
let [y x] = p
printl(x + y)
printl(Point[1 2])
let r:Point = [5]
printl(r)
printl(Point(3))
```

## Construction

A record type's fields are its constructor's parameters, read like a function's:

- `Point[20 22]` and `Point(20 22)` construct explicitly, positionally or with `name=value` fields in any order;
- where a record type is expected (an annotation, an `array<Point>` element, a dictionary value, an argument), a bare literal `[x=20]` or `[20]` uses it;
- a field with a default may be left out, and a default may use earlier fields (`stop:int64=start`);
- an optional field `next:Node?` defaults to `none`;
- leaving out any other field, giving one twice, or naming an unknown field is an error;
- when every field has a default, the type's bare name where a value goes constructs it, as `Origin()` would.

<!-- dewy-example: {"mode":"reject","diagnostic":"Point needs its field 'y', which has no default"} -->
```dewy
Point:type = [x:int64 y:int64]
let p:Point = [x=1]
```

<!-- dewy-example: {"mode":"run","stdout":"[start=4 stop=4]\n[x=0 y=0]\n[left=1 right=2]\n"} -->
```dewy
Span:type = [start:int64 stop:int64=start]
printl(Span(4))
Origin:type = [x:int64=0 y:int64=0]
let o = Origin
printl(o)
make_pair = (left:int64 right:int64):>[left:int64 right:int64] => [left=left right=right]
printl(make_pair(1 2))
```

Given values are evaluated first, in written order, then the defaults in field order. Names in a default come from the scope where the type was declared. A constructor that does more than fill fields is an ordinary function returning the record.

## Structural Types

Anonymous record types agree by field names and types, in any order; an inline shape such as `[x:int y:int]` can be written in any annotation. Anonymous records print with their fields in name order. Named records are distinct types: a `Point` is not a `Size` even with the same fields.

<!-- dewy-example: {"mode":"run","stdout":"42\n[x=1 y=2]\n"} -->
```dewy
sum = (pt:[x:int y:int]):>int => pt.x + pt.y
printl(sum([y=22 x=20]))
printl([y=2 x=1])
```

### Intersections

`A & B` of record types has the fields of both. A field on both sides takes the intersection of its types; when that is empty, the declaration is an error. A value of the intersection passes where an `A` or a `B` is expected. Intersections are module-level declarations of plain records; minting with `type of` is described in [Errors and Forwarding](errors-and-forwarding.md#declaring-error-types).

<!-- dewy-example: {"mode":"run","stdout":"[line=1 column=2 label=\"x\"]\n"} -->
```dewy
Located:type = [line:int64 column:int64]
Labeled:type = [label:string]
LabeledLocation:type = Located & Labeled
printl(LabeledLocation[line=1 column=2 label="x"])
```

<!-- dewy-example: {"mode":"reject","diagnostic":"this intersection has no values"} -->
```dewy
Located:type = [line:int64]
Named:type = [line:string]
Both:type = Located & Named
```

### Spreads

`[defaults... speed=12]` copies a record's fields into a new literal; later fields and spreads replace earlier ones of the same name. Every operand runs once, in source order.

<!-- dewy-example: {"mode":"run","stdout":"[speed=12 name=\"d\"]\n"} -->
```dewy
Settings:type = [speed:int64=1 name:string="d"]
let defaults:Settings = []
let tuned:Settings = [defaults... speed=12]
printl(tuned)
```

## Fields and Copies

Fields are read with `.` and assigned on a mutable binding. Copies are independent, including nested arrays and records. `value.copy` asks for an independent value explicitly; it is what `$explicit_copies` requires where a copy has a cost (see [Values, Copies, and Places](values.md)).

<!-- dewy-example: {"mode":"run","stdout":"[values=[20 22]]\n[values=[99 22]]\n"} -->
```dewy
let original = [values=[20 22]]
let copy = original
copy.values[0] = 99
printl(original)
printl(copy)
```

`@record.field` passes the place of a field, so a function can change it in the caller:

<!-- dewy-example: {"mode":"run","stdout":"[x=2 y=3]\n"} -->
```dewy
Point:type = [x:int64 y:int64]
mover = (@pt:Point) => { pt.x += 1 }
bump = (@n:int64) => { n += 1 }
let p = Point[1 2]
mover(@p)
bump(@p.y)
printl(p)
```

`a =? b` compares records field by field, recursively. A type may define `__eq__` and `hash`, which also apply where it is nested in arrays, records, optionals and unions.

### Field invariants

A field may carry a refinement. It is proven wherever a value is made or the field is stored, and it is a fact wherever the field is read. A field may refer to an earlier sibling: `high:int64<high >=? low>`.

<!-- dewy-example: {"mode":"run","stdout":"42\n"} -->
```dewy
Ratio:type = [top:int64 bottom:int64<bottom >? 0>]
scale = (r:Ratio):>int64 => r.top // r.bottom
printl(scale(Ratio[84 2]))
```

<!-- dewy-example: {"mode":"reject","diagnostic":"refinement refuted"} -->
```dewy
Ratio:type = [top:int64 bottom:int64<bottom >? 0>]
let r = Ratio[1 0]
```

## Recursive Records

A record may hold optional values of its own type, directly or through other records and unions. Copies stay independent; there is no pointer syntax. A recursive type must admit a finite value: `next:Node?` can end with `none`, while `next:Node` cannot.

<!-- dewy-example: {"mode":"run","stdout":"42\n120\n"} -->
```dewy
Node:type = [value:int next:Node?]
sum = (node:Node?):>int => {
    let cur = node
    let total = 0
    loop cur is? Node { total += cur.value; cur = cur.next }
    return total
}
let original = Node[20 Node[22]]
let copy = original
if copy.next is? Node { copy.next.value = 100 }
printl(sum(original))
printl(sum(copy))
```

## Generic Records

Type parameters come before the fields: `Box:type = <T>[value:T]`. Constructors usually infer them. An integer type parameter is a constant carried in the type, usable in lengths and refinements.

<!-- dewy-example: {"mode":"run","stdout":"Dewy\n[value=[20 22]]\n64\n"} -->
```dewy
Box:type = <T>[value:T]
let b = Box<string>["Dewy"]
printl(b.value)
printl(Box([20 22]))
Ring:type = <T N>[
    first:T
    capacity = ():>int64 => N
]
printl(Ring<string 64>["a"].capacity)
```

## Methods

A record type or literal may declare methods as rows among its fields: `name = (params) => body`. Inside a method, a bare field or method name is that member of the object the method was called on; there is no `self`. A parameter or local of the same name hides the member.

<!-- dewy-example: {"mode":"run","stdout":"6 41\n1\n"} -->
```dewy
Span:type = [
    start:int
    stop:int = start
    width = () => stop - start
    grow = (by:int) => { stop += by }
    unit = ():>Span => Span(0 1)
]
counter = (start=0) => [
    value=start
    increment = () => (value += 1)
]
let s = Span(3 7)
s.grow(2)
let c = counter(40)
c.increment()
printl"{s.width} {c.value}"
printl(Span.unit.width)
```

- A method that assigns or grows a member changes its object, so it is called on a variable, field or element, not a temporary.
- A method that reaches no member is static and can be called on the type (`Span.unit`).
- A zero-argument method that gives a value is called without parentheses; one called for its effect keeps them (`c.increment()`).
- Methods are not stored in values, are not constructor fields, and do not print. They are not values yet (`@c.increment` is an error).
- Types with methods are declared at module level. A function written inside a method may read members but cannot change them yet.

<!-- dewy-example: {"mode":"reject","diagnostic":"not on a temporary value"} -->
```dewy
Span:type = [start:int stop:int grow = (by:int) => { stop += by }]
Span(1 2).grow(3)
```

A program function named like a library method, with the same kind of first argument, takes over `x.name` on such values in its module, with a warning.

## Operators and Indexing

Ordinary functions with protocol names give records operators: `__add__`, `__sub__`, `__mul__`, `__truediv__`, `__floordiv__`, `__mod__`, `__pow__`, `__unary_sub__`, `__eq__`, `__ne__`, `__lt__`, `__le__`, `__gt__`, `__ge__`, and `__index__` / `__setindex__` for `x[i]`. Comparisons return `bool`; `not=?` derives from `__eq__`, and `<=?`, `>?`, `>=?` from `__lt__`. Operators are found in either operand's defining module, so importing the type is enough. `__as__ = ():>string` sets how a value prints.

<!-- dewy-example: {"mode":"run","stdout":"[x=4 y=6]\ntrue\n"} -->
```dewy
Vec:type = [x:int y:int]
__add__ = (a:Vec b:Vec):>Vec => Vec[a.x + b.x a.y + b.y]
printl(Vec[1 2] + Vec[3 4])

Key:type = [id:uint64 label:string]
__eq__ = (a:Key b:Key):>bool => a.id =? b.id
hash = (key:Key):>uint64 => key.id.hash
printl(Key[1 "b"] in? set[Key[1 "a"]])
```

Lifecycle hooks (`$__drop__`, `$__copy__`, `$__move__`) for records that own resources are described in [Values, Copies, and Places](values.md).
