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

Or perhaps a better idea is instead of dealing with \ and ;, we could use the type of the variable to coerce the shape to be whatever the user wants. Think of the initial version as shape underspecified, and then the type specification gives extra info on how to deal with the shape

```dewy
// this is a column vector
primes: int[1 10] = [
    2
    lazy i in [3, 5..)
        if i .% #ctx.primes .=? 0 |> @reduce(, (prev, v) => prev and v)
            i
][..10)


// this is a row vector
primes: int[10 1] = [
    2
    lazy i in [3, 5..)
        if i .% #ctx.primes .=? 0 |> @reduce(, (prev, v) => prev and v)
            i
][..10)
```


### is \ syntax or escaping a newline? [DONE: syntax]

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
row_vec = [1, 2, 3]

col_vec = [1 2 3]
col_vec = [1; 2; 3]
col_vec = [
    1
    2
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

## Ambiguous/Undecidable Parses

Because of the fact that juxtaposition can mean operations with different precedence levels, combined with the ability to have expressions that perform operations before expressing the value, it is possible to construct pathological examples that are unparsable:

```dewy
// undecidable if it should be case 1 or 2
{
  let A: int|fn = x=>x
  A(2)^(A=0 3)
}

// also maybe undecidable
(let A=x=>x A)2^(let A=0 3)
```

A(B)^C

case 1: left is fn, op is call
(A(B))^C

```
pow:
  C
  call:
    B
    A
```

By evaluating C first (since exponentiation is right associative), we convert A to a number, meaning that `call` is no longer the correct operation

case 2: left is value op is multiply
A\*(B^C)

```
mul:
  A
  pow:
    C
    B
```

If you assume that it is a multiply instead of a call, A is evaluated first due to multiplication being left associative, but then at that point, A is already defined before it can be modified by the rightmost block, so A is still a function, and therefore `mul` is the wrong operation.

This is a contradiction, and therefore the parse is undecidable. Such parses will raise an error on compilation. The main issue will be detecting such cases. I think the way to handle it is to pick the operation before the expression based on the current type of the expressions, and then if the precedence changes in the process of evaluating, it is a

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

~~Actually based on this video (https://www.youtube.com/watch?v=X6Jhxm1lPHY), I'm gonna switch the order of the thing being imported with the import path. So things would be:~~

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

on further thought, it's a weak argument, since sometimes you don't know what item to import but other times you don't know the name of where it is coming from (also IDEs are pretty good at giving you options in either case). So I think it's a wash, and the original allows us to unify all the syntax for imports with regular unpacking syntax.

## Unpack syntax

unpacking from a list:

```dewy
s = ['Hello' ['World' '!'] 5 10]

[a b c d] = s
[a ...b] = s
[...a b] = s
[a [b c] ...d] = s
```

unpacking from an object with named fields:

```dewy
o = [apple=1 banana=2 carrot=3]

[apple banana carrot] = o
[apple] = o
[apple carrot] = o
[carrot] = o
// [apple ...rest] = o //apple = 1, rest = [banana=2 carrot=3] //TBD if this is allowed


o2 = [apple=1 banana=[carrot=3 durian=4] eggplant=5 pear=6]

[apple banana eggplant pear] = o2
[apple [carrot durian]=banana eggplant pear] = o2
[a=apple b=banana c=eggplant d=pear] = o2
[apple [c=carrot durian]=banana] = o2
```

unpacking from a map:

```dewy
m = ['apple' -> 1 'banana' -> 2 'carrot' -> 3]

// not sure about the semantics of this one.. Perhaps it is like this:
[a b c] = m.['apple' 'banana' 'carrot']
[a c] = m.['apple' 'carrot']
//[a c ...rest] = m.['apple' 'carrot' ...] not sure if this syntax works here...
[[k1 v1] [k2 v2] ...rest] = m   // k1='apple' v1=1 k2='banana' v2=2 rest=['carrot'->3]
[p1 p2 p3] = m                  //p1='apple'->1 p2='banana'->2 p3='carrot'->3
```

incidentally, this is how you'd do a swap

```dewy
[a b] = [b a]
```

### Unpacking with type annotations

```dewy
const person = [
    name = 'John'
    age = 30
]

const p = person
const [name age] = person
const [name:string, age:number] = person
const [[l1, l2, ...letters] = name, age:number] = person
const [[l1:char, l2:char, ...letters:string] = name, age=number] = person
```

> Note: `char` is just `string<length=1>`

## Unifying imports, unpacks, and declarations [YES!]

```dewy
const bigthing = import p"bigthing.dewy"
let [something1 [sub1 sub2] = something2] = import p'path/to/file.dewy'
const [prop1 prop2] = myobj
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

## Precedence of comma vs assignment [conservative: comma has lower precedence than equals |OR| liberal: get rid of commas altogether and use space separation (or commas are optional)]. Maybe have it be easy to toggle between the two while parsing, to test which feels better

All the below discussion is old. It basically comes down to 2 options:

- comma has lower precedence than equals. Any cases where that is a problem, we wrap the expression in parenthesis
- comma has higher precedence than equals. we have a paradigm shift in syntax, where we just don't use commas is all cases, and instead use spaces. commas could be optional, and have the higher precedence than equals

The first case is better because it keeps the language closer to what people are used to, while only introducing a bit of inflexibility. I think case 2 definitely has some interesting possibilities, but it requires a pretty radical syntax shift. tbd if the syntax shift would feel natural / like dewy. Though it is true I have always been a bit uncertain about the point of the comma operator, since I've already removed from list/dict/etc. syntax.

---

There are situations when comma needs to have higher precedence than assignment, but also situations where it is the opposite:

```dewy
//comma needs lower precedence
foo = (a, b=1, c=2) => a+b+c

//comma needs higher precedence
a,b,c = 1,2,3

//comma needs lower precedence
myfunc = (a, b, c) => a+b+c
myfunc2 = (c) => myfunc(a=1, b=2)
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
// with list syntax
foo = [a b=5] => a + b
foo = [a:int b:int=5 c:int=10] => a + b + c
foo(a=5 b=10)

// or even just parentheses
foo = (a b=5) => a + b
foo = (a:int b:int=5 c:int=10) => a + b + c
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

Another two hot take are:

1. make the arguments list be space separated rather than comma separated
2. add `;` to the end of arguments that have a default value

```dewy
foo = (a:int b:int=1 c:int=2) => a+b+c

//or

foo = (a:int;, b:int=1;, c:int=2) => a+b+c
```

The second case works with the current syntax rules since `;` is the end of an expression. But it is a bit obnoxious. The first case is a bit more elegant, but it's unconventional and not clear if people would adapt to it. Also it really changes a lot about the style of the language.

Another hot take is to have a different operator for handling unpacking. E.g. `as`

```dewy
foo = (a:int, b:int=1, c:int=2) => a+b+c
1, 2, 3 as a, b, c
```

## Should we get rid of the low precedence range juxtapose, and force ranges with step size to wrap the tuple in parenthesis, or should loops with multiple iterators require parenthesis around each iterator? [leaning remove need for commas in most situations]

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

### spaces instead of commas

Last Last alternative is to make arguments be space separated rather than comma separated, then we don't need to compromise on the precedence of comma

What might that look like in many instances:

```dewy
foo = (a:int b:int=1 c:int=2) => a+b+c
foo(5 10 15)

bar = (a b=1 c=2) => a+b+c
bar(5)
bar(5 c=20)

[a b c] = [1 2 3]
(a b c) = (1 2 3)
{a b c} = {1 2 3} // tbd how the scope around a b c affects things. If a, b, c exist already then they get reassigned, otherwise they only exist in the scope?

sum = (a b) => a + b
add5 = @sum(5)
thirtyseven = @add5(32)
sum_redux = (x y) => thirtyseven(a=x b=y)


r = first,second..last
r = [first,second..last]


Point = (x:number y:number) => [
    let x = x
    let y = y
    __repr__ = () => 'Point({x}, {y})'
    __str__ = () => '({x}, {y})'
]


f = (x:int y:int opflag:bool=void) => if opflag x + y else x - y
f(5 6) // compiler error
f(5 6 opflag=true) // 11



let g = (a:bool b:float ...args) => {
    printl'a: {a}, b: {b}'
    f(...args)
}

let f = (c:str d:int) => {
    printl'c: {c}, d: {d}'
}
```

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

I think I'm still leaning towards requiring `let x = x` and `let y = y` in all cases.
~~Actually now I'm leaning towards one of the implicit versions. This last idea about wrapping with {} to make any arguments not captured I think is actually pretty good, just requires working out the semantics~~

Basically, if you look at the case of creating an object without the function

```dewy
let x = 10

let obj = [
    y = 20
    f = () => x + y
]

obj.x // TBD if this is allowed or not
```

While it is clear that you can use `x` within the object, it is also maybe clear that you would not be able to do something like `obj.x` as `x` was not defined within the scope of the object

<!-- **although** actually maybe it would make sense to allow `obj.x` since perhaps the dot operator could just be looking up the scope chain for the variable `x`? It certainly makes the semantics simpler, since dot would then be just a proxy over the scope of the object. If you want to make an object that doesn't capture any of the surrounding scope, you would do something like:

```dewy
let x = 10

let obj = #noscope[
    y = 20
    f = () => 10 + y
]

obj.x // would fail
```

perhaps `{{}}` could be no-scope, e.g.

```dewy
let x = 10

let obj = {{[
    y = 20
    f = () => 10 + y
]}}
``` -->

On further thought, the notion that `.` could be accessing the entire scope of the object is sort of dumb. I think this is very similar to the concept of namespaces, and so I think that the ideas should be merged into a single concept. `let` inside of an object is what assigns something into that object's namespace. Without `let`, the object doesn't own the item, and therefor, there is no reason the member accesser `.` should be able to see things the object doesn't own. This way the semantics are very clear and unambiguous.

## Literal arguments in functions OR literals as type annotations

for example if you wanted to define the factorial function via operator overloading, where normal arguments are integer, and the base case is a literal 1, perhaps it might be something like this:

```dewy
fact = n:1 => n
fact |= n:int => n * fact(n-1)

```

## Arguments conventions for positional vs keyword [arguments without a default value are position only (allow both positional and keyword during partial evaluation), and must be provided to call. default-valued arguments are keyword only, and need not be provided. Use val=void to create a keyword value that must be overwritten by the user]

When defining a function, the following semantics will be used to manage how arguments are expected when calling the function:

- arguments without a default value are position only, and must be provided when calling
- default-valued arguments are keyword only, and need not be provided when calling
- positional and keyword arguments can be interspersed in the function definition, as well as the call. The only thing that matters is that the order of the positional arguments match up (keyword arguments, if any, can be in any order)

```dewy
// no arguments
f0 = () => 0 // can call with `f0` or `f0()`

// 1 positional argument
f1 = x => x + 1     // can call with `f1(5)`
f1b = (x) => x + 1  // can call with `f1b(5)`

// 1 optional keyword-only argument
f1c = (x=2) => x + 1 // can call with 'f1c' or `f1c()` or `f1c(x=5)`

// 2 positional arguments
f2 = (x, y) => x + y // can call with `f2(5, 6)`

// 1 positional and 1 optional keyword-only argument
f2b = (x, y=2) => x + y // can call with `f2b(5)` or `f2b(5, y=6)`

// 3 positional arguments
f3 = (x, y, z) => x + y + z // can call with `f3(5, 6, 7)`
```

Also note that partial function evaluation follows the exact same semantics, it is just that the arguments will be bound without calling the function

```dewy
f1 = (x, y) => x + y
f1a = @f1(5) // f1a is now a function that takes 1 argument
f1b = @f1(5, 6) // f1b is now a function that takes 0 arguments
f1c = @f1(y=6) // TBD if this is allowed. referring to a positional argument by name, but only in partial evaluation?

f2 = (x, y=2) => x + y
f2a = @f2(5) // f2a is now a function that takes 0 arguments
f2b = @f2(y=6) // f2b is now a function that takes 1 argument
f2c = @f2(5, y=6) // f2c is now a function that takes 0 arguments
```

Though a question this brings up is that currently doing partial evaluation is a bit restricted for positional arguments, since you can't skip ahead and specify them by name... Perhaps non-default arguments can be given either by position or by name, but default arguments still must be given by name. Or perhaps partial evaluation gets a special exception where you can refer to positional arguments by name if you want to skip ahead

### val=void for a required keyword argument

If the library writer wants a value that is keyword-only, but force the user to overwrite it, they can use `val=void`. Since no value can actually be set to `void`, there will be a compiler error if the user does not overwrite it.

```dewy
f = (x:int, y:int, opflag:bool=void) => if opflag x + y else x - y
f(5, 6) // compiler error
f(5, 6, opflag=true) // 11

add = @f(opflag=true)
add(5, 6) // 11

sub = @f(opflag=false)
sub(5, 6) // -1
```

There will probably need to be a bit of type checking magic here since `opflag` could never actually be `void` so the typing should show it always being just a boolean. But perhaps this could be a convention that works with `void`


### Alternative for positional vs keyword and also handles capture

Could just make use of #labels inside of the arguments declaration to specify some arguments have special properties

```dewy
f = (#pos x:int y:int #kw opflag:bool #capture z) => if opflag z*(x + y) else z*(x - y)
f(5, 6, opflag=true, z=2) // 22
```

I think this might be the best in terms of flexibility without obtuse syntax, while also leaning into how arguments declarations are just regular groups of expressions. Additionally, a notation for capture fits nicely into this framework

The only thing that might be a bit tricky is allowing partial evaluation to play nicely with all these features.

Longer example
```dewy
f = (
    #pos
        x:int
        y:int
        z:int
    #kw
        opflag:bool
        verbose:bool=false
        scale:float=1.0
        weight:float=1.0
        precision:int=2
    #capture
        a
        b
        c
) => {
    //some implementation...
}
```

## function overloading and partial application

Just a note about how partial application would work on an overloaded function. Basically as arguments are added, the list of possible functions that match are narrowed down (and maintained in the new function object). Once all options are narrowed down to a single one, and all arguments have been provided, only then can the function be called

## Match case syntax

I'm thinking we make use of the existing `->` notation for match case, so we only need to add the `match` keyword

```dewy
match x {
    1 -> 'one'
    2 -> 'two'
    3 -> 'three'
    _ -> 'other'
}
```

But more interesting is that the left side can be an unpack pattern, also maybe use `=>` since it could be interpreted as a kind of function call (a bit weird though for literal values e.g. 5 => 'five')

```dewy
match x {
    [a b] => a + b
    [a b c] => a + b + c
    _ => 0
}
```

Though this is tricky because how do we distinguish between a list with two elements that we just named `a` and `b` and an object with members a and b (also for objects, what if you only want to match against part of it, e.g. it has some member named `a` of some specific type, but the rest doesn't matter?)

Probably keep `=>` since the left hand side is only ever used for declarations, so we know anything is specifying a literal pattern. If you want to match against values stored in variables, you might do something with `=?`
    
```dewy
myvar = 3

match x {
    [a b] => a + b
    [a b c =? myvar] => a + b + c  // only match if c is equal to myvar
    [a b c] => a + b + c           // any other cases with 3 elements
    _ => 0
}
```

I think this is starting to get into the full functionality provided by e.g. python's pattern matching, e.g. ability to match against types, specific values, etc. Also I think the case of matching a literal may actually be more like:

```dewy
match x {
    [a b] => a + b
    [a b 3] => a + b + c    // only match if c is equal to 3
    [a b c] => a + b + c
    5 => 'five'             // match against a literal
    _ => 0
}
```

A bit more work needs to go into distinguishing between the different types that may be unpacked, e.g. object vs array, etc., as well as how to match for specific types, etc.

## Debugging: Ability to dump program state at a point, and pick up from that point

Basically, when debugging, say it takes a lot of time/computation to get to a particular point in your code that you're debugging. There should be a way to dump the program state right before that point, and then subsequent debugging runs can pick up directly from that point without having to go through all the previous computation again

Think of it like a better version of a core dump. Ideally it would also include the relevant stack trace and what not.

```dewy
let x = 5

#dump_state
#restart_here
call_some_function()
```

Also should be able to do a debug mode where it automatically dumps the state on any exiting error (tbd since there aren't exceptions in dewy... but perhaps types marked as error types will trigger this behavior)

## Dewy Decorator syntax

python decorators are excellent, and I want to replicate their functionality and expressiveness in dewy. I think they might make use of the `<|` operator

```dewy

let decorator = (f) => (...args) => {
    printl'before'
    let result = f(...args)
    printl'after'
    return result
}

// simplest
let myfunc = (a, b) => a + b
let myfunc = decorator(myfunc)

// option 2
let myfunc = (a, b) => a + b
let myfunc |>= decorator

// in a single expression
let myfunc = decorator <|
    (a, b) => a + b
```

Technically all the options above are valid. As to which will be the most idiomatic, I'm leaning towards the first one, since it's the most explicit about what is happening. But the single expression version is also a good contender

Also decorator functions are welcome to take arguments the same way as in python--by making them a higher order function

```dewy
let decorator = (extra:bool) => (f) => (...args) => {
    if extra printl'extra'
    printl'before'
    let result = f(...args)
    printl'after'
    return result
}

let myfunc = decorator(true) <|
    (a, b) => a + b
```

## <| and |> are treated as a jux-call with super low precedence

Basically when doing post-tokenization, if we see a `<|` or `|>` we should replace them immediately with a jux-call (or jux-call-reversed) operator, but one with very low level precedence. This means that we don't need to take handles of the functions we want to use, since they are treated as juxtaposed (thus catching the function before it executes), even though they might not touching the operator.

Though perhaps there should be some consideration that the pipe operators are just regular operators, and so the left and the right operands get evaluated. In this case, any time you want to pipe into a function, you'd need to prefix the function with `@` to have a handle to the function so that it is not evaluated.

## Graphics + accelerated compute programming

compute and graphics support
long term goal: webgpu api directly implemented in dewy (i.e. apis for vulcan, metal, and directx)

in the meantime:

- [wgpu](https://wgpu.rs/) for a rust implementation we can hook into
- [C++ webgpu native tutorial](https://eliemichel.github.io/LearnWebGPU/getting-started/hello-webgpu.html)
  - seems like it calls a webgpu C api directly, which is more in line with what I think I want..

Also look into cuda, opencl, halide, etc. graphics accelerated compute libraries

## Scopes, capitalization, combination identifiers, aliases

### capitalization/case-insensitive identifiers

I think I'm not going to allow case-insensitive identifiers. Units written out will all just be lower case. Same with e.g. constants like `pi`, etc.

### combination identifiers

For handling units, I think scopes should support a form of dynamic lookup over combinations. The flow would be:

1. check the regular list of identifiers
1. if not found, perform the dynamic check over combination identifiers
   - combination identifiers should also get some sort of post processing when found (e.g. multiply prefix by unit)
1. if dynamic check finds a match, store the identifier in the regular list of identifiers and return the result
1. else lookup fails

e.g. `kilogram`. initially `kilogram` is not in the scope. so we do a dynamic lookup over si prefixes and units, and are able to construct kilogram from `kilo` and `gram`. `kilogram` is then computed as `kilo * gram` and stored in the regular scope as `kilogram`.

TBD how to declare a set of combination identifiers

```dewy
prefixes = ['kilo'-> 1e3 'mega' -> 1e6 'giga' -> 1e9 'tera' -> 1e12 ...]
units = ['gram' -> [1 0 0 0 0 0 0] 'meter' -> [0 1 0 0 0 0 0] 'second' -> [0 0 1 0 0 0 0] ...]

combo [prefixes.keys units.keys]: PhysicalNumber = (prefix, unit) => prefixes[prefix] * units[unit]
```

### aliases [handled just by doing `myalias = () => value`]

~~Aliases basically allow you to have multiple names pointing to the same underlying variable. Aliases can be declared via the `alias` keyword~~

```dewy
let meter = [0 1 0 0 0 0 0] //etc. some definition of a meter
alias metre = meter
alias m = meter
```

~~When performing the lookup of a variable in a scope, first check for regular identifiers, then check for aliases.~~

~~Ideally aliases and combination identifiers would play nice with each other, e.g. you could define all the written-out units+prefixes as a combo, and then set up aliases for each of them (e.g. the abbreviation, plural versions, etc), and it would all just work out~~

Aliases are not actually going to be a thing. Instead you can effectively create an alias by binding to a zero-argument function, e.g.

```dewy
let meter = [0 1 0 0 0 0 0]
let metre = () => meter
let m = () => meter
```

Since zero-arg functions can be called without parenthesis, it functions identically to how an alias might work. This is nice because it is very clear how the aliasing mechanics work, as a consequence of normal let/const declarations and function closures.

## Let, Const, Local [probably just use `const`, `let`, `local`, and maybe `fixed`]

The declaration keywords all have to do with what happens when trying to assign a value without the keyword

```dewy
let x = 5
x = 6 // allowed, x is now 6
{
    x = 7 // allowed, x in outer scope is now 7
}

const y = 5
y = 6 // not allowed, compile time error
{
    y = 7 // not allowed, compile time error
}

local z = 5 //local is a like const, but does not cause compile time error when trying to overwrite in lower scopes
z = 6 // not allowed, compile time error
{
    z = 7 // allowed. equivalent to let z = 7. in inner scope is now 7, outer scope is still 5
}
```

Local is useful for standard library values that users might want to use the same identifier for for a different purpose. E.g. `i`, `j`, `k` which by default are quaternion units, but user's frequently use them as loop indices. So at the standard library level, `i`, `j`, `k` would be declared as `local`.

Perhaps there is a better name instead of `local` though. `shadow`? Basically want something that explains that it is const, but can be overwritten in lower scopes. Other options are:

- `shadowable`
- `localconst`
- `constlocal`
- `locallet` //allows for having a const and let version of local
- `letlocal`
- `weakconst`
- `scopedconst`
- `scopeconst`
- `hereconst`
- `loco`

Lastly I'm considering one that has the name and type declaration `fixed` but allows for the value to be overwritten. This might be for cases of shared methods that the user can append onto, e.g. `__add__`. Though probably we won't allow users to access the value directly, but rather access them through a function for registering new methods

```dewy
fixed __add__:<T,U,V>callable<(a:T, b:U), V>
const register__add__ = (func:callable<(a:T, b:T), T>) => __add__ |= func
```

## Security design

TODO
in general memory safety is a given but other areas not handled by rust are important to consider:

- https://www.horizon3.ai/attack-research/attack-blogs/analysis-of-2023s-known-exploited-vulnerabilities/
- https://owasp.org/www-project-top-ten/
- https://www.ibm.com/reports/threat-intelligence
- jonathan blow on mitigating buffer overflow risks: https://www.youtube.com/watch?v=EJRdXxS_jqo

## closure explicit syntax for specifying what variables they capture

In C++, you can have a lambda that captures specific variables from the parent scope (perhaps not exactly correct syntax, from jonathan blow talk on about his hypothetical language):

```cpp
auto f = [y](float x) { return x + y; }
```

This is an interesting idea. As is, in dewy, functions have available to them all variables in the parent scope and up. But it might be a good idea to have a mechanism for restricting this to specific variables. Perhaps the default is access to all, or the default is access to none, and you have to opt in to access to all, or access to specific variables.

```dewy
let y = 5
let z = 10

let f = (x:float, #capture[y]) => x + y

let g = (x:float, #capture_all) => x + y + z
// let g = (x:float, #capture[y, z]) => x + y + z

// alternative syntax
let f = ([y], x:float) => x + y
let g = ([y, z], x:float) => x + y + z
let g = ([#all], x:float) => x + y + z


// jonathon blow suggests specifying the capture as part of the body rather than the function type
let f = (x:float) => #capture[y]{ x + y }
//let g = (x:float) => #capture_all{ x + y + z } //I think this is default, and therefore redundant
let g = (x:float) => #nocapture{ x + x*x + x*x*x }
```

More thought needed on the actual syntax, but I do think it's an important feature

## Compiletime execution

I think jai has it 100% correct in that you can run any language feature at compile time.
I'm thinking there could be 2 compiletime modes a user could select:

- interpreted
- jit-compiled

Both would execute the code at compiletime, and have results available for use at runtime-baked into the executable. Under this framework, nothing would be run at compiletime unless explicitly specified by the user (as opposed to what I was previously thinking which was we would try to intelligently figure out what to precompute).

I think the syntax might look something like this:

```dewy
main = () => {
    let x = 5
    let y = 6
    let z = #pre{ x + y }
    let q = #jit{ x + y }
}
```

where `#jit` and `#pre` syntactically behave like functions applying to the expression on the right. `#pre` is the interpreted version of compiletime actions, while jit is the jit-compiled version. The results of the compiletime expressions are then baked into the executable, i.e. we would be compiling the following for runtime:

```dewy
main = () => {
    let x = 5
    let y = 6
    let z = 11
    let q = 11
}
```

Also an orthogonal intersection with this; loading files is typically done by filename, but what if the user built a string at compiletime that would then be used to compile for runtime. I think that could be pretty powerful.

## Format string specifiers ["{fmt'.2f'(x)}"]

In python, you can format f-strings via certain format codes, e.g.

```python
x = 5.123456
print(f'{x:.2f}')
```

I like the idea of quick format strings, but we need to figure out how to make this kind of thing work with dewy's syntax. One idea is that there is a format function that you partially apply with the format string, and then it receives the format input, e.g. something like this:

```dewy

// defining formatter functions for each type
let f = (fmt:str, val:int): str => ... //some function for handling formatting ints
f |= (fmt:str, val:float): str => ... //some function for handling formatting floats
// etc. implementations of formatters


let x = 5.123456
printl'{x |> @f'.2f'}'
```

I think this actually looks pretty good, except for the fact that f is perhaps not the best name for the formatter function... But ideally it would be only a single letter long. If we make f a higher order function, we can get rid of the @, e.g.

```dewy
let f = (fmt:str) => (val:int): str => ... //some function for handling formatting ints
f |= (fmt:str) => (val:float): str => ... //some function for handling formatting floats
// etc. implementations of formatters

let x = 5.123
printl'{x |> f'.2f'}'
```

or some other options

```dewy
printl'{x |> fmt'.2f'}' //alternative name
printl'{fmt'.2f'(x)}' //alternative syntax
```

which actually I think is probably perfect.

Specific note about how I think this should be enforced,

```dewy
//somehow want to restrict T to be any concrete type that isn't `any`
const fmt_type = <<T>(pattern:str) => (val: T) => str>

//somehow fmt should not be reassignable, but you should be able to overload it. maybe we need something in addition to let/const...
const fmt = #overload(fmt_type)
fmt |= (pattern:str) => (val: int) => ...
fmt |= (pattern:str) => (val: float) => ...
// etc. formatters
```

## Argument Type Propogation for spread arguments

In python, you can use `*args`, and `**kwargs` to capture extra arguments and pass them further into functions. This is great, but it doesn't maintain type information at all, e.g.

```python
def g(a:bool, b:float, *args):
    #do something with a and b
    print(f'a: {a}, b: {b}')

    #do something with the rest of the arguments
    f(*args)

def f(c: str, d: int):
    print(f'c: {c}, d: {d}')
```

When you look at the type signature of `g`, it will say it takes `(a: bool, b: float, args: Any)`.

Dewy should properly propogate the types of the arguments, so that the type signature of `g` would actually be `(a: bool, b: float, c: str, d: int)`. Same idea with keyword arguments.

```dewy
let g = (a:bool, b:float, ...args) => {
    printl'a: {a}, b: {b}'
    f(...args)
}

let f = (c:str, d:int) => {
    printl'c: {c}, d: {d}'
}
```

TBD how hard it will be to handle this from the type checking point of view, but it is necessary for programmer convenience

Also tbd is the syntax for specifying `**kwargs`. Perhaps `...args` indicates any extra arguments, regardless of how they are specified.

## Strongly typed databases

I think databases are bad, and could use an overhaul that can integrate them into languages more seamlessly. On random idea I had was about representing data with its structure+type definitions in the same place. Here's an example I was working with for collecting chinese characters into a dataset

```dewy
let Word = [
    character: str
    pinyin: str
    english: str
    level: 'HSK1' | 'HSK2' | 'HSK3' | 'HSK4' | 'HSK5' | 'HSK6'
]

let data = csv<Word>'''
爱,ài,"to love; affection; to be fond of; to like","HSK1"
八,bā,"eight; 8","HSK1"
爸爸,bà ba,"father (informal); CL:个[ge4] ,位[wei4]","HSK1"
杯子,bēi zi,"cup; glass; CL:个[ge4] ,支[zhi1]","HSK1"
... etc.

''' // necessary to end the data with a delimiter
```

Some things that could be improved would be the necessity of having the ending quote. ideally we could just have something that says anything after this point is part of the data.

Perhaps we could do something more like this:

```dewy
let Word = [
    character: str
    pinyin: str
    english: str
    level: 'HSK1' | 'HSK2' | 'HSK3' | 'HSK4' | 'HSK5' | 'HSK6'
]

#data_start(csv<Word>) //could easily specify other plain-text data formats
爱,ài,"to love; affection; to be fond of; to like","HSK1"
八,bā,"eight; 8","HSK1"
爸爸,bà ba,"father (informal); CL:个[ge4] ,位[wei4]","HSK1"
杯子,bēi zi,"cup; glass; CL:个[ge4] ,支[zhi1]","HSK1"
... etc.
```

## Struct/Type definition syntax

I think wherever possible, type definitions should not use new syntax, but fit within what is already established.

### Structs

For example, I think struct definitions look like this:

```dewy
let vect3:type = [
    x:real
    y:real
    z:real
]

let p:vect3 = [x=1 y=2 z=3]
```

Basically a struct definition is just an object with a bunch of declared, but undefined fields. Then you can use that object to specify types for instances you're making.

I think this clashes a little bit with the construction for making a class/instance,

```dewy
let Vect3 = (x:real, y:real, z:real) => [
    x = x
    y = y
    z = z
]

let p = Vect3(1, 2, 3)
```

though that may just end up being a stylistic thing. TBD how types would be handled in the case of classes--the way I'm thinking is redundant, so perhaps there would be a shorthand

```dewy
let vect3:type = [
    x:real
    y:real
    z:real
]
let Vect3 = (x:real, y:real, z:real): vect3 => [
    x = x
    y = y
    z = z
]
```

Also something to think about is if you can include fields in a type that are already defined, e.g. with some default value, or perhaps methods, etc.

```dewy
let vect3:type = [
    x:real
    y:real
    z:real
    length = () => sqrt(x*x + y*y + z*z)
]


let p:vect3 = [x=1 y=2 z=3] //does p have `.length`?
```

Perhaps declaring types on fields can do extra work when a concrete value is assigned, e.g. when doing `p:vect3 = [x=1 y=2 z=3]`, perhaps under the hood, there is an implicit `vect3[x=1 y=2 z=3]` called which attaches all the predefined fields/methods/etc. to the object.

### Other types

For declaring types derived from other types, I'll have to think of more examples, but the main one I can think of is for integers with restricted ranges

```dewy
let x:int<range=[0..10]> = 5

let ascii:type = int<range=[0x20..0x7E)> //e.g. just printable ascii characters
```

where I think the fields you can set inside the `< >` are probably defined at struct definition time, something like this

```dewy
//probably lots more compiletime stuff that would happen with `int`, but this is the general idea
let int:type = [
    _value:#builtin... //perhaps this is a compiletime thing. and depending on the size of range, it makes it the smallest possible type

    //type properties
    range:range<int>=-inf..inf
    //etc...
]
```

### compiletime type definitions

TBD how this will work, but I think the most powerful types will be defined this way

## How do libraries work

see this discussion about jai for ideas: https://www.youtube.com/watch?v=3TwEaRZ4H3w

Points I like:

- single file libraries should be a thing. So a single file should be able to be completely packaged up without any other supporting files
- import flexibility for renaming stuff, making sure nothing overlaps
- everything is compiled in one go as if it's all one giant source file?
-

SomeLibrary.dewy

```dewy
//Example library
// any values to be used by the library, but not included in the export
let Y = 10
let other_stuff = () => ...

// Primary exported content
export const SomeLibrary = [
    let do_something = () => ...
    let something_else = () => ...
    let X = ...
    let Z = Y * other_stuff
]
```

```dewy
//from the main program
let [SL = SomeLibrary] = (import)p'SomeLibrary.dewy'

// calling into the library "namespace"
SL.do_something()
```

What if `import` was a function that wrapped `p` so you could do it like this:

```dewy
let SL = import'path/to/SomeLibrary.dewy'.SomeLibrary
let [SomeLibrary] = import'path/to/SomeLibrary.dewy'
```

TBD on import syntax, more thought needed...
What does import syntax need to accomplish

- path to library, or library name if it's from the standard library
- bringing in the library as it is named (ideally not having to repeat the name more than once)
- bringin in the library with a different name
- directly importing sub-members of the library
- spreading all members of the library into the current scope (ideally without having to name them all)

```dewy
// import math from standard library
let [math] = #STL

// import SomeLibrary from a file
let [SomeLibrary] = import'path/to/SomeLibrary.dewy'

// import all exported members of SomeLibrary.dewy into the current scope (equivalent to the above)
...import'path/to/SomeLibrary.dewy'

// import SomeLibrary with a different name
let [SL=SomeLibrary] = import'path/to/SomeLibrary.dewy'

// import sub-members of SomeLibrary
let [do_something, something_else] = import'path/to/SomeLibrary.dewy'.SomeLibrary

// equivalent to the above
let [[do_something, something_else] = SomeLibrary] = import'path/to/SomeLibrary.dewy'

// import all members of SomeLibrary into the current scope
// let [...SomeLibrary] = import'path/to/SomeLibrary.dewy' //TBD if this makes sense

// equivalent to the above
...import'path/to/SomeLibrary.dewy'.SomeLibrary
```

## Code Snippets as first class citizens

Very inspired by jai's macro system: https://www.youtube.com/watch?v=QX46eLqq1ps

Basically, in the same way that functions are fist class citizens and can be manipulated and passed around, a more primitive form of this is code snippets. Code snippets are any code, and can be inserted places, passed around, etc. I think in the grand scheme, functions should be semantically derived from code snippets, i.e. code snippets are a generalization over functions. Snippets are also hygenic as in jai, so declarations in a snippet don't interfere with declarations where it is inserted, unless you specify that they should.

```jai
for_expansion :: (array: $T/Bucket_Array, body: Code, pointer: bool, reverse: bool) #expand {
    `it_index := -1
    for <=reverse bucket, bi: array.all_buckets {
        for <=reverse *=(pointer||array.always_iterate_by_pointer) `it, i: bucket.data {
            if !bucket.occupied[i] continue;

            it_index += 1;
            #insert body(break=break bucket, remove={bucket.occupied[i]=false; bucket.count-=1;});
        }
    }
}
```

Probably manage code snippets with a `Code` type as in jai, and expand them with an `#expand` directive

```dewy
let s = #code {
    let y = 6
    x + y
}


let f = (x:int) => #expand(s)
```

Historically, I had been thinking about using backticks for code literals, but at the moment that intersects with the transpose operator...

TODO: more examples on this, I think it's very powerful. Also I think the syntax isn't final
