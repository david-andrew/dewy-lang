"""
Initial parsing pass. A simple pratt-style parser
"""

from typing import Sequence, Callable, TypeAlias, get_args
from dataclasses import dataclass
from enum import Enum, auto
from . import t1
from . import t2
from .reporting import SrcFile, ReportException


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

_operator_set = get_args(Operator)


@dataclass
class qint:
    """
    quantum int for dealing with precedences that are multiple values at the same time
    qint's can only be strictly greater or strictly less than other values. Otherwise it's ambiguous
    In the case of ambiguous precedences, the symbol table is needed for helping resolve the ambiguity
    """
    values: set[int]
    def __post_init__(self): assert len(self.values) > 1, f'qint must have more than one value. Got {self.values}'
    def __gt__(self, other: 'int|qint') -> bool: return all(v > other for v in self.values)
    def __lt__(self, other: 'int|qint') -> bool: return all(v < other for v in self.values)
    def __ge__(self, other: 'int|qint') -> bool: return self.__gt__(other)
    def __le__(self, other: 'int|qint') -> bool: return self.__lt__(other)
    def __eq__(self, other: object) -> bool: return False
    def __add__(self, other: int) -> 'qint':
        if not isinstance(other, int): return NotImplemented
        return qint({v + other for v in self.values})
    def __radd__(self, other: int) -> 'qint': return self.__add__(other)
    def __sub__(self, other: int) -> 'qint':
        if not isinstance(other, int): return NotImplemented
        return qint({v - other for v in self.values})
    def __rsub__(self, other: int) -> 'qint':
        if not isinstance(other, int): return NotImplemented
        return qint({other - v for v in self.values})
    def __mul__(self, other: int) -> 'qint':
        if not isinstance(other, int): return NotImplemented
        if other == 0: raise RuntimeError(f'Currently, multiplying by 0 is not allowed. got {self}*{other}. TBD if this was reasonable (would return int(0) instead of qint)')
        return qint({v * other for v in self.values})
    def __rmul__(self, other: int) -> 'qint': return self.__mul__(other)
    def __floordiv__(self, other: int) -> 'qint':
        if not isinstance(other, int): return NotImplemented
        return qint({v // other for v in self.values})
    def __rfloordiv__(self, other: int) -> 'qint':
        if not isinstance(other, int): return NotImplemented
        return qint({other // v for v in self.values})


class Associativity(Enum):
    left = auto()
    right = auto()
    prefix = auto()
    postfix = auto()
    flat = auto()
    fail = auto()



BASE_BIND_POWER = 1
NO_BIND = -1
def _convert_to_bp(precedence:int): 
    return BASE_BIND_POWER+2*precedence

assoc_to_bp_funcs: dict[Associativity, Callable[[int], tuple[int, int]]] = {
    Associativity.left: lambda precedence: (_convert_to_bp(precedence), _convert_to_bp(precedence)+1),
    Associativity.right: lambda precedence: (_convert_to_bp(precedence)+1, _convert_to_bp(precedence)),
    Associativity.prefix: lambda precedence: (_convert_to_bp(precedence), NO_BIND),
    Associativity.postfix: lambda precedence: (NO_BIND, _convert_to_bp(precedence)),
    Associativity.flat: lambda precedence: (_convert_to_bp(precedence)+1, _convert_to_bp(precedence)),  # flat parses as left to right, but uses N-ary node instead of regular node
    Associativity.fail: lambda precedence: (_convert_to_bp(precedence)+1, _convert_to_bp(precedence)),  # also parses left to right, but will error if a node ever is handed a child of the same operator
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
    (Associativity.prefix, ['`']),
    (Associativity.postfix, ['`']),
    (Associativity.prefix, ['not', '~']),
    (Associativity.postfix, ['?']),
    (Associativity.right,  ['^']),
    (Associativity.left, [t2.Juxtapose]),  # jux-multiply
    (Associativity.prefix, ['*', '/', '//']),
    (Associativity.left, ['*', '/', '//', 'mod', '\\']),
    (Associativity.prefix, ['+', '-']),
    (Associativity.left, ['+', '-']),
    (Associativity.left, ['<<', '>>', '<<<', '>>>', '<<!', '!>>']),
    (Associativity.flat,  [',']),
    (Associativity.left, [t2.RangeJuxtapose]),  # jux-range
    (Associativity.fail, ['in']),    # A in B
    (Associativity.left, ['=?', '>?', '<?', '>=?', '<=?']),
    (Associativity.left, ['and', 'nand', '&']),
    (Associativity.left, ['xor', 'xnor']),
    (Associativity.left, ['or', 'nor', '|']),
    (Associativity.left,  ['as', 'transmute']),  # A as B as C as D
    (Associativity.fail, ['of']),
    (Associativity.fail, [':']),    # A:B:C
    (Associativity.left, [':>']),   # A:>B:>C
    (Associativity.right,  ['=>']), # () => () => () => 42
    (Associativity.left, ['|>']),   # x |> f1 |> f2 |> f3
    (Associativity.right, ['<|']),  # f3 <| f2 <| f1 <| x 
    (Associativity.fail,  ['->', '<->']),
    (Associativity.fail,  ['=', '::', ':=', t2.CombinedAssignmentOp]),
    (Associativity.postfix, [t1.Semicolon]),  # postfix semicolon
    # LOWEST PRECEDENCE
]


# TODO: adjust so operators have left and right precedence levels to support pratt parsing
precedence_table: dict[str|type[t1.Token], int | qint] = {}
associativity_table: dict[int, Associativity] = {}
bind_power_table: dict[int, tuple[int, int]] = {}
for i, (assoc, group) in enumerate(reversed(operator_groups)):

    # mark precedence level i as the specified associativity
    associativity_table[i] = assoc
    bind_power_table[i] = assoc_to_bp_funcs[assoc](i)

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


@dataclass
class AST: ...

@dataclass
class Atom(AST):
    item: t1.Token

@dataclass
class BinOp(AST):
    """either a binary node, a prefix node, or a postfix node"""
    op: Operator
    left: AST
    right: AST


@dataclass
class Prefix(AST):
    op: t1.Operator|t2.BroadcastOp
    item: AST

@dataclass
class Postfix(AST):
    op: t1.Operator|t1.Semicolon|t2.BroadcastOp
    item: AST


# used for operators that are flat rather than have an associativity (namely comma separated expressions)
@dataclass
class Nary(AST):
    """N-ary node for operators that """
    op: Operator  # Typically this will be comma. consider making it exclusively comma?
    items: list[AST|t1.Token]




def parse(srcfile: SrcFile) -> list[AST]:
    """simple bottom up iterative shunting-esque algorithm driven by pratt-style binding powers"""
    """
    Steps:
    1. collect all AST nodes
    2. identify if node shifts left, right, none based on binding power of adjacent opererators
    3. apply reductions:
        - binary operators that recieve both left and right
        - unary prefix operators that receive right (if the thing to the left cannot end an expression (i.e. it is an operator, but not possibly a postfix operator))
        - unary postfix operators that receive left (simpler since no postfix operators are also binary operators)
        - flat operators that are a full alternating sequence of (arg, op, arg, op, ... op, arg) with no connecting operators on either side (if leftmost and rightmost operators shifted inward, there shouldn't be any connecting operators)
        - for fail associativity operators, treat like regular binary, but if a child AST would have the same operator as the parent node, error out
    4. repeat until no new nodes constructed


    tricky examples
    10*-5   [<int 10>, <op *>, Node(-, None, 5)]
    10?-5   [<int 10>, <op ?>, Node(-, None, 5)] -> [Node(?, 10, None), Node(-, None, 5)]

    --x vs y--x
    <op -><op -><id x>
    <id y><op -><op -><id x>

    10? >? -x + /y  [<int 10><op ?><op >?><op -><>]
    """

    tokens = t2.postok(srcfile)
    return parse_inner(tokens)

def parse_inner(tokens: list[t1.Token]) -> list[AST]:
    # TODO: figure out how to handle applying shunt loop to inner tokens...
    
    # fn to convert all atom tokens to Atom ASTs and recurse into all inner tokens
    def atomize(tokens: list[t1.Token]) -> list[AST|Operator]:
        for i, t in enumerate(tokens):
            if not isinstance(t, _operator_set):
                t2.recurse_into(t, atomize)
                tokens[i] = Atom(t)
        return tokens
    
    # apply conversion to top layer
    items = atomize(tokens)

    # perform the actual parsing
    return reduce_loop(items)

def reduce_loop(items: list[Operator|AST]) -> list[AST]:
    """repeatedly apply shunting reductions until no more occur. modifies `tokens` in place"""
    while True:
        l0 = len(items)
        items = shunt_pass(items)
        if len(items) == l0:
            break
    assert all(isinstance(AST, i) for i in items), "INTERNAL ERROR: shunt-loop produced list with non-ASTs"
    return items

def shunt_pass(items: list[Operator|AST]) -> None:
    """apply a shunting reduction. modifies `tokens` in place"""
    import pdb; pdb.set_trace()
    ...





def test():
    from ..myargparse import ArgumentParser
    from .t0 import tokens_to_report # mildly hacky but Token2's duck-type to what this expects
    from pathlib import Path
    parser = ArgumentParser()
    parser.add_argument('path', type=Path, required=True, help='path to file to tokenize')
    args = parser.parse_args()
    path: Path = args.path
    src = path.read_text()
    srcfile = SrcFile(path, src)
    try:
        asts = parse(srcfile)
    except ReportException as e:
        print(e.report)
        exit(1)
    
    print(asts)
    # print(tokens_to_report(tokens, srcfile))

if __name__ == '__main__':
    test()