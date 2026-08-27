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
fill(@names)
set(@triple[1])
```

## Growing Arrays

An array declared without an exact length can change length through methods on the value itself:

<!-- dewy-example: compiler -->

```dewy
let xs:array<int64> = [10 20]
xs.push(30)              # [10 20 30]
xs.insert(15 1)          # [10 15 20 30]
let last = xs.pop        # 30
let first = xs.pop(0)    # 10
xs.truncate(1)           # [15]
xs.sort
xs.clear
```

`push`, `pop`, `insert`, `truncate`, `clear`, `reserve`, and `sort` are the growth methods; `pop` yields the removed element. Container operations always live on the container: there is no free `push(xs x)`.

Operations that could fail must be proven safe at compile time. `xs.pop` needs a proven non-empty array, `xs.pop(i)` and `xs.insert(v i)` need a proven index, and an ordinary `xs[i]` needs a proven bound. Literal lengths, `push`/`pop` stepping those lengths, and guards such as `if i <? xs.length` all supply the proof; see [Refinements](refinements.md).

## Loop Capture

A loop can express values for `[]` to collect:

```dewy
let squares = [
    loop number in 1..10
        number^2
]
```

This is the ordinary loop expression, not a separate comprehension grammar.

## Spreading

A trailing `...` inserts the contents of an existing container into a surrounding literal. Arrays (and sets) spread their elements into an array literal, mixed freely with written elements; objects spread their fields into an object literal, where a later entry with the same name wins — the natural "copy with changes" form:

<!-- dewy-example: compiler -->

```dewy
let main = ():>int64 => {
    let heads = [1 2]
    let tails = [8 9]
    let both = [heads... tails...]         # [1 2 8 9]
    let padded = [0 both... 10]            # [0 1 2 8 9 10]

    let point = [x=1 y=2]
    let moved = [point... x=5]             # [x=5 y=2]
    let tagged = [point... label="origin"] # [x=1 y=2 label="origin"]
    return padded.length + moved.x + tagged.y    # 13
}
```

The result's length is known exactly when every spread operand's length is; otherwise it is a runtime-length array. Spreading into dictionary and set literals is not implemented yet.

## Shapes and Multidimensional Data

Arrays are also the foundation for vectors, matrices, and tensors. Dewy's shape and literal syntax must support contiguous multidimensional representations without preventing ordinary arrays of arrays.

> **Provisional design:** Exact multidimensional shape annotations, dimension separators, broadcasting, and axis selection are still being unified. The one-dimensional `array<T length=N>` form and nested array values are settled. Multidimensional arrays will likely look like `array<T length=[l1 l2 ... lN]>`, and make use of `;` and newlines for tracking new dimensions in array literals (tbd how it interplays with loop capture)

## Dictionaries and Bidictionaries

A dictionary collects key/value pairs written with `->`:

<!-- dewy-example: compiler -->

```dewy
let ratings = [
    "star trek" -> 89
    "star wars" -> 73
]
```

Dictionaries retain insertion order. Iteration yields key/value pairs in that order:

<!-- dewy-example: compiler -->

```dewy
let ratings = [
    "star trek" -> 89
    "star wars" -> 73
]

loop [title score] in ratings
    printl"{title}: {score}"
```

### Looking Up Keys

Indexing a dictionary is only allowed when the compiler can prove the key is present. A key is proven when it came from the literal, was just stored, is being iterated, or was tested with `in?`:

<!-- dewy-example: compiler -->

```dewy
let ratings = ["star trek" -> 89 "star wars" -> 73]
let trek = ratings["star trek"]        # from the literal

ratings["dune"] = 91
let dune = ratings["dune"]              # just stored

let title = "alien"
if title in? ratings
    printl"{ratings[title]}"           # proven by the guard; the guard's search is reused
```

This is Dewy's general rule for operations that raise exceptions in Python: they must be proven safe or they do not compile. When a key may be missing, say so with `get`:

<!-- dewy-example: compiler -->

```dewy
let ratings = ["star trek" -> 89 "star wars" -> 73]
let maybe = ratings.get("alien")        # int64 | undefined
let score = ratings.get("alien" 0)      # 0 when absent
```

### Changing a Dictionary

`d[key] = value` stores a value, replacing the value of an existing key in place or appending a new entry at the end. `pop` removes a proven key and yields its value; with the name-only `default` argument the key need not be proven:

<!-- dewy-example: compiler -->

```dewy
let ratings = ["star trek" -> 89 "dune" -> 91]
let removed = ratings.pop("dune")                   # proven present
let gone = ratings.pop("alien" default=(-1))        # -1 when absent
ratings.clear
```

`d.length` counts entries, `d.keys` is a set of the keys, `d.values` an array of the values in insertion order, and `d1 | d2` (or `d1 or d2`) merges two dictionaries the way Python does: shared keys take the right value while keeping the left position, and new keys append. A dictionary must not change while a loop iterates it; the compiler rejects stores, `pop`, and `clear` inside such a loop.

Dictionaries are ordinary values: they can be passed to functions, returned, stored in objects, and written as literals in any expression. A callee that stores into a dictionary parameter works on its own copy unless the parameter is a place.

`<->` describes a bidirectional mapping whose values can be looked up from either side.

## Sets

A set holds each member once and remembers first-seen order:

<!-- dewy-example: compiler -->

```dewy
let permissions = set["read" "write" "read"]     # two members
permissions.add("execute")
"read" in? permissions
permissions.length

let taken = permissions.pop("read")               # proven: it came from the literal
permissions.pop("nope" default=undefined);        # absent: nothing happens
```

`pop` follows the dictionary rule: a proven member, or a `default` when it may be missing. `s.values` is an array of the members, and the set operators produce new sets:

<!-- dewy-example: compiler -->

```dewy
let evens = set[0 2 4 6]
let small = set[0 1 2 3]

let both = evens & small        # intersection: 0 2   (`and` also works)
let either = evens | small      # union: 0 2 4 6 1 3  (`or` also works)
let only = evens - small        # difference: 4 6
let odd_one_out = evens xor small
```

Because `d.keys` is a set, the same operators compare the keys of two dictionaries.

> **Provisional design:** Bidirectional dictionaries, equality and ordering of containers, compound operator forms such as `|=`, and keys beyond words and strings remain under design.

Objects also use square brackets, but named fields with `=` distinguish them from positional containers. Continue with [Structural Objects](object-types.md), or consult the exact [array and container reference](../../reference/arrays-and-containers.html).
