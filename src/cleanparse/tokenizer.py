from . import errors

from typing import Generic, TypeAlias, TypeVar
from abc import ABC
from dataclasses import dataclass
from pathlib import Path

class Phase(ABC):
    def __init_subclass__(cls) -> None:
        """ensure that each subclass of Phase, itself can only have one at most one subclass, all in one single inheritance chain"""
        super().__init_subclass__()
        for base in cls.__bases__:
            if not issubclass(base, Phase): continue
            existing = getattr(base, "_single_child", None)
            if existing is not None and existing is not cls:
                raise TypeError(f"{base.__name__} already has a direct subclass {existing.__name__}; cannot subclass it again with {cls.__name__}")
            base._single_child = cls


class Tokenized(Phase): ...
class Chained(Tokenized): ...
class Parsed(Chained): ...
class Resolved(Parsed): ...
class Typechecked(Resolved): ...
# etc phases



T = TypeVar('T', bound=Phase)
class AST(Generic[T], ABC): ...


# For Token to src tracking
# map from tokens to the index it is in the list[Token]
tok_idx_max:dict[Token, int] = {}

# For AST to src tracking
# start and stop indicate what tokens from the list[Token] the AST is made of
ast_src_map:dict[AST, Span[Token]] = {}



Token:TypeAlias = AST[Tokenized]

class Identifier(Token): ...
class StringQuote(Token): ...
class StringChars(Token): ...
class StringEscape(Token): ...
class StringInterpolationOpen(Token): ...
class StringInterpolationClose(Token): ...



"""
printf'Hello, World!'
   __/\__
"""

def tokenize(source: str) -> list[Token]: ...
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

