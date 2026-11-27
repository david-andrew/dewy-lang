# Ranges and Iteration

> [Generated coverage](/status/#ref-ranges-and-iteration) names related acceptance programs. Every example on this page compiles with the current compiler unless it is marked **Design only**.

## Range Forms

A range contains `..`. Endpoints written next to `..` are its bounds; either may be left out (`first..`, `..last`).

| Form | Values |
|---|---|
| `a..b`, `[a..b]` | `a` through `b`, both included |
| `[a..b)` | `a` up to but not including `b` |
| `(a..b]` | after `a` through `b` |
| `(a..b)` | strictly between `a` and `b` |
| `[a, s..b]` | `a`, then steps of `s - a`, through `b` |
| `a..` | `a` onward, without end |

The first two values of a stepped range set its step, `second - first`. The step may ascend or descend but must be nonzero: distinct literals prove it, as do facts such as `if step >? 0`; an unproven step is an error. A plain range never counts down: `5..0` is empty.

<!-- dewy-example: {"mode":"run","stdout":"1 2 3 \n1 2 \n2 3 \n0 4 8 \n10 8 6 4 2 \n"} -->
```dewy
loop i in 1..3 { print"{i} " }
printl("")
loop i in [1..3) { print"{i} " }
printl("")
loop i in (1..3] { print"{i} " }
printl("")
loop x in [0, 4..10] { print"{x} " }
printl("")
loop y in [10, 8..0) { print"{y} " }
printl("")
```

<!-- dewy-example: {"mode":"reject","diagnostic":"cannot prove the range step is nonzero"} -->
```dewy
every = (s:int64) => { loop i in [0, s..10] { printl(i) } }
every(2)
```

Endpoints and the start value are evaluated once, in source order. A loop over a range keeps a counter; no array is built. A range with no start cannot be iterated.

An open range such as `0..` or `[1, 3..]` runs until `break` or `return`. Reaching the end of its integer type is an obligation: the compiler's counter-progress assumption proves it for 64-bit counters, and `$no_assumed_bounds` turns that assumption off.

<!-- dewy-example: {"mode":"run","stdout":"0\n1\n2\n"} -->
```dewy
loop i in 0.. {
    if i >? 2 break
    printl(i)
}
```

### Stored ranges

A bounded range can be stored, passed and returned. Its type is `IntRange`: two `int64` bounds and a step, captured once. It holds no array; each loop over it gets its own cursor, and membership checks the bounds and the step.

<!-- dewy-example: {"mode":"run","stdout":"20\ntrue\nfalse\n[0,2..8]\n"} -->
```dewy
evens = [0, 2..10)
total = (r:IntRange):>int64 => {
    let t:int64 = 0
    loop v in r { t += v }
    return t
}
printl(total(evens))
printl(4 in? evens)
printl(5 in? evens)
printl(evens)
```

A stored range needs both bounds; open ranges are used directly in loops and membership tests.

## Membership

`value in? range` tests the bounds (and step) without building an array. The value is evaluated first, then each bound once. `not in?` negates it. The same operator tests arrays (elements), dictionaries (keys), sets (members) and strings (substrings).

<!-- dewy-example: {"mode":"run","stdout":"true\nfalse\ntrue\n"} -->
```dewy
printl(42 in? [0..100))
printl(100 in? [0..100))
printl(8 not in? [1, 3..9])
```

## Slices

A range used as an index selects a slice: `xs[1..3)`, `text[0..5)`. Inside the brackets, `end` is the receiver's last index, so `xs[end]` is `xs[xs.length - 1]` and is proven the same way. A stepped range selects every `s`-th element. A slice's bounds are proven like an index. `xs[$clamp a..b)` instead clamps the bounds to the array, as Python's slices do. Slices are covered in detail in [Arrays and Containers](arrays-and-containers.md#indexing-and-slices).

<!-- dewy-example: {"mode":"run","stdout":"[20 30]\n[40 50]\n[10 30 50]\n[20 30 40 50]\n"} -->
```dewy
let xs = [10 20 30 40 50]
printl(xs[1..3))
printl(xs[end-1..end])
printl(xs[0, 2..])
printl(xs[$clamp 1..10))
```

## Iterator Headers

In a loop condition, `name in source` takes the next value, binds it and reports whether there was one. Sources are ranges, arrays, strings (by grapheme), sets, dictionaries, generators, and records that provide `length` and `__index__`.

The source is evaluated once. `loop x in xs` iterates the value `xs` had at loop entry: the body may change `xs` without affecting the iteration, and no copy is made unless the body writes `xs`. The name holds the step's own copy of the element, so assigning it does not change the array.

### Combined headers

`and` joins several iterator clauses that advance together; the loop stops when any source ends. A counter `0..` alongside a source is Dewy's `enumerate`, and two sources are its `zip`:

<!-- dewy-example: {"mode":"run","stdout":"0: ant\n1: bee\n2: cat\n"} -->
```dewy
let words = ["ant" "bee" "cat"]
loop i in 0.. and w in words { printl"{i}: {w}" }
```

`or` keeps going until every source ends; an exhausted source supplies `none`:

<!-- dewy-example: {"mode":"run","stdout":"10 1\n20 2\nnone 3\n"} -->
```dewy
let lefts = [10 20]
loop left in lefts or right in [1 2 3] { printl"{left} {right}" }
```

Ordinary conditions may follow iterator clauses with `and`. The iterators advance first, then the conditions are tested with the new bindings; the loop ends at the first false condition (it does not skip the element). Inside the body the conditions are facts, so `i <? text.length` proves `text[i]`:

<!-- dewy-example: {"mode":"run","stdout":"1\n2\n3\n"} -->
```dewy
leading = (src:string):>int64 => {
    let n:int64 = 0
    loop i in 0.. and i <? src.length and src[i] =? " " { n += 1 }
    return n
}
printl(leading(" x"))
printl(leading("  y"))
printl(leading("   "))
```

All sources and bounds are evaluated once, in source order. Write `as` conversions of a source in parentheses: `loop b in (text as array<uint8>)`.

### Unpacking

A bracketed target unpacks each element: by position for arrays and tuples, by field name for records. With two names, a dictionary yields keys and values in insertion order. Nested groups follow the same rules. Unpacking an array by position needs a known length, such as a fixed-length element type:

<!-- dewy-example: {"mode":"run","stdout":"red: 42\nblue: 12\n6\n15\n"} -->
```dewy
let scores = ["red"->[20 22] "blue"->[4 8]]
loop [team [home away]] in scores { printl"{team}: {home+away}" }
let rows:array<array<int length=3>> = [[1 2 3] [4 5 6]]
loop [x y z] in rows { printl(x + y + z) }
```

<!-- dewy-example: {"mode":"reject","diagnostic":"unpacking requires exactly 2 elements"} -->
```dewy
let rows = [[1 2] [3]]
loop [a b] in rows { printl(a + b) }
```

### Changing the array

Changing the length of an array that a loop iterates by value is an error, which offers both fixes:

<!-- dewy-example: {"mode":"reject","diagnostic":"write `loop x in @xs` to iterate the live array"} -->
```dewy
let xs = [1 2 3]
loop x in xs { if x =? 2 { xs.push(4) } }
```

`loop x in @xs` iterates the place live: each step reads the current length and element, so pushes made by the body are visited. This is the worklist idiom. A live loop takes one name over a growable array named by a binding or field path, and cannot be part of a combined header.

<!-- dewy-example: {"mode":"run","stdout":"[0 1 2 3]\n"} -->
```dewy
Node:type = int64<n => 0 <=? n and n <? 4>
let edges:array<array<Node>> = [[1 2] [3] [3] []]
let seen = fill(false 4)
let order:array<Node> = [0]
seen[0] = true
loop node in @order {
    loop next in edges[node] {
        if not seen[next] { seen[next] = true; order.push(next) }
    }
}
printl(order)
```

`loop @item in xs` names the stored element instead of a copy: assigning it, changing its fields or calling a changing method on it updates the array. Copies of the array taken earlier stay unchanged. In a combined header, an `@` target may join counters and conditions over that one array (`loop i in 0.. and @job in jobs`).

<!-- dewy-example: {"mode":"run","stdout":"[21 22]\n[20 21]\n"} -->
```dewy
let values = [20 21]
let saved = values
loop @value in values { value += 1 }
printl(values)
printl(saved)
```

### Iterators

A value whose type has a `next` method giving the next element or `none` is an iterator. `loop x in it` steps a copy of the iterator. To steer the traversal from the body, bind the iterator and loop over its place: `loop x in @it` steps the bound iterator itself, so the body can call its other methods. The bundled `tree` module's walk is one such iterator:

<!-- dewy-example: {"mode":"run","stdout":"home\ndrafts\nnotes.txt\n"} -->
```dewy
from tree import Tree
let files:Tree<string> = []
let home = files.add("home")
files.add("old.txt" files.add("drafts" home))
files.add("notes.txt" home)
let w = files.walk
loop name in @w {
    if name =? "drafts" { w.skip_children() }
    printl(name)
}
```

An iterator loop binds one value and is not part of a combined header yet. Iterator protocols are provisional. `lazy` blocks that produce iterators are described in [Generators](generators.md).

### Custom sequences

A record type with a `length` function and `__index__(container index)` is a finite indexed sequence: loops and comprehensions visit positions `0` through `length - 1`.

<!-- dewy-example: {"mode":"run","stdout":"[40 41 42]\n"} -->
```dewy
Series:type = [first:int count:int]
length = (s:Series) => s.count
__index__ = (s:Series index:int) => s.first + index
printl([loop value in Series[40 3] value])
```
