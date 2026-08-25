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

## Combining Object Requirements

`&` combines structural types without creating nominal identity:

<!-- dewy-example: design-only -->
```dewy
const Located:type = [line:int64 column:int64]
const Labeled:type = [label:string]
const LabeledLocation:type = Located & Labeled
```

Fields present on only one side are retained. When both sides contain the same field, its required type is the intersection of the two field types. If that becomes `never`, the complete object type is impossible. The two declarations must also agree about whether the field is mutable; silently choosing one would break the other contract.

## Constructors Are Functions

A constructor is an ordinary function returning an object:

```dewy
let make_pair = (left:int64 right:int64):>Pair =>
    [left=left right=right]

let pair = make_pair(20 22)
```

Default parameters, overloads, and generics apply to constructors exactly as they apply to other functions.

A type with a structural body can construct that body directly:

```dewy
let unit_x = Pair[left=1 right=0]
```

The object literal is checked against the named structure. When a type also carries nominal ancestry, the constructed value retains that identity; [Defining Exceptions](errors-as-values.md#defining-exceptions) shows such a hybrid type.

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
