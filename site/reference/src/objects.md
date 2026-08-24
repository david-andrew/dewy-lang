# Structural Objects

An object is a structural value containing named fields in source order. Field names, field types, and order participate in its structural type.

```dewy
let Pair:type = [left:int64 right:int64]
let pair:Pair = [left=20 right=22]
```

A type alias names the structure; it does not create a runtime class object or give the structure nominal identity.

## Fields and Mutation

Member access uses `.`. A mutable object binding permits assignment to its mutable fields. Ordinary object copies remain independent:

```dewy
let original = [name="draft" saved=false]
let copy = original
copy.saved = true             # original.saved remains false
```

Nested array and object fields recursively follow the same value rule.

## Constructors

A constructor is an ordinary function returning an object:

```dewy
let make_pair = (left:int64 right:int64):>Pair =>
    [left=left right=right]
```

Dewy does not require a separate class declaration syntax.

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
