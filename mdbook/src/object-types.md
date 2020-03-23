# Object and Class Types


## TODO

Object types are basically just containers containing assigments of variables and functions

```
my_obj = [
    a = 'apple'
    b = 'banana'
    c = 'cat'
]
```

You can access the members of the object using the `.` accessor

```
my_obj.a  //returns 'apple'
my_obj.c  //returns 'cat'
```


To create an object constructor (like many languages have classes that you can instantiate) we create a function that returns an object


```
constructor = (param1, param2) => {
    return [
        p1 = param1
        p2 = param2
    ]
}

my_obj = constructor(42, 'pi')
my_obj.p1  //returns 42
my_obj.p2  //returns 'pi'
```

You can also store functions inside of objects, allowing objects to completely cover regular object behaviors from other languages

```
constructor = (param1, param2) => {
    return [
        p1 = param1
        p2 = param2
        func = () => printl('p1 is {p1} and p2 is {p2}') 
    ]
}
```

There will not be any sort of `this` or `self` parameter as in other languages to access an objects members from within itself/any contained functions. Instead because the functions are at the same scope as the declaration of the objects members, those members are available to the function. 

Note that here there is a meaningful distinction between referencing and copying a parameter within the function body.

```
//shorthand constructor declaration
my_class0 = (param1) => [
    p1 = param1
    func = () => printl('p1 is {p1}')
]

my_class1 = (param1) => [
    p1 = param1
    func = () => printl('p1 is {@p1}')
]

my_obj0 = my_class0('apple')
my_obj1 = my_class1('apple')

my_obj0.func  //prints 'p1 is apple'
my_obj1.func  //prints 'p1 is apple'

//change the member data for each object
my_obj0.p1 = 'pie'
my_obj1.p1 = 'pie'

//re-call func to see how the output changes
my_obj0.func  //prints 'p1 is apple'
my_obj1.func  //prints 'p1 is pie'

```

notice how when `func` doesn't reference the parameters using `@` that their original value gets printed, while using `@` means that the new updated value is used. This is because in the first instance, the parameters in the function are copied, while the second instance references the live parameter in the object scope.