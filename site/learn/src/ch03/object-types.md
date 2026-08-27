# Structural Objects

An object is a value with named fields. It does not require a separate class declaration:

```dewy
let account = [
    name = "Ada"
    active = true
]

account.name
```

Field names, field types, and their order form the object's structural type.

## Naming an Object Shape

A type alias gives a structural shape a reusable name:

```dewy
let Pair:type = [left:int64 right:int64]
let origin:Pair = [left=0 right=0]
```

The alias does not create a runtime class object or nominal identity. Another value with the same required structure satisfies the same structural contract.

## Recursive Shapes

A named shape can refer to itself, as long as the recursion goes through a union — usually `| undefined`, so that a chain can end:

<!-- dewy-example: compiler -->

```dewy
let Node:type = [value:int64 next:Node|undefined]

let sum = (list:Node|undefined):>int64 => {
    let total:int64 = 0
    let cur:Node|undefined = list
    loop cur is? Node {
        total += cur.value
        cur = cur.next
    }
    return total
}

let main = ():>int64 => {
    let list:Node|undefined = undefined
    let i:int64 = 1
    loop i <=? 4 {
        list = [value=i next=list]
        i += 1
    }
    return sum(list)      # 10
}
```

`cur is? Node` narrows `cur` for the loop body, and `cur.next is? Node` would narrow the field itself. A field typed plainly `Node` is rejected: without a union there is no last node. Recursive values are still values — assigning a chain to another binding copies the whole chain.

## Combining Object Requirements

`&` combines structural types without creating nominal identity:

<!-- dewy-example: design-only -->
```dewy
const Located:type = [line:int64 column:int64]
const Labeled:type = [label:string]
const LabeledLocation:type = Located & Labeled
```

Fields present on only one side are retained. When both sides contain the same field, its required type is the intersection of the two field types. If that becomes `never`, the complete object type is impossible. The two declarations must also agree about whether the field is mutable; silently choosing one would break the other contract.

## Constructing Objects

A named object type is its own constructor: call it with the fields in order, or by name, and leave out any field the type gives a default for.

<!-- dewy-example: compiler -->
```dewy
let Span:type = [start:int64 stop:int64 = start label:string = "span"]

let a = Span(1 9)
let b = Span(stop=5 start=2 label="b")
let c = Span(7)                        # stop defaults to start
printl"{a.stop - a.start} {b.label} {c.stop}"   # 8 b 7
```

The field list is the signature — the same rules as a function's parameters, with defaults allowed to use earlier fields — so there is no separate class declaration to write. A constructor can still be an ordinary function returning an object when construction needs more than filling fields:

```dewy
let make_pair = (left:int64 right:int64):>Pair =>
    [left=left right=right]

let pair = make_pair(20 22)
```

A type with a structural body can construct that body directly:

```dewy
let unit_x = Pair[left=1 right=0]
```

The object literal is checked against the named structure. When a type also carries nominal ancestry, the constructed value retains that identity; [Defining Exceptions](errors-as-values.md#defining-exceptions) shows such a hybrid type.

## Methods

A named type can carry behavior: method rows next to the fields, whose bodies use the fields by name. A method that changes fields needs a binding to work on; one that only reads can be called on anything.

<!-- dewy-example: compiler -->
```dewy
let Span:type = [
    start:int64
    stop:int64 = start
    width = () => stop - start
    grow = (by:int64) => { stop += by }
]

let s = Span(3 7)
s.grow(2)
printl"{s.start}..{s.stop} is {s.width} wide"   # 3..9 is 6 wide
```

When construction itself needs logic, add a constructor overload with `&=` — an ordinary function returning the type — and `Span(…)` picks the field-wise constructor or the overload by the arguments:

```dewy
Span &= (text:string):>Span => Span(0 text.length)
let whole = Span("seven..")     # 0..7
```

## Behavior Inside Objects

Function fields can use sibling fields directly:

<!-- dewy-example: compiler -->
```dewy
let counter = (start:int64=0) => [
    value = start
    increment = () => (value += 1)
]

let count = counter(40)
count.increment
count.increment
printl"count is {count.value}"
```

Accessing a zero-argument function field calls it when that call is valid. Explicit `count.increment()` is equivalent.

## Objects Are Values

Ordinary copies are independent:

```dewy
let Document:type = [name:string saved:bool]
let original:Document = [name="draft" saved=false]
let copy = original
copy.saved = true

# original.saved is still false
```

To update the caller's object deliberately, accept and pass a place:

```dewy
let save = (@document:Document):>void => (document.saved = true)
save(@original)
```

Fields and array elements can be selected directly, such as `set(@original.saved)`.

## Operators and Conversions

Objects participate in operators and conversions through typed overloads. The precise overloadable conversion protocol is preferred over a second class-specific “dunder” model:

```dewy
let __add__ = __add__ & (
    (a:Pair b:Pair):>Pair =>
        [left=a.left + b.left right=a.right + b.right]
)
```

> **Provisional design:** Extracted methods, escaping captured fields, function-handle identity, and the final convention for attaching overloads to structural types are part of the function-handle and generic-object design.

The Reference defines [structural object behavior](../../reference/objects.html) and [value semantics](../../reference/values.html).
