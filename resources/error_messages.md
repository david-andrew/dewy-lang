## ranges with tuples that are not size 2
```
a, myrange = 1, 2,4..10
```
ranges may have either an expression that evaluates to a single rangable value, or a tuple of size 2. If we ever parse a tuple with a different size juxtaposed to a range, it is an error. **Point out** that the user probably meant to wrap their range so that the extra tuple part is separated from the range
```
a, myrange = 1, [2,4..10]
```



## Using commas when providing arguments to a function
```dewy
f3 = (x y z) => x + y + z 

```
In most languages the call for `f3` would look like `f3(5, 6, 7)`. But in dewy, commas construct a tuple, and are not used for separating arguments to a function. Arguments are separated with spaces e.g. `f3(5 6 7)`. **Point out** If the user calls a function with not enough arguments, and the argument they passed in is a tuple, then they probably didn't mean to put the commas