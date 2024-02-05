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

## Capturing the result of a block with multiple expressions (related to list comprihensions/generators) [multiple expressions in a block return a generator, unless the block is wrapped in `[]`]

lets say you have a block

```dewy
a = {
    1+1
    2+2
    3+3
}
```

how should this behave? what gets stored in `a`? It's pretty obvious when it's just a single expression in the block

```dewy
a = { 1+1 }
```

`a` should definitely just be `2`.

I'm thinking though for the first case, I think `a` should get a generator. Basically it would be the same as if in python you did:

```python
def gen():
    yield 1+1
    yield 2+2
    yield 3+3

a = gen()
```

Though this does bring up a different interesting question, what is the difference between these two:

```dewy
a = { 1+1 2+2 3+3 }
b = () => { 1+1 2+2 3+3 }


A = a // 2
A = a // 4
A = a // 6


//B = b // 2
//B = b // 4
//B = b // 6
//actually I think this is what would happen
gen = b // generator object
B = gen // 2
B = gen // 4
B = gen // 6

```

More thought is needed on this though. Basically should come up with a long list of examples and use cases

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

- Seven Dimensions: https://www.youtube.com/watch?v=bI-FS7aZJpY
- a joke about measurement: https://www.youtube.com/watch?v=KmfdeWd0RMk

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
- if distinct class, makes it easier to handle parsing all the different combinations of units with their prefixes, abbreviations, plural forms, etc.

I'm actually leaning towards having a feature for complex named identifiers. Basically you could define lexer rules that would check if an identifier matched some criteria, and then use that to refer to a specific value (which may be constructed from other values)

So, something like:

```dewy
long_si_prefix_table = [
    'kilo' -> 1e3
    'mega' -> 1e6
    ...
]
short_si_prefix_table = ...
long_unit_table = ...
short_unit_table = [
    'm' -> //perhaps some sort of meter singleton
    's' -> //...
    'g' -> //...
    ...
]
#complex_identifier(
    //rules for parsing units with their prefixes (both abbreviated and written out)
    //function for handling the result, combining from the tables above to get the value
)
```

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

## Piping multiple arguments vs piping a list [functions called with tuple get each argument separately, functions called with list get the whole list as one]

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

## Import/Export syntax [`[from <file path>] import <thing(s)>`. TBD on if export syntax is necessary `export <thing(s)>`]

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

Actually based on this video (https://www.youtube.com/watch?v=X6Jhxm1lPHY), I'm gonna switch the order of the thing being imported with the import path. So things would be:

```dewy
from p"stuff.dewy" import myfun
from p"stuff2.dewy" import myfun2, myfun3 as f1, mymodule as [f2 f3 mod3 as [f4 f5]]]
import p"../mylib3.dewy" as mylib3
from p"mylib4.dewy" import ...

import IO
from Math import sin, cos, tan
import seaborn as sns
from sklearn import RandomForest
```

probably don't allow the syntax

```dewy
let [sin cos tan] = import Math
```

If someone did want to break it down like that, they'd need to do it as two separate imports

```dewy
import Math
let [sin cos tan] = Math
```

## Relative Path default starting location: cwd vs **file** [definitely __file__. require user to specify CWD/ if they want it]

when making a relative path in dewy, should it be relative to where the `dewy` command was invoked (i.e. the current directory), or should it be relative to the file that is currently being executed?

```
from p"../mylib.dewy" import ...

p'some_text_file.txt'.write_text('hello world')
```

I think intuitively, most people think like it's relative to **file**. Plenty of times I get burned by writing scripts and then running them from different locations. It's especially good for imports, since that should never be affected by the location of the invocation of the script.

If you want to make it relative to the current directory, you can just do

```
from p"{cwd}/mylib.dewy" import ... //why anyone would ever want this is beyond me

p'{cwd}/some_text_file.txt'.write_text('hello world')
```

## Unpack syntax

```dewy
s = ['Hello' ['World' '!'] 5 10]

// tuple version
a, b, c, d = s
a, ...b = s
...a, b = s
a, [b, c], ...d = s

// list version
[a b c d] = s
[a ...b] = s
[...a b] = s
[a [b c] ...d] = s
```

unpacking from an object with named fields:

```dewy
o = [apple=1 banana=2 carrot=3]

// tuple version
a, b, c = o
a, = o
a, c = o
c, = o

// list version. I think I prefer this
[a b c] = o
[a] = o
[a c] = o
[c] = o
```

unpacking from a map

```dewy
m = ['apple' -> 1 'banana' -> 2 'carrot' -> 3]

// tuple version
'apple' -> a, 'banana' -> b, 'carrot' -> c = m
'apple' -> a, 'carrot' -> c = m
'carrot' -> c = m

// list version
['apple' -> a 'banana' -> b 'carrot' -> c] = m
['apple' -> a 'carrot' -> c] = m
['carrot' -> c] = m
```

I think in general, I prefer the bracketed version

incidentally, this is how you'd do a swap

```dewy
[a b] = [b a]
a, b = b, a
```

## Unifying imports, unpacks, and declarations [YES!]

```dewy
const bigthing = import p"bigthing.dewy"
let [something1, [sub1, sub2] = something2] = import p'path/to/file.dewy'
const [prop1, prop2] = myobj
let apple = 42
```

## Global functions vs object methods

Only in very rare instances will there be globally available functions. It is mainly reserved for cases where it is a fundamental aspect of the language, rather than an intrinsic property of the object.

Python's `len` function absolutely would not qualify. It should have been a property on all of the objects that have length!

- many math functions, (e.g. `abs` `min` `max` `sin` `cos` `tan` etc.) that take in a numeric expression
- autodiff which takes in (what? perhaps an expression with symbolic variables in it)
- introspection/functions for interacting with Dewy internals, e.g. (from python) `type`, `__class__`, `__name__` etc.

## Unified naming for length/size/shape/dim/etc.

(TODO) these need to be picked, and be consistent across objects of the same type. Could have multiple of these if it makes sense/they represent usually different things.

## unified naming for vectors/matrices/tensors/etc. ["Array"]

basically I want a single type that represents a regular grid of numbers. Technically tensor is the most general, but IDK if I like the syntax. ~~I'm leaning towards everything just be called `vec` or `vector`.~~

I think maybe a separate notion of list is unnecessary

I think I've settled on "Array" being the term (though tbd if we shorten to arr). Array is non-specific in the number of dimensions it has. If an array has a specific shape that fits one of the other terms, it could be called that in context, but the type will still be "Array"

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

## Function overloading [`|` and `or`]

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

But actually the best might just be to use `and`

Such overloading will be especially important for user's defining infix operations over custom types:

```
Point = (x:number, y:number) => [
    x = x  //TBD if these are necessary since x/y are already in scope
    y = y
    __repr__ = () => 'Point({x}, {y})'
    __str__ = () => '({x}, {y})'
]

__add__ |= (a:Point, b:Point) => Point(a.x + b.x, a.y + b.y)
```

### also random note about in place overloading

normally in place operators are just syntactic sugar like so:

```
a += 15
// a = a + 15
```

but for function overloading, since functions need to be @referenced, this is what happens

```
myfunc |= (a:int, b:int) => 'second version'
// myfunc = @myfunc | ((a:int, b:int) => 'second version')
```

that is to say, functions are @ referenced when part of an in-place operator

conceivably, we could also do something like this to maintain the symmetry of the notation:

```
@myfunc |= (a:int, b:int) => 'second version'
// @myfunc = @myfunc | ((a:int, b:int) => 'second version')
```

This implies that in the `@myfunc` on the left receiving the assignment the `@` is a no-op. which may or may not be what I want to do

Clearly the first way is better though

## Type syntax just forwards to type function

```
let myvar: vector<int, length=5> = [1 2 3 4 5]
```

perhaps this is really just sugar/gets converted to a call to type with the given parameters

```
let myvar: type(base=vector, params=(int, length=5)) = [1 2 3 4 5]
```

## Type system

(combination of nominative and structural, i.e. julia and typescript)

- type graph for build in types "atoms". user can expand the type graph if they want, though that will be pretty rare
- structural/complex constructed type "molecules" like in typescript (e.g. unions, intersections, structs, etc.), that don't necessarily fit into the type graph.
  TODO: more discussion, e.g. where do parametric types go? probably in the graph

## names for different declaration types

There are three explicit declarations types (and one implicit type)

`let`: variable type. If the name already exists in a higher scope, a new shadow for the name is made
`const`: constant type, unmodifiable
`tbd`: types that are constant, but do not cause compile time error when trying to overwrite in lower scopes. instead they make a new shadow. Perhaps we don't have this type, and just force the user to explicitly use `let` when they want to overwrite const types.

- I think a common case would be `i` for the complex value, and the user will want to overwrite it with i as the common iterator index in loops. that's a weird case though because it uses none of the mutability declarations. It would be `loop i in a..b`, so presumably loop uses `let` by default

simply doing `name = value` may or may not be allowed depending on if name is already defined, and the mutability it has.

- if `name` does not exist yet, then this is equivalent to `let name = value`
- if `name` exists and was declared with `let`, then this is equivalent to updating that instance of `name` with the new value
- if `name` exists and was declared with `const` then this will fail at compile-time

To put it another way, `name = value` is sort of equivalent to `create_or_overwrite name = value`. perhaps we'll even have `create_or_overwrite` used internally, and `name = value` is just syntactic sugar for it

## Precedence of comma vs assignment [leaning towards requiring parenthesis around default function arguments, e.g. `foo = a,(b=1),(c=2) => a+b+c`, e.g. `foo123 = @foo((a=1),(b=2),(c=3))`]

There are situations when comma needs to have higher precedence than assignment, but also situations where it is the opposite:

```dewy
//comma needs lower precedence
foo = (a, b=1, c=2) => a+b+c

//comma needs higher precedence
a,b,c = 1,2,3
```

possibly solved by making comma have lower precedence and requiring parenthesis in the second case:

```dewy
(a,b,c) = (1,2,3)
```

however I do not like this, as it decreases flexibility in the language, and prevents the ability of removing parenthesis from many tuple expressions, which is laborious.

Another alternative is to introduce a higher precedence version of the assignment operator

```dewy
foo = (a, b:=1, c:=2) => a+b+c
```

The problem I have here is that other than the walrus operator, I'm not sure I can think of any syntax that I like for the operator. Unfortunately the walrus operator itself was going to have the same precedence as the assignment operator, so I'd have to forgo having it if another operator syntax can't be found. Not the end of the world though since the walrus operator's effect can be pretty simply achieved

````dewy
//with walrus operator
loop (chunk := get_next_chunk())? {
    //do stuff with chunk
}

//equivalent
loop (chunk = get_next_chunk() chunk?) {
    //do stuff with chunk
}

The nice thing about having the higher precedence assignment operator is that it allows us to remove parenthesis from argument lists in a function declaration:
```dewy
foo = a, b:=1, c:=2 => a+b+c
````

Possible syntaxes:

- `foo = a:int, (b:int=1), (c:int=2) => a+b+c`
- `foo = a:int, b:int:=1, c:int:=2 => a+b+c`
- `foo = a:int, b:int<-1, c:int<-2 => a+b+c`
- `foo = a:int, b:int#=1, c:int#=2 => a+b+c`
- `foo = a:int, b:int=1, c:int=2 => a+b+c`
- `foo = a:int, b:int~1, c:int~2 => a+b+c`
- `foo = a:int, b:int<=1, c:int<=2 => a+b+c`
- `foo = a:int, b:int$1, c:int$2 => a+b+c`
- `foo = a:int, b:int::1, c:int::2 => a+b+c`
- `foo = a:int, b:int$=1, c:int$=2 => a+b+c`
- `foo = a:int, b:int[=]1, c:int[=]2 => a+b+c`
- `foo = a:int, b:int(1), c:int(2) => a+b+c`
- `foo = a:int, b:int<>1, c:int<>2 => a+b+c`

I think the best case is `foo = a:int, (b:int=1), (c:int=2) => a+b+c`.

- it forces the developer to be more aware of the precedence of operators in the language
- it is the most explicit and intuitive about what is happening (though not necessarily intuitive that it would be necessary to do this way)
- it makes use of the existing language semantics, without introducing new operators

A somewhat radical take, but technically within the rules of the language is to use array literals for the argument list

```dewy
foo = [a b=5] => a + b
foo = [a:int b:int=5 c:int=10] => a + b + c
```

This is potentially better than requiring parenthesis:

- since arrays are space separated, the assignment is parsed logically as one would expect

It does bring into question what the purpose of tuples are. Why not just use array syntax everywhere with no commas for anything?

Or we could just allow both.

Though there is still a problem in other cases, e.g. calling a function and overwriting a value by name:

```dewy
sum = (a, b) => a + b   //simple addition function
add5 = @sum(5)          //partially evaluate sum with a=5
thirtyseven = @add5(32) //new function that takes 0 arguments

//recreate the sum function by overwriting the partial evaluation
new_sum = (x, y) => thirtyseven(a=x, b=y)
```

In this case, we still have an issue with the comma operator having the wrong precedence when calling `thirtyseven`...

## Should we get rid of the low precedence range juxtapose, and force ranges with step size to wrap the tuple in parenthesis, or should loops with multiple iterators require parenthesis around each iterator? [leaning have range-jux have lower precedence than comma, and any time you want to do `a in range`, you need to wrap the range. `in` gets higher precedence than logical operators]

Currently there is a conflict with the operator precedence. We cannot have both of these:

```dewy
//range with a step size
r = [first,second..last]

//loop with multiple iterators
loop i in 1..5 and j in 1..5
{
    printl('{i} {j}')
}
```

The problem is with the precedence of the range juxtapose. Right now range juxtapose is lower than comma, allowing the first case `first,second..last` to work without needing to wrap the tuple in parenthesis. However, `,` comma is generally a pretty low precedence operator due to how tuples are typically sequences of expressions, so most operators should have higher precedence. `in` must have even lower precedence than range juxtapose so that the range is constructed before the `in` expression. This means in the second example, the `and` will bind with the `5` and `j` rather than the correct interpretation.

The two approaches to fixing:

1. keep precedence of range juxtapose/in below comma, and require any logically combined iterators to be wrapped in parenthesis:
   ```dewy
   loop (i in 1..5) and (j in 1..5)
   {
       printl('{i} {j}')
   }
   ```
2. increase the precedence of range juxtapose/in to be above logical operators (e.g. `and`, `or`, etc.), and require any ranges with step size to be wrapped in parenthesis:
   ```dewy
   r = [(first,second)..last]
   ```

I think it comes down to which will occur more often--I suspect logically combined iterators will be much more common than ranges with a step size. So I'm leaning option 2.

Last alternative is to just require that all ranges have parenthesis or brackets around them... This allows low range_jux precedence, and also doesn't require us to wrap the range first,second in parenthesis. Also it makes it always unambiguous what the bounds are on the range (i.e. open or closed).
EXCEPT this breaks the whole syntax for multidimensional indexing, making it super verbose

## Parsing flow expressions joined with `else` [Fixed, handled correctly in post-tokenization!]

This isn't a syntax issue, but rather a parsing issue. Where should the correct nesting of flow expressions be handled?

e.g.

```dewy
if a if b c else if d e else f else g
```

Ideally this would be correctly nested during tokenization, but as is, with the token_blacklist which excludes `else` while parsing flow expressions, any nested expressions are not able to be constructed. To fix in the tokenizer, it would require some sort of more complicated stack to keep track of if an `else` could be joined to the current expression or not

Pros:

- easier to deal with the result as flow expressions already are properly nested

Cons:

- complicates the process of `get_next_chain()`

The alternative would be to handle it during parsing. Honestly, I think we need to handle it during tokenization because keyword expressions are not infix expressions, so if we push it to parse time, it greatly complicates parsing (which as is, is relatively elegant). Also it's not clear that it would be possible to handle tokenization correctly anyways, unless we skip bundling up captured expressions with the keywords they go with :-(

## adding methods to types based on first argument of function

In some languages you can have a type, and then externally define functions that take that type as the first argument, and then let you call that function as if it was a method on the first type. e.g.

```dewy
obj = [
    x = 5
    y = 10
]

objType = type(obj)

f = o:objType => o.x + o.y

obj.f() //returns 15
```

I think this should definitely be a feature in dewy (with a bit more thought on how they typing works). But I actually think it should be expanded to work for tuples of values as well

```dewy
A = [
    x = 5
    y = 10
]
B = [
    z = [1 2 3 4 5]
]

f = a:type(A), b:type(B), c:int => (a.x + a.y - c) .* z

// these all do the same thing
A.f(B, 5)       // [10 20 30 40 50]
(A, B).f(5)     // [10 20 30 40 50]
(A, B, 5).f     // [10 20 30 40 50]
```

The question is if this is useful. Definitely allowing the function to attach to methods of the first type makes sense, but hard to say if allowing for more complicated attachments via tuples is useful for anything.

Also though this is basically like the same thing as the pipe operator..

```
A = [
    x = 5
    y = 10
]
B = [
    z = [1 2 3 4 5]
]

f = a:type(A), b:type(B), c:int => (a.x + a.y - c) .* z

// equivalent to the above
A |> @f( , B, 5)
(A, B) |> @f( , , 5)
(A, B, 5) |> @f
```

But honestly this could replace the need for the pipe operator!

Also important note: I think this should probably be opt-in to make a function be able to be used as a method on matching type. perhaps something like

```dewy
#methodable
f = a:type(A), b:type(B), c:int => (a.x + a.y - c) .* z
```

## Enums are just string unions

Earlier I had been thinking I wanted some way for you to be able to use enum values when calling a function, where the enum value is only defined in the body of the function, but not necessarily at the call site. But this breaks a lot of things if using regular enums. However this can easily be achieved by just making the argument a string union over the desired enumeration fields. Dewy should be able to identify the type, and reduce it down to enum-like performance without doing string comparisons

```dewy
///////// file1.dewy //////////

option = <'opt1' | 'opt2' | 'opt3' | 'etc'>

A = [
    f = o:option => printl'you selected option {o}'
]

///////////////////////////////

///////// file2.dewy //////////
import A from p'file1.dewy'

// compiler ensures that the input is only one of the valid strings
// compiler also optimizes strings into integers under the hood
A.f('opt3')

myOpt:option = 'etc'
```

I think this is the general way to construct enums in Dewy. For python style enums where there is a top level name and then you refer to values in that name, you'd just make an object

```dewy
// python-style enum
MyEnum = [
    A = auto
    B = auto
    C = auto
    D = auto
]

MyEnum.A
```

## Should function arguments be included in the body of an object as parameters, without requiring the user to explicitly assign them? [leaning requiring user to explicitly assign them]

e.g. in this:

```dewy
Point = (x:number, y:number) => [
    let x = x
    let y = y
    __repr__ = () => 'Point({x}, {y})'
    __str__ = () => '({x}, {y})'
]
```

> Note that x and y need to be declared using `let` since x and y exist in the parent scope from the arguments, just doing `x = x` would reassign the `x` in the parent scope, but would not assign it in the object scope

does the user need to do the `let x = x` and `let y = y` step? I think there are pros and cons.

As is, it is more verbose, but it is definitely clear that x and y exist in the object since they are explicitly set

without, you might have something like this:

```dewy
Point = (x:number, y:number) => [
    __repr__ = () => 'Point({x}, {y})'
    __str__ = () => '({x}, {y})'
]
```

which is more concise, and I definitely appreciate not having to repeat yourself, since technically `x` and `y` are present in the scope (though technically it's 1 scope up from the obj literal?). The only confusing thing is what if you have arguments that you don't want to include in your object? when it's explicit, you are more flexible to specify the shape of your object, and have it take any construction arguments you want...

A thought on when you have arguments you don't want to include in the object: delete any terms you don't want

```dewy
Point = (x:number, y:number, verbose:bool=false) => [
    if verbose printl'hello world'
    del verbose

    __repr__ = () => 'Point({x}, {y})'
    __str__ = () => '({x}, {y})'
]
```

Or perhaps we can distinguish between implicit and explicit argument capturing via {[]} vs [].

```dewy
Point = (x:number, y:number) => []  // x and y are captured
Point = (x:number, y:number) => {[]}  // x and y are not captured
Point = (x:number, y:number) => {[let x = x let y = y]}  // x and y are captured
```

~~I think I'm still leaning towards requiring `let x = x` and `let y = y` in all cases.~~
Actually now I'm leaning towards one of the implicit versions. This last idea about wrapping with {} to make any arguments not captured I think is actually pretty good, just requires working out the semantics

## Literal arguments in functions OR literals as type annotations

for example if you wanted to define the factorial function via operator overloading, where normal arguments are integer, and the base case is a literal 1, perhaps it might be something like this:

```dewy
fact = n:1 => n
fact |= n:int => n * fact(n-1)

```
