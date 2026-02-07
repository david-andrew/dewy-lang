"""
Initial parsing pass. A simple pratt-style parser
"""

from textwrap import dedent
from itertools import product
from typing import NoReturn, Sequence, Callable, TypeAlias, Literal, cast, overload, Never
from dataclasses import dataclass
from enum import Enum, auto

from . import t0
from . import t1
from . import t2
from .reporting import SrcFile, ReportException, Error, Pointer, Span
from .utils import ordinalize

import pdb



@dataclass
class qint[T=None]:
    """
    quantum int for dealing with precedences that are multiple values at the same time
    qint's can only be strictly greater or strictly less than other values. Otherwise it's ambiguous
    In the case of ambiguous precedences, the symbol table is needed for helping resolve the ambiguity

    Optionally, qints may store some payload or metadata per each value by passing in a dict[int, T] rather than a set[int]
    """
    values: dict[int, T]
    @overload
    def __init__(self: qint[None], values: set[int]): ...
    @overload
    def __init__(self: qint[T], values: dict[int, T]): ...
    def __init__(self, values: set[int]|dict[int, T]):
        if isinstance(values, set): values = {v: None for v in values} # default to None if no payload is provided
        self.values = values
        self.__post_init__()
    def __post_init__(self):
        assert len(self.values) > 1, f'qint must have more than one value. Got {self.values}'
        assert all(isinstance(v, int) for v in self.values), f'qint values must be integers. Got {self.values}'
    def __gt__(self, other: int|qint) -> bool: return all(v > other for v in self.values)
    def __lt__(self, other: int|qint) -> bool: return all(v < other for v in self.values)
    def __ge__(self, other: int|qint) -> bool: return self.__gt__(other)
    def __le__(self, other: int|qint) -> bool: return self.__lt__(other)
    def __eq__(self, other: object) -> bool: return False
    def __add__(self, other: int) -> qint[T]:
        if not isinstance(other, int): return NotImplemented
        return qint({(v + other):p for v, p in self.values.items()})
    def __radd__(self, other: int) -> qint[T]: return self.__add__(other)
    def __sub__(self, other: int) -> qint[T]:
        if not isinstance(other, int): return NotImplemented
        return qint({(v - other):p for v, p in self.values.items()})
    def __rsub__(self, other: int) -> qint[T]:
        if not isinstance(other, int): return NotImplemented
        return qint({(other - v):p for v, p in self.values.items()})
    def __mul__(self, other: int) -> qint[T]:
        if not isinstance(other, int): return NotImplemented
        if other == 0: raise RuntimeError(f'Currently, multiplying by 0 is not allowed. got {self}*{other}. TBD if this was reasonable (would return int(0) instead of qint)')
        return qint({(v * other):p for v, p in self.values.items()})
    def __rmul__(self, other: int) -> qint[T]: return self.__mul__(other)
    def __floordiv__(self, other: int) -> qint[T]:
        if not isinstance(other, int): return NotImplemented
        return qint({(v // other):p for v, p in self.values.items()})
    def __rfloordiv__(self, other: int) -> qint[T]:
        if not isinstance(other, int): return NotImplemented
        return qint({(other // v):p for v, p in self.values.items()})
    @overload
    def __getitem__(self: qint[None], key: int) -> Never: ...
    @overload
    def __getitem__(self: qint[T], key: int) -> T: ...
    def __getitem__(self: qint[T], key: int) -> T:
        return self.values[key]
    def __repr__(self) -> str:
        if all(v is None for v in self.values.values()):
            return f'qint({repr(set(self.values.keys()))})'
        return f'qint({repr(self.values)})'


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
    (Associativity.postfix, ['`']), #TODO/Note: at the moment, prefix vs postfix precedence of (`) is backed into the algorithm, and wouldn't listen to the ordering in the table...
    (Associativity.prefix, ['`']),
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
    if isinstance(op, t2.QJuxtapose):
        return qint(set(get_precedence(o) for o in op.options))

    # simple operators, just look up in the table
    precedence = precedence_table.get(type(op))
    if precedence is not None:
        return precedence
    
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


@dataclass
class ProtoAST:
    """transformation of t2.Chain that can be used at this phase. Comprises a single expression"""
    items: list[AST|t2.Operator]


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

        # convert all other items (potentially recursively) into ASTs
        if isinstance(t, (t1.Block, t1.ParametricEscape)):
            ast = parse_block(t, ctx)
        elif isinstance(t, t1.IString):
            ast = parse_istring(t, ctx)
        elif isinstance(t, t2.KeywordExpr):
            ast = parse_keyword_expr(t, ctx)
        elif isinstance(t, t2.Flow):
            ast = parse_flow(t, ctx)
        elif isinstance(t, (t1.Real, t1.String, t1.BasedString, t1.Identifier, t1.Semicolon, t1.Metatag, t1.Integer, t2.OpFn)):
            ast = Atom(t)
        items.append(ast)

    result = reduce_loop([ProtoAST(items)], ctx)
    return result

def parse_block(block: t1.Block|t1.ParametricEscape, ctx: Context) -> Block:
    inner = []
    for item in block.inner:
        if not isinstance(item, t2.Chain):
            raise ValueError(f'INTERNAL ERROR: unexpected item type in Block.inner. expected Chain, got {type(item)=}')
        inner.append(parse_chain(item, ctx))
    
    if isinstance(block, t1.ParametricEscape):
        return ParametricEscape(inner=inner)

    return Block(inner=inner, kind=block.kind, base=block.base)

def parse_istring(istring: t1.IString, ctx: Context) -> IString:
    content = []
    for item in istring.content:
        if isinstance(item, str):
            content.append(item)
        elif isinstance(item, (t1.Block, t1.ParametricEscape)):
            content.append(parse_block(item, ctx))
        else:
            # unreachable
            raise ValueError(f'INTERNAL ERROR: unexpected item type in IString. content. got {type(item)=}')
    
    return IString(content)

def parse_keyword_expr(keyword_expr: t2.KeywordExpr, ctx: Context) -> KeywordExpr:
    parts: list[t1.Keyword | AST] = []
    for item in keyword_expr.parts:
        if isinstance(item, t2.Chain):
            parts.append(parse_chain(item, ctx))
        else:
            parts.append(item)
    return KeywordExpr(parts)

def parse_flow(flow: t2.Flow, ctx: Context) -> Flow:
    arms = [parse_keyword_expr(arm, ctx) for arm in flow.arms]
    default = parse_chain(flow.default, ctx) if flow.default is not None else None
    return Flow(arms=arms, default=default)


def reduce_loop(chains: list[ProtoAST], ctx: Context) -> AST:
    """
    repeatedly apply shunting reductions until no more occur. modifies `tokens` in place
    
    Each chain in the list is an ambiguous alternative parse (initially there should only be one, but the list can grow if ambiguous operators are present)
    If multiple chains are present at the end, an Ambiguous node is returned containing all the candidates
    Otherwise the parsed AST is returned
    """
    while True:
        initial_lengths = [len(chain.items) for chain in chains]
        shunt_pass(chains, ctx)

        # exit loop if no reductions occurred
        if all(len(chain.items) == initial_length for initial_length, chain in zip(initial_lengths, chains)):
            break
    
    # during development, this might also be hit due to internal errors, e.g. bugs where something is not properly reducing
    # TODO: this could be a user error, e.g. `A&;b&c`. Do full error reporting
    # perhaps do: for each item in list, if is op, determine what kinds of reductions it could participate in and show error listing them vs what was present
    candidates: list[AST] = []
    for chain in chains:
        if not len(chain.items) == 1:
            raise ValueError(f"INTERNAL ERROR: reduce_loop produced {len(chain.items)} items, expected 1")
        item = chain.items[0]
        if not isinstance(item, AST):
            raise ValueError(f"INTERNAL ERROR: shunt-loop produced non-AST item. got {item=}")
        candidates.append(item)
    
    # multiple alternate parses means an ambiguous node
    if len(candidates) > 1:
        return Ambiguous(candidates)

    # unambiguous case
    return candidates[0]


def shunt_pass(chains: list[ProtoAST], ctx: Context) -> None:
    """apply a shunting reduction. modifies `chains` in place (potentially adding new lists in the case of ambiguities)"""
    new_chains: list[ProtoAST] = []
    for chain in chains:
        raw_shift_dirs, candidate_operator_idxs, reverse_ast_idxs_map = identify_shifts(chain, ctx)
        
        # TODO: for now, just simple case
        if not all(isinstance(shift_dir, int) for shift_dir in raw_shift_dirs):
            pdb.set_trace()
            all_shift_dirs = [...] 
        else:
            all_shift_dirs: list[list[ShiftDir]] = [raw_shift_dirs]

        # make copies of the current chain for each of the extra ambiguous shift direction sets
        ambiguous_cases = [chain]
        for _ in range(len(all_shift_dirs)-1):
            case = ProtoAST(chain.items.copy())
            ambiguous_cases.append(case)
            new_chains.append(case)

        # TODO: for ambiguous cases, basically make cartesian product over ambiguous shift dirs, and then identify reductions for each one
        for shift_dirs, case in zip(all_shift_dirs, ambiguous_cases):
            reductions = identify_reductions(case, shift_dirs, candidate_operator_idxs, reverse_ast_idxs_map, ctx)

            # apply reductions in reverse order to avoid index shifting issues
            for reduction, (left_bound, right_bound), _ in reversed(reductions):
                case.items[left_bound:right_bound] = [reduction]
    
    # include the new cases in the list of chains
    chains.extend(new_chains)


ShiftDir: TypeAlias = Literal[-1, 0, 1]

# TODO: replace candidate_operator_idxs with a more explicit pairing of each operator and a ShiftMeta
#       otherwise we'd need to do some weird list of list of candidate operator idxs to handle when ambiguous cases come up
#       when ambiguous cases can just include the shift direction in the ShiftMeta
#       Alternatively, we could just not return candidate_operator_idxs, and just infer it from where shift_dirs != 0, and add the shift dir to that index
#       candidate_operator_idxs = [i+shift_dir for i, shift_dir in enumerate(shift_dirs) if shift_dir != 0]
@dataclass
class ShiftMeta:
    left_op: t2.Operator
    right_op: t2.Operator
def identify_shifts(chain: ProtoAST, ctx: Context) -> tuple[list[ShiftDir|qint[ShiftMeta]], set[int], dict[int, int]]:
    # identify items that could shift
    ast_idxs = [i for i, item in enumerate(chain.items) if isinstance(item, AST)]
    asts = cast(list[AST], [chain.items[i] for i in ast_idxs])
    reverse_ast_idxs_map = {idx: i for i, idx in enumerate(ast_idxs)} # so we can look up the index of an ast's shift dir in the shift_dirs list
    candidate_operator_idxs: set[int] = set()
    
    # determine the direction items would shift according to operator binding power of the adjacent operators
    shift_dirs: list[ShiftDir|qint[ShiftMeta]] = [0] * len(ast_idxs)
    for i, (ast, ast_idx) in enumerate(zip(asts, ast_idxs)):
        # get left and/or right operators if present
        left_op = chain.items[ast_idx - 1] if ast_idx > 0 else None
        right_op = chain.items[ast_idx + 1] if ast_idx < len(chain.items) - 1 else None

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
            assert left_op is not None and right_op is not None, f'INTERNAL ERROR: left and right operators are not present. got {left_op=} and {right_op=}'
            assert not isinstance(left_op, AST) and not isinstance(right_op, AST), f'INTERNAL ERROR: left and right operators are not operators. got {left_op=} and {right_op=}'
            possible_left_ops = [left_op] if not isinstance(left_op, t2.QJuxtapose) else left_op.options
            possible_right_ops = [right_op] if not isinstance(right_op, t2.QJuxtapose) else right_op.options
            assert len(possible_left_ops) > 1 or len(possible_right_ops) > 1, f"INTERNAL ERROR: ambiguous binding powers didn't have multiple operator candidates. got {possible_left_ops=} and {possible_right_ops=}"
            """
            for each operator on left
                for each operator on right
                    determine shift dir for left vs right
                    assert left != right, INTERNAL ERROR
                    dir = sign(right-left) (or might be the other way around)
                    if left > right
                        insert into table: ambiguous_shift_map[i].append((dir, left_op))
                    elif right > left
                        insert into table: ambiguous_shift_map[i].append((dir, right_op))
            shift_dirs[i] = 'multiple'
            """
            quantum_shift_dirs: list[tuple[ShiftDir, ShiftMeta]] = []
            for left_op, right_op in product(possible_left_ops, possible_right_ops):
                _, left_bp = get_bind_power(left_op)
                right_bp, _ = get_bind_power(right_op)
                assert isinstance(left_bp, int) and isinstance(right_bp, int), f"INTERNAL ERROR: left and right binding powers are not integers. got {left_bp=} and {right_bp=} for {left_op=} and {right_op=}"
                assert left_bp != right_bp, f"INTERNAL ERROR: left and right have identical binding power. this shouldn't be possible. got {left_bp=} and {right_bp=} for {left_op=} and {right_op=}"
                shift_dir = -1 if left_bp > right_bp else 1
                quantum_shift_dirs.append((shift_dir, ShiftMeta(left_op, right_op)))


            # deduplicate shift dirs by combining operators from cases that shifted the same way back into quantum operators
            # TODO: need to work out how to actually do deduplication. this isn't right
            #       might be just grouping all ops with the same precedence level so that bind power isn't a qint
            # left_metas = [meta for dir, meta in quantum_shift_dirs if dir == -1]
            # right_metas = [meta for dir, meta in quantum_shift_dirs if dir == 1]
            # if len(left_metas) > 1:
            #     assert all(isinstance(meta.left_op, t2.Juxtapose) for meta in left_metas) or all(meta.left_op == left_metas[0].left_op for meta in left_metas), f"INTERNAL ERROR: left operators are not all the same or not all Juxtapose. got {left_metas=}"
            #     assert all(isinstance(meta.right_op, t2.Juxtapose) for meta in right_metas) or all(meta.right_op == right_metas[0].right_op for meta in right_metas), f"INTERNAL ERROR: right operators are not all the same or not all Juxtapose. got {right_metas=}"
            #     left_meta_left_op_loc = left_metas[0].left_op.loc
            #     left_meta_left_op = left_metas[0].left_op if not isinstance(left_metas[0].left_op, t2.Juxtapose) else t2.QJuxtapose(left_meta_left_op_loc, [meta.left_op for meta in left_metas])
            #     pdb.set_trace()



            # TODO: handle ambiguous case...
            # perhaps set shift = qint(-1, 1)
            # then when reducing, any shift that was qint makes an ambiguous node
            # and then after all the reductions, something spreads out all the ambiguous nodes orthogonally to the list of items...
            pdb.set_trace()
            ...
    
    return shift_dirs, candidate_operator_idxs, reverse_ast_idxs_map

Reduction: TypeAlias = tuple[AST, tuple[int, int], Associativity]
def identify_reductions(chain: ProtoAST, shift_dirs: list[ShiftDir], candidate_operator_idxs: set[int], reverse_ast_idxs_map: dict[int, int], ctx: Context) -> list[Reduction]:
    # identify reductions
    all_reductions: list[tuple[AST, tuple(int, int)]] = []
    for candidate_operator_idx in sorted(candidate_operator_idxs):
        left_ast_idx = candidate_operator_idx - 1
        right_ast_idx = candidate_operator_idx + 1
        left_ast = chain.items[left_ast_idx] if left_ast_idx >= 0 else None
        right_ast = chain.items[right_ast_idx] if right_ast_idx < len(chain.items) else None
        left_ast_shift_dir_idx = reverse_ast_idxs_map.get(left_ast_idx)  # index of the ast in the shift_dirs list
        right_ast_shift_dir_idx = reverse_ast_idxs_map.get(right_ast_idx)  # index of the ast in the shift_dirs list
        left_ast_shift_dir = shift_dirs[left_ast_shift_dir_idx] if left_ast_shift_dir_idx is not None else 0
        right_ast_shift_dir = shift_dirs[right_ast_shift_dir_idx] if right_ast_shift_dir_idx is not None else 0

        op = chain.items[candidate_operator_idx]
        assert isinstance(op, t2.Operator), f'INTERNAL ERROR: candidate operator is not an operator. got {op=}'
        associativity = get_associativity(op)
        if not isinstance(associativity, list):
            associativity = [associativity]
        
        reductions: list[tuple[AST, tuple[int, int], Associativity]] = []  # ast from reduction, and indices of tokens participating in the reduction
        for a in associativity:
            if (a == Associativity.left or a == Associativity.right) and (left_ast_shift_dir == 1 and right_ast_shift_dir == -1):
                assert isinstance(left_ast, AST) and isinstance(right_ast, AST), f'INTERNAL ERROR: left and right ASTs are not ASTs. got {left_ast=}, {right_ast=}, {left_ast_idx=}, {right_ast_idx=}'
                reductions.append((BinOp(op, left_ast, right_ast), (left_ast_idx, right_ast_idx+1), a))
            elif a == Associativity.prefix and (right_ast_shift_dir == -1) and (not could_be_binop(candidate_operator_idx, chain) and not could_be_postfix(candidate_operator_idx, chain)):
                assert isinstance(right_ast, AST), f'INTERNAL ERROR: right AST is not an AST. got {right_ast=}'
                reductions.append((Prefix(op, right_ast), (candidate_operator_idx, right_ast_idx+1), a))
            elif (a == Associativity.postfix) and (left_ast_shift_dir == 1):
                assert isinstance(left_ast, AST), f'INTERNAL ERROR: left AST is not an AST. got {left_ast=}'
                reductions.append((Postfix(op, left_ast), (left_ast_idx, candidate_operator_idx+1), a))
            elif (a == Associativity.flat) and (left_ast_shift_dir == 1 and right_ast_shift_dir == -1):
                # check for the whole flat chain
                res = collect_flat_operands(left_ast_idx, right_ast_idx, op, chain, reverse_ast_idxs_map, shift_dirs)
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
        
    return all_reductions


# TODO: a possibly cleaner approach than doing all this left checking of operators:
#       have the parse break chains into chunks where chunks are are some atom surrounded by prefix and postix operators
#       probably would use roughly the same process as is ues in t2.collect_chunk
#       then we wouldn't need to determine if something were prefix or postfix, it would all just be attached to the single atom in the chunk 

def could_be_binop(op_idx: int, chain: ProtoAST) -> bool:
    """
    determine if the operator (which is both prefix and binary according to the precedence table) could actually be a binary operator in its current position
    To be a binary operator, there would need to be a left operand that it connects to.
    The parsing rule is that when an operator could be prefix or binary, it always picks binary.

    example cases
    (looking at `/` next to `y`)
    x/y      -> True.  `/` could take `x` as a left operand
    x-/y     -> False. `-` is binary, thus making `/` a prefix
    x?/y     -> True. `?` is postfix only, therefore `/` could be binary
    /y       -> False. `/` has nothing to the left to connect to
    x+`/y    -> False. backtick (`) cannot connect to left `+` so backtick must be prefix, and therefore `/` cannot be binary
    x+``/y   -> False. backtick (`) cannot connect to left `+` so backtick must be prefix, and therefore `/` cannot be binary
    x`-/y    -> False. binary `-` means the `/` must be a prefix
    x`~/y    -> False. `~` left of `/` is prefix only, therefore `/` must also be prefix
    x`?/y    -> True. backtick (`) is postfix to `x`, and `?` is postfix only. Therefore `/` could be binary
    x`````/y -> True. all backticks (`) are postfix to `x`
    x``+``/y -> False. `+` in middle blocks right backticks (`) from connecting to `x`, so they must be prefixes on `y`
    """
    # early return if definitely not a binop
    op = chain.items[op_idx]
    assert isinstance(op, t2.Operator), f'INTERNAL ERROR: operator is not an operator. got {op=}'
    if not t2.is_binary_op(op):
        return False

    i = op_idx - 1
    while i >= 0:
        item = chain.items[i]
        # All ASTs except for semicolon can attach
        if isinstance(item, AST):
            if isinstance(item, Atom) and isinstance(item.item, t1.Semicolon):
                return False  # semicolon cannot attach to anything
            return True
        
        # type of op determines if the left is an expresison that could attach, or prefix to the current expression
        prefix = t2.is_prefix_op(item)
        postfix = t2.is_postfix_op(item)
        binary = t2.is_binary_op(item)
        if binary:
            return False
        if prefix and not postfix:
            return False
        if postfix and not prefix:
            return True
        if prefix and postfix:
            i -= 1 # can't determine yet if the left is a separate expression or prefix to this one
            continue
        
        raise ValueError(f'INTERNAL ERROR: operator is neither prefix, postfix, nor binary. got {item=}, {binary=}, {prefix=}, {postfix=}')
        
    # no items to left that could attach
    return False

# TODO: note that currently same symbol prefix and postfix operators always prefer the postfix one (regardless of ordering in the precedence table)
#       a more ideal algorithm would be able to use the table to select the correct interpretation
#       because the only operator that could be both prefix and postfix is backtick (`), it is fine to leave it as is
def could_be_postfix(op_idx: int, chain: ProtoAST) -> bool:
    """same idea as could_be_binop, but for postfix operators"""
    # early return if definitely not a postfix
    op = chain.items[op_idx]
    assert isinstance(op, t2.Operator), f'INTERNAL ERROR: operator is not an operator. got {op=}'
    if not t2.is_postfix_op(op):
        return False

    i = op_idx - 1

    while i >= 0:
        item = chain.items[i]
        if isinstance(item, AST):
            if isinstance(item, Atom) and isinstance(item.item, t1.Semicolon):
                return False  # semicolon cannot attach to anything
            return True
        
        prefix = t2.is_prefix_op(item)
        postfix = t2.is_postfix_op(item)
        binary = t2.is_binary_op(item)
        if binary:
            return False
        if postfix and not prefix:
            return True
        if prefix and not postfix:
            return False
        if prefix and postfix:
            i -= 1 # can't determine yet if the right is a separate expression or postfix to this one
            continue
        
        raise ValueError(f'INTERNAL ERROR: operator is neither prefix, postfix, nor binary. got {item=}, {binary=}, {prefix=}, {postfix=}')
        
    # no items to right that could attach
    return False

def collect_flat_operands(left_ast_idx: int, right_ast_idx: int, op: t2.Operator, chain: ProtoAST, reverse_ast_idxs_map: dict[int, int], shift_dirs: list[Literal[-1, 0, 1]]) -> tuple[list[AST], tuple[int, int]]|None:
    # check for the whole flat chain
    left_ast, right_ast = chain.items[left_ast_idx], chain.items[right_ast_idx]
    operands: list[AST] = [left_ast, right_ast]
    indices: list[int] = [left_ast_idx, right_ast_idx]
    i = right_ast_idx + 1

    # verify to the left
    j = left_ast_idx - 1
    while j > 0 and isinstance(chain.items[j], t2.Operator) and t2.op_equals(chain.items[j], op):
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
        operands.insert(0, chain.items[prev_ast_idx])
        indices.insert(0, prev_ast_idx)
        j -= 2

    # verify to the right
    while i < len(chain.items) and isinstance(chain.items[i], t2.Operator) and t2.op_equals(chain.items[i], op):
        next_ast_idx = i + 1
        if next_ast_idx >= len(chain.items):
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
        operands.append(chain.items[next_ast_idx])
        i += 2

    bounds = (indices[0], indices[-1]+1)

    return operands, bounds



def ast_to_tree_str(ast: AST, level: int = 0) -> str:
    space = "    "
    branch = "│   "
    tee = "├── "
    last = "└── "

    TreeItem: TypeAlias = AST | t1.Token | t2.Operator | str

    def truncate(s: str, max_len: int = 40) -> str:
        if len(s) <= max_len:
            return s
        return s[:max_len - 3] + "..."

    def op_label(op: t2.Operator) -> str:
        if isinstance(op, t1.Operator): return op.symbol
        if isinstance(op, t2.InvertedComparisonOp): return f"not {op.op}"
        if isinstance(op, t2.BroadcastOp): return f".{op_label(op.op)}"
        if isinstance(op, t2.CombinedAssignmentOp): return f"{op_label(op.op)}="
        if isinstance(op, t2.QJuxtapose): return f"QJuxtapose({', '.join(op_label(o) for o in op.options)})"
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
        if isinstance(tok, t1.String): return f"String({repr(truncate(tok.content.replace("\n", "\\n")))})"
        if isinstance(tok, t2.Chain): return "Chain"
        if isinstance(tok, t1.BasedString): return f"BasedString({tok.base})"
        if isinstance(tok, t2.BroadcastOp): return f"BroadcastOp({op_label(tok.op)})"
        if isinstance(tok, t2.CombinedAssignmentOp): return f"CombinedAssignmentOp({op_label(tok.op)})"
        if isinstance(tok, t2.OpFn): return f"OpFn({op_label(tok.op)})"
        return type(tok).__name__

    def text_label(text: str) -> str:
        return f"Text({repr(truncate(text.replace("\n", "\\n")))})"

    def item_label(item: TreeItem) -> str:
        if isinstance(item, AST): return ast_label(item)
        if isinstance(item, t1.Token): return token_label(item)
        if isinstance(item, t2.Operator): return f"Operator({op_label(item)})"
        if isinstance(item, str): return text_label(item)
        raise ValueError(f'INTERNAL ERROR: reached unreachable state. {item=}, {type(item)=}')

    def ast_label(node: AST) -> str:
        if isinstance(node, Atom): return token_label(node.item)
        if isinstance(node, BinOp): return f"BinOp({op_label(node.op)})"
        if isinstance(node, Prefix): return f"Prefix({op_label(node.op)})"
        if isinstance(node, Postfix): return f"Postfix({op_label(node.op)})"
        if isinstance(node, Flat): return f"Flat({op_label(node.op)})"
        if isinstance(node, Ambiguous): return f"Ambiguous({len(node.candidates)})"
        if isinstance(node, Block): return f"Block(kind='{node.kind}'{f", base={node.base}" if node.base else ""})"
        if isinstance(node, IString): return "IString"
        if isinstance(node, ParametricEscape): return "ParametricEscape"
        if isinstance(node, KeywordExpr): return "KeywordExpr"
        if isinstance(node, Flow): return "Flow"
        return type(node).__name__

    def iter_token_children(tok: t1.Token) -> list[tuple[str, TreeItem]]:
        if isinstance(tok, t2.Chain): return [(f"inner[{i}]", child) for i, child in enumerate(tok.items)]
        if isinstance(tok, t1.BasedString): return [("digits", "".join(d.src for d in tok.digits))]
        if isinstance(tok, t2.BroadcastOp): return [("op", tok.op)]
        if isinstance(tok, t2.CombinedAssignmentOp): return [("op", tok.op)]
        if isinstance(tok, t2.OpFn): return [("op", tok.op)]
        return []

    def iter_ast_children(node: AST) -> list[tuple[str, TreeItem]]:
        if isinstance(node, BinOp): return [("left", node.left), ("right", node.right)]
        if isinstance(node, (Prefix, Postfix)): return [("item", node.item)]
        if isinstance(node, Flat): return [(f"items[{i}]", item) for i, item in enumerate(node.items)]
        if isinstance(node, Atom): return iter_token_children(node.item)
        if isinstance(node, Ambiguous): return [(f"candidates[{i}]", child) for i, child in enumerate(node.candidates)]
        if isinstance(node, Block): return [(f"inner[{i}]", child) for i, child in enumerate(node.inner)]
        if isinstance(node, IString): return [(f"content[{i}]", child) for i, child in enumerate(node.content)]
        if isinstance(node, ParametricEscape): return [(f"inner[{i}]", child) for i, child in enumerate(node.inner)]
        if isinstance(node, KeywordExpr): return [(f"parts[{i}]", part) for i, part in enumerate(node.parts)]
        if isinstance(node, Flow): return [(f"arms[{i}]", arm) for i, arm in enumerate(node.arms)] + ([("default", node.default)] if node.default is not None else [])
        return []

    lines: list[str] = []
    root_prefix = space * level
    lines.append(root_prefix + item_label(ast))

    def render(item: TreeItem, prefix: str, edge_label: str, is_last: bool) -> None:
        connector = last if is_last else tee
        lines.append(prefix + connector + f"{edge_label}: {item_label(item)}")
        child_prefix = prefix + (space if is_last else branch)
        children: list[tuple[str, TreeItem]]
        if isinstance(item, AST):
            children = iter_ast_children(item)
        elif isinstance(item, t1.Token):
            children = iter_token_children(item)
        else:
            children = []
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