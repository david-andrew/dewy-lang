# Object and Class Types

Object types are containers of named fields: values and functions in source order.
Field names and order are part of the type. A named `type` alias is a compile-time
name for that structural type; it is not a runtime value.

```dewy
let Pair:type = [left:int64 right:int64]
let origin:Pair = [left = 0 right = 0]
```

Anonymous object literals use `=` (or `let`/`const`) at the top level of `[]`.
Empty `[]` is not classified as an object. Dictionary arrows (`->`, `<->`) are a
separate container kind.

```dewy
let point = [
    x = 10
    y = 20
    sum = ():>int64 => x + y
]
point.x
point.sum          % zero-argument function fields are called
point.sum()        % explicit call of the same field
```

Constructors are ordinary functions that return object literals. Assignment,
parameters, and returns use value semantics: a copy of the object, not an alias.
Function fields may read sibling fields; they have no `self` parameter. Extracting
a method as a naked function value is not supported.

```dewy
let make = (x:int64 y:int64):>Pair => [left = x right = y]
let get_left = (pair:Pair):>int64 => pair.left
```

Object types are basically just containers containing assignments of variables and functions

```dewy
my_obj = [
    a = 'apple'
    b = 'banana'
    c = 'cat'
]
```

You can access the members of the object using the `.` accessor

```dewy
my_obj.a  %returns 'apple'
my_obj.c  %returns 'cat'
```

To create an object constructor (like many languages have classes that you can instantiate) we create a function that returns an object

```dewy
constructor = (param1 param2) => {
    return [
        p1 = param1
        p2 = param2
    ]
}

my_obj = constructor(42 'pi')
my_obj.p1  %returns 42
my_obj.p2  %returns 'pi'
```

You can also store functions inside of objects, allowing objects to completely cover regular object behaviors from other languages

```dewy
constructor = (param1 param2) => {
    return [
        p1 = param1
        p2 = param2
        func = () => printl('p1 is {p1} and p2 is {p2}')
    ]
}
```

There will not be any sort of `this` or `self` parameter as in other languages to access an objects members from within itself/any contained functions. Instead because the functions are at the same scope as the declaration of the objects members, those members are available to the function.

If we remove any unnecessary syntax, the shorthand for constructing an object looks like this:

```dewy
my_class0 = param1 => [
    p1 = param1
    func = () => printl('p1 is {p1}')
]
```

that is, just a function that returns an object literal, no need for braces or `return`.

## Dunder Methods

Similar to python, objects can define custom so-called "double-underscore" or "dunder" methods, which hook into the language's built-in functionality.

```dewy
% Define a point class with a custom add method
Point = (x:number y:number) => [
    x = x  %TBD if these are necessary since x/y are already in scope
    y = y
    __add__ = other:Point => Point(x+other.x y+other.y)
    __repr__ = () => 'Point({x}, {y})'
    __str__ = () => '({x}, {y})'
]

% Create two points and add them together
p1 = Point(1 2)
p2 = Point(3 4)
p3 = p1 + p2
printl(p3)  %prints Point(4 6)
```

Though actually for `__add__`, it might make more sense for it to be global, and you add an alternate that gets dispatched on rather than including it in the object itself:

```dewy
__add__ |= (a:Point b:Point) => Point(a.x+b.x a.y+b.y)
```

(TODO: longer explanation)
