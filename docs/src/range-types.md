# Ranges

A range represents some span over a set of values. Typically ranges will be over numbers, however any orderable set could be used for a range (e.g. strings, dates, etc.). Ranges are frequently used for loops, indexing, and several other places.

Ranges always contain a `..` and may include left and or right values that are juxtaposed, optionally specifying the bounds and step size.

## Range Syntax

The syntax for ranges is inspired by Haskell syntax for ranges:

```dewy
[first..]               // first to inf
[first,second..]        // first to inf, step size is second-first
[first..last]           // first to last
[first,second..last]    // first to last, step size is second-first
[..2ndlast,last]        // -inf to last, step size is last-2ndlast
[..last]                // -inf to last
[..]                    // -inf to inf
```

Note that `[first..2ndlast,last]` is explicitly **NOT ALLOWED**, as it is covered by `[first,second..last]`, and can have unintuitive behavior.

In addition, ranges can have their bounds be inclusive or exclusive. Inclusive bounds are indicated by square brackets, and exclusive bounds are indicated by parenthesis. The default is inclusive bounds. Also left and right bounds can be specified independently, so you can have a range that is inclusive on the left and exclusive on the right, or vice versa.

```dewy
[first..last]   // first to last including first and last
[first..last)   // first to last including first, excluding last
(first..last]   // first to last excluding first, including last
(first..last)   // first to last excluding first and last
first..last     // same as [first..last]
```

### Juxtaposition
The left and right values are only considered part of the range if they are juxtaposed with the `..`. Values not juxtaposed with the range are considered separate expressions.

```dewy
first..last     // first to last
first ..last    // -inf to last. first is not part of the range
first.. last    // first to inf. last is not part of the range
first .. last   // -inf to inf. neither first or last are part of the range
```

Note that the range juxtaposition operator has relatively low precedence, so you can construct various common ranges without needing parenthesis.

```dewy
first..last+1           // first to last+1
first,second..last      // first to last, step size is second-first
first/2,first..last+10  // first/2 to last, step size is first/2
```

The juxtaposition requirement allows ranges to be used to index into matricies

```dewy
my_array = [
    0 1 2 3 4 5 6 7 8 9 
    10 11 12 13 14 15 16 17 18 19
    20 21 22 23 24 25 26 27 28 29
]
my_array[1.. 6..]     //returns [16 17 18 19; 26 27 28 29]
```


## Numeric Ranges

Probably the most common type of range will be a numeric ranges which describes a span over real numbers.

Some simple examples include:

```dewy
range1 = (1..5)  // 2 3 4
range2 = (1..5]  // 2 3 4 5
range3 = [1..5)  // 1 2 3 4
range4 = [1..5]  // 1 2 3 4 5
range5 = 1..5    // 1 2 3 4 5
```

## Ordinal Ranges

Ranges can also be constructed using any ordinal type. Currently the only only built in ordinal type other than numbers would be strings.

For example, the following range captures all characters in the range from `'a'` to `'z'` inclusive

```
ord_range = 'a'..'z'
```

All alpahbetical characters might be represented like so

```
alpha_range = 'a'..'z' + 'A'..'Z'
ascii_range = 'A'..'z' //this would include extra characters like '[\]^_{|}' etc.
```

But I probably won't just be limited to individual characters. In principle you ought to be able to do something like this

```
word_range = 'apple'..'zebra'
'panda' in? word_range  //returns true
```

which would create a range that consists of every possible 5 letter combination starting from the word `'apple'` and iterating through to the word `'zebra'`. NOTE that this is distinct from every dictionary word in that range, as it will include many many gibberish words. 

TDB exactly what criteria will be used for ordering strings, as I like string orderings that respect numbers embedded in them (e.g. `'apple2'` should come before `'apple10'`), but that becomes difficult with arbitrary strings. perhaps there might be a macro setting for the ordering type used


## Range Uses

Ranges have a variety of different uses in Dewy.

### Ranges in Loops

Probably the most common use is in conjunction with loops as a sequence to iterate over:

```dewy
loop i in 0..5 print'{i} '
```

The above will print `'0 1 2 3 4 5 '`.

To iterate over values in reverse, you can specify a reversed range:

```dewy
loop i in 5,4..0 print'{i} '
```

This prints `'5 4 3 2 1 0 '`. **Note:** when specifying a reversed range, you must include the step size. Forgetting to specify the step size will result in an empty range, as ranges are normally increasing.

### Range Arithmetic

Ranges can be used in arithmetic expressions, often as a way to construct new ranges.

```
//division version
loop i in [0..4]/4 print'{i} '

//multiplication version
loop i in [0..4]*0.25 print'{i} '
```

Both of which will print `'0 0.25 0.5 0.75 1 '`

These are both equivalent to directly constructing the range `0,0.25..4`, however the arithmetic versions are frequently more convenient.

This type of construction is closely related to the `linspace()`/`logspace()` functions in Dewy. TBD but `linspace`/`logspace` may in fact be implemented like so:

```dewy
linspace = (interval:range, n:int=10) => {
    start, stop = interval.start, interval.stop
    step = (stop-start)/(n-1)
    return interval.start,interval.start+step..interval.stop
}
logspace = (interval:range, n:int=10, base:real=10) => base^linspace(interval, n)
```

### Compound Range Construction

Additionally you can construct more complex ranges by combining together multiple ranges:

```dewy
complex_range = [1..5] + (15..20)
loop i in complex_range
    printn(i)           //prints 1 2 3 4 5 16 17 18 19
7 in? complex_range     //returns false
16 in? complex_range    //returns true
```

The same range as above can be constructed using subtraction

```dewy
complex_range = [1..20) - (5..15]
```

### Interval Membership

You can also check if a value falls within a specified range

```dewy
5 in? [1..5]         //returns true
5 in? (1..5)         //returns false
3.1415 in? (1..5)    //returns true 
```

### Indexing Sequences

ranges can be used to select values from a sequence. For example, say we want a substring we can do the following

```dewy
full_string = 'this is a string'

substring = full_string[3..12]
printl(substring) //prints 's is a str'
```

This works for any sequence type. **Note:** only integer ranges can be used to index into sequences (TBD if this might be relaxed to real valued ranges).

Also, because of juxtaposition, we can easily make the selection inclusive or exclusive on either side.

```
full_string = 'this is a string'

substring1 = full_string(3..12)  // ' is a st'
substring2 = full_string[3..12)  // 's is a st'
substring3 = full_string(3..12]  // ' is a str'
```


You can specify that a range continues to the end of the sequence, or starts from the beginning by omitting the value for that side. This will construct a range that goes to infinity in that direction, which will select all elements in that direction.

```
full_string = 'this is a string'

substring_to_end = full_string[3..] // 's is a string'
substring_from_start = full_string[..12] // 'this is a str'
whole_string = full_string[..] //selects the whole string
```

Paired with the special `end` token which represents the index of the last element in a sequence, this provides the means to select any desired subset of a sequence.

```
arr[end]      // last element
arr[end-1]    // second to last element
arr[..end-3]  // first element to 4th to last element
arr[5..end-3] // 5th element to 4th to last element
arr[end-3..]  // 4th to last element to last element
```