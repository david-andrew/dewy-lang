# Discussion Points
Here will contain all features that I have aspects I'm undecided on (and any resolutions I come up with)


## lazy loop by default
need to decide if all loops should be lazy, or there should be an explicit `lazy` keyword used instead of `loop` (or could be lazy by default and have an `eager` loop keyword)


## bind expressions or statements [DONE: bind is an expression that returns void]
need to decide if bind expressions e.g. `x = 1` express values that are capturable. e.g. in a list comprehension, you might be doing work
```
mylist = [
    a = 2
    loop i in [3, 5..)
        if something(i + a)
            i
]
```
like it's clear that `a = 2` shouldn't be capturable by the comprehension, rather it's just statement, not an expression. The alternative is that bind expressions are full fledged expressions that can be captured and used as values. To not capture in a comprehension, you'd need to suppress the value probably using ;. Honestly I'm not a fan and think it should be one of the rare exceptions that is a statement, rather than an expression. If they were expressions, the semantics would be really weird, like you could capture a bind and pass it into a different context, which doesn't really make sense. E.g. you could do
```
some_function = () => {
    y = 42
    z = y + 1 * 2
    mybind = x = y
    return mybind
}

captured_bind = some_function()

captured_bind // expresses `x=y`. what does this even do???
```

And then there's the `:=` operator which is a proper bind expression, but it returns the value assigned, rather than what I was describing above where the bind action itself would have been returned.

Actually on further thought, I think bind should still be an expression, it's just that the bind expression returns `void`, thus even if it is in a context that captures expressions, it doesn't lead to anything. This way, we keep the "Everything is an expression" mantra.



## will complex list comprehensions be column vectors if people use usual spacing?
e.g. 
```
#ctx
primes = [
    2
    lazy i in [3, 5..)
        if i .% #ctx.primes .=? 0 |> @reduce(, (prev, v) => prev and v)
            i
][..10)
```

Notice how it's a 2 then a newline, then the generator for each of the values. In dewy a column vector vs a row vector would be made like so:
```
col_vec = [
    1
    2
    3
]

row_vec = [1 2 3]
```

(perhaps comprehensions are just the default vector dimension by default, regardless of how the spacing inside was)

Alternatively in most cases it won't matter whether the list is a row or column vector. In cases where it does matter, the user can make use of either \ and ; to specify the opposite vector dimension. e.g.
```
row_vec = [
    1\
    2\
    3
]

col_vec = [1; 2; 3]
```

So if a person wanted to make the original comprehension return a row vector instead of a column vector, they'd do
```
primes = [
    2\
    lazy i in [3, 5..)
        if i .% #ctx.primes .=? 0 |> @reduce(, (prev, v) => prev and v)
            i\
][..10)
```

## is \ syntax or escaping a newline? [DONE: syntax]
related point to previous: is \ escaping the newline, or is actual syntax for saying the next newline doesn't count (e.g. could have comments after it). I it should be bona-fide syntax because it's less cumbersome than an escape. If it's an escape, nothing can come after it (including whitespace) except the newline:
```
row_vec = [
    1\
    2\
    3
]
```
whereas if it's syntax, you can have whitespace and comments after it:
```
row_vec = [
    1\    // this is a comment
    2\    // some more comments
    3     // no need for a \ here because it's the last element
]
```

actually perhaps instead of `\`, we could use `,`, since it makes things into tuples, so a tuple directly inside a vector would be interpreted as a row vector. e.g.
```
row_vec = [
    1,
    2,
    3
]
```


## How does multidimensional indexing work? [DONE: each dimension access is separated by spaces. Also ranges may not contain any spaces]
e.g. if you have this 3D array, how can you index each dimension with a range?
```
my_tensor = [
     1  2  3  4  5
     6  7  8  9 10
    11 12 13 14 15
    16 17 18 19 20
    21 22 23 24 25
    
    26 27 28 29 30
    31 32 33 34 35
    36 37 38 39 40
    41 42 43 44 45
    46 47 48 49 50
    
    51 52 53 54 55
    56 57 58 59 60
    61 62 63 64 65
    66 67 68 69 70
    71 72 73 74 75

    76  77  78  79  80
    81  82  83  84  85
    86  87  88  89  90
    91  92  93  94  95
    96  97  98  99 100

    101 102 103 104 105
    106 107 108 109 110
    111 112 113 114 115
    116 117 118 119 120
    121 122 123 124 125
]

