# Container Types

Container types are things like arrays, dictionaries, and sets. all containers are specified using square brackets `[]`, while the contents (or other factors) determine the type of container

## Arrays

An array is simple a list of values inside a container

```dewy
my_array = [0 1 2 3 'apple' 'banana' 'peach' true]
printl(my_array[3])  %prints '3'
```

> Note: values do not need commas to separate them. Also arrays can contain objects of different types, though arrays where all values are just a single type will be more efficient. Arrays are 0-indexed (with potentially the option to set an arbitrary index)

TODO->explain how to make matrices and other linear algebra stuff.

## Dictionaries

A dictionary is a list of key-value pairs

```dewy
my_dictionary = [
    'apple' -> 10
    'banana' -> 15
    'peach' -> 3
    'pear' -> 6
]
printl(my_dictionary['peach'])  %prints '3'
```

Again note the lack of a need for comma separation between key-value pairs.

Additionally if you wish, you can define a bi-directional dictionary using a double-ended arrow:

```dewy
my_bidictionary = [
    0 <-> 'zero'
    1 <-> 'one'
    'two' <-> 2
    3 <-> 'three'
]
printl(my_bidictionary['three'])  %prints '3'
printl(my_bidictionary[3])        %prints 'three'
```

> Note: when creating a bidictionary, every arrow must by double-ended. As new elements are added, the bidictionary will maintain the bidirectional links between each element. Regular dictionaries will not maintin such links.

## Sets

A set is an unordered collection of elements

```dewy
my_set = set[0 1 2 3 'apple' 'banana' 'peach' true]
printl(3 in? my_set)  %prints 'true'
printl('pear' in? my_set)  %prints 'false'
```


## Objects

See the entry on **Object and Class Types** for more details. But breifly, an object can be created by wrapping declarations in a container

```dewy
my_obj = [
    apple = 5
    bananas = 0.89
    buy_apples = q => q * apples
    buy_bananas = q => q * bananas
]

printl(my_obj.apples) %prints out 5
printl(my_obj.buy_bananas(10))  %prints out 8.9
```
