# Container Types

Container types are things like arrays, dictionaries, and sets. all containers are specified using square brackets `[]`, while the contents (or other factors) determine the type of container

## Arrays

An array is simple a list of values inside a container

```dewy
my_array = [0 1 2 3 'apple' 'banana' 'peach' true]
printn(my_array[3])  //prints '3'
```

Note that values do not need commas to separate them. Also arrays can contain objects of different types, though arrays as only a single type will be more efficient. Arrays are 0-indexed (with potentially the option to set an arbitrary index)

## Dictionaries

A dictionary is a list of key-value pairs

```dewy
my_dictionary = [
    'apple' -> 10
    'banana' -> 15
    'peach' -> 3
    'pear' -> 6
]
printn(my_dictionary['peach'])  //prints '3'
```

Again note the lack of a need for comma separation. (Potentially may add an option for using `<-` arrows in addition to `->` arrows, esp. b/c of `<->` arrows)

Additionally if you wish, you can define a bi-directional dictionary using a double-ended arrow:

```dewy
my_bidictionary = [
    0 <-> 'zero'
    1 <-> 'one'
    'two' <-> 2
    3 <-> 'three'
]
printn(my_bidictionary['three'])  //prints '3'
printn(my_bidictionary[3])        //prints 'three'
```

Note that to create an actual bidictionary, every arrow must by double-ended. As new elements are added, the bidictionary will maintain the bidirectional links between each element. Regular dictionaries will not maintin such links.

## Sets

A set is an unordered collection of elements. (TODO:determine set notation.)

For now, sets will probably be declared like so

```dewy
my_set = Set([0 1 2 3 'apple' 'banana' 'peach' true])
print(3 in? my_set)  //prints 'true'
print('pear' in? my_set)  //prints 'false'
```