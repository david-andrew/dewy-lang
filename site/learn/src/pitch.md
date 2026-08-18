# Dewy

A strongly-typed, compiled, general-purpose language with strong STEM support.

## Everything is an expression

```dewy
phase = if temperature <? freezing
            'solid'
        else if temperature <? boiling
            'liquid'
        else
            'gas'

squares = [loop n in 1..10 n^2]

circumference = {
    diameter = 2 * radius
    pi * diameter
}
```

## One loop to rule them all

```dewy
loop true printl'hello'                     # infinite loop

loop i <? 10 { i += 1 }                     # while

loop fruit in ['apple' 'banana' 'peach']    # for-each
    printl'I like to eat {fruit}!'

loop i in 0.. and fruit in fruits           # combine iterators with `and`, `or`, etc.
    printl'{i}) {fruit}'
```

## Whitespace, not commas

```dewy
my_array = [1 2 3 4 5]

ratings = [
    'star trek' -> 89
    'star wars' -> 73
    'battlestar galactica' -> 92
    'stargate' -> 98
]

add = (a b) => a + b
add(40 2)
```

## Physical units built in

```dewy
mass = 10kg
velocity = 30(m/s)
energy = 1/2 * mass * velocity^2    # 4500 J

W = 20N * 10m * cos(45°)            # 141.42 J
8(km/h) + 20(m/s)                   # mixed units convert
2kg + 3m                            # error: mismatched dimensions

system.sleep(10seconds)
```

## Mathematics is ordinary code

```dewy
quadratic = (a b c x) => a(x^2) + b(x) + c    # juxtaposition multiplies
root1 = (-b + (b^2 - (4a)c)^/2) / 2a          # ^/2 is square root
root2 = (-b - (b^2 - (4a)c)^/2) / 2a

identity = sin(x)^2 + cos(x)^2                # juxtaposition calls

primes = [2 3 5 7 11 13 17 19 23 29 31 37 41 43 47 53 59 61 67 71 73 79 83 89 97]
mods = 20 .% primes                           # .op broadcasts elementwise

A = [
    1 2
    3 4
]
B = [0 1 ; 1 0]
C = A * B                                     # matrix multiplication
```

## Ranges are nice

```dewy
[1..5]      # 1 2 3 4 5     inclusive bounds
[1..5)      # 1 2 3 4       exclusive right (python style)
(1..5]      # 2 3 4 5       exclusive left
1..5        # bare range, same as [1..5]

[1,3..9]    # 1 3 5 7 9     step comes from the first pair
[5,4..0]    # 5 4 3 2 1 0   count down
0..         # 0 to infinity
..-10       # -infinity to -10
'a'..'z'    # any ordered type

5 in? (1..5)                # false

fullstring = 'this is a string'
substring = fullstring[3..end-3]    # 's is a str'
```

## Easy functional programming

```dewy
square = x => x^2

sum = (a b) => a + b
add5 = @sum(5)          # partial application
add5(24)                # 29
```

## Objects without a class sublanguage

```dewy
Point = (x:number y:number) => [
    mag = () => (x^2 + y^2)^/2
    show = () => printl'({x}, {y})'
]

p = Point(3 4)
p.mag                   # 5
```

## Types establish meaning

```dewy
count = 42                            # inferred as int
ratio:rational = 3/4                  # int <: rational <: real <: number

scale = (value:number factor:number):>number => value * factor
names:array<string> = ['Ada' 'Grace']
items:array<int|string> = [1 'two' 3] # parameterized type containing a union

identity = <T>(value:T):>T => value   # generic function

# overload a function
format = ((value:int):>string => 'integer')
       & ((value:string):>string => value)   

# overloads dispatch by argument type
format(42) 
format('life the universe and everything')
```

## Generators fall out of loops

```dewy
{ 1 2 3 }                       # a block expresses each value inside it
loop i in [1..5] i              # a loop expresses one value per iteration

[loop i in [1..5] i]            # [] captures what was expressed: [1 2 3 4 5]
sum([loop i in [1..5] i])       # or consume it directly: 15

[loop i in [1..3] { i i^2 }]    # multiple values per iteration: [1 1 2 4 3 9]
[loop i in [1..5] { i -> i^2 }] # -> pairs build a dict instead of an array

[                               # nesting builds higher dimensions
    loop i in [1..3]
    [loop j in [1..3] [i j]]
]
```