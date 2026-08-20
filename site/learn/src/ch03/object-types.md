# Object Types

Objects are containers of named fields, values and functions, in source
order. Field names and order are part of the type. A `type` alias is a
name for that structure, not a class object sitting in memory.

```dewy
let Pair:type = [left:int64 right:int64]
let origin:Pair = [left = 0 right = 0]
```

Anonymous literals use `=` at the top level of `[]`. `->` and `<->` make
a dictionary instead.

```dewy
let point = [
    x = 10
    y = 20
    sum = ():>int64 => x + y
]
point.x
point.sum           # zero-arg field, gets called
point.sum()         # same thing, spelled out
```

## Constructors

There is no `class` keyword. A constructor is a function that returns an
object.

```dewy
let make = (x:int64 y:int64):>Pair => [left = x right = y]
let get_left = (pair:Pair):>int64 => pair.left
```

Assigning, passing, and returning give you a copy, not an alias.

```dewy
let original = [x = 10 y = 20]
let copy = original
copy.x = 32         # original.x is still 10
```

Functions inside can see sibling fields. There is no `self` or `this`;
they are in the same scope. You cannot take a method out as a naked
function value.

A compact constructor looks like this:

```dewy
Point = (x:number y:number) => [
    mag = () => (x^2 + y^2)^/2
    show = () => printl'({x}, {y})'
]

p = Point(3 4)
p.mag               # 5
```

## Dunder Methods

Double-underscore methods hook into built-ins, the same idea as Python:

```dewy
Point = (x:number y:number) => [
    x = x
    y = y
    __add__ = other:Point => Point(x+other.x y+other.y)
    __repr__ = () => 'Point({x}, {y})'
    __str__ = () => '({x}, {y})'
]

p1 = Point(1 2)
p2 = Point(3 4)
p3 = p1 + p2
printl(p3)          # Point(4 6)
```

Or hang the operator on a shared function and let the argument types
pick which one runs, instead of putting `__add__` on every instance:

```dewy
__add__ = __add__ & ((a:Point b:Point) => Point(a.x+b.x a.y+b.y))
```

`&` overloads are in [Function Types](function-types.md).
