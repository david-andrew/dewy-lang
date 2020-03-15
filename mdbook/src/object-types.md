# Object Types


## TODO

Object types are basically just blocks of code bound to a variable

```
my_obj = {
    a = 'apple'
    b = 'banana'
    c = 'cat'
}
```

You can access the members of the object using the `.` accessor

```
my_obj.a  //returns 'apple'
my_obj.c  //returns 'cat'
```


To create an object constructor (like many languages have classes that you can instantiate) we create a function that returns an object


```
constructor = (param1, param2) => {
    return {
        p1 = param1
        p2 = param2
    }
}

my_obj = constructor(42, 'pi')
my_obj.p1  //returns 42
my_obj.p2  //returns 'pi'
```

You can also store functions inside of objects, allowing objects to completely cover regular object behaviors from other languages

```
constructor = (param1, param2) => {
    return {
        p1 = param1
        p2 = param2
        func = () => printl('p1 is {p1} and p2 is {p2}') 
    }
}
```

TBD on if there will be a `this` parameter, or if you just directly refer to parameters inside of the scope of the object. I think it may make sense to not have a `this`, as objects are really just a series of bindings in a shared scope. This does have implications for lazy vs eager loading of variables that are captured in functions--this implies that parameters are lazily loaded, thus allowing any changes in object parameters to be reflected by the change in output from the function. Otherwise if externally referenced parameters were frozen in functions, then the example `func` from above would only ever have the initial values of `p1` and `p2`. TBD on how `param1` and `param2` would work in the body of the function--they would probably just be frozen to the values they had when they were passed in