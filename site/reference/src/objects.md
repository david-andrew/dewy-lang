# Structural Objects

An object is a structural value containing named fields in source order. Field names, field types, and order participate in its structural type.

```dewy
let Pair:type = [left:int64 right:int64]
let pair:Pair = [left=20 right=22]
```

A type alias names the structure; it does not create a runtime class object or give the structure nominal identity.

## Structural Intersections

Intersecting object types combines their field requirements. Unique fields are retained; a field required by both sides receives the intersection of its two types.

<!-- dewy-example: design-only -->
```dewy
const Located:type = [line:int64 column:int64]
const Labeled:type = [label:string]
const LabeledLocation:type = Located & Labeled

# equivalent requirements:
# [line:int64 column:int64 label:string]
```

Matching fields must have the same mutability. Choosing the stricter-looking declaration would be unsound: code accepting the mutable contract is allowed to write the field, while the const contract prohibits that write. Incompatible field types normalize the containing intersection to `never`.

Intersection never creates nominal identity. A structurally stronger alias remains the same nominal kind as any nominal component it already contains.

## Fields and Mutation

Member access uses `.`. A mutable object binding permits assignment to its mutable fields. Ordinary object copies remain independent:

```dewy
let original = [name="draft" saved=false]
let copy = original
copy.saved = true             # original.saved remains false
```

Nested array and object fields recursively follow the same value rule.

## Constructors

Calling an object type constructs a value of it. The field list is the constructor's signature, read exactly like a function's: positional arguments fill fields in declaration order, keyword arguments name them, and a field declared with a default (`name:type = default`) may be left out — a default may refer to earlier fields by name.

<!-- dewy-example: compiler -->
```dewy
let Span:type = [start:int64 stop:int64 = start label:string = "span"]

let a = Span(1 9)                      # positional
let b = Span(stop=5 start=2 label="b") # keywords, in any order
let c = Span(7)                        # stop = start, label = "span"
```

The call is checked as the object literal `[start=1 stop=9 label="span"]` against the type: an unknown field, a field given twice, too many positional arguments, or a missing field without a default is an error. Types are values, so in a value context the name is the constructor and in a type context it is the type, with no separate class declaration.

Construction that needs more than filling fields is an ordinary function added to the type's **constructor overload set** with `&=`; a call dispatches over the field-wise signature and the overloads by the usual most-specific rule, so keyword-only parameters, validation, and error-value results live where functions already have them:

<!-- dewy-example: compiler -->
```dewy
let Range:type = [start:int64 stop:int64]
Range &= (text:string):>Range => Range(0 text.length)

let a = Range(1 9)          # field-wise
let b = Range("seven..")    # the overload
```

A constructor can also be an ordinary function returning an object:

```dewy
let make_pair = (left:int64 right:int64):>Pair =>
    [left=left right=right]
```

### Positional Literals

Where an object type is expected — an annotation, an element of `array<Point>`, a dictionary's value — an object literal may give its fields *positionally*, in declaration order, exactly as a constructor call would; a field left out takes its default:

<!-- dewy-example: compiler -->

```dewy
let Point:type = [x:int64 y:int64 = 0]
let Spec:type = [digits:set<string> case_insensitive:bool]

const specs:dict<string Spec> = [
    'b' -> [set'01' false]
    't' -> [set'012' false]
]

let main = ():>int64 => {
    let p:Point = [3]                        # [x=3 y=0]
    let corners:array<Point> = [[1 2] [5 6]]
    return p.x + corners[1].y + specs['t'].digits.length   # 3 + 6 + 3
}
```

Mixing named and positional items is not allowed; too many items, or a missing field without a default, is an error naming the field.

## Methods

An object type may declare methods: `name = (params) => body` rows among the fields. Inside a method, bare names of the type's fields and methods refer to the instance (`stop - start`, `width`); a method that assigns or grows a field takes its receiver as a place, so it must be called on a binding or a field, not on a temporary. Calls are `value.method(args)`, and a zero-argument method is called by `value.method` alone.

<!-- dewy-example: compiler -->
```dewy
let Span:type = [
    start:int64
    stop:int64 = start
    width = () => stop - start
    grow = (by:int64) => { stop += by }
    shifted = (by:int64):>Span => Span(start + by stop + by)
]

let main = ():>int64 => {
    let s = Span(3 7)
    s.grow(2)                       # 3..9
    return s.width + s.shifted(1).start   # 6 + 4
}
```

Methods are compiled as ordinary functions taking the instance first (`Span__width(self)`), so no function value is stored in the object; they are not values yet (`s.grow` without a call is an error). Methods and constructor overloads are declared on module-level types only.

A structural or hybrid type can also contextually construct an object literal:

<!-- dewy-example: design-only -->
```dewy
const ContextError:type =
    (type of error) & [context:string code:int64]

let problem = ContextError[
    context='request body'
    code=400
]
```

The fields are checked against the structural portion, and the resulting value carries the type's nominal ancestry. A structurally strengthened alias requires all fields from the combined intersection.

## Function Fields

A function field may use sibling fields from the object literal's scope:

<!-- dewy-example: compiler -->
```dewy
let counter = (start:int64=0) => [
    value = start
    increment = () => (value += 1)
]
```

Accessing a zero-argument function field calls it when that call is valid. Explicit `()` remains available.

Extracting a method as a stored naked function, escaping captures, and full function-handle identity depend on the provisional function-handle and closure design.

## Places Through Fields

`@object.field` selects the place occupied by the field at the end of the complete route. Although the parser groups the prefix first, the language does not expose an intermediate reference value for `object`. `@(object.field)` selects the same place. There is no separate `object.@field` syntax.

See [Values, Copies, and Places](values.md) for aliasing and overlap rules.

## Recursive Objects

An object type may contain itself through a union-typed field: `let Node:type = [value:int64 next:Node|none]`. The self-referencing member is held behind a handle, copies are deep, and `is?` narrows the field route (`node.next is? Node`) so the field can be read and assigned as a `Node`. See [Recursive Types](types-and-conversions.md#recursive-types).
