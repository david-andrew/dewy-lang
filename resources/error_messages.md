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


Actually no that we've made commas just syntactic sugar for groups i.e. `a, b, c` -> `(a b c)`, this error might not be relevant anymore, TBD how the parser handles it. Basically if someone does `f3(5, 6, 7)` that becomes `f3((5 6 7))` which may or may not be valid. Keep an eye on this.


## Shadowing a variable after using it in a given scope
```dewy
let x: int = 5

{
    printl(x) // use x from the outer scope
    let x: str = "hello" // redeclare x
    // proceed to use x
}
```

Basically this should emit a warning, as in most cases user's probably want to use the value declared in the local scope. In the rare case that they wanted to use the outer value first, and then redeclare/shadow it, this works, but I think it's unidiomatic

## TBD other shadowing warnings
...

