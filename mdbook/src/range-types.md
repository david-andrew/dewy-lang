# Range Types

## Numeric ranges

Numeric ranges allow you to describe a range of real numbers

Inclusive and exclusive bounds on a range can be specified with `[]` i.e. open bounds, and `()` i.e. closed bounds. If no bounds are included, then the default is open bounds

```dewy
range1 = 1:5    // 1 2 3 4 5
range2 = (1:5)  // 2 3 4
range3 = (1:5]  // 2 3 4 5
range4 = [1:5)  // 1 2 3 4
range5 = [1:5]  // 1 2 3 4 5
```

Ranges are a convenient way to loop a specified number of times. The following prints `AppleBanana` 21 times

```dewy
loop i in 0:20
    printn('AppleBanana')
```

You can also check if a value falls within a specified range

```dewy
5 in? [1:5]         //returns true
5 in? (1:5)         //returns false
3.1415 in? (1:5)    //returns true 
```

Additionally you can construct more complex ranges by using arithmetic on basic ranges

```dewy
complex_range = [1:5] + (15:20)
loop i in complex_range
    printn(i)           //prints 1 2 3 4 5 16 17 18 19
7 in? complex_range     //returns false
16 in? complex_range    //returns true
```

The same range as above can be constructed using subtraction

```dewy
complex_range = [1:20) - (5:15]
```

### Ranges in loops

Ranges are commonly used in conjunction with loops

```
loop i in 0:5 { print('{i} ') }
```

The above will print `0 1 2 3 4 5 `. And to iterate over a list in reverse, you can simply reverse the range

```
loop i in range 5:0 { print('{i} ') }
```

This prints `5 4 3 2 1 0 `. To use non-integers for looping, probably use `linspace()`/`logspace()`. Considering a syntax as follows for ranges that are non-integer

```
//division version
loop i in [0:4]/4 { print('{i} ') }

//multiplication version
loop i in [0:4]*0.25 { print('{i} ') }
```

Both of which will print `'0 0.25 0.5 0.75 1 '`

## Ordinal Ranges

Ranges can also be constructed using any ordinal type. Currently the only only built in ordinal type other than numbers would be strings.

For example, the following range captures all characters in the range from `'a'` to `'z'` inclusive

```
ord_range = 'a':'z'
```

All alpahbetical characters might be represented like so

```
alpha_range = 'a':'z' + 'A':'Z'
ascii_range = 'A':'z' //this would include extra characters like '[\]^_{|}' etc.
```

But I probably won't just be limited to individual characters. In principle you ought to be able to do something like this

```
word_range = 'apple':'zebra'
'panda' in? word_range  //returns true
```

which would create a range that consists of every possible 5 letter combination starting from the word `'apple'` and iterating through to the word `'zebra'`. NOTE that this is distinct from every dictionary word in that range, as it will include many many gibberish words. 

TDB exactly what criteria will be used for ordering strings, as I like string orderings that respect numbers embedded in them (e.g. `'apple2'` should come before `'apple10'`), but that becomes difficult with arbitrary strings. perhaps there might be a macro setting for the ordering type used

## Indexing Sequences

ranges can be used to select values from a sequence. For example, say we want a substring we can do thw following

```dewy
full_string = 'this is a string'

substring = full_string[3:12]
printl(substring) //prints 's is a str'
```

This works for any sequence type. Note that the default range is inclusive (indicated by array indexing using square brackets). If you want to have exclusive bounds, simply wrap the range in parenthesis/brackets

```
full_string = 'this is a string'

substring1 = full_string[(3:12)]
substring2 = full_string[[3:12)]
substring3 = full_string[(3:12]]

printl(substring1) //prints ' is a st'
printl(substring2) //prints 's is a st'
printl(substring3) //prints ' is a str'
```

Note that all ranges used to index sequences must be integer ranges

Lastly, you can specify that a range starts from the beginning of the sequence, or continues to the end of the sequence using the special `_` (underscore) identifier

```
full_string = 'this is a string'

substring_to_end = full_string[3:_]
printl(substring_to_end) //prints 's is a string'

substring_from_start = full_string[_:12]
printl(substring_from_start) //prints 'this is a str'

whole_string = full_string[_:_] //selects the whole string
```

TBD on how inclusive/exclusive works with `_`. I'm inclined to think the underscore ignores inclusive/exclusive, and always selects the first/last element.

Also potentially can `_` be combined with math to select points near the endpoints? 

```
arr[_]     // last element
arr[_-1]   // second to last element
arr[5:_-3] // 5th element to 4th to last element
arr[_-3:_] // 4th to last element to last element
```

