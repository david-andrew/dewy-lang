[tasks]
- split repo into branches with C version, python version, and perhaps any other old versions. Current python work goes on main at top level
- probably make identifier not a prototype, and instead anything that uses identifiers uses them instead of python strings
    - e.g. Bind(Identifier, AST), Call(Identifier), etc.
- rename .type property on AST classes to basetype or default type. Add a type function which does a runtime check of the type
- post tokanization steps:
    - combining chains of operators into opchains (e.g. x^/-2, needs to chain the ^/- into a single op)
    - wrap up conditional/etc. blocks into a single token
        - create `class Flow_t()` for holding the groups
        - if <chain> <chain> (optional else <chain>)
        - loop <chain> <chain> (optional else <chain>)

- Arrays should allow specifying new scope or no new scope

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
    