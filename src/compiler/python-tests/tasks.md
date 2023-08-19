[tasks]
- split repo into branches with C version, python version, and perhaps any other old versions. Current python work goes on main at top level
- rename .type property on AST classes to basetype or default type. Add a type function which does a runtime check of the type
    - really need to make a type matrix for representing results of all the operators on pairs of every combination of types
- post tokanization steps:
    - combining chains of operators into opchains (e.g. x^/-2, needs to chain the ^/- into a single op)
    - wrap up conditional/etc. blocks into a single token
        - create `class Flow_t()` for holding the groups
        - if <chain> <chain> (optional else <chain>)
        - loop <chain> <chain> (optional else <chain>)
    - also dewy.py needs to be modified to accomodate `Flow()`, containing sequence of `If()`/`Loop()`
- handling scope while parsing: parsing needs to be chain by chain, namely if a an expression binds a value to an identifier, later expressions should be able to get the type of that identifier!
- probably make identifier not a prototype, and instead anything that uses identifiers uses them instead of python strings
    - e.g. Bind(Identifier, AST), Call(Identifier), etc.
- Arrays should create a new scope for their contents
- `else` should maybe be a binary operator that operates on flow clauses (if/loop/compound)

- chainer functions:
    def bundle_conditionals(tokens:list[Token]):
    def chain_operators(tokens:list[Token]):
    def desugar_ranges(tokens:list[Token]): #insert operands on left/right of range if they were omitted
- some sort of process to freeze all lists after chaining so that they can be cached
- parser functions:
    @cache
    def typeof(tokens: list[Token]) -> Type: #this should be the same type system used in the interpreter!
        # recursively determine the type of the sequence of tokens
        # follow a similar process to parsing, breaking down the expressions, etc.
    
    @cache
    def split_by_lowest_precedence(tokens: list[Token]) -> tuple[list[Token], Token, list[Token]]:
        # self explanatory

    @cache
    def parse(tokens: list[token]) -> AST:
    