"""
Initial parsing pass. A simple pratt-style parser
"""

from textwrap import dedent
from typing import NoReturn, Sequence, Callable, TypeAlias, Literal, cast
from dataclasses import dataclass
from enum import Enum, auto

from . import t0
from . import t1
from . import t2
from .reporting import SrcFile, ReportException, Error, Pointer, Span
from .utils import ordinalize

import pdb



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
        assert all(isinstance(v, int) for v in self.values), f'qint values must be integers. Got {self.values}'
    def __gt__(self, other: int|qint) -> bool: return all(v > other for v in self.values)
    def __lt__(self, other: int|qint) -> bool: return all(v < other for v in self.values)
    def __ge__(self, other: int|qint) -> bool: return self.__gt__(other)
    def __le__(self, other: int|qint) -> bool: return self.__lt__(other)
    def __eq__(self, other: object) -> bool: return False
    def __add__(self, other: int) -> qint:
        if not isinstance(other, int): return NotImplemented
        return qint({v + other for v in self.values})
    def __radd__(self, other: int) -> qint: return self.__add__(other)
    def __sub__(self, other: int) -> qint:
        if not isinstance(other, int): return NotImplemented
        return qint({v - other for v in self.values})
    def __rsub__(self, other: int) -> qint:
        if not isinstance(other, int): return NotImplemented
        return qint({other - v for v in self.values})
    def __mul__(self, other: int) -> qint:
        if not isinstance(other, int): return NotImplemented
        if other == 0: raise RuntimeError(f'Currently, multiplying by 0 is not allowed. got {self}*{other}. TBD if this was reasonable (would return int(0) instead of qint)')
        return qint({v * other for v in self.values})
    def __rmul__(self, other: int) -> qint: return self.__mul__(other)
    def __floordiv__(self, other: int) -> qint:
        if not isinstance(other, int): return NotImplemented
        return qint({v // other for v in self.values})
    def __rfloordiv__(self, other: int) -> qint:
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
    Associativity.prefix: lambda precedence: (NO_BIND, _convert_to_bp(precedence)),
    Associativity.postfix: lambda precedence: (_convert_to_bp(precedence), NO_BIND),
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
    (Associativity.left, ['.', t2.CallJuxtapose, t2.IndexJuxtapose]),  # x.y sin(x) x[y]
    (Associativity.fail, [t2.TypeParamJuxtapose]),
    (Associativity.fail, [t2.EllipsisJuxtapose]),  # A...  ...B
    (Associativity.prefix, ['`']),
    (Associativity.postfix, ['`']),
    (Associativity.prefix, ['not', '~']),
    (Associativity.postfix, ['?']),
    (Associativity.right,  ['^']),
    (Associativity.left, [t2.MultiplyJuxtapose]),  # x(y) (x)y
    (Associativity.prefix, ['*', '/', '//']),
    (Associativity.left, ['*', '/', '//', '%', '\\']),
    (Associativity.prefix, ['+', '-']),
    (Associativity.left, ['+', '-']),
    (Associativity.left, ['<<', '>>', '<<<', '>>>', '<<!', '!>>']),
    (Associativity.flat,  [',']),
    (Associativity.flat, [t2.RangeJuxtapose]),  # jux-range
    (Associativity.fail, ['in']),    # A in B
    (Associativity.left, ['=?', '>?', '<?', '>=?', '<=?', 'is?', 'isnt?', 'in?', '@?']),
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


def get_precedence(op: t2.Operator) -> int | qint:
    
    if isinstance(op, t1.Operator):
        return precedence_table[op.symbol]
    if isinstance(op, t2.InvertedComparisonOp):
        return precedence_table[op.op]
    if isinstance(op, t2.CombinedAssignmentOp):
        return precedence_table['=']
    if isinstance(op, t2.BroadcastOp):
        return get_precedence(op.op)
    if isinstance(op, t2.QOperator):
        return qint(set(get_precedence(o) for o in op.options))
    try:
        return precedence_table[type(op)]
    except KeyError:
        pdb.set_trace()
        raise ValueError(f'INTERNAL ERROR: unexpected operator type for determining precedence. got {op=}')

def get_bind_power(op: t2.Operator) -> tuple[int, int] | tuple[qint, qint]:
    precedence = get_precedence(op)
    if isinstance(precedence, int):
        return bind_power_table[precedence] 
    left_bps, right_bps = zip(*[bind_power_table[p] for p in precedence.values])
    left_bps = list(filter(lambda bp: bp != NO_BIND, left_bps))
    right_bps = list(filter(lambda bp: bp != NO_BIND, right_bps))
    left_bps = qint(set(left_bps)) if len(left_bps) > 1 else left_bps[0]
    right_bps = qint(set(right_bps)) if len(right_bps) > 1 else right_bps[0]
    return (left_bps, right_bps)

def get_associativity(op: t2.Operator) -> Associativity | list[Associativity]:
    precedence = get_precedence(op)
    if isinstance(precedence, int):
        return associativity_table[precedence]
    return [associativity_table[p] for p in precedence.values]

@dataclass
class Context:
    srcfile: SrcFile

# TODO: consider making ASTs include a span now that we don't keep the old tokens for containers
@dataclass
class AST: ...

@dataclass
class BinOp(AST):
    """either a binary node, a prefix node, or a postfix node"""
    op: t2.Operator
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
    op: t2.Operator
    items: list[AST]


# TBD how to set this up since don't have a whole AST when we see ambiguity, just reductions in a list
# perhaps instead keep the reductions + AST/tokens they tend over
# also ideally there would be maximal sharing when dealing with ambiguous cases.
@dataclass
class Ambiguous(AST):
    candidates: list[AST]

# ASTs that represent whole expressions that can be used as operands
# most of these are just thin rewrites of their t1/t2 counterparts
@dataclass
class Block(AST):
    inner: list[AST]
    kind: Literal['{}', '[]', '()', '[)', '(]', '<>']
    base: t0.BasePrefix | None

@dataclass
class ParametricEscape(AST):
    inner: list[AST]
@dataclass
class IString(AST):
    content: list[str | ParametricEscape | Block]
@dataclass
class KeywordExpr(AST):
    parts: list[t1.Keyword | AST]
@dataclass
class Flow(AST):
    arms: list[KeywordExpr]
    default: AST|None=None

@dataclass
class Atom(AST):
    """all non-container Tokens just get wrapped up into an Atom AST"""
    item: t1.Token


# special error cases when trying to make a reduction
# NOTE: if there become many more special cases to check, make a table that looks up functions given the operator
def validate_flat(ast: Flat, ctx: Context) -> NoReturn|None:
    # since rangejux is the only flat to check at the moment, have a simpler structure here
    if not isinstance(ast.op, t2.RangeJuxtapose):
        return
    
    # verify that .. only appears once in the range expression
    dotdot_idxs = [i for i, t in enumerate(ast.items) if isinstance(t, Atom) and t2.is_dotdot(t.item)]
    jux_spans = []
    for idx in dotdot_idxs:
        dotdot_span = ast.items[idx].item.loc
        if idx > 0:
            jux_spans.append(Span(dotdot_span.start, dotdot_span.start))
        if idx < len(ast.items) - 1:
            jux_spans.append(Span(dotdot_span.stop, dotdot_span.stop))
    if len(dotdot_idxs) > 1:
        error = Error(
            srcfile=ctx.srcfile,
            title="multiple `..` tokens encountered in single range expression",
            pointer_messages=[
                Pointer(ast.items[idx].item.loc, message=f"{ordinalize(i+1)} connected `..` token", placement='below')
                for i, idx in enumerate(dotdot_idxs)
            ] + [
                Pointer(span, message='RangeJuxtapose', placement='above') for span in jux_spans
            ],
            # TODO (long term): probably would be better to somehow point to the docs...
            hint=dedent("""\
                A range expression may only include one `..` token.
                Possible Fixes:
                - Insert whitespace next to `..` to create multiple range expressions 
                - wrap ranges in () or [] or (] or [) to explicitly delimit
                - remove any extra `..` so that there is only one per range
                
                Some examples of ranges:
                - first..             # first to inf
                - ..last              # -inf to last
                - first..last         # first to last
                - ..                  # -inf to inf
                
                Specifying a step size:
                - first,second..      # first to inf, step size is second-first
                - first,second..last  # first to last, step size is second-first
                - ..2ndlast,last      # -inf to last, step size is last-2ndlast
                
                Specifying inclusivity bounds:
                - [first..last]       # first to last including first and last
                - [first..last)       # first to last including first, excluding last
                - (first..last]       # first to last excluding first, including last
                - (first..last)       # first to last excluding first and last
                - first..last         # defaults to inclusive, i.e. [first..last]
                
                Range arguments attach via juxtaposition:
                - first..last         # first to last. Both sides are included
                - first ..last        # -inf to last. first is not part of the range
                - first.. last        # first to inf. last is not part of the range
                - first .. last       # -inf to inf. neither first or last are included
                """
            ),

        )
        error.throw()




# TODO: make this return a single block AST instead of a list of ASTs...
# NOTE: while Atom wraps around Tokens, any inner tokens will NOT have any Chains
#       i.e. parsing process replaces all Chains with whatever AST that chain would produce
def parse(srcfile: SrcFile) -> list[AST]:
    """
    simple bottom up iterative shunting-esque algorithm driven by pratt-style binding powers
    
    Steps:
    1. collect all AST nodes
    2. identify if node shifts left, right, none based on binding power of adjacent operators
    3. apply reductions to "fulfilled" operators:
        TODO: note adjust the conditions mentioned here now that we are operating on Chains, not list[Token]
        - binary operators that receive both left and right
        - unary prefix operators that receive right (if the thing to the left cannot end an expression (i.e. it is an operator, but not possibly a postfix operator))
        - unary postfix operators that receive left (simpler since no postfix operators are also binary operators)
        - flat operators that are a full alternating sequence of (arg, op, arg, op, ... op, arg) with no connecting operators on either side (if leftmost and rightmost operators shifted inward, there shouldn't be any connecting operators)
        - for fail associativity operators, treat like regular binary, but if a child AST would have the same operator as the parent node, error out
    4. repeat until no new reductions constructed


    tricky examples
    10*-5   [<int 10>, <op *>, Node(-, None, 5)]
    10?-5   [<int 10>, <op ?>, Node(-, None, 5)] -> [Node(?, 10, None), Node(-, None, 5)]

    --x vs y--x
    <op -><op -><id x>
    <id y><op -><op -><id x>

    10? >? -x + /y  [<int 10><op ?><op >?><op -><>]
    """

    chains = t2.postok(srcfile)
    ctx = Context(srcfile=srcfile)
    asts = [parse_chain(chain, ctx) for chain in chains]
    return asts

# TODO: consider making AST container types for each of the items that recursed into so we aren't shoving ASTs where tokens are expected...
def parse_chain(chain: t2.Chain, ctx: Context) -> AST:
    assert isinstance(chain, t2.Chain), f'INTERNAL ERROR: parse_chain must be called on Chain, got {type(chain)}'
    
    items: list[t2.Operator|AST] = [] 
    for t in chain.items:
        # operators are added as is, to be used by the reduction loop
        if isinstance(t, t2.Operator):
            items.append(t)
            continue
        
        # chains are not allowed at the top level of a chain
        if isinstance(t, t2.Chain):
            raise ValueError(f'INTERNAL ERROR: top level item in chain was another chain. .this shouldn\'t be possible. got {t=}')

        # convert all other items into ASTs
        if isinstance(t, (t1.Block, t1.ParametricEscape)):
            ast = parse_block(t, ctx)
        elif isinstance(t, t1.IString):
            ast = parse_istring(t, ctx)
        elif isinstance(t, t1.ParametricEscape):
            ast = parse_parametric_escape(t, ctx)
        elif isinstance(t, (t2.KeywordExpr, t2.FlowArm)):
            ast = parse_keyword_expr_or_flow_arm(t, ctx)
        elif isinstance(t, t2.Flow):
            ast = parse_flow(t, ctx)
        elif isinstance(t, (t1.Real, t1.String, t1.BasedString, t1.Identifier, t1.Semicolon, t1.Metatag, t1.Integer, t2.OpFn)):
            ast = Atom(t)
        items.append(ast)

    reduce_loop(items, ctx)
    assert len(items) == 1, f"INTERNAL ERROR: parse_chain produced {len(items)} items, expected 1"
    return items[0]

def parse_block(block: t1.Block|t1.ParametricEscape, ctx: Context) -> AST:
    inner = parse_inner(block.inner, ctx)
    return Block(inner=inner, kind=block.kind, base=block.base) #Block(span=block.loc, inner=inner)

def parse_istring(istring: t1.IString, ctx: Context) -> AST:
    pdb.set_trace()

def parse_parametric_escape(parametric_escape: t1.ParametricEscape, ctx: Context) -> AST:
    pdb.set_trace()

def parse_keyword_expr_or_flow_arm(keyword_expr_or_flow_arm: t2.KeywordExpr|t2.FlowArm, ctx: Context) -> AST:
    pdb.set_trace()

def parse_flow(flow: t2.Flow, ctx: Context) -> AST:
    pdb.set_trace()
    
from typing import Any
def parse_inner(items: list[t2.Chain], ctx: Context) -> list[AST|Any]:
    asts: list[AST] = []
    for i in items:
        if not isinstance(i, t2.Chain):
            continue  # t1.IString, KeywordExpr, FlowArm, etc. contain non-chains that get dealt with later
            pdb.set_trace()  # TODO: is there a case where this might happen? e.g. expression keywords?
            raise ValueError(f'INTERNAL ERROR: unexpected item type. expected Chain, got {type(i)=}')

        asts.append(parse_chain(i, ctx))
    return asts


def reduce_loop(items: list[t2.Operator|AST], ctx: Context) -> list[AST]:
    """repeatedly apply shunting reductions until no more occur. modifies `tokens` in place"""
    while True:
        l0 = len(items)
        shunt_pass(items, ctx)
        if len(items) == l0:
            break
    
    # during development, this might also be hit due to internal errors, e.g. bugs where something is not properly reducing
    # TODO: this could be a user error, e.g. `A&;b&c`. Do full error reporting
    # perhaps do: for each item in list, if is op, determine what kinds of reductions it could participate in and show error listing them vs what was present
    assert all(isinstance(i, AST) for i in items), "INTERNAL ERROR: shunt-loop produced list with non-ASTs"
    
    return items

def shunt_pass(items: list[t2.Operator|AST], ctx: Context) -> None:
    """apply a shunting reduction. modifies `tokens` in place"""
    # identify items that could shift
    ast_idxs = [i for i, item in enumerate(items) if isinstance(item, AST)]
    asts = cast(list[AST], [items[i] for i in ast_idxs])
    reverse_ast_idxs_map = {idx: i for i, idx in enumerate(ast_idxs)} # so we can look up the index of an ast's shift dir in the shift_dirs list
    candidate_operator_idxs: set[int] = set()
    
    # determine the direction items would shift according to operator binding power of the adjacent operators
    shift_dirs: list[Literal[-1, 0, 1]] = [0] * len(ast_idxs)
    for i, (ast, ast_idx) in enumerate(zip(asts, ast_idxs)):
        # get left and/or right operators if present
        left_op = items[ast_idx - 1] if ast_idx > 0 else None
        right_op = items[ast_idx + 1] if ast_idx < len(items) - 1 else None

        # semicolon is a special case that can only shift left if left is SemicolonJuxtapose
        if isinstance(ast, Atom) and isinstance(ast.item, t1.Semicolon) and not isinstance(left_op, t2.SemicolonJuxtapose):
            continue
        
        # get binding power of left and right (if they are operators)
        left_bp, right_bp = NO_BIND, NO_BIND
        if isinstance(left_op, t2.Operator):
            _, left_bp = get_bind_power(left_op)
        if isinstance(right_op, t2.Operator):
            right_bp, _ = get_bind_power(right_op)
        
        if left_bp == NO_BIND and right_bp == NO_BIND:
            continue
        
        # determine direction of shift
        if left_bp > right_bp:
            shift_dirs[i] = -1
            candidate_operator_idxs.add(ast_idx - 1)
        elif left_bp < right_bp:
            shift_dirs[i] = 1
            candidate_operator_idxs.add(ast_idx + 1)
        elif left_bp == right_bp:
            raise ValueError(f"INTERNAL ERROR: left and right have identical binding power. this shouldn't be possible. got {left_bp=} and {right_bp=} for {left_op=} and {right_op=}")
        else:
            # TODO: handle ambiguous case...
            # perhaps set shift = qint(-1, 1)
            # then when reducing, any shift that was qint makes an ambiguous node
            # and then after all the reductions, something spreads out all the ambiguous nodes orthogonally to the list of items...
            pdb.set_trace()
            ...

    # identify reductions
    all_reductions: list[tuple[AST, tuple(int, int)]] = []
    for candidate_operator_idx in sorted(candidate_operator_idxs):
        left_ast_idx = candidate_operator_idx - 1
        right_ast_idx = candidate_operator_idx + 1
        left_ast = items[left_ast_idx] if left_ast_idx >= 0 else None
        right_ast = items[right_ast_idx] if right_ast_idx < len(items) else None
        left_ast_shift_dir_idx = reverse_ast_idxs_map.get(left_ast_idx)  # index of the ast in the shift_dirs list
        right_ast_shift_dir_idx = reverse_ast_idxs_map.get(right_ast_idx)  # index of the ast in the shift_dirs list
        left_ast_shift_dir = shift_dirs[left_ast_shift_dir_idx] if left_ast_shift_dir_idx is not None else 0
        right_ast_shift_dir = shift_dirs[right_ast_shift_dir_idx] if right_ast_shift_dir_idx is not None else 0

        op = items[candidate_operator_idx]
        assert isinstance(op, t2.Operator), f'INTERNAL ERROR: candidate operator is not an operator. got {op=}'
        associativity = get_associativity(op)
        if not isinstance(associativity, list):
            associativity = [associativity]
        
        reductions: list[tuple[AST, tuple[int, int], Associativity]] = []  # ast from reduction, and indices of tokens participating in the reduction
        for a in associativity:
            if (a == Associativity.left or a == Associativity.right) and (left_ast_shift_dir == 1 and right_ast_shift_dir == -1):
                assert isinstance(left_ast, AST) and isinstance(right_ast, AST), f'INTERNAL ERROR: left and right ASTs are not ASTs. got {left_ast=}, {right_ast=}, {left_ast_idx=}, {right_ast_idx=}'
                reductions.append((BinOp(op, left_ast, right_ast), (left_ast_idx, right_ast_idx+1), a))
            elif a == Associativity.prefix and (right_ast_shift_dir == -1) and (not t2.is_binary_op(op) or not left_could_attach(left_ast_idx, items)): # TODO: perhaps still not right. problem case: --x. basically need to check that no chains exist to the left...
                reductions.append((Prefix(op, right_ast), (candidate_operator_idx, right_ast_idx+1), a))
            elif (a == Associativity.postfix) and (left_ast_shift_dir == 1):
                reductions.append((Postfix(op, left_ast), (left_ast_idx, candidate_operator_idx+1), a))
            elif (a == Associativity.flat) and (left_ast_shift_dir == 1 and right_ast_shift_dir == -1):
                # check for the whole flat chain
                res = collect_flat_operands(left_ast_idx, right_ast_idx, op, items, reverse_ast_idxs_map, shift_dirs)
                if res is None:
                    continue
                operands, bounds = res
                ast = Flat(op, operands)
                validate_flat(ast, ctx)  # check that 
                reductions.append((ast, bounds, a))
            elif (a == Associativity.fail) and (left_ast_shift_dir == 1 and right_ast_shift_dir == -1):
                # TODO: full error report for these exceptions
                if isinstance(left_ast, BinOp) and t2.op_equals(left_ast.op, op):
                    raise ValueError(f'USER ERROR: operator {op} is not allowed to be nested inside itself. got {left_ast.op=} and {op=}')
                if isinstance(right_ast, BinOp) and t2.op_equals(right_ast.op, op):
                    raise ValueError(f'USER ERROR: operator {op} is not allowed to be nested inside itself. got {right_ast.op=} and {op=}')
                reductions.append((BinOp(op, left_ast, right_ast), (left_ast_idx, right_ast_idx+1), a))
        
        if len(reductions) == 0:
            continue
        if len(reductions) > 1:
            # filter duplicates
            tmp = []
            for i, r in enumerate(reductions):
                if r not in reductions[i+1:]:
                    tmp.append(r)
            reductions = tmp
            # prefer binops over prefix/postfix
            to_remove = []
            for r0 in reductions:
                r0_ast = r0[0]
                if isinstance(r0_ast, Prefix):
                    for r1 in reductions:
                        r1_ast = r1[0]
                        if isinstance(r1_ast, BinOp) and r1_ast.op == r0_ast.op: # compare directly instead of op_equals b/c spans must match too
                            to_remove.append(r0)
                            break
            for r in to_remove:
                reductions.remove(r)

            # if all prefix/postfix reductions, select the one with the highest binding power
            if all(isinstance(r[0], (Prefix, Postfix)) for r in reductions):
                bind_powers = [get_bind_power(ast.op)[0 if isinstance(ast,Postfix) else 1] for ast,_,_ in reductions]
                max_bp = max(bind_powers)
                reductions = [r for r, bp in zip(reductions, bind_powers) if bp == max_bp]

        if len(reductions) > 1:
            pdb.set_trace()
            raise ValueError(f'INTERNAL ERROR: multiple reductions found for {op=}. got {reductions=}')
        
        # add the reduction to the list
        all_reductions.append(reductions[0])
        
    
    # apply reductions in reverse order to avoid index shifting issues
    for reduction, (left_bound, right_bound), _ in reversed(all_reductions):
        items[left_bound:right_bound] = [reduction]

# TODO: the description here is a bit confusing (and it says True twice). need to fix, but no longer understand how it works
def left_could_attach(left_ast_idx: int, items: list[t2.Operator|AST]) -> bool:
    """determine if the items left of a candidate prefix or binary operator connect to that binary operator
    cases:
    op was binop or prefix, e.g. `... - x`, return True
    left is prefix or binary, then op is prefix, e.g. `... -- x` return True

    other hard cases
    +`-x
    +``-x
    `--x
    `~-x
    `?-x
    """
    i = left_ast_idx
    while i > 0:
        item = items[i]
        # All ASTs except for semicolon can attach
        if isinstance(item, AST):
            if isinstance(item, Atom) and isinstance(item.item, t1.Semicolon):
                return False
            return True
        
        # type of op determines if the left is an expresison that could attach, or prefix to the current expression
        if isinstance(item, t2.Operator):
            prefix = t2.is_prefix_op(item)
            postfix = t2.is_postfix_op(item)
            binary = t2.is_binary_op(item)
            if binary:
                return False
            elif prefix and not postfix:
                return False
            elif postfix and not prefix:
                return True
            elif prefix and postfix:
                i -= 1 # can't determine yet if the left is a separate expression or prefix to this one
                continue
            else: # unreachable
                raise ValueError(f'INTERNAL ERROR: reached unreachable state. {binary=}, {prefix=}, {postfix=}')
        
        raise ValueError(f'INTERNAL ERROR: reached unreachable state. {item=}, {left_ast_idx=}, {items[left_ast_idx]=}, {i=}')
    # no items to left that could attach
    return False

def collect_flat_operands(left_ast_idx: int, right_ast_idx: int, op: t2.Operator, items: list[t2.Operator|AST], reverse_ast_idxs_map: dict[int, int], shift_dirs: list[Literal[-1, 0, 1]]) -> tuple[list[AST], tuple[int, int]]|None:
    # check for the whole flat chain
    left_ast, right_ast = items[left_ast_idx], items[right_ast_idx]
    operands: list[AST] = [left_ast, right_ast]
    indices: list[int] = [left_ast_idx, right_ast_idx]
    i = right_ast_idx + 1

    # verify to the left
    j = left_ast_idx - 1
    while j > 0 and isinstance(items[j], t2.Operator) and t2.op_equals(items[j], op):
        prev_ast_idx = j - 1
        if prev_ast_idx < 0:
            # TODO: full error report
            raise ValueError(f'USER ERROR: missing operand for flat operator {op}. got {operands=}')
        prev_ast_i = reverse_ast_idxs_map.get(prev_ast_idx)
        if prev_ast_i is None:
            raise ValueError("INTERNAL ERROR: item didn't shift, indicating something is probably wrong...")
        prev_ast_shift_dir = shift_dirs[prev_ast_i]
        if prev_ast_shift_dir == 0:
            raise ValueError(f"INTERNAL ERROR: item didn't shift, indicating something is probably wrong... got {prev_ast_shift_dir=} for {prev_ast_idx=}")
        if prev_ast_shift_dir == -1:
            # not ready to reduce yet
            return None
        operands.insert(0, items[prev_ast_idx])
        indices.insert(0, prev_ast_idx)
        j -= 2

    # verify to the right
    while i < len(items) and isinstance(items[i], t2.Operator) and t2.op_equals(items[i], op):
        next_ast_idx = i + 1
        if next_ast_idx >= len(items):
            # TODO: full error report
            raise ValueError(f'USER ERROR: missing operand for flat operator {op}. got {operands=}')
        next_ast_i = reverse_ast_idxs_map.get(next_ast_idx)
        if next_ast_i is None:
            raise ValueError("INTERNAL ERROR: item didn't shift, indicating something is probably wrong...")
        next_ast_shift_dir = shift_dirs[next_ast_i]
        if next_ast_shift_dir == 0:
            raise ValueError(f"INTERNAL ERROR: item didn't shift, indicating something is probably wrong... got {next_ast_shift_dir=} for {next_ast_idx=}")
        if next_ast_shift_dir == 1:
            #not ready to reduce yet
            return None
        indices.append(next_ast_idx)
        operands.append(items[next_ast_idx])
        i += 2

    bounds = (indices[0], indices[-1]+1)

    return operands, bounds



def ast_to_tree_str(ast: AST, level: int = 0) -> str:
    space = "    "
    branch = "│   "
    tee = "├── "
    last = "└── "

    @dataclass(frozen=True)
    class TreeGroup:
        label: str
        items: t2.Chain

    def op_label(op: t2.Operator) -> str:
        if isinstance(op, t1.Operator):
            return op.symbol
        if isinstance(op, t2.InvertedComparisonOp):
            return f"not {op.op}"
        if isinstance(op, t2.BroadcastOp):
            return f".{op_label(op.op)}"
        if isinstance(op, t2.CombinedAssignmentOp):
            return f"{op_label(op.op)}="
        if isinstance(op, t2.QOperator):
            return f"QOperator({', '.join(op_label(o) for o in op.options)})"
        return type(op).__name__

    def token_label(tok: t1.Token) -> str:
        if isinstance(tok, t1.Identifier): return f"Identifier({tok.name})"
        if isinstance(tok, t1.Operator): return f"Operator({tok.symbol})"
        if isinstance(tok, t1.Keyword): return f"Keyword({tok.name})"
        if isinstance(tok, t1.Metatag): return f"Hashtag({tok.name})"
        if isinstance(tok, t1.Integer): return f"Integer({tok.value.src})"
        if isinstance(tok, t1.Real): 
            frac = f".{tok.fraction.src}" if tok.fraction is not None else ""
            exp = ""
            if tok.exponent is not None:
                marker = "p" if tok.exponent.binary else "e"
                sign = "" if tok.exponent.positive else "-"
                exp = f"{marker}{sign}{tok.exponent.value.src}"
            return f"Real({tok.whole.src}{frac}{exp})"
        if isinstance(tok, t1.String):
            content = tok.content.replace("\n", "\\n")
            if len(content) > 40:
                content = content[:37] + "..."
            return f"String({content!r})"
        if isinstance(tok, t2.Chain): return "Chain"
        if isinstance(tok, t1.BasedString): return f"BasedString({tok.base})"
        # if isinstance(tok, t1.BasedArray): return f"BasedArray({tok.base})"
        if isinstance(tok, t1.ParametricEscape): return "ParametricEscape"
        if isinstance(tok, t1.IString): return "IString"
        if isinstance(tok, t2.BroadcastOp): return f"BroadcastOp({op_label(tok.op)})"
        if isinstance(tok, t2.CombinedAssignmentOp): return f"CombinedAssignmentOp({op_label(tok.op)})"
        if isinstance(tok, t2.OpFn): return f"OpFn({op_label(tok.op)})"
        if isinstance(tok, t2.KeywordExpr): return "KeywordExpr"
        if isinstance(tok, t2.FlowArm): return "FlowArm"
        if isinstance(tok, t2.Flow): return "Flow"
        return type(tok).__name__

    def text_label(text: str) -> str:
        content = text.replace("\n", "\\n")
        if len(content) > 40:
            content = content[:37] + "..."
        return f"Text({content!r})"

    def item_label(item: object) -> str:
        if isinstance(item, AST): return ast_label(item)
        if isinstance(item, t1.Token): return token_label(item)
        if isinstance(item, TreeGroup): return item.label
        if isinstance(item, str): return text_label(item)
        return type(item).__name__

    def ast_label(node: AST) -> str:
        if isinstance(node, Atom): return token_label(node.item)
        if isinstance(node, BinOp): return f"BinOp({op_label(node.op)})"
        if isinstance(node, Prefix): return f"Prefix({op_label(node.op)})"
        if isinstance(node, Postfix): return f"Postfix({op_label(node.op)})"
        if isinstance(node, Flat): return f"Flat({op_label(node.op)})"
        if isinstance(node, Ambiguous): return f"Ambiguous({len(node.candidates)})"
        if isinstance(node, Block): return f"Block(kind='{node.kind}', base='{node.base}')"

        return type(node).__name__

    def iter_token_children(tok: t1.Token) -> list[tuple[str, object]]:
        if isinstance(tok, t2.Chain): return [(f"inner[{i}]", child) for i, child in enumerate(tok.items)]
        if isinstance(tok, t1.ParametricEscape): return [(f"inner[{i}]", child) for i, child in enumerate(tok.inner)]
        if isinstance(tok, t1.BasedString): return [("digits", "".join(d.src for d in tok.digits))]
        if isinstance(tok, t1.IString): return [(f"content[{i}]", child) for i, child in enumerate(tok.content)]
        if isinstance(tok, t2.BroadcastOp): return [("op", tok.op)]
        if isinstance(tok, t2.CombinedAssignmentOp): return [("op", tok.op)]
        if isinstance(tok, t2.OpFn): return [("op", tok.op)]
        if isinstance(tok, t2.KeywordExpr):
            out: list[tuple[str, object]] = []
            expr_i = 0
            for i, part in enumerate(tok.parts):
                if isinstance(part, list):
                    out.append((f"parts[{i}]", TreeGroup(f"expr[{expr_i}]", cast(list[object], part))))
                    expr_i += 1
                else:
                    out.append((f"parts[{i}]", part))
            return out
        if isinstance(tok, t2.FlowArm):
            out: list[tuple[str, object]] = []
            expr_i = 0
            for i, part in enumerate(tok.parts):
                if isinstance(part, list):
                    out.append((f"parts[{i}]", TreeGroup(f"expr[{expr_i}]", cast(list[object], part))))
                    expr_i += 1
                else:
                    out.append((f"parts[{i}]", part))
            return out
        if isinstance(tok, t2.Flow):
            out: list[tuple[str, object]] = [(f"arms[{i}]", arm) for i, arm in enumerate(tok.arms)]
            if tok.default is not None:
                out.append(("default", TreeGroup("default", cast(list[object], tok.default))))
            return out
        return []

    def iter_ast_children(node: AST) -> list[tuple[str, object]]:
        if isinstance(node, BinOp): return [("left", node.left), ("right", node.right)]
        if isinstance(node, (Prefix, Postfix)): return [("item", node.item)]
        if isinstance(node, Flat): return [(f"items[{i}]", item) for i, item in enumerate(node.items)]
        if isinstance(node, Atom): return iter_token_children(node.item)
        if isinstance(node, Block): return [(f"inner[{i}]", child) for i, child in enumerate(node.inner)]

        return []

    lines: list[str] = []
    root_prefix = space * level
    lines.append(root_prefix + item_label(ast))

    def render(item: object, prefix: str, edge_label: str, is_last: bool) -> None:
        connector = last if is_last else tee
        lines.append(prefix + connector + f"{edge_label}: {item_label(item)}")
        child_prefix = prefix + (space if is_last else branch)
        children: list[tuple[str, object]]
        if isinstance(item, AST): children = iter_ast_children(item)
        elif isinstance(item, t1.Token): children = iter_token_children(item)
        elif isinstance(item, TreeGroup): children = [(f"items[{i}]", child) for i, child in enumerate(item.items.items)]
        else: children = []
        for i, (child_edge, child) in enumerate(children):
            render(child, child_prefix, child_edge, i == len(children) - 1)

    children = iter_ast_children(ast)
    for i, (edge_label, child) in enumerate(children):
        render(child, root_prefix, edge_label, i == len(children) - 1)

    return "\n".join(lines)


def test():
    from ..myargparse import ArgumentParser
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
    
    for ast in asts:
        print(ast_to_tree_str(ast))
        print()
    


if __name__ == '__main__':
    test()