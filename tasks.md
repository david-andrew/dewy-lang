[tasks]
- make all operator tokens inherit from operator_t, rather than just token. this should simplify some of the type checks that want to know if something is an operator
- make tuple an actual class that inherits from array rather than a PrototypeAST. Tuples are just const arrays, but some contexts expect them (namely as args function declarations, and as multiple arguments for functions that take more than 1 argument)
- overhaul the docs
    - add a hello many world entry that uses matrices, e.g. 6-DoF robot arm forward kinematics
- pull out the old old python expression parser from the git history into its own branch
- handling scope while parsing: parsing needs to be chain by chain, namely if a an expression binds a value to an identifier, later expressions should be able to get the type of that identifier!
- include exmaple programs that do and don't work in the README. ideally this would be automated, e.g. on push, it would try to run them, and see if it is successful/has the correct output, vs raises exception/prints (pdb)
- rename .type property on AST classes to basetype or default type. Add a type function which does a runtime check of the type
    - really need to make a type matrix for representing results of all the operators on pairs of every combination of types
- post tokanization steps:
    - combining chains of operators into opchains (e.g. x^/-2, needs to chain the ^/- into a single op)
- probably make identifier not a prototype, and instead anything that uses identifiers uses them instead of python strings
    - e.g. Bind(Identifier, AST), Call(Identifier), etc.
- Arrays should create a new scope for their contents
- some sort of process to freeze all lists after chaining so that they can be cached
- handling whitespace in matrix literals. As is, all whitespace is removed, but we need it to be able to parse 2D matrices correctly. e.g.:
    
    ```
    mat = [
        1 2 3
        4 5 6
        7 8 9
    ]
    ``` 
    (seems like my original idea was to use the token coordinates to figure this part out)

- also handling `;` for higher dimensional tensor literals (see julia syntax for example). Perhaps `;` wraps whatever expression it attaches to in something like `Colonize(expr)`, and then in most cases, that evaluates to `void`, but inside of an array, the array replaces `Colonize()` with the inner expression, and counts the number of `Colonize()` layers for determining how many dimensions the next line is offset by
- ... shouldn't be an operator, it should be a literal. When ... is juxtaposed with something it does the unpacking, but when it is by itself, it is a literal ellipsis
Operators to add:
    - polar angle operator `∠` for constructing complex numbers, e.g. `7.81 ∠ 230.19°`. potentially also allow for keyword `angle`
    - dot/cross product operators
    - tensor product operator `⊗`
    - square root operator `√`
- add a `end` literal that can be tokenized/parsed. It will be mainly used for relative indexing from the end of a sequence, e.g. `arr[end-1]` to get the second to last element of an array.
- add an `inf` literal
- handling range syntax. probably make `..` non-juxtaposable, which means any juxtaposes next to it are deleted (or perhaps converted to a range_jux which has super low precedence). Then figure out how to parse `first, second .. final` style syntax. perhaps have a custom range_cat operator with the lowest precedence that concatenates expressions next to it into the range (if any are present, or voids should have been put in their place)