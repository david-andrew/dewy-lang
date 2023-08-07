[tasks]
- builtins should take the exact type that they are, e.g. callable<[str], undefined>
- write out basic type graph, including just callables
  - can do numbers/etc later
- test type graph and is_instance descendancy checks





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
    