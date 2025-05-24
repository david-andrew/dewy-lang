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

## inserting a new variable that shadows something used later
since dewy should be stored as an AST, it should be straightforward to identify instances when the user is inserting a new variable into some context, and the variable shadows something that comes later. Ths should be a warning that shows up until the user dismisses it.

For example, in the compiler, I was modifying the `compile_fn_literal` function, to take an extra parameter, and it turned out a same-named parameter was used later. So getting a warning there would have been good. In dewy it might look like:
```dewy
% original version
compile_fn_literal = (ast:FunctionLiteral|Closure scope:Scope module:QbeModule current_func:QbeFunction) => {
    fn_scope = Scope([scope...][-1])
    current_func = QbeFunction('tmp_fn', False, [], None, [QbeBlock('@start')])

    % ommitted parts %
    loop arg in args (
        match arg
            case Identifier(name as name)
                ... use name here as the identifier name ...
            % rest of cases omitted %
    )
}

% new version
compile_fn_literal = (ast:FunctionLiteral|Closure scope:Scope module:QbeModule current_func:QbeFunction name:str|undefined) => {
    fn_scope = Scope([scope...][-1])
    name = name ?? make_anonymous_fn_name
    current_func = QbeFunction(name, False, [], None, [QbeBlock('@start')])

    % ommitted parts %
    loop arg in args (
        match arg
            case Identifier(name as name)
                ... use name here as the identifier name ...
            % rest of cases omitted %
    )
}
```
Adding the name parameter and using it above should generate a warning since there is already usage of it below. Note that this kind of warning is sort of ephemeral, e.g. if the code had been written this way from scratch, no such warning would be generated. It is only because of new stuff shadowing existing stuff that the warning would show up.
> note even though the warning is ephemeral, it should be present until the user explicitly dismisses it. So it should remain between sessions (perhaps in __dewycache__ there can live a file tracking such ephemeral warnings/errors, and also probably keeping a history of those that were dismissed/fixed)

## TBD other shadowing warnings
...
