# Arrays and Containers

## Arrays

An array is an ordered homogeneous value. Array indexing is zero-based.

```dewy
let names:array<string> = ["Ada" "Grace"]
let triple:array<int64 length=3> = [10 20 30]
```

`array<T>` specifies the element type. Growable arrays hold word scalars, strings, and objects; an object element is stored as an independent copy, so the array never aliases the value pushed into it, and a popped element remains valid. Inside an index, `end` is the last index (`xs.length - 1`) and composes freely: `xs[end]`, `xs[end - 1]`, `xs[2..end]`, proven from the same facts. Iterating an array of objects (`loop s in spans`) binds the loop variable as a read-only borrow of each element — assigning it, its fields, growing its arrays, or passing it as a place is rejected; copy it (`let mine:Span = s`) to change it. `array<T length=N>` additionally refines the length. Array values follow Dewy's value semantics: binding, assignment, argument passing, and return produce an independent value unless the program explicitly passes a place.

```dewy
let original = [1 2 3]
let copy = original
copy[0] = 9                  # original remains [1 2 3]
```

The compiler may implement an unobservable copy as a move, borrowed read, shared immutable backing storage, or another equivalent representation.

`.length` reports the length. Integer indexes select elements, and range indexes select slices. The compiler must prove an ordinary index valid; operations that perform explicit runtime validation are separate checked interfaces.

### Growth Methods

An array whose type has no exact length (`array<T>`) may change length through methods on the value. `xs.push(v)` appends; `xs.pop` removes and yields the last element and `xs.pop(idx)` the element at `idx`, shifting later elements down; `xs.insert(v idx)` inserts before `idx` (`idx` may equal the length); `xs.truncate(n)` keeps the first `n` elements; `xs.clear` empties; `xs.reserve(n)` requests capacity; `xs.sort` orders integer elements ascending in place.

Each partial operation carries a proof obligation: `pop` requires a proven positive length, and `pop(idx)`/`insert(v idx)` require `0 <= idx < length` (`<=` for `insert`). Proofs come from literal lengths (an exact length is retained as a fact until a length-changing operation steps it), from `push`/`pop` stepping known lengths, and from guards such as `xs.length >? 0` or `idx <? xs.length`. A binding declared with an exact length (`array<T length=N>`) cannot change length.

Container mutation is reached only through the container value; free functions are reserved for genuinely global operations.

A loop inside `[]` is loop capture: the collector receives each non-`void` value the loop expresses and produces an array.

A trailing `...` after a sequence inserts its elements into a surrounding array literal. Fixed elements and spreads may mix: `[heads... tails...]`, `[0 xs... 1]`.

## Shapes and Dimensions

Arrays are also the intended foundation for vectors, matrices, and tensors. Shape belongs in array type information rather than requiring unrelated matrix classes.

The exact general multidimensional literal and type syntax remains provisional. In particular, nested `array<array<T>>` must remain a valid array-of-arrays construction and must not prevent a contiguous representation such as an array whose `length` or `shape` is a sequence of dimensions.

## Dictionaries and Bidictionaries

A dictionary literal uses `->` pairs; a bidictionary uses `<->` pairs and supports lookup in both directions:

<!-- dewy-example: design-only -->

```dewy
let scores = ["Ada" -> 10 "Grace" -> 12]
let names = [1 <-> "one" 2 <-> "two"]
```

Dictionaries retain insertion order, and iteration yields key/value pairs in that order:

<!-- dewy-example: compiler -->

```dewy
let scores = ["Ada" -> 10 "Grace" -> 12]

loop [name score] in scores
    printl"{name}: {score}"
```

`dict<K V>` names a dictionary type; a dictionary literal in a `dict<K V>` context adopts those entry types, and an empty literal requires such a context. Dictionaries are values with the ordinary value semantics: they are passed, returned, stored, and compared by value, and copies are independent.

### Lookup

`d[key]` is valid only when the key is *proven present* and then has type `V`. A key is proven when it is a constant entry of the literal that initialized the dictionary, was stored by `d[key] = value`, is the key bound by `loop [key value] in d`, or was tested by a guard `if key in? d`. Facts are path-sensitive (a key proven on every branch stays proven after the branches join) and are invalidated when the dictionary or the key binding is reassigned. A guard's search result is reused by the guarded lookup, so a proven lookup performs no second search. An unproven `d[key]` is a compile error.

`d.get(key)` is the lookup that may miss, with type `V | undefined`. `d.get(key default)` yields `default` when the key is absent and has type `V`.

### Mutation

`d[key] = value` replaces the value of an existing key in place or appends a new entry. `d.pop(key)` removes a proven key and yields its value; `d.pop(key default=v)` removes the key if present and yields its value, else `v`, without a proof. `d.clear` removes every entry. `d.length` is the number of entries.

A dictionary must not be mutated by a loop that iterates it; stores, `pop`, and `clear` inside such a loop are compile errors.

### Views and Combination

`d.keys` is a fresh `set<K>` of the keys and `d.values` a fresh `array<V>` of the values, both in insertion order. `d1 | d2` (equivalently `d1 or d2`) is a new dictionary containing every entry of `d1` followed by the entries of `d2` whose keys are new; for shared keys the right value replaces the left value at the left position. Other operators do not apply to dictionaries; combine key sets instead.

### Representation

A dictionary is a compact hash table: dense entries in insertion order with their stored hashes, plus a sparse probe table using open addressing with CPython's perturbation sequence. Removal leaves a tombstone, iteration and growth compact entries lazily, and none of this is observable beyond the order and complexity guarantees. Keys and values are currently word-sized scalars or strings.

Bidirectional dictionaries and container equality remain provisional.

## Sets

`set[...]` constructs a set; `set<T>` names its type. Members are distinct, and a set remembers first-seen order for iteration and `s.values` (a fresh `array<T>`).

<!-- dewy-example: compiler -->

```dewy
let permissions = set["read" "write"]
permissions.add("execute")
let present = "read" in? permissions
let taken = permissions.pop("read")
```

`s.add(x)` inserts a member. `x in? s` tests membership. `s.pop(x)` removes a proven member and yields it; `s.pop(x default=v)` removes `x` if present and yields it, else `v` (`default=undefined` makes the result `T | undefined`). `s.clear` empties the set; `s.length` counts members. Sets are not indexable and have no `keys`.

Set operators produce new sets: `|`/`or` union, `&`/`and` intersection, `-` difference, `xor` symmetric difference. Operands must have the same element type. Literal members must currently be constants (duplicates collapse at compile time), and a set must not be mutated by a loop that iterates it.

Set equality, ordering, and compound operator forms remain provisional.

## Literal Classification

At the top level of `[]`:

- positional values form an array;
- named `=` fields form an object;
- `->` pairs form a dictionary;
- `<->` pairs form a bidictionary.

`set[...]` constructs a set from positional values. Mixed top-level forms must satisfy the rules of the selected container rather than silently switching interpretation element by element.