my_tensor[..2,0 .. () [0 4 5]] // should return a 4D tensor of shape [3 5 1 3]

```

### Things I'm realizing about ranges:
- range syntax should not allow any spaces in between. e.g.
    ```
    my_tensor[0 .. 10] // is interpreted as a 3 dimensional index returning a tensor of shape [1 5 1]
    ```
- these rules fall from how you'd index a vector/matrix/tensor/etc. with a list of values:
    ```
    my_tensor[0 1 2] // returns a [1 1 1] tensor
    my_tensor[[0 1 2]] // returns a [3 5 5] tensor
    ```

    i.e. each space separated thing accesses that dimension. If you want to access multiple elements in a particular dimension, you need to wrap them up so that they are a single expression in the indexing block





## Juxtaposition for everything [Yes! rely on type safety to determine what happens or compile error if incompatible]
- e.g. a function call could literally be `<fn><jux><value>` if the type of id was a function. Technically this leads to an interesting syntax (that I think stylistically should be discouraged)
```
inc = i:int => i+1

// all of these are identical, and would be parsed as function calls
inc(10)
(inc)10
(inc)(10)
inc{10}
{inc}10
{inc}{10}
(inc){10}
{inc}(10)
```

The nice thing about this is that it handles the whole string prefix function thing perfectly. e.g.
```
path = s:string => [
    //process s based on / and \ separators
    //store result in this object
]

path"this/is/a/file/path.ext"
```

which literally gets parsed as `<id:path> <jux> <str:"this/is/a/file/path.ext">`, i.e. already a function call.


In fact, this style could probably allow for custom operators to be added, e.g. by making the operator be an identifier. e.g.
```
dot = (left:vector<T>, right:vector<T>) => left .* right |> sum

then you can use it like an operator
a = [1 2 3]
b = [4 5 6]

a(dot)b
```

though actually this doesn't work because it looks like a is called with dot as an argument. If we make dot be a higher order function, then it sort of works, but just looks like a function call at that point
```
dot = (left:vector<T>) => (right:vector<T>) => left .* right |> sum
dot(a)b
```

In fact for it to work where you can do `a(dot)b`, you would need a function inside of vector objects that takes a function operator, and applies it to a vector next to it. e.g.
```
//vector type definition
vector = (vals) => [
    //save vals
    //save other metadata
    __call__ = (fn) => (other) => fn(vals, other)
]

//dot function
dot = (left:vector<T>, right:vector<T>) => left .* right |> sum

//usage
a = [1 2 3]
b = [4 5 6]
result = a(dot)b
```

## How to handle unit dimensionality
see: 
* https://www.youtube.com/watch?v=bI-FS7aZJpY
* https://www.youtube.com/watch?v=KmfdeWd0RMk



## No need for zip function
as a consequence of iterators expressing a boolean value , I think it implies a straightforward way to zip together 2 sequences
```
A = [1 2 3]
B = [4 5 6 7 8]
pairs = [
    loop i in A and j in B
        [i j]
]

//pairs is [[1 4] [2 5] [3 6]]
```

A cool consequence of this is you can change the logic operator and get a different behavior
```
pairs = [
    loop i in A or j in B
        [i j]
]

//pairs is [[1 4] [2 5] [3 6] [undefined 7] [undefined 8]]
```

In fact, it makes it trivial to enumerate a list
```
loop i in count and v in some_sequence
    printl[i v]
```

certainly if you glue the two sequences together, you could do the whole zip process, and unpack as two variables
```
A = [1 2 3]
B = [4 5 6]
sums = [
    loop i, j in [A; B]`
        i + j
]

//sums is [5 7 9]
```



## Should units be their own token class, or just be pre-existing named identifiers?
- if ID, then it makes it super easy to add new ones
- if distinct class, makes it easier to handle how units have somewhat different precedence than other identifiers.
   e.g. there's the whole `<number> <space> <unit>` construction that I'm not quite sure how to handle without units being their own type