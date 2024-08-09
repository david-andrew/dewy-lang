from typing import Generator, Sequence
from enum import Enum, auto
from dataclasses import dataclass

from .syntax import (
    AST,
    Block
)
from .tokenizer import (
    Token,
    Operator_t,
    ShiftOperator_t,
    Juxtapose_t,
    Comma_t,
)
from .postok import (
    RangeJuxtapose_t,
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


def parse(tokens: list[Token], scope: Scope) -> Generator[AST, None, None]:
    """
    Parse all tokens into a sequence of ASTs
    """
    pdb.set_trace()
    raise NotImplementedError


@dataclass
class qint:
    """
    quantum int for dealing with precedences that are multiple values at the same time
    qint's can only be strictly greater or strictly less than other values. Otherwise it's ambiguous
    """
    values: set[int]

    def __gt__(self, other: 'int|qint') -> bool:
        if isinstance(other, int):
            return all(v > other for v in self.values)
        return all(v > other for v in self.values)

    def __lt__(self, other: 'int|qint') -> bool:
        if isinstance(other, int):
            return all(v < other for v in self.values)
        return all(v < other for v in self.values)

    def __ge__(self, other: 'int|qint') -> bool: return self.__gt__(other)
    def __le__(self, other: 'int|qint') -> bool: return self.__lt__(other)
    def __eq__(self, other: 'int|qint') -> bool: return False


######### Operator Precedence Table #########
# TODO: class for compund operators, e.g. += -= .+= .-= not=? not>? etc.
# TODO: how to handle unary operators in the table? perhaps make PrefixOperator_t/PostfixOperator_t classes?
# TODO: add specification of associativity for each row
class Associativity(Enum):
    left = auto()  # left-to-right
    right = auto()  # right-to-left
    prefix = auto()
    postfix = auto()
    none = auto()
    fail = auto()


operator_groups: list[tuple[Associativity, Sequence[Operator_t]]] = list(reversed([
    (Associativity.prefix, [Operator_t('@')]),
    (Associativity.left, [Operator_t('.'), Juxtapose_t(None)]),  # jux-call, jux-index
    (Associativity.prefix, [Operator_t('not')]),
    (Associativity.right,  [Operator_t('^')]),
    (Associativity.left, [Juxtapose_t(None)]),  # jux-multiply
    (Associativity.left, [Operator_t('*'), Operator_t('/'), Operator_t('%')]),
    (Associativity.left, [Operator_t('+'), Operator_t('-')]),
    (Associativity.left, [ShiftOperator_t('<<'), ShiftOperator_t('>>'), ShiftOperator_t(
        '<<<'), ShiftOperator_t('>>>'), ShiftOperator_t('<<!'), ShiftOperator_t('!>>')]),
    (Associativity.none, [Operator_t('in')]),
    (Associativity.left, [Operator_t('=?'), Operator_t('>?'), Operator_t('<?'), Operator_t('>=?'), Operator_t('<=?')]),
    (Associativity.left, [Operator_t('and'), Operator_t('nand'), Operator_t('&')]),
    (Associativity.left, [Operator_t('xor'), Operator_t('xnor')]),
    (Associativity.left, [Operator_t('or'), Operator_t('nor'), Operator_t('|')]),
    (Associativity.none,  [Comma_t(None)]),
    (Associativity.left, [RangeJuxtapose_t(None)]),  # jux-range
    (Associativity.right,  [Operator_t('=>')]),  # () => () => () => 42
    (Associativity.fail,  [Operator_t('=')]),
    (Associativity.none,  [Operator_t('else')]),
]))
precedence_table: dict[Operator_t, int | qint] = {}
associativity_table: dict[int, Associativity] = {}
for i, (assoc, group) in enumerate(operator_groups):

    # mark precedence level i as the specified associativity
    associativity_table[i] = assoc

    # insert all ops in the row into the precedence table at precedence level i
    for op in group:
        if op not in precedence_table:
            precedence_table[op] = i
            continue

        val = precedence_table[op]
        if isinstance(val, int):
            precedence_table[op] = qint({val, i})
        else:
            precedence_table[op] = qint(val.values | {i})


def operator_precedence(op: Operator_t | ShiftOperator_t | Juxtapose_t | Comma_t) -> int | qint:
    """
    precedence:
    [HIGHEST]
    (prefix) @
    . <jux call> <jux index access>
    (prefix) not ...
    (postfix) ? `
    ^                                   //right-associative
    <jux mul>
    / * %
    + -
    << >> <<< >>> <<! !>>
    in
    =? >? <? >=? <=? not=? <=> is? isnt? @?
    and nand &
    xor xnor                            //following C's precedence: and > xor > or
    or nor |
    ,                                   //tuple maker
    <jux range>                         //e.g. [first,second..last]
    =>
    = .= <op>= .<op>=  (e.g. += .+=)    //right-associative (but technically causes a type error since assignments can't be chained)
    else
    (postfix) ;
    <seq> (i.e. space)
    [LOWEST]

    TODO:
    - add operators: as transmute |> <| -> <-> <- :

    [Notes]
    .. for ranges is not an operator, it is an expression. it uses juxtapose to bind to left/right arguments (or empty), and type-checks left and right
    if-else-loop chain expr is more like a single unit, so it doesn't really have a precedence. but they act like they have the lowest precedence since the expressions they capture will be full chains only broken by space/seq
    the unary versions of + - * / % have the same precedence as their binary versions
    """

    # TODO: handling compound operators like +=, .+=, etc.
    # if isinstance(op, CompoundOperator_t):
    #     op = op.base

    try:
        return precedence_table[op]
    except:
        raise ValueError(f"ERROR: expected operator, got {op=}") from None


def operator_associativity(op: Operator_t | ShiftOperator_t | Juxtapose_t | Comma_t | int) -> Associativity:
    if not isinstance(op, int):
        i = operator_precedence(op)
        assert isinstance(i, int), f'Cannot determine associativity of operator ({
            op}) with multiple precedence levels ({i})'
    else:
        i = op
    try:
        return associativity_table[i]
    except:
        raise ValueError(f"Error: failed to determine associativity for operator {op}") from None
