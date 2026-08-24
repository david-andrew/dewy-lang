# Arrays and Containers

## Arrays

An array is an ordered homogeneous value. Array indexing is zero-based.

```dewy
let names:array<string> = ["Ada" "Grace"]
let triple:array<int64 length=3> = [10 20 30]
```

`array<T>` specifies the element type. `array<T length=N>` additionally refines the length. Array values follow Dewy's value semantics: binding, assignment, argument passing, and return produce an independent value unless the program explicitly passes a place.

```dewy
let original = [1 2 3]
let copy = original
copy[0] = 9                  # original remains [1 2 3]
```

The compiler may implement an unobservable copy as a move, borrowed read, shared immutable backing storage, or another equivalent representation.

`.length` reports the length. Integer indexes select elements, and range indexes select slices. The compiler must prove an ordinary index valid; operations that perform explicit runtime validation are separate checked interfaces.

## Shapes and Dimensions

Arrays are also the intended foundation for vectors, matrices, and tensors. Shape belongs in array type information rather than requiring unrelated matrix classes.

The exact general multidimensional literal and type syntax remains provisional. In particular, nested `array<array<T>>` must remain a valid array-of-arrays construction and must not prevent a contiguous representation such as an array whose `length` or `shape` is a sequence of dimensions.

## Dictionaries and Bidictionaries

A dictionary literal uses `->` pairs; a bidictionary uses `<->` pairs and supports lookup in both directions:

```dewy
let scores = ["Ada" -> 10 "Grace" -> 12]
let names = [1 <-> "one" 2 <-> "two"]
```

The broad literal distinction is settled, while complete type, collision, mutation, ordering, and representation rules remain provisional.

## Sets

The intended set form is `set[...]`:

```dewy
let permissions = set["read" "write"]
```

Membership uses `in?`. Complete set construction, equality, and ordering rules remain provisional.

## Literal Classification

At the top level of `[]`:

- positional values form an array;
- named `=` fields form an object;
- `->` pairs form a dictionary;
- `<->` pairs form a bidictionary.

Mixed top-level forms must satisfy the rules of the selected container rather than silently switching interpretation element by element.
