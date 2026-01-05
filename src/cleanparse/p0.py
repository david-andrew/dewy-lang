"""
Initial parsing pass. A simple pratt-style parser
"""

from typing import Sequence, Callable, TypeAlias
from dataclasses import dataclass
from enum import Enum, auto
from . import t1
from . import t2


Operator: TypeAlias = (
      t1.Operator
    | t2.Juxtapose
    | t2.RangeJuxtapose
    | t2.EllipsisJuxtapose
    | t2.TypeParamJuxtapose
    | t2.InvertedComparisonOp
    | t2.CombinedAssignmentOp
    | t2.BroadcastOp
    | t1.Semicolon
)


@dataclass
class qint:
    """
    quantum int for dealing with precedences that are multiple values at the same time
    qint's can only be strictly greater or strictly less than other values. Otherwise it's ambiguous
    In the case of ambiguous precedences, the symbol table is needed for helping resolve the ambiguity
    """
    values: set[int]

    def __post_init__(self):
        assert len(self.values) > 1, f'qint must have more than one value. Got {self.values}'

    def __gt__(self, other: 'int|qint') -> bool:
        return all(v > other for v in self.values)

    def __lt__(self, other: 'int|qint') -> bool:
        return all(v < other for v in self.values)

    def __ge__(self, other: 'int|qint') -> bool: return self.__gt__(other)
    def __le__(self, other: 'int|qint') -> bool: return self.__lt__(other)
    def __eq__(self, other: object) -> bool: return False
    def __add__(self, other: int) -> 'qint':
        if not isinstance(other, int):
            raise NotImplementedError(f'Cannot add qint to {other=}')
        return qint({v + other for v in self.values})
    def __sub__(self, other: int) -> 'qint':
        if not isinstance(other, int):
            raise NotImplementedError(f'Cannot subtract qint from {other=}')
        return qint({v - other for v in self.values})
    def __mul__(self, other: int) -> 'qint':
        if not isinstance(other, int):
            raise NotImplementedError(f'Cannot multiply qint by {other=}')
        return qint({v * other for v in self.values})
    def __idiv__(self, other: int) -> 'qint':
        if not isinstance(other, int):
            raise NotImplementedError(f'Cannot divide qint by {other=}')
        return qint({v // other for v in self.values})


class Associativity(Enum):
    left = auto()
    right = auto()
    prefix = auto()
    postfix = auto()
    none = auto()
    fail = auto()



BASE_BIND_POWER = 1   #TBD, but 0 probably for groups ()
NO_BIND = -1
def _convert_to_bp(precedence:int): 
    return BASE_BIND_POWER+2*precedence

bp_funcs: dict[Associativity, Callable[[int], tuple[int, int]]] = {
    Associativity.left: lambda precedence: (_convert_to_bp(precedence), _convert_to_bp(precedence)+1),
    Associativity.right: lambda precedence: (_convert_to_bp(precedence)+1, _convert_to_bp(precedence)),
    Associativity.prefix: lambda precedence: (_convert_to_bp(precedence), NO_BIND),
    Associativity.postfix: lambda precedence: (NO_BIND, _convert_to_bp(precedence)),
    # TBD about these ones... perhaps make them just have bind_power(precedence) for both sides
    Associativity.none: lambda precedence: (_convert_to_bp(precedence), _convert_to_bp(precedence)),
    Associativity.fail: lambda precedence: (_convert_to_bp(precedence), _convert_to_bp(precedence)),
}



"""
expressions that need to make sense given precedence table/rules:

-x-y      => (-x) - y
/x-y      => 1/x - y
/x/y      => (1/x)/y
-x/y      => 0 - x/y
-x^2      => -(x^2)
~A|B?     => (~A)|(B?)
-sin(x)^2 => -((sin(x))^2)
-a(x)^2   => -(a*(x^2))


"""

operator_groups: list[tuple[Associativity, Sequence[str|type[t1.Token]]]] = [
    # HIGHEST PRECEDENCE
    (Associativity.left, ['.', t2.Juxtapose]),  # jux-call, jux-index
    (Associativity.fail, [t2.TypeParamJuxtapose]),
    (Associativity.fail, [t2.EllipsisJuxtapose]),  # jux-ellipsis
    # (Associativity.none, [t2.BackticksJuxtapose]),  # jux-backticks
    (Associativity.prefix, ['`']),
    (Associativity.postfix, ['`']),
    (Associativity.prefix, ['not', '~']),
    (Associativity.right,  ['^']),
    (Associativity.left, [t2.Juxtapose]),  # jux-multiply
    (Associativity.left, ['*', '/', '//', 'mod', '\\']),
    (Associativity.left, ['+', '-']),
    (Associativity.left, ['<<', '>>', '<<<', '>>>', '<<!', '!>>']),
    (Associativity.none,  [',']),
    (Associativity.left, [t2.RangeJuxtapose]),  # jux-range
    (Associativity.none, ['in']),
    (Associativity.left, ['=?', '>?', '<?', '>=?', '<=?']),
    (Associativity.postfix, ['?']),
    (Associativity.left, ['and', 'nand', '&']),
    (Associativity.left, ['xor', 'xnor']),
    (Associativity.left, ['or', 'nor', '|']),
    (Associativity.none,  ['as', 'transmute']),
    (Associativity.fail, ['of']),
    (Associativity.none, [':']),
    (Associativity.right, [':>']),
    (Associativity.right,  ['=>']),  # () => () => () => 42
    (Associativity.right, ['|>']),
    (Associativity.left, ['<|']),
    (Associativity.fail,  ['->', '<->']),
    (Associativity.fail,  ['=', '::', ':=', t2.CombinedAssignmentOp]),
    (Associativity.postfix, [t1.Semicolon]),  # postfix semicolon
    # LOWEST PRECEDENCE
]


# TODO: adjust so operators have left and right precedence levels to support pratt parsing
precedence_table: dict[str|type[t1.Token], int | qint] = {}
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


# # TODO: this should probably take an argument for indicating left or right side
# def operator_precedence(op: t1.Operator|t2.BroadcastOp|t2.CombinedAssignmentOp|t1.Semicolon) -> int | qint:
#     try:
#         if isinstance(op, t1.Operator):
#             return precedence_table[op]
#         if isinstance(op, t2.BroadcastOp):
#             return operator_precedence(op.op)
        
#         return precedence_table[type(op)]
    
#     except Exception as e:
#         raise ValueError(f"INTERNAL ERROR: failed to determine precedence for unknown operator {op=}") from e


@dataclass
class Node:
    op: Operator
    left: 'Node' | t1.Token | None
    right: 'Node' | t1.Token | None