# Range Types

Ranges allow you to describe a range of numbers

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