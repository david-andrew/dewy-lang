# WIP/Misc. Ideas

## Set literal notation

I would like to be able to create set literals without having to pass a list literal into the `Set` constructor. Problem is sets currently look like regular lists, and can't be distinguished. Here are some ideas for set literal notation:

`.` before each item in the set:

```dewy
my_set = [.'item1' .'item2' .'item3' .'etc']
```

`Set` before a list literal

```dewy
my_set = Set['item1' 'item2' 'item3' 'etc']
my_set = #set['item1' 'item2' 'item3' 'etc'] //or using hashtags
```

`$` before a list literal

```dewy
my_set = $['item1' 'item2' 'item3' 'etc']
```

```dewy
my_set = ['item1' \ 'item2' \ 'item3' \]
```

```dewy
my_set = ['item1'-- 'item2'-- 'item3'--]
```

tilde before each item

```dewy
my_set = [~'item1' ~'item2' ~'item3' ~'etc']
```


replace array new row punctuator `;` with `|` and then use `;` for set items. I think this sort of fits with how `;` is an expression surpresser, so it is sort of like surpressing the regular ability to access the items, but idk if it makes sense, b/c what if you want to make an array, but you need to perform some calculations that also happen to express a value (e.g. a function call that returns an unused value). Then how would you surpress the output of the function call without making the result look like a set item?

```dewy
my_set = ['item1'; 'item2'; 'item2'; ]
```


## Places whitespace isn't allowed

Basically these won't necessarily result in a syntax error, but they do not mean what the user might think they mean. Most of the time they should throw an error, but sometimes there are other constructs that they could be referring to

In between a member access:

```dewy
my_item.member  //okay
my_item .member //not okay
```

Depending on what I decide for set literal notation, the second one might be creating a set item.

In between a function name and it's arguments:

```dewy
my_func(arg1, arg2, arg3)  //okay
my_func (arg1, arg2, arg3) //not okay
```

Since some functions can be called with no parenthesis, the second case is ambiguous as to whether the function is called with no arguments, or with the arguments list given. If `my_func` has a no-arguments version, that one would be called, otherwise the compiler would throw a syntax error

Surrounding both sides of a loop

```dewy
//okay
{ /{block of code}/ }
loop true
{ /{block of code}/ }


//not okay
{ /{block of code}/ }

loop true

{ /{block of code}/ }

```

In the second case, it's ambiguous which block the loop attaches to, so the compiler will throw a syntax error. (potentially putting a `;` semicolon on either side of the loop line will tell it that it attaches to the block on the other side, regardless of whitespace...)

## Sections I need to add to docs

- how package management works (TODO->read about how julia & V package management works. also ideas about auto stl importing)