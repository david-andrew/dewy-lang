from typing import Generator

from .syntax import (
    AST,
    Block
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


class Scope:

    # TODO: rest of implementation
    @staticmethod
    def default() -> 'Scope':
        # TODO: scope should include default functions for printl, print, readl, etc.
        return Scope()


def top_level_parse(tokens: list[Token]) -> AST:
    """Main entrypoint to kick off parsing a sequence of tokens"""

    scope = Scope.default()

    items = [*parse(tokens, scope)]
    if len(items) == 1:
        return items[0]

    return Block(items, '{}')

    pdb.set_trace()
    raise NotImplementedError


def parse(tokens: list[Token], scope: Scope) -> Generator[AST, None, None]:
    """
    Parse all tokens into a sequence of ASTs
    """
    pdb.set_trace()
    raise NotImplementedError
