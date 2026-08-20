# Container Types

Arrays, dictionaries, and sets all use square brackets `[]`. The contents
decide which container you get. Objects also use `[]`; they have
[their own page](object-types.md).

Values in a container are separated by whitespace, not commas.

## Arrays

An array is an ordered list of values:

```dewy
my_array = [0 1 2 3 'apple' 'banana' 'peach' true]
printl'{my_array[3]}'    # 3
```

Arrays are 0-indexed. Same-type arrays are the common case and the fast
one. You can write the type explicitly:

```dewy
names:array<string> = ['Ada' 'Grace']
let pair:array<int64 length=2> = [10 20]
pair.length
pair[end]
pair[0..1]
```

A semicolon starts a new dimension. Matrices are still arrays:

```dewy
A = [
    1 2
    3 4
]
B = [0 1 ; 1 0]
```

[Linear Algebra](linear-algebra.md) covers multiply and broadcast.

## Dictionaries

A dictionary is a list of key-value pairs joined by `->`:

```dewy
my_dictionary = [
    'apple' -> 10
    'banana' -> 15
    'peach' -> 3
    'pear' -> 6
]
printl'{my_dictionary['peach']}'    # 3
```

`<->` makes it bidirectional. Every pair in that literal has to be
`<->`. Lookup works from either side:

```dewy
my_bidictionary = [
    0 <-> 'zero'
    1 <-> 'one'
    'two' <-> 2
    3 <-> 'three'
]
my_bidictionary['three']    # 3
my_bidictionary[3]          # 'three'
```

## Sets

A set is an unordered collection:

```dewy
my_set = set[0 1 2 3 'apple' 'banana' 'peach' true]
3 in? my_set        # true
'pear' in? my_set   # false
```

## Objects

An object is a container of named fields. Field assignments use `=` at
the top level of `[]`. Empty `[]` is not an object.

```dewy
my_obj = [
    apples = 5
    bananas = 0.89
    buy_bananas = q => q * bananas
]
my_obj.apples
my_obj.buy_bananas(10)
```
