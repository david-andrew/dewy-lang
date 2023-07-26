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


## How does multidimensional indexing work? [DONE: each dimension access is separated by spaces as in regular arrays. Parsing precedence will determine what attaches to .. and user's can use ()/[] to disambiguate]
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


Basically the question really comes down to how are lists containing ranges handled from a parsing point of view? In generally, juxtaposing a tensor with a list will try to access the tensor. Though actually, since matrix multiplication is a thing, aren't there contexts where we'd want it to multiply rather than access? Probably need the type of the left and right to determine if it's a multiply or an access... Perhaps array literals on the right-hand-side cannot be multiplied with juxtaposition, and will always be interpreted as accessing? still needs type information, but it's a pretty good clear rule.



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
* Seven Dimensions: https://www.youtube.com/watch?v=bI-FS7aZJpY
* a joke about measurement: https://www.youtube.com/watch?v=KmfdeWd0RMk

Also related:
- cursed units: https://www.youtube.com/watch?v=kkfIXUjkYqE



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



## should we allow certain string prefix functions to be parsed as raw strings? [probably not]
e.g. allow `dewy'''if rand > 0.5 { print('hi') } else { print('bye') }'''` to be parsed using the raw string tokenizer, rather than the regular string tokenizer. At present, if you want to use the raw string tokenizer, you'd have to do `(dewy)r"your raw string"`, which is a little clunky. It's hard to say what to do though because there may be instances where you'd want to allow string interpolation, but other instances where the string interpolation would get in the way. 

This could be accomplished, e.g. by having a file or something that list out all of the prefixes that should be parsed that way, and then the raw string tokenizer pulls that list to determine what prefixes count as the beginning of a raw string.

If we allowed specific string function types to be parsed as raw strings, it causes a couple problems:
- if the function that is the prefix is ever redefined, the tokenizer will not follow the new definition, and in fact, the new function definition won't be applied to the string (unless we're really careful... sounds like a headache)
- let's say we wanted an interpolated string, there's not an easy syntax to go back



## how to handle the fact that juxtapose having two different precedences 
~~[for now, probably start with a jux-unknown during initial parse, and replace with jux-call or jux-multiply in a post parse step when we can check the type of the left/right expressions]~~

**[for now, check the (eval result) type of the left and right, and determine if it is a multiply of a call based on the types. If it is a union of types and could be either a multiply or call based on the union, throw an error.]**
depending on if it should be a multiply juxtapose or a call juxtapose, the ^ operator has a precedence in between them, making things confusing.

function call juxtaposition has higher precedence than ^
```
sin(x)^2 + cos(x)^2  // => (sin(x))^2 + (cos(x))^2
```

But we can easily make an identical set of tokens that have a reversed precedence
```
sin = 2 cos = 3
sin(x)^2 + cos(x)^2 // => sin((x)^2) + cos((x)^2) 
                    // => 2((x)^2) + 3((x)^2)
```

see also:
```
2x^2 + 3x + 4
2(x)^2 + 3(x) + 4
```

what's even more messed up is if the type of the identifier is a union between one that is callable, and one that is multipliable, then the precedence gets decided at runtime!
```
sin: ((x:float) => float) | float
cos: ((x:float) => float) | float

sin(x)^2 + cos(x)^2 // undecidable until runtime
```

Note that the way julia handles it is that if sin/cos are value rather than functions, it is illegal syntax to juxtapose them like
```
sin(x)^2 + cos(x)^2
```

Instead you must put parenthesis around the identifier
```
(sin)x^2 + (cos)x^2
```

TBD what the solution is. Ideally we could parse things that look like calls into calls, and things that don't look like calls into multiplies, but the () get stripped away, and in all cases we're just left with id,jux,id without any parenthesis...



## How to have physical number literals with units [use juxtaposition]
Originally I wanted to be able to say things like
```
10 kg * 9.8 m/s^2
15 kg
7 kg * 10 m/s/s
25 N/m^2 + 15 Pa
12 kg + 8 kg
3 m * 5 s
25 J - 15 J
9 N * 6 m
1500 W / 10 A
5 A * 2 Ω
8 ms^-1 / 2 s
```
however this presents a problem as there is a space between the number and the unit, making it seem like they are separate expressions. I could have the parsing process try to get around this by looking for instances of numeric expression ASTs right next unit expression ASTs.

The alternative is to make use of juxtaposition to attach units to expressions
```
10kg * 9.8(m/s^2)
15kg
7kg * 10(m/s/s)
25(N/m^2) + 15(Pa)
12(kg) + 8(kg)
3(m) * 5(s)
25(J) - 15(J)
9(N) * 6(m)
1500(W) / 10(A)
5(A) * 2(Ω)
8(ms^-1) / 2(s)
```

For these, you can attach the unit directly to the number if it is just a single unit, or you can wrap single units and unit expressions in parenthesis and juxtapose them with the number. The great thing about this approach is it already works under the current system, with no needed adjustments to the parsing process. It is slightly less aesthetic, but honestly I'd say it's like 95% as good.


## is `|>` just for function application, or can it be a general juxtapose operator?
I'm leaning towards it just being a juxtapose operator, though tbd if it affects examples like this
```
i .% #ctx.primes .=? 0 |> @reduce(, (prev, v) => prev and v)
```

The other weird thing to think about is that it flips the arguments around for the juxtaposition, e.g.

```
sin(2pi(rad))
2pi(rad) |> sin
```

so perhaps we could have a reversed version that juxtaposes without flipping around...
```
sin <| 2pi(rad)
```


## Piping multiple arguments vs piping a list
since I want to be able to pipe multiple arguments, as well as a list, perhaps there could be a spread pipe operator that spreads the arguments out, e.g.

```
a, b, c |*> myfunc
```

whereas just using the regular pipe would treat the list as a single argument
```
a, b, c |> myfunc
```

This probably also implies the existence of a `<*|` reverse order spread pipe operator

Alternative syntaxes for the operator:
```
*>
<*

[>
<]

:>
<:
```



Also, what about vectorized pipes? e.g. say you have a function that takes a single argument, but you want to vectorize passing in a list

```
[1 2 3] |> myfunc
```

perhaps the dot syntax would work here
```
[1 2 3] .|> myfunc
```


(random note for later. what about handling vectorized calls in general, e.g. `myfunc.[1 2 3]`, how is juxtapose vs dot handled there to make that clear?)



## Execution order and Lazy evaluation [function body is lazily evaluated. functions can capture any local variables at that scope, even if they are defined later, so long as they are defined by the time the function is called]
Python lets you use functions that are defined later in the file (if you use it inside a function definition). But there's not a clear easy way to do that in dewy

```

let func1 = () => {
    printl"func1"
    func2
}

let func2 = () => printl"func2"
```

Nice languages let this work, e.g. in python the definition of func2 is available because the function names are evaluated first, and then the inner declarations are evaluated later. But I'm not sure this will work in dewy, because defining a function is the same as assigning a variable, so what if we did something like this

```
let apple = func2

let func2 = () => "func2"
```


Though now that I'm looking at it, I think the way to handle it is that function bodies are not evaluated at the point they are defined, they are evaluated when they are used, which is very much like python.

I was also thinking about making the language broadly lazily evaluated, but I think that runs into issues with how people would expect procedural code to evaluate. I think in general things should probably be greedy, unless using a lazy construct, such as a function body


Weird things I think this may imply:

```
let func1 = () => {
    printl'apple is {apple}'
}

apple = 10

func1()
```

which technically would work. If however func1 was called somewhere before apple was defined, it would fail. This weirds me out a bit, because what if there is some variable that the user defines in another file that the function is expected to capture? I feel like that's getting too complicated to handle (let alone being a bad practice)--perhaps we just disallow non-local values like that to be captured. Only values in the scope where the function is defined may be captured. But they can be defined after the function definition, so that we can have the nice behavior where function definition order isn't important.

For exported functions, any captured values must be defined before the call to export, which is treated as the point that any external code will call the function from.



## Import/Export syntax [`import <thing(s)> [from <file path>]` and `export <thing(s)>`]

```
// importing from local files
import myfun from p"stuff.dewy"
import myfun2, myfun3 from p"stuff2.dewy"

// importing stdlib stuff. TBD on if any of this stuff is auto-imported
import IO                       //std lib import whole module object
let [sin cos tan] = import Math //std lib break out specific values

// importing from installed packages
import RandomForest from sklearn
```

technically sin, cos, tan should all be available without having to import them. It's more for installed package syntax.

## Global functions vs object methods
Only in very rare instances will there be globally available functions. It is mainly reserved for cases where it is a fundamental aspect of the language, rather than an intrinsic property of the object.

Python's `len` function absolutely would not qualify. It should have been a property on all of the objects that have length!

- many math functions, (e.g. `abs` `min` `max` `sin` `cos` `tan` etc.) that take in a numeric expression
- autodiff which takes in (what? perhaps an expression with symbolic variables in it)


## Unified naming for length/size/shape/dim/etc.
(TODO) these need to be picked, and be consistent across objects of the same type. Could have multiple of these if it makes sense/they represent usually different things.

## unified naming for vectors/matrices/tensors/etc.
basically I want a single type that represents a regular grid of numbers. Technically tensor is the most general, but IDK if I like the syntax. I'm leaning towards everything just be called `vec` or `vector`

I think maybe a separate notion of list is unnecessary

## Handling symbolics
- create symbolic expression
  - evaluate expression by setting value of symbolic variables
  - operate on expression, e.g. `autodiff`
  - use in a larger expression `expr1 + expr2`

e.g.
```
let W: vec[5 2] = symbol
let b: vec[5] = symbol

let x: vec[2] = symbol

let y = W * x + b
let dydW = autodiff(y, W)

//evaluate expression
let Wi = randn[5 2]
let bi = randn[5]
let xi = randn[2]

let grad = dydW(W=Wi, b=bi, x=xi)
```
honestly though this is actually competing a bit with just the function notation

```
let y = (W:vec[5 2], b:vec[5], x:vec[2]) => W * x + b
let dydW = autodiff(y, W) //though how do we specify which variable? what does pytorch do?
```

I do like the idea of having a symbolic type. Might also be good to keep them separate because you can restrict what types of operations are valid on symbolics, whereas functions are much more general. More consideration needed though.

## Coupling variable lifetimes with resources
imagine I want to make a temporary file for doing some operation, and then delete the temporary file when I'm done. This will typically be over the same scope as some process. I want some way to automatically have the cleanup code for deleting the file be called when whatever coupled variable goes out of scope. It shouldn't matter how the code exits, e.g. if there's an error, cleanup should happen anyways

I think python's with statement syntax is a bit too verbose in that it requires you to explicitly wrap whatever process in the context. Instead I want something more like this:

```
let file = open("temp.txt", "w")
//some sort of binding to when file variable goes out of scope
#on_cleanup(file, () => file.close())

//do stuff with file
```

Then no matter how the scope is exited, the file will always be closed. And the programmer doesn't have to worry about making sure that some context covers the right bounds or anything. Instead it is literally tied to the lifetime of the variable.

This is similar to python's weak references


## Function overloading [leaning `xor`]

function overloading will be achieved by combining two or more function literals / function references and binding to a single variable. The question is which operator should be used to achieve this

```
func1 = (a:int, b:str) => 'first version'
func2 = (a:int, b:int) => 'second version'

//Using the `|` operator normally for type unions:
overloaded = @func1 | @func2

//Using `xor` normally for boolean/bitwise exclusive or
overloaded = @func1 xor @func2
```


Also an existing function could be updated to be overloaded, or further overloaded
```
myfunc = (a:int, b:str) => 'first version'
myfunc |= (a:int, b:int) => 'second version'
myfunc |= (a:int, b:int, c:int) => 'third version'
```

or 

```
myfunc = (a:int, b:str) => 'first version'
myfunc xor= (a:int, b:int) => 'second version'
myfunc xor= (a:int, b:int, c:int) => 'third version'
```

Pros and cons for both:
- `|` is probably more intuitive
- `|` is mainly for types though

- `xor` means the correct thing: one of these but not both
- `xor` might be slightly less intuitive though


### also random note about in place overloading

normally in place operators are just syntactic sugar like so:
```
a += 15  
// a = a + 15
```

but for function overloading, since functions need to be @referenced, this is what happens

```
myfunc xor= (a:int, b:int) => 'second version'
// myfunc = @myfunc xor (a:int, b:int) => 'second version'
```

that is to say, functions are @ referenced when part of an in-place operator

conceivably, we could also do something like this to maintain the symmetry of the notation:
```
@myfunc xor= (a:int, b:int) => 'second version'
// @myfunc = @myfunc xor (a:int, b:int) => 'second version'
```

This implies that in the `@myfunc` on the left receiving the assignment the `@` is a no-op. which may or may not be what I want to do