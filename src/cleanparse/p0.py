"""
Initial parsing pass. A simple pratt-style parser
"""

from typing import Sequence, Callable, TypeAlias, get_args, Literal
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
    | t2.SemicolonJuxtapose
    | t2.InvertedComparisonOp
    | t2.CombinedAssignmentOp
    | t2.BroadcastOp
)

_operator_set = get_args(Operator)

def op_equals(left: Operator, right: Operator) -> bool:
    if not isinstance(left, Operator) or not isinstance(right, Operator): return False # only check equality of operators
    if type(left) != type(right): return False # ensure left and right are the same type of operator
    if isinstance(left, t1.Operator):
        return left.symbol == right.symbol
    if isinstance(left, t2.InvertedComparisonOp):
        return left.op == right.op
    if isinstance(left, t2.CombinedAssignmentOp):
        return op_equals(left.op, right.op)
    if isinstance(left, t2.BroadcastOp):
        return left.op == right.op

    assert isinstance(left, (t2.Juxtapose, t2.RangeJuxtapose, t2.EllipsisJuxtapose, t2.TypeParamJuxtapose, t2.SemicolonJuxtapose)), f'INTERNAL ERROR: unexpected operator types. expected juxtapose. got {left=} and {right=}'
    return True


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
    (Associativity.prefix, ['@']),
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
    (Associativity.left, [t2.SemicolonJuxtapose]),  # for suppression
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
    op: t1.Operator|t2.BroadcastOp
    item: AST


# used for operators that are flat rather than have an associativity (namely comma separated expressions)
@dataclass
class Flat(AST):
    """node for flat operators that all combine to a single operation rather than a tree (e.g. comma separated expressions)"""
    op: Operator
    items: list[AST]




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
    # identify items that could shift
    ast_idxs = [i for i, item in enumerate(items) if isinstance(item, AST)]
    reverse_ast_idxs_map = {idx: i for i, idx in enumerate(ast_idxs)} # so we can look up the index of an ast's shift dir in the shift_dirs list
    candidate_operator_idxs: list[int] = []
    
    # determine the direction items would shift according to operator binding power of the adjacent operators
    shift_dirs: list[Literal[-1, 0, 1]] = [0] * len(ast_idxs)
    for i, ast_idx in enumerate(ast_idxs):
        # get left and right items
        left_op = items[ast_idx - 1] if ast_idx > 0 else None
        right_op = items[ast_idx + 1] if ast_idx < len(items) - 1 else None
        
        # get binding power of left and right (if they are operators)
        left_bp, right_bp = NO_BIND, NO_BIND
        if isinstance(left_op, Operator):
            _, left_bp = bind_power_table[left_op]
        if isinstance(right_op, Operator):
            right_bp, _ = bind_power_table[right_op]
        
        if left_bp == NO_BIND and right_bp == NO_BIND:
            continue
        
        # determine direction of shift
        if left_bp > right_bp:
            shift_dirs[i] = -1
            candidate_operator_idxs.append(ast_idx - 1)
        elif left_bp < right_bp:
            shift_dirs[i] = 1
            candidate_operator_idxs.append(ast_idx + 1)
        else:
            raise ValueError(f"INTERNAL ERROR: left and right have identical binding power. this shouldn't be possible. got {left_bp=} and {right_bp=} for {left_op=} and {right_op=}")
    
    # identify reductions
    all_reductions: list[tuple[AST, tuple(int, int)]] = []
    for candidate_operator_idx in candidate_operator_idxs:
        left_ast_idx = candidate_operator_idx - 1
        right_ast_idx = candidate_operator_idx + 1
        left_ast = items[left_ast_idx]
        right_ast = items[right_ast_idx]
        left_ast_shift_dir_idx = reverse_ast_idxs_map.get(left_ast_idx)  # index of the ast in the shift_dirs list
        right_ast_shift_dir_idx = reverse_ast_idxs_map.get(right_ast_idx)  # index of the ast in the shift_dirs list
        left_ast_shift_dir = shift_dirs[left_ast_shift_dir_idx] if left_ast_shift_dir_idx is not None else 0
        right_ast_shift_dir = shift_dirs[right_ast_shift_dir_idx] if right_ast_shift_dir_idx is not None else 0

        op = items[candidate_operator_idx]
        assert isinstance(op, Operator), f'INTERNAL ERROR: candidate operator is not an operator. got {op=}'
        precedence = precedence_table[op]
        if isinstance(precedence, int):
            associativity = [associativity_table[precedence]]
        else:
            associativity = [associativity_table[p] for p in precedence.values]
        
        reductions: list[tuple[AST, tuple(int, int)]] = []  # ast from reduction, and indices of tokens participating in the reduction
        for a in associativity:
            if (a == Associativity.left or a == Associativity.right) and (left_ast_shift_dir == 1 and right_ast_shift_dir == -1):
                reductions.append((BinOp(op, left_ast, right_ast), (left_ast_idx, right_ast_idx+1)))
            elif (a == Associativity.prefix) and (right_ast_shift_dir == -1):
                reductions.append((Prefix(op, right_ast), (candidate_operator_idx, right_ast_idx+1)))
            elif (a == Associativity.postfix) and (left_ast_shift_dir == 1):
                reductions.append((Postfix(op, left_ast), (left_ast_idx, candidate_operator_idx+1)))
            elif (a == Associativity.flat) and (left_ast_shift_dir == 1 and right_ast_shift_dir == -1):
                # check for the whole flat chain
                try:
                    operands, indices = collect_flat_operands(left_ast, right_ast, right_ast_idx, items, reverse_ast_idxs_map, shift_dirs)
                except Exception: #TODO: make this the exception of trying to unpack none
                    continue
                reductions.append((Flat(op, operands), indices))
            elif (a == Associativity.fail) and (left_ast_shift_dir == 1 and right_ast_shift_dir == -1):
                # TODO: full error report for these exceptions
                if isinstance(left_ast, BinOp) and op_equals(left_ast.op, op):
                    raise ValueError(f'USER ERROR: operator {op} is not allowed to be nested inside itself. got {left_ast.op=} and {op=}')
                if isinstance(right_ast, BinOp) and op_equals(right_ast.op, op):
                    raise ValueError(f'USER ERROR: operator {op} is not allowed to be nested inside itself. got {right_ast.op=} and {op=}')
                reductions.append((BinOp(op, left_ast, right_ast), (left_ast_idx, right_ast_idx+1)))
        
        if len(reductions) == 0:
            continue
        if len(reductions) > 1:
            raise ValueError(f'INTERNAL ERROR: multiple reductions found for {op=}. got {reductions=}')
        all_reductions.append(reductions[0])
        
    
    # apply reductions in reverse order to avoid index shifting issues
    for reduction, (left_bound, right_bound) in reversed(all_reductions):
        items[left_bound:right_bound] = [reduction]



def collect_flat_operands(left_ast: AST, right_ast: AST, right_ast_idx: int, items: list[Operator|AST], reverse_ast_idxs_map: dict[int, int], shift_dirs: list[Literal[-1, 0, 1]]) -> list[AST]|None:
    # check for the whole flat chain
    operands: list[AST] = [left_ast, right_ast]
    i = right_ast_idx + 1
    while i < len(items) and op_equals(items[i], op):
        next_ast_idx = i + 1
        if next_ast_idx >= len(items):
            raise ValueError(f'USER ERROR: missing operand for flat operator {op}. got {operands=}')
        # next_ast = items[next_ast_idx]
        next_ast_i = reverse_ast_idxs_map.get(next_ast_idx)
        if next_ast_i is None:
            import pdb; pdb.set_trace()
            raise ValueError("INTERNAL ERROR: item didn't shift, indicating something is probably wrong...")
        next_ast_shift_dir = shift_dirs[next_ast_i]
        if next_ast_shift_dir == 0:
            raise ValueError(f"INTERNAL ERROR: item didn't shift, indicating something is probably wrong... got {next_ast_shift_dir=} for {next_ast_idx=}")
        if next_ast_shift_dir == 1:
           #not ready to reduce yet
            return None
        operands.append(items[next_ast_idx])
        i += 2

    return operands




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