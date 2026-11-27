# Arrays and Containers

> [Generated coverage](/status/#ref-arrays-and-containers) names related acceptance programs. Every example on this page compiles with the current compiler unless it is marked **Design only**.

Arrays, tuples, dictionaries and sets are values. Binding, assigning, passing and returning one gives an independent value; the compiler shares storage until a write and moves values at their last use, so most copies cost nothing. Pass `@xs` to let a function change the caller's array (see [Values, Copies, and Places](values.md)).

## Arrays

`array<T>` is a growable, zero-indexed sequence of `T`. `array<T length=N>` has a fixed positive length known when compiling and stores its elements inline.

<!-- dewy-example: {"mode":"run","stdout":"[\"Ada\" \"Grace\"]\n[\"Bea\" \"Grace\"]\n30\n"} -->
```dewy
let names:array<string> = ["Ada" "Grace"]
let triple:array<int64 length=3> = [10 20 30]
let copy = names
copy[0] = "Bea"
printl(names)
printl(copy)
printl(triple[2])
```

`[]` takes its type from context, as `1` does: an array, dictionary, set or record with defaults. With no context it is an error asking for the type:

<!-- dewy-example: {"mode":"reject","diagnostic":"cannot infer the type of 'x'"} -->
```dewy
let x = []
```

An array literal takes its element type from the expected type (`let bytes:array<uint8> = [0 255]`), and otherwise from its elements. `fill(value count)` makes `count` copies of a value.

### Methods

| Method | Effect |
|---|---|
| `push(v)`, `extend(ys)`, `insert(v i)` | add elements; `insert` places `v` before `i` |
| `pop()`, `pop(i)` | remove and return the last element, or the one at `i` |
| `truncate(n)`, `clear()` | keep the first `n`, or none |
| `sort()`, `reverse()` | reorder in place |
| `sorted`, `reversed` | a new array |
| `get(i)` | the element, or `none` out of bounds |
| `index_of(x)` | the first position of `x`, or `Missing` |
| `count(x)`, `count(f)` | elements equal to `x`, or accepted by `f` |
| `map(f)`, `filter(f)`, `any(f)`, `all(f)` | apply a predicate or function |
| `min_by(key)`, `max_by(key)` | first element with the least or greatest key |
| `is_empty`, `length` | inspection |
| `join(sep)` | for strings: one string |

`sort` and `sorted` take `key=` and `reverse=true`; both are stable. `sort_with(less)` and `sorted_with(less)` take a comparison function.

Each partial operation is an obligation on the caller: `pop()` needs a nonempty array, `pop(i)` and `insert(v i)` need `i` in bounds, and `min_by`, `max_by`, `first` and `last` need `length >? 0`. Literal lengths, pushes, pops and guards supply the facts:

<!-- dewy-example: {"mode":"reject","diagnostic":"pop() of an empty array"} -->
```dewy
let xs:array<int64> = []
printl(xs.pop())
```

<!-- dewy-example: {"mode":"run","stdout":"[\"Ada\" \"Bea\" \"Cal\"]\nCal\n1\nMissing\n-1\n[10 20 30]\n[3 2]\ntrue\n"} -->
```dewy
let names = ["Ada" "Bea"]
names.push("Cal")
printl(names)
printl(names.pop())
let xs = [3 1 2]
printl(xs.index_of(1))
printl(xs.index_of(9))
printl(xs.index_of(9) ?? -1)
printl(xs.sorted.map((x) => x * 10))
printl(xs.filter((x) => x >? 1))
printl(xs.any((x) => x >? 2))
```

There is no `zip` or `enumerate`: a combined loop walks sources in step, `loop i in 0.. and x in xs` (see [Combined headers](ranges-and-iteration.md#combined-headers)).

### Combining

`+` does not join arrays; on arrays it is reserved for elementwise math, and `.+` adds element by element. Spread arrays and sets into a literal, `[head... item tail...]`, or append in place with `extend`:

<!-- dewy-example: {"mode":"run","stdout":"[1 2 3 4 1 2 3]\n[11 22 33]\n"} -->
```dewy
let xs = [1 2 3]
printl([xs... 4 xs...])
printl(xs .+ [10 20 30])
```

<!-- dewy-example: {"mode":"reject","diagnostic":"`+` does not join arrays"} -->
```dewy
let a = [1 2]
let b = [3]
printl(a + b)
```

### Equality

`xs =? ys` compares by value: the same length and pairwise equal elements, recursively. Storage is never compared. Floating-point elements follow float equality (`NaN` is unequal to itself).

## Indexing and Slices

An index must be proven in bounds before the program runs; there is no hidden check (see [Making Code Prove](refinements-and-effects.md#making-code-prove)). `xs.get(i)` takes an out-of-bounds index as a value instead.

| Form | Selects |
|---|---|
| `xs[i]` | one element |
| `xs[end]`, `xs[end-1]` | counted from the last index, `xs.length - 1` |
| `xs[a..b)`, `xs[a..b]` | a contiguous slice, end excluded or included |
| `xs[a..]`, `xs[..b)` | to the end, from the start |
| `xs[0, 2..]` | a stepped selection |
| `xs[$clamp a..b)` | a slice with bounds clamped to the array, as in Python |
| `xs[indexes]`, `xs[mask]` | elements at an index array, or where a `bool` array is true |

The receiver and its bounds are evaluated once. A slice is a new array. Selections may also be assigned: a scalar fills every selected element, and an array supplies exactly one replacement per element.

<!-- dewy-example: {"mode":"run","stdout":"[20 30]\n[20 30 40]\n50\n[10 20]\n[20 30 40 50]\n[]\n[50 30 10]\n[0 20 0 40 0]\n"} -->
```dewy
let xs = [10 20 30 40 50]
printl(xs[1..3))
printl(xs[1..3])
printl(xs[end])
printl(xs[..2))
printl(xs[$clamp 1..10))
printl(xs[$clamp 7..9))
printl(xs[end, end-2..0])
let ys = [10 20 30 40 50]
ys[0, 2..] = 0
printl(ys)
```

Inside nested brackets, each `end` counts its own receiver. `new` inside brackets inserts an axis of length one, as NumPy's `newaxis` does.

## Tuples and Fixed Arrays

`[int64 string]` is a fixed-length array with a type per position: Dewy's tuple. A constant index reads that position's type; any other index gives the union of the element types and is proven in bounds like an array index.

Unpacking with `let [a b] = value` works on arrays, tuples and records. Fixed lengths are checked while compiling; a growable array's length is an obligation. `_` discards an element and `...rest` takes the remainder. `[a b] = [b a]` swaps.

<!-- dewy-example: {"mode":"run","stdout":"8\n7 seven\n[2 3]\n2 1\n1\n1\n"} -->
```dewy
let entry:[int64 string] = [7 "seven"]
printl(entry[0] + 1)
let [n name] = entry
printl"{n} {name}"
let [first ...mid last] = [1 2 3 4]
printl(mid)
let a = 1
let b = 2
[a b] = [b a]
printl"{a} {b}"
let moves:array<[int64 int64]> = [[1 0] [0 1]]
loop [dx dy] in moves { printl(dx + dy) }
```

Assigning a growable array to a fixed-length one requires its length to be proven.

## Dictionaries

`dict<K V>` maps keys to values. The literal is `[k -> v ...]`. Dictionaries keep insertion order, and iteration yields keys and values in that order.

### Lookup

`d[key]` needs the key proven present: by a guard (`if key in? d`), an earlier store into `d[key]`, a key of the literal that made the dictionary, or a key taken from the dictionary itself. An unproven lookup is an error. `d.get(key)` takes a missing key as a value: it gives `V?`, usually followed by `??`.

<!-- dewy-example: {"mode":"reject","diagnostic":"cannot prove the key is in the dictionary"} -->
```dewy
let d = ["a" -> 1]
let k = "b"
printl(d[k])
```

<!-- dewy-example: {"mode":"run","stdout":"Ada: 10\nGrace: 12\n10\n0\nset[\"Ada\" \"Grace\" \"Bea\"]\n[10 12 7]\n10\n[\"Grace\" -> 12 \"Bea\" -> 7]\n"} -->
```dewy
let scores = ["Ada" -> 10 "Grace" -> 12]
loop [name score] in scores { printl"{name}: {score}" }
printl(scores["Ada"])
printl(scores.get("Bea") ?? 0)
scores["Bea"] = 7
printl(scores.keys)
printl(scores.values)
printl(scores.pop("Ada"))
printl(scores)
```

### Updates

| Operation | Meaning |
|---|---|
| `d[k] = v` | replace the value, or add the entry at the end |
| `d[k] += v`, `d[k].push(x)` | change an existing entry; the key must be proven present |
| `d.pop(k)` | remove a present key and return its value |
| `d.pop(k default=none)` | remove the key if present; the default otherwise |
| `d.remove(k)` | remove the key if present; `bool` whether it was |
| `d.insert_if_absent(k v)` | add only when missing; `bool` whether it was added |
| `d.keys`, `d.values` | a new set of keys, a new array of values, in insertion order |
| `d1 \| d2` | every entry of `d1`, plus `d2`'s new keys; a shared key takes `d2`'s value |

Counting and grouping put the key in first, so the update is proven:

<!-- dewy-example: {"mode":"run","stdout":"[\"a\" -> 2 \"b\" -> 1]\ntrue\nfalse\n[\"x\" -> 1 \"y\" -> 20 \"z\" -> 3]\n"} -->
```dewy
let counts:dict<string int64> = []
loop w in ["a" "b" "a"] {
    if w not in? counts counts[w] = 0
    counts[w] += 1
}
printl(counts)
let visited:dict<int64 int64> = []
printl(visited.insert_if_absent(7 1))
printl(visited.insert_if_absent(7 2))
printl(["x" -> 1 "y" -> 2] | ["y" -> 20 "z" -> 3])
```

A loop over a dictionary iterates a snapshot of its entries, so changing the dictionary in the body does not change the iteration. Dictionaries compare and hash by their entries, ignoring order. A float key is an obligation: it must be proven not `NaN`.

### Total dictionaries

`totaldict<K V>` has an entry for every value of a finite key type, a union of literals. Its literal must list every key, and the error names any missing one. Every lookup is proven, and it has no `pop` or `clear`:

<!-- dewy-example: {"mode":"run","stdout":"16\n"} -->
```dewy
BasePrefix:type = '0b' | '0o' | '0x'
const RADIX:totaldict<BasePrefix int64> = ['0b' -> 2 '0o' -> 8 '0x' -> 16]
radix_of = (base:BasePrefix):>int64 => RADIX[base]
printl(radix_of('0x'))
```

## Sets

`set[...]` makes a set and `set<T>` names its type. Members are distinct and keep first-insertion order. `set(values)` makes the set of an array's elements and `set"0123"` the set of a string's graphemes.

| Operation | Meaning |
|---|---|
| `s.push(x)` | add a member; an existing member keeps its position |
| `x in? s`, `s.has(x)` | membership |
| `s.remove(x)` | remove if present; `bool` whether it was |
| `s.pop(x)`, `s.pop()` | remove and return a present member, or any member of a nonempty set |
| `a \| b`, `a & b`, `a - b`, `a xor b` | union, intersection, difference, symmetric difference |
| `s.values`, `s.sorted`, `[s...]` | the members as an array |

A set has no positions: collect it into an array to index or sort it.

<!-- dewy-example: {"mode":"run","stdout":"set[\"visible\" \"moving\" \"selected\"]\ntrue\nset[\"visible\" \"selected\"]\nset[\"0\" \"1\" \"2\" \"3\"]\n"} -->
```dewy
let tags = set["visible" "moving" "visible"]
tags.push("selected")
printl(tags)
printl("moving" in? tags)
printl(tags - set["moving"])
printl(set"0123")
```

## Loop Capture

A collector whose item is a loop gathers every value the loop body expresses, in order: none on a path that expresses nothing (an `if` without `else` filters), several when the body expresses several. `break`, `continue`, assignments and `void` calls express nothing. Nested loops flatten into the one collection. `set[loop ...]` collects a set, and `key -> value` values collect a dictionary (a later duplicate key replaces the value).

<!-- dewy-example: {"mode":"run","stdout":"[1 4 9 16]\n[0 2 4 6 8]\n[11 12 21 22]\n[0 0 1 10 2 20]\nset[1 3 5 7 9]\n[\"a\" -> 1 \"bb\" -> 2]\n[[0 1 2] [3 4 5]]\n"} -->
```dewy
printl([loop i in [1..5) i * i])
printl([loop n in [0..10) if n % 2 =? 0 n])
printl([loop a in [1..3) loop b in [1..3) a * 10 + b])
printl([loop i in [0..3) {i i*10}])
printl(set[loop n in [0..10) if n % 2 =? 1 n])
printl([loop w in ["a" "bb"] w -> w.length])
printl([loop y in [0..2) [loop x in [0..3) x + y * 3]])
```

Collectors are eager. A grid built by a comprehension keeps its row lengths as facts, so its elements index without guards; prefer it to filling a grid after making it.

## Literal Classification

At the top level of `[...]`:

- positional values make an array (or a tuple, or a record given positionally, when the context says so);
- `name=value` fields make a record;
- `key -> value` pairs make a dictionary.

`set[...]` makes a set. Mixing these forms in one literal is an error. Multidimensional numeric arrays and matrices are described in [Numeric Types](numeric-types.md).
