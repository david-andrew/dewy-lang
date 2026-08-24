# Containers

Square brackets collect values. Whitespace separates elements, so ordinary Dewy containers do not require commas.

## Arrays

An array is an ordered homogeneous value:

```dewy
let names = ["Ada" "Grace" "Linus"]
printl(names[1])
```

Arrays are indexed from zero. An annotation can state the element type and a known length:

```dewy
let names:array<string> = ["Ada" "Grace"]
let triple:array<int64 length=3> = [10 20 30]

triple.length
triple[end]
triple[0..1]
```

Array values copy by meaning. If a function should deliberately update an existing array or element, pass its [place](values-and-places.md):

```dewy
sort(@names)
set(@triple[1])
```

## Building Arrays with Loops

A loop can express values for `[]` to collect:

```dewy
let squares = [
    loop number in 1..10
        number^2
]
```

This is the ordinary loop expression, not a separate comprehension grammar.

## Shapes and Multidimensional Data

Arrays are also the foundation for vectors, matrices, and tensors. Dewy's shape and literal syntax must support contiguous multidimensional representations without preventing ordinary arrays of arrays.

> **Provisional design:** Exact multidimensional shape annotations, dimension separators, broadcasting, and axis selection are still being unified. The one-dimensional `array<T length=N>` form and nested array values are settled.

## Dictionaries and Bidictionaries

A dictionary collects key/value pairs written with `->`:

```dewy
let ratings = [
    "star trek" -> 89
    "star wars" -> 73
]
```

`<->` describes a bidirectional mapping whose values can be looked up from either side.

## Sets

The intended set literal makes its unordered meaning explicit:

```dewy
let permissions = set["read" "write"]
"read" in? permissions
```

> **Provisional design:** Dictionary, bidictionary, and set literals have a selected overall direction, but their complete type, ordering, collision, and mutation rules remain under design.

Objects also use square brackets, but named fields with `=` distinguish them from positional containers. Continue with [Structural Objects](object-types.md), or consult the exact [array and container reference](../../reference/arrays-and-containers.html).
