[tasks]
- rename .type property on AST classes to basetype or default type. Add a type function which does a runtime check of the type
- make Call take a tuple, where bound args are just bind expressions



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
    