from typing import Generator, Sequence
from enum import Enum, auto
from dataclasses import dataclass, field
from itertools import groupby, chain as iterchain

from .syntax import (
    AST,
    Block,
    ListOfASTs,
    void,
    String,
    IString,
    Flowable,
    Identifier,
    Function,
    Call,
    Assign,

)
from .tokenizer import (
    Token,
    Block_t,
    Operator_t,
    ShiftOperator_t,
    Juxtapose_t,
    Comma_t,
    String_t,
    Escape_t,
    Undefined_t,
    Identifier_t,
    Integer_t,
    Boolean_t,
    BasedNumber_t,
    RawString_t,
    DotDot_t,
)
from .postok import (
    RangeJuxtapose_t,
    get_next_chain,
    Chain,
    is_op,
    Flow_t,

)


import pdb


"""
TODO:
- work out Scope
- work out typing so that we can determine what are functions as we parse.
   ---> functions are the main distinction for which precedence to use for juxtaposition
"""


# Scope class only used during parsing to keep track of callables
@dataclass
class Scope:
    parent: 'Scope | None' = None
    #TODO: maybe replace str->AST with str->signature (where signature might be constructed based on the func structure)
    callables: dict[str, AST | None] = field(default_factory=dict)

    @staticmethod
    def default() -> 'Scope':
        return Scope(callables={
            'printl': None,
            'print': None,
            'readl': None #TODO: this needs to say readl returns a string|error
        })


def top_level_parse(tokens: list[Token]) -> AST:
    """Main entrypoint to kick off parsing a sequence of tokens"""

    scope = Scope.default()
    ast = parse(tokens, scope)
    if isinstance(ast, ListOfASTs):
        ast = Block(ast.asts, '()')

    # post processing on the parsed AST
    # express_identifiers(ast)
    # tuples_to_arrays(ast)
    # ensure_no_prototypes(ast) #ensure all settled...
    # ensure_no_unwrapped_ranges(ast)
    # set_ast_scopes(ast, scope)

    return ast

def parse_generator(tokens: list[Token], scope: Scope) -> Generator[AST, None, None]:
    """
    Parse all tokens into a sequence of ASTs
    """

    while len(tokens) > 0:
        chain, tokens = get_next_chain(tokens)
        yield parse_chain(chain, scope)


def parse(tokens: list[Token], scope: Scope) -> AST:
    items = [*parse_generator(tokens, scope)]

    # depending on how many expressions were parsed, return an AST or container
    if len(items) == 0:
        ast = void # literally nothing was parsed
    elif len(items) == 1:
        ast = items[0]
    else:
        ast = ListOfASTs(items)

    return ast

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
        if isinstance(other, int):
            return all(v > other for v in self.values)
        return all(v > other for v in self.values)

    def __lt__(self, other: 'int|qint') -> bool:
        if isinstance(other, int):
            return all(v < other for v in self.values)
        return all(v < other for v in self.values)

    def __ge__(self, other: 'int|qint') -> bool: return self.__gt__(other)
    def __le__(self, other: 'int|qint') -> bool: return self.__lt__(other)
    def __eq__(self, other: object) -> bool: return False


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


"""
[HIGHEST PRECEDENCE]
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
[LOWEST PRECEDENCE]

TODO:
- add operators: as transmute |> <| -> <-> <- :

[Notes]
.. for ranges is not an operator, it is an expression. it uses juxtapose to bind to left/right arguments (or empty), and type-checks left and right
if-else-loop chain expr is more like a single unit, so it doesn't really have a precedence. but they act like they have the lowest precedence since the expressions they capture will be full chains only broken by space/seq
the unary versions of + - * / % have the same precedence as their binary versions
"""
operator_groups: list[tuple[Associativity, Sequence[Operator_t]]] = list(reversed([
    (Associativity.prefix, [Operator_t('@')]),
    (Associativity.left, [Operator_t('.'), Juxtapose_t(None)]),  # jux-call, jux-index
    (Associativity.prefix, [Operator_t('not')]),
    (Associativity.right,  [Operator_t('^')]),
    (Associativity.left, [Juxtapose_t(None)]),  # jux-multiply
    (Associativity.left, [Operator_t('*'), Operator_t('/'), Operator_t('%')]),
    (Associativity.left, [Operator_t('+'), Operator_t('-')]),
    (Associativity.left, [*map(ShiftOperator_t, ['<<', '>>', '<<<', '>>>', '<<!', '!>>'])]),
    (Associativity.none, [Operator_t('in')]),
    (Associativity.left, [Operator_t('=?'), Operator_t('>?'), Operator_t('<?'), Operator_t('>=?'), Operator_t('<=?')]),
    (Associativity.left, [Operator_t('and'), Operator_t('nand'), Operator_t('&')]),
    (Associativity.left, [Operator_t('xor'), Operator_t('xnor')]),
    (Associativity.left, [Operator_t('or'), Operator_t('nor'), Operator_t('|')]),
    (Associativity.none,  [Comma_t(',')]),
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


def operator_precedence(op: Operator_t) -> int | qint:

    # TODO: handling compound operators like .+, +=, .+=, etc.
    # if isinstance(op, CompoundOperator_t):
    #     op = op.base

    try:
        return precedence_table[op]
    except:
        raise ValueError(f"ERROR: expected operator, got {op=}") from None


def operator_associativity(op: Operator_t | int) -> Associativity:
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


def is_callable(ast:AST, scope: Scope):
    match ast:
        case Identifier(name):
            return name in scope.callables
        case _:
            raise ValueError(f"ERROR: unhandled case to check if is_callable: {ast=}")

    pdb.set_trace()


def parse_chain(chain: Chain[Token], scope: Scope) -> AST:
    assert isinstance(chain, Chain), f"ERROR: parse chain must be called on Chain[Token], got {type(chain)}"

    if len(chain) == 0:
        return void
    if len(chain) == 1:
        return parse_single(chain[0], scope)

    left, op, right = split_by_lowest_precedence(chain, scope)
    left, right = parse(left, scope), parse(right, scope)

    assert not (left is void and right is void), f"Internal Error: both left and right returned void during parse chain, implying both left and right side of operator were empty, i.e. chain was invalid: {chain}"

    # 3 cases are prefix expr, postfix expr, or binary expr
    if left is void:
        return build_unary_prefix_expr(op, right, scope)
    if right is void:
        return build_unary_postfix_expr(left, op, scope)
    return build_bin_expr(left, op, right, scope)




def split_by_lowest_precedence(tokens: Chain[Token], scope: Scope) -> tuple[Chain[Token], Token, Chain[Token]]:
    """
    return the integer index/indices of the lowest precedence operator(s) in the given list of tokens
    """
    assert isinstance(
        tokens, Chain), f"ERROR: `split_by_lowset_precedence()` may only be called on explicitly known Chain[Token], got {type(tokens)}"

    # collect all operators and their indices in the list of tokens
    idxs, ops = zip(*[(i, token) for i, token in enumerate(tokens) if is_op(token)])

    if len(ops) == 0:
        pdb.set_trace()
        # TODO: how to handle this case?
        return Chain(), None, Chain()
        raise ValueError()
    if len(ops) == 1:
        i, = idxs
        op, = ops
        return Chain(tokens[:i]), op, Chain(tokens[i+1:])

    # when more than one op present, find the lowest precedence one
    ranks = [operator_precedence(op) for op in ops]
    min_rank = min(ranks)

    # verify that the min is strictly less than or equal to all other ranks
    if not all(min_rank <= r for r in ranks):
        # TODO: probably enumerate out all permutations of the ambiguous operators and return all of them as a list of lists of indices
        # make use of scope/chain typeof to disambiguate if need be
        raise NotImplementedError(f"TODO: ambiguous precedence for {ops=} with {ranks=}, in token stream {tokens=}")

    # find operators with precedence equal to the current minimum
    op_idxs = [i for i, r in zip(idxs, ranks) if r == min_rank]

    if len(op_idxs) == 1:
        i, = op_idxs
        return Chain(tokens[:i]), tokens[i], Chain(tokens[i+1:])

    # handling when multiple ops have the same precedence, select based on associativity rules
    if isinstance(min_rank, qint):
        assocs = {operator_associativity(i) for i in min_rank.values}
        if len(assocs) > 1:
            raise NotImplementedError(
                f'TODO: need to type check to deal with multiple/ambiguous operator associativities: {assocs}')
        assoc, = assocs
    else:
        assoc = operator_associativity(min_rank)

    match assoc:
        case Associativity.left: i = op_idxs[-1]
        case Associativity.right: i = op_idxs[0]
        case Associativity.prefix: i = op_idxs[0]
        case Associativity.postfix: i = op_idxs[-1]
        case Associativity.none: i = op_idxs[-1]  # default to left. handled later in parsing
        case Associativity.fail: raise ValueError(f'Cannot handle multiple given operators in chain {tokens}, as lowest precedence operator is marked as un-associable.')

    return Chain(tokens[:i]), tokens[i], Chain(tokens[i+1:])





def parse_single(token: Token, scope: Scope) -> AST:
    """Parse a single token into an AST"""
    match token:
        case Undefined_t(): return undefined
        case Identifier_t(): return Identifier(token.src)
        case Integer_t(): return Number(int(token.src))
        case Boolean_t(): return Bool(bool_to_bool(token.src))
        case BasedNumber_t(): return Number(based_number_to_int(token.src))
        case RawString_t(): return String(token.to_str())
        case DotDot_t(): return Range()
        case String_t(): return parse_string(token, scope)
        case Block_t(): return parse_block(token, scope)
        case Flow_t(): return parse_flow(token, scope)

        case _:
            # TODO handle other types...
            pdb.set_trace()
            ...

    pdb.set_trace()
    raise NotImplementedError()
    ...


def build_bin_expr(left: AST, op: Token, right: AST, scope: Scope) -> AST:
    """create a unary prefix expression AST from the op and right AST"""

    match op:
        case Juxtapose_t():
            if is_callable(left, scope):
                return Call(left, right)
            else:
                return BinOp(left, right, Operator_t('*'))

        case Operator_t(op='='):
            if isinstance(left, Identifier) or isinstance(left, Declare):
                return Assign(left, right)
            else:
                # TODO: handle other cases, e.g. a.b, a[b], etc.
                #      probably make bind take str|AST as the left-hand-side target
                #      return Bind(left, right)
                pdb.set_trace()
                ...

        case Operator_t(op='=>'):
            if isinstance(left, Void):
                # TODO: scope needs to be set. not sure if should set here or on a post processing pass...
                return Function([], right, scope)
            elif isinstance(left, Identifier):
                return Function([Arg(left.name)], right, scope)
            elif isinstance(left, Block):
                pdb.set_trace()
                ...
            # TODO: what about typed arguments, or arguments with default values...
            else:
                raise ValueError(f'Unrecognized left-hand side for function literal: {left=}, {right=}')

        # a bunch of simple cases:
        # case ShiftOperator_t(op='<<'):  return LeftShift(left, right)
        # case ShiftOperator_t(op='>>'):  return RightShift(left, right)
        # case ShiftOperator_t(op='<<<'): return LeftRotate(left, right)
        # case ShiftOperator_t(op='>>>'): return RightRotate(left, right)
        # case ShiftOperator_t(op='<<!'): return LeftRotateCarry(left, right)
        # case ShiftOperator_t(op='!>>'): return RightRotateCarry(left, right)
        case Operator_t(op='+'): return Add(left, right, None)
        case Operator_t(op='-'): return Sub(left, right, None)
        case Operator_t(op='*'): return Mul(left, right, None)
        case Operator_t(op='/'): return Div(left, right, None)
        case Operator_t(op='%'): return Mod(left, right, None)
        case Operator_t(op='^'): return Pow(left, right, None)

        # comparison operators
        case Operator_t(op='=?'): return Equal(left, right)
        case Operator_t(op='>?'): return Greater(left, right)
        case Operator_t(op='<?'): return Less(left, right)
        case Operator_t(op='>=?'): return GreaterEqual(left, right)
        case Operator_t(op='<=?'): return LessEqual(left, right)
        # case Operator_t(op='in?'): return MemberIn(left, right)
        # case Operator_t(op='is?'): return Is(left, right)
        # case Operator_t(op='isnt?'): return Isnt(left, right)
        # case Operator_t(op='<=>'): return ThreewayCompare(left, right)

        # Logical Operators. TODO: outtype=Bool is not flexible enough...
        case Operator_t(op='and'): return And(left, right, outtype=Bool)
        case Operator_t(op='or'): return Or(left, right, outtype=Bool)
        case Operator_t(op='nand'): return Nand(left, right, outtype=Bool)
        case Operator_t(op='nor'): return Nor(left, right, outtype=Bool)
        case Operator_t(op='xor'): return Xor(left, right, outtype=Bool)
        case Operator_t(op='xnor'): return Xnor(left, right, outtype=Bool)

        # Misc Operators
        case RangeJuxtapose_t():
            if isinstance(right, Range):
                assert right.first is undefined and right.second is undefined, f"ERROR: can't attach expression to range, range already has values. Got {
                    left=}, {right=}"
                match left:
                    case Tuple(exprs=[first, second]):
                        right.first = first
                        right.second = second
                        return right
                    case _:
                        right.first = left
                        return right

            if isinstance(left, Range):
                assert left.secondlast is undefined and left.last is undefined, f"ERROR: can't attach expression to range, range already has values. Got {
                    left=}, {right=}"
                match right:
                    case Tuple(exprs=[secondlast, last]):
                        left.secondlast = secondlast
                        left.last = last
                        return left
                    case _:
                        left.last = right
                        return left

            raise ValueError(f'INTERNAL ERROR: Range Juxtapose must be next to a range. Got {left=}, {right=}')

        case Comma_t():
            # TODO: combine left or right tuples into a single tuple
            if isinstance(left, Tuple) and isinstance(right, Tuple):
                return Tuple([*left.exprs, *right.exprs])
            elif isinstance(left, Tuple):
                return Tuple([*left.exprs, right])
            elif isinstance(right, Tuple):
                return Tuple([left, *right.exprs])
            else:
                return Tuple([left, right])

        case Operator_t(op='else'):
            if isinstance(left, Flow) and isinstance(right, Flow):
                # merge left+right as single flow
                return Flow([*left.branches, *right.branches])
            elif isinstance(left, Flow):
                # append right to left
                return Flow([*left.branches, right])
            elif isinstance(right, Flow):
                # prepend left to right
                return Flow([left, *right.branches])
            else:
                # create a new flow out of the left and right
                return Flow([left, right])

        case Operator_t(op='in'):
            if isinstance(left, Identifier):
                return In(left.name, right)

            pdb.set_trace()
            # TODO: handle unpacking case where left is a PackStruct
            # TDB if post-tokenizer or parser handles. probably parser, which would build a PackStruct AST node
            # elif isinstance(left, PackStruct):
            #     return In(left, right)

            raise NotImplementedError(
                f"Parsing of operator 'in' operator for non-identifiers on left, has not been implemented yet. Got {left=}, {right=}")

        case _:
            pdb.set_trace()
            raise NotImplementedError(f'Parsing of operator {op} has not been implemented yet')


def build_unary_prefix_expr(op: Token, right: AST, scope: Scope) -> AST:
    """create a unary prefix expression AST from the op and right AST"""
    match op:
        # normal prefix operators
        case Operator_t(op='+'): return right
        case Operator_t(op='-'): return Neg(right, None)
        case Operator_t(op='*'): return right
        case Operator_t(op='/'): return Inv(right, None)
        case Operator_t(op='not'): return Not(right, outtype=Bool)  # TODO: don't want to hardcode Bool here!
        case Operator_t(op='@'): raise NotImplementedError(f"TODO: prefix op: {op=}")
        case Operator_t(op='...'): raise NotImplementedError(f"TODO: prefix op: {op=}")

        # binary operators that appear to be unary because the left can be void
        # => called as unary prefix op means left was ()/void
        case Operator_t(op='=>'): return Function(void, right)

        case _:
            raise ValueError(f"INTERNAL ERROR: {op=} is not a known unary prefix operator")


def build_unary_postfix_expr(left: AST, op: Token, scope: Scope) -> AST:
    """create a unary postfix expression AST from the left AST and op token"""
    match op:
        # normal postfix operators
        case Operator_t(op='!'): raise NotImplementedError(f"TODO: postfix op: {op=}")  # return Fact(left)

        # binary operators that appear to be unary because the right can be void
        # anything juxtaposed with void is treated as a zero-arg call()
        case Juxtapose_t(): return Call(to_callable(left), Array([]))

        case _:
            raise NotImplementedError(f"TODO: {op=}")


def parse_string(token: String_t, scope: Scope) -> String | IString:
    """Convert a string token to an AST"""

    if len(token.body) == 1 and isinstance(token.body[0], str):
        return String(token.body[0])

    # else handle interpolation strings
    parts = []
    for chunk in token.body:
        if isinstance(chunk, str):
            parts.append(chunk)
        elif isinstance(chunk, Escape_t):
            parts.append(chunk.to_str())
        else:
            # put any interpolation expressions in a new scope
            ast = parse(chunk.body, scope)
            if isinstance(ast, Block):
                ast.brackets = '{}'
            else:
                ast = Block([ast], brackets='{}')
            parts.append(ast)

    # combine any adjacent Strings into a single string (e.g. if there were escapes)
    parts = iterchain(*((''.join(g),) if issubclass(t, str) else (*g,) for t, g in groupby(parts, type)))
    # convert any free strings to ASTs
    parts = [p if not isinstance(p, str) else String(p) for p in parts]

    return IString(parts)


def parse_block(block: Block_t, scope: Scope) -> AST:
    """Convert a block token to an AST"""

    # if new scope block, nest the current scope
    newscope = block.left == '{' and block.right == '}'
    if newscope:
        scope = Scope(scope)

    # parse the inside of the block
    inner = parse(block.body, scope)

    delims = block.left + block.right
    match delims, inner:
        case '()' | '{}', void:
            return inner
        case '()' | '{}', ListOfASTs():
            return Block(inner.asts, brackets=delims)
        case '[]', ListOfASTs():
            # TODO: handle if this should be an object or dictionary instead of an array
            return Array(inner.asts)
        case '()' | '[]' | '(]' | '[)', Range():
            inner.include_first = block.left == '['
            inner.include_last = block.right == ']'
            # inner.was_wrapped = True #TODO: look into removing this attribute (needs post-tokenization process to be able to separate the range (and any first,second..last expressions) from surrounding tokens)
            return inner

        # catch all cases for any type of AST inside a block or range
        case '()' | '{}', _:
            return Block([inner], newscope=delims == '{}')
        case '[]', _:
            # TODO: handle if this should be an object or dictionary instead of an array
            return Array([inner])
        case _:
            pdb.set_trace()
            raise NotImplementedError(f'block parse not implemented for {block.left+block.right}, {type(inner)}')


def parse_flow(flow: Flow_t, scope: Scope) -> Flowable:

    # special case for closing else clause in a flow chain. Treat as `<if> <true> <clause>`
    if flow.keyword is None:
        return If(Bool(True), parse_chain(flow.clause, scope))

    cond = parse_chain(flow.condition, scope)
    clause = parse_chain(flow.clause, scope)

    match flow.keyword:
        case Keyword_t(src='if'): return If(cond, clause)
        case Keyword_t(src='loop'): return Loop(cond, clause)
        case _:
            pdb.set_trace()
            ...
            raise NotImplementedError('TODO: other flow keywords, namely lazy')
    pdb.set_trace()
    ...
