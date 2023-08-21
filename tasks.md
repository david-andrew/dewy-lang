[tasks]
- overhaul the docs
    - look into moving the docs build folder into mdbook folder if possible. should be `docs/` -> `docs/build/`, and `mdbook/` -> `docs/`
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
- also handling `;` for higher dimensional tensor literals (see julia syntax for example). Perhaps `;` wraps whatever expression it attaches to in something like `Colonize(expr)`, and then in most cases, that evaluates to `void`, but inside of an array, the array replaces `Colonize()` with the inner expression, and counts the number of `Colonize()` layers for determining how many dimensions the next line is offset by