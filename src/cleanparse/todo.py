"""
Tasks:
- next tokenization step for hello world: insert juxtapose
- finish whole parsing process for hello world happy path
- finish escape characters implementation to handle unicode and hex (requires ability to eat based numbers since variable width can use based numbers (or default to hex))
- 
"""




# For AST to src tracking
# start and stop indicate what tokens from the list[Token] the AST is made of
ast_src_map:dict[AST, Span] = {}




# Chain:TypeAlias = AST[Chained]
# def chain(tokens: list[Token]) -> list[Chain]: ...




# def tokenize(source: str) -> list[AST[Tokenized]]: ...
src = path.read_text()
ast = tokenize(src)
ast = post_process(ast)
ast = top_level_parse(ast)
ast = post_parse(ast)
ast = resolve(ast)
ast = typecheck(ast)


f"""
Tracking locations for debugging

token:
    src:str
    loc:Location
Chain:
    parent_tokens:list[token]
    ...
AST:
    parent_chains:list[chain]
    ...




When doing typecheck_and_resolve, I feel like we need a structure for tracking declarations present for each line of code


```
                        % () 
loop b in 1..10 (       % (b:int)             | (b:int a:int c:int) => (b:int a:int|void c:int|void)
    a = 1               % (b:int a:int)       | (b:int a:int c:int) => (b:int a:int c:int|void)
    c = 2               % (b:int a:int c:int)
)

```


perhaps it's a map for each AST in the tree
type_state: dict[AST, TypeStateLink/Node]
iteration order over an AST should maybe be the order that ASTs are executed?
then we could just iterate over the AST and for each node, make a new TypeState node linked to the previous 
(if there were any new entries), and we insert into the map with the current id(node) as key




final ASTs that make codegen easier
- no bare identifiers/typed identifiers. only express(name:str) or signature(name:str) or other specialized identifiers based on their context
---> no context should be necessary. All ASTs should be fully contextualized



FunctionLiteral:
    signature: FunctionSignature
    body: Body
    scope: Scope|None



TODO: some research around typechecking/maintaining scope for each AST in the sequence of the program
---> e.g. draw out some example programs, and trace what happens to the scope at each AST
---> especially of interest is cases that are non-linear, e.g. a variable doesn't exist on one iteration of a loop, but is present at the next, and so forth
"""



"""
Parsing algorithm:
do the simplest thing, basically what I was doing in the np prat example, but just do it with loops rather than parallelized!
while any shifts happened last time
    for non operator tokens
        determine if shifts left or right based on binding energy
        (TBD handling if Quantum. perhaps some sort of local bifurcation/copy once for both cases)

"""

