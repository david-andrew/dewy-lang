from typing import Generator

from .syntax import (
    AST
)
from .tokenizer import (
    Token
)

import pdb


"""
TODO:
- work out Scope
- work out typing so that we can determine what are functions as we parse.
   ---> functions are the main distinction for which precedence to use for juxtaposition
"""


def top_level_parse(tokens: list[Token]) -> AST:
    """Main entrypoint to kick off parsing a sequence of tokens"""
    pdb.set_trace()
    raise NotImplementedError


class Scope:
    ...


def parse(tokens: list[Token], scope: Scope) -> Generator[AST, None, None]:
    """
    Parse all tokens into a sequence of ASTs
    """
    pdb.set_trace()
    raise NotImplementedError
