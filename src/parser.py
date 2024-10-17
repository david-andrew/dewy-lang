from typing import Generator, Sequence, cast, overload, Literal, Type as PyType
from enum import Enum, auto
from dataclasses import dataclass, field
from itertools import groupby, chain as iterchain

from .syntax import (
    AST,
    Access,
    Declare,
    PointsTo, BidirPointsTo,
    Type,
    ListOfASTs, PrototypeTuple, Block, BareRange, Ellipsis, Spread, Array, Group, Range, ObjectLiteral, Dict, BidirDict, TypeParam,
    Void, Undefined, void, undefined, untyped,
    String, IString,
    Flowable, Flow, If, Loop, Default,
    PrototypeFunctionLiteral, PrototypePyAction, Call,
    Index,
    PrototypeIdentifier, Identifier, TypedIdentifier, ReturnTyped, UnpackTarget, Assign,
    Int, Bool,
    Range, IterIn,
    Less, LessEqual, Greater, GreaterEqual, Equal, MemberIn,
    LeftShift, RightShift, LeftRotate, RightRotate, LeftRotateCarry, RightRotateCarry,
    Add, Sub, Mul, Div, IDiv, Mod, Pow,
    And, Or, Xor, Nand, Nor, Xnor,
    Not, UnaryPos, UnaryNeg, UnaryMul, UnaryDiv, AtHandle,
    DeclarationType,
    DeclareGeneric, Parameterize,
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
    TypeParam_t,
    Undefined_t,
    Identifier_t,
    Integer_t,
    Boolean_t,
    BasedNumber_t,
    RawString_t,
    DotDot_t, DotDotDot_t,
    Keyword_t,
)
from .postok import (
    RangeJuxtapose_t,
    EllipsisJuxtapose_t,
    TypeParamJuxtapose_t,
    get_next_chain,
    Chain,
    is_op,
    Flow_t,
    Declare_t,
    OpChain_t,
    VectorizedOp_t,
    CombinedAssignmentOp_t,
)
from .utils import (
    bool_to_bool,
    based_number_to_int,
)

import pdb



# Scope class only used during parsing to keep track of callables
@dataclass
class Scope:
    @dataclass
    class _var():
        # name:str #name is stored in the dict key
        decltype: DeclarationType
        type: Type
        value: AST

    parent: 'Scope | None' = None
    # callables: dict[str, AST | None] = field(default_factory=dict) #TODO: maybe replace str->AST with str->signature (where signature might be constructed based on the func structure)
    vars: 'dict[str, Scope._var]' = field(default_factory=dict)

    @overload
    def get(self, name:str, throw:Literal[True]=True, search_parents:bool=True) -> 'Scope._var': ...
    @overload
    def get(self, name:str, throw:Literal[False], search_parents:bool=True) -> 'Scope._var|None': ...
    def get(self, name:str, throw:bool=True, search_parents:bool=True) -> 'Scope._var|None':
        for s in self:
            if name in s.vars:
                return s.vars[name]
            if not search_parents:
                break

        if throw:
            raise KeyError(f'variable "{name}" not found in scope')
        return None

    def assign(self, name:str, value:AST):
        assert len(DeclarationType.__members__) == 2, f'expected only 2 declaration types: let, const. found {DeclarationType.__members__}'

        # var is already declared in current scope
        if name in self.vars:
            var = self.vars[name]
            assert var.decltype != DeclarationType.CONST, f"Attempted to assign to constant variable: {name=}{var=}. {value=}"
            var.value = value
            return

        var = self.get(name, throw=False)

        # var is not declared in any scope
        if var is None:
            self.let(name, value, untyped)
            return

        # var was declared in a parent scope
        if var.decltype == DeclarationType.LET:
            var.value = value
            return

        raise ValueError(f'Attempted to assign to constant variable: {name=}{var=}. {value=}')

    def declare(self, name:str, value:AST, type:Type, decltype:DeclarationType):
        if name in self.vars:
            var = self.vars[name]
            assert var.decltype != DeclarationType.CONST, f"Attempted to {decltype.name.lower()} declare a value that is const in this current scope. {name=}{var=}. {value=}"

        self.vars[name] = Scope._var(decltype, type, value)

    def let(self, name:str, value:AST, type:Type):
        self.declare(name, value, type, DeclarationType.LET)

    def const(self, name:str, value:AST, type:Type):
        self.declare(name, value, type, DeclarationType.CONST)

    def __iter__(self) -> Generator['Scope', None, None]:
        """return an iterator that walks up each successive parent scope. Starts with self"""
        s = self
        while s is not None:
            yield s
            s = s.parent

    #TODO: these should actually be defined in python.py. There should maybe only be stubs here..
    @classmethod
    def default(cls: PyType['Scope']) -> 'Scope':
        return cls(vars={
            'printl': Scope._var(
                DeclarationType.CONST,
                Type('callable'),
                PrototypePyAction(
                    Group([Assign(TypedIdentifier(Identifier('s'), Type('string')), String(''))]),
                    Type('void')
                )
            ),
            'print': Scope._var(
                DeclarationType.CONST,
                Type('callable'),
                PrototypePyAction(
                    Group([Assign(TypedIdentifier(Identifier('s'), Type('string')), String(''))]),
                    Type('void')
                )
            ),
            'readl': Scope._var(
                DeclarationType.CONST,
                Type('callable'),
                PrototypePyAction(
                    Group([]),
                    Type('string')
                )
            )
        })




def top_level_parse(tokens: list[Token]) -> AST:
    """Main entrypoint to kick off parsing a sequence of tokens"""

    scope = Scope.default()
    ast = parse(tokens, scope)
    if isinstance(ast, ListOfASTs):
        ast = Group(ast.asts)

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
    <jux ellipsis>                      //e.g. [...args]
    :                                   //e.g. let x:int
    :>                                  //e.g. let x:():>int => 42
    (prefix) not
    (postfix) ? `
    ^                                   //right-associative
    <jux mul>
    / * %
    + -
    << >> <<< >>> <<! !>>
    ,                                   //tuple maker
    <jux range>                         //e.g. [first,second..last]
    in
    =? >? <? >=? <=? not=? <=> is? isnt? @?
    and nand &
    xor xnor                            //following C's precedence: and > xor > or
    or nor |
    as transmute
    =>
    |>                                  //function pipe operators
    <|
    -> <->                              //dict pointers
    = .= <op>= .<op>=  (e.g. += .+=)    //right-associative (but technically causes a type error since assignments can't be chained)
    else
    (postfix) ;
    <seq> (i.e. space)
[LOWEST PRECEDENCE]

[Notes]
.. for ranges is not an operator, it is an expression. it uses juxtapose to bind to left/right arguments (or empty), and type-checks left and right
if-else-loop chain expr is more like a single unit, so it doesn't really have a precedence. but they act like they have the lowest precedence since the expressions they capture will be full chains only broken by space/seq
the unary versions of + - * / % have the same precedence as their binary versions
"""
operator_groups: list[tuple[Associativity, Sequence[Operator_t]]] = list(reversed([
    (Associativity.prefix, [Operator_t('@')]),
    (Associativity.left, [Operator_t('.'), Juxtapose_t(None)]),  # jux-call, jux-index
    (Associativity.right, [EllipsisJuxtapose_t(None)]),  # jux-ellipsis
    (Associativity.none, [TypeParamJuxtapose_t(None)]),
    (Associativity.none, [Operator_t(':')]),
    (Associativity.right, [Operator_t(':>')]),
    (Associativity.prefix, [Operator_t('not')]),
    (Associativity.right,  [Operator_t('^')]),
    (Associativity.left, [Juxtapose_t(None)]),  # jux-multiply
    (Associativity.left, [Operator_t('*'), Operator_t('/'), Operator_t('%')]),
    (Associativity.left, [Operator_t('+'), Operator_t('-')]),
    (Associativity.left, [*map(ShiftOperator_t, ['<<', '>>', '<<<', '>>>', '<<!', '!>>'])]),
    (Associativity.none,  [Comma_t(',')]),
    (Associativity.left, [RangeJuxtapose_t(None)]),  # jux-range
    (Associativity.none, [Operator_t('in')]),
    (Associativity.left, [Operator_t('=?'), Operator_t('>?'), Operator_t('<?'), Operator_t('>=?'), Operator_t('<=?')]),
    (Associativity.left, [Operator_t('and'), Operator_t('nand'), Operator_t('&')]),
    (Associativity.left, [Operator_t('xor'), Operator_t('xnor')]),
    (Associativity.left, [Operator_t('or'), Operator_t('nor'), Operator_t('|')]),
    (Associativity.none,  [Operator_t('as'), Operator_t('transmute')]),
    (Associativity.right,  [Operator_t('=>')]),  # () => () => () => 42
    (Associativity.right, [Operator_t('|>')]),
    (Associativity.left, [Operator_t('<|')]),
    (Associativity.fail,  [Operator_t('->'), Operator_t('<->')]),
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
        assert isinstance(i, int), f'Cannot determine associativity of operator ({op}) with multiple precedence levels ({i})'
    else:
        i = op
    try:
        return associativity_table[i]
    except:
        raise ValueError(f"Error: failed to determine associativity for operator {op}") from None


def is_callable(ast:AST, scope: Scope):
    match ast:
        # ASTs the have to be evaluated to determine the type
        case PrototypeIdentifier(name):
            #TODO: use full type checker here to determine the type
            # DEBUG: for now, hardcode to call
            return True
        #TODO: any other types that need to be evaluated to determine if callable
        case Access(right=PrototypeIdentifier()) | Access(right=AtHandle(operand=PrototypeIdentifier())):
            #TODO: same deal as above. for debugging, hardcode to call
            return True
        
        # known callable ASTs
        case PrototypePyAction() | PrototypeFunctionLiteral():
            return True

        #TODO: may change this in the future, but for now, assume at handle can only be used on callables 
        #      as in when doing partial evaluation
        case AtHandle():
            return True

        # known non-callables
        case Int() | String() | Bool(): #TODO: rest of them..
            return False

        # recuse into other ASTs
        # TODO: need to handle more cases for group. e.g. it could have multiple items that are void, but still only return a single AST
        #       and then also if there are multiple non-void items that makes a generator, which I think is not callable
        case Group(items):
            if len(items) == 0: return False #TODO: this generally shouldn't be possible as this should parse to a void literal
            if len(items) == 1: return is_callable(items[0], scope)
            pdb.set_trace()
            raise NotImplementedError(f"ERROR: unhandled case to check if is_callable: {ast=}")
            types = [get_type(i, scope) for i in items]
            types = [*filter(lambda t: t is not void, types)]
            if len(types) == 0: return False # this is possible if all items evaluate to void
            if len(types) == 1: return is_callable_type(types[0])
            if len(types) > 1: return False

        case _:
            raise ValueError(f"ERROR: unhandled case to check if is_callable: {ast=}")

    pdb.set_trace()

def is_indexable(ast:AST, scope: Scope):
    pdb.set_trace()
    raise NotImplementedError


def parse_chain(chain: Chain[Token], scope: Scope) -> AST:
    assert isinstance(chain, Chain), f"ERROR: parse chain must be called on Chain[Token], got {type(chain)}"

    if len(chain) == 0:
        return void
    if len(chain) == 1:
        return parse_single(chain[0], scope)

    left, op, right = split_by_lowest_precedence(chain, scope)
    left, right = parse_chain(left, scope), parse_chain(right, scope)

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
        # return Chain(), None, Chain()
        raise ValueError()
    if len(ops) == 1:
        i, = idxs
        op, = ops
        return Chain(tokens[:i]), op, Chain(tokens[i+1:])

    # when more than one op present, find the lowest precedence one
    ranks = [operator_precedence(op) for op in ops]
    min_rank = min(ranks)
    min_idx = ranks.index(min_rank)

    # verify that the min is strictly less than or equal to all other ranks
    if not all(min_rank <= r for r in ranks[:min_idx] + ranks[min_idx+1:]):
        # TODO: probably enumerate out all permutations of the ambiguous operators and return all of them as a list of lists of indices
        # make use of scope/chain typeof to disambiguate if need be
        pdb.set_trace()
        raise NotImplementedError(f"TODO: ambiguous precedence for {ops=} with {ranks=}, in token stream {tokens=}")

    # find operators with precedence equal to the current minimum
    op_idxs = [i for i, r in zip(idxs, ranks) if r == min_rank or r is min_rank]

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
        case Identifier_t(): return PrototypeIdentifier(token.src)
        case Integer_t(): return Int(int(token.src))
        case Boolean_t(): return Bool(bool_to_bool(token.src))
        case BasedNumber_t(): return Int(based_number_to_int(token.src))
        case RawString_t(): return String(token.to_str())
        case DotDot_t(): return BareRange(void, void)
        case DotDotDot_t(): return Ellipsis()
        case String_t(): return parse_string(token, scope)
        case Block_t(): return parse_block(token, scope)
        case TypeParam_t(): return parse_type_param(token, scope)
        case Flow_t(): return parse_flow(token, scope)
        case Declare_t(): return parse_declare(token, scope)

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
            elif isinstance(right, (Range, Array)) and is_indexable(left, scope):
                return Index(left, right)
            else:
                return Mul(left, right)

        case Operator_t(op='='): return Assign(left, right)
        case Operator_t(op='=>'): return PrototypeFunctionLiteral(left, right)
        case Operator_t(op='->'): return PointsTo(left, right)
        # case Operator_t(op='<-'): return PointsTo(right, left) #TBD if we just remove this one...
        case Operator_t(op='<->'): return BidirPointsTo(left, right)
        case Operator_t(op='.'): return Access(left, right)

        # a bunch of simple cases:
        case ShiftOperator_t(op='<<'):  return LeftShift(left, right)
        case ShiftOperator_t(op='>>'):  return RightShift(left, right)
        case ShiftOperator_t(op='<<<'): return LeftRotate(left, right)
        case ShiftOperator_t(op='>>>'): return RightRotate(left, right)
        case ShiftOperator_t(op='<<!'): return LeftRotateCarry(left, right)
        case ShiftOperator_t(op='!>>'): return RightRotateCarry(left, right)
        case Operator_t(op='+'): return Add(left, right)
        case Operator_t(op='-'): return Sub(left, right)
        case Operator_t(op='*'): return Mul(left, right)
        case Operator_t(op='/'): return Div(left, right)
        case Operator_t(op='÷'): return IDiv(left, right)
        case Operator_t(op='%'): return Mod(left, right)
        case Operator_t(op='^'): return Pow(left, right)

        # comparison operators
        case Operator_t(op='=?'): return Equal(left, right)
        case Operator_t(op='>?'): return Greater(left, right)
        case Operator_t(op='<?'): return Less(left, right)
        case Operator_t(op='>=?'): return GreaterEqual(left, right)
        case Operator_t(op='<=?'): return LessEqual(left, right)
        case Operator_t(op='in?'): return MemberIn(left, right)
        # case Operator_t(op='is?'): return Is(left, right)
        # case Operator_t(op='isnt?'): return Isnt(left, right)
        # case Operator_t(op='<=>'): return ThreewayCompare(left, right)

        # Logical Operators. TODO: outtype=Bool is not flexible enough...
        case Operator_t(op='and'): return And(left, right)
        case Operator_t(op='or'): return Or(left, right)
        case Operator_t(op='nand'): return Nand(left, right)
        case Operator_t(op='nor'): return Nor(left, right)
        case Operator_t(op='xor'): return Xor(left, right)
        case Operator_t(op='xnor'): return Xnor(left, right)

        # Misc Operators
        case Operator_t(op=':'):
            if isinstance(left, PrototypeIdentifier): return TypedIdentifier(Identifier(left.name), right)
            #TBD if there are other things that can have type annotations beyond identifiers
            raise ValueError(f'ERROR: can only apply a type to an identifier. Got {left=}, {right=}')
        case Operator_t(op=':>'): return ReturnTyped(left, right)

        case TypeParamJuxtapose_t():
            if isinstance(left, TypeParam):
                return DeclareGeneric(left, right)
            if isinstance(right, TypeParam):
                return Parameterize(left, right)
            raise ValueError(f"INTERNAL ERROR: TypeParamJuxtapose must be attached to a type param. {left=}, {right=}")

        case EllipsisJuxtapose_t():
            assert isinstance(left, Ellipsis), f'INTERNAL ERROR: EllipsisJuxtapose was attached to a non ellipsis token. {left=}, {right=}'
            return Spread(right)

        case RangeJuxtapose_t():
            if isinstance(right, BareRange):
                assert right.left is void, f"ERROR: can't attach expression to range, range already has values. Got {left=}, {right=}"
                right.left = left
                return right

            if isinstance(left, BareRange):
                assert left.right is void, f"ERROR: can't attach expression to range, range already has values. Got {left=}, {right=}"
                left.right = right
                return left

            raise ValueError(f'INTERNAL ERROR: Range Juxtapose must be next to a range. Got {left=}, {right=}')

        case Comma_t():
            # TODO: combine left or right tuples into a single tuple
            if isinstance(left, PrototypeTuple) and isinstance(right, PrototypeTuple):
                return PrototypeTuple([*left.items, *right.items])
            elif isinstance(left, PrototypeTuple):
                return PrototypeTuple([*left.items, right])
            elif isinstance(right, PrototypeTuple):
                return PrototypeTuple([left, *right.items])
            else:
                return PrototypeTuple([left, right])

        case Operator_t(op='else'):
            if isinstance(left, Flow) and isinstance(right, Flow):
                # merge left+right as single flow
                return Flow([*left.branches, *right.branches])
            elif isinstance(left, Flow):
                # append right to left
                assert not isinstance(left.branches[-1], Default), f"ERROR: can't merge default branch into middle of flow. Got: {left=}, {right=}"
                if isinstance(right, Flowable):
                    return Flow([*left.branches, right])
                return Flow([*left.branches, Default(right)])

            elif isinstance(right, Flow):
                # prepend left to right
                assert isinstance(left, Flowable), f"ERROR: can only prepend Flowables to left of a Flow. Got: {left=}, {right=}"
                return Flow([left, *right.branches])
            else:
                # create a new flow out of the left and right
                assert isinstance(left, Flowable), f"ERROR: can only create a Flow from Flowables. Got: {left=}, {right=}"
                if isinstance(right, Flowable):
                    return Flow([left, right])
                return Flow([left, Default(right)])

        case Operator_t(op='in'):
            return IterIn(left, right)
        
        case OpChain_t(ops=list() as ops) if len(ops) > 1: #TODO: shouldn't be possible to make an OpChain with 1 or 0 ops
            for unary_op in reversed(ops[1:]):
                right = build_unary_prefix_expr(unary_op, right, scope)
            return build_bin_expr(left, ops[0], right, scope)            

        case _:
            pdb.set_trace()
            raise NotImplementedError(f'Parsing of operator {op} has not been implemented yet')


def build_unary_prefix_expr(op: Token, right: AST, scope: Scope) -> AST:
    """create a unary prefix expression AST from the op and right AST"""
    match op:
        # normal prefix operators
        case Operator_t(op='+'): return UnaryPos(right)
        case Operator_t(op='-'): return UnaryNeg(right)
        case Operator_t(op='*'): return UnaryMul(right)
        case Operator_t(op='/'): return UnaryDiv(right)
        case Operator_t(op='not'): return Not(right)  # TODO: don't want to hardcode Bool here!
        case Operator_t(op='@'): return AtHandle(right)

        # binary operators that appear to be unary because the left can be void
        # => called as unary prefix op means left was ()/void
        case Operator_t(op='=>'): return PrototypeFunctionLiteral(void, right)

        case _:
            raise ValueError(f"INTERNAL ERROR: {op=} is not a known unary prefix operator")


def build_unary_postfix_expr(left: AST, op: Token, scope: Scope) -> AST:
    """create a unary postfix expression AST from the left AST and op token"""
    match op:
        # normal postfix operators
        case Operator_t(op='!'): raise NotImplementedError(f"TODO: postfix op: {op=}")  # return Fact(left)

        # binary operators that appear to be unary because the right can be void
        # anything juxtaposed with void is treated as a zero-arg call()
        case Juxtapose_t():
            return Call(left)

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
                parts.append(ast)
            elif isinstance(ast, ListOfASTs):
                pdb.set_trace()
                # not sure if this should ever come up, might be a parse bug
                # or might just need to convert to a block...
            else:
                parts.append(Block([ast]))

    # combine any adjacent Strings into a single string (e.g. if there were escapes)
    parts = iterchain(*((''.join(g),) if issubclass(t, str) else (*g,) for t, g in groupby(parts, type)))
    # convert any free strings to ASTs
    parts = [p if not isinstance(p, str) else String(p) for p in parts]

    # cast because pyright complains
    parts = cast(list[AST], parts)
    return IString(parts)


def as_dict_inners(items:list[AST]) -> list[PointsTo] | None:
    """Determine if the inner items indicate the container is a Dict (i.e. all items are points-to)"""
    if all(isinstance(i, PointsTo) for i in items):
        return cast(list[PointsTo], items)
    return None

def as_bidir_dict_inners(items:list[AST]) -> list[BidirPointsTo] | None:
    """Determine if the inner items indicate the container is a BidirDict (i.e. all items are bidir-points-to)"""
    if all(isinstance(i, BidirPointsTo) for i in items):
        return cast(list[BidirPointsTo], items)
    return None

def as_array_inners(items:list[AST]) -> list[AST] | None:
    """Determine if the inner items indicate the container is an Array (i.e. no points-to, assigns, or declarations)"""
    invalid_types = (Declare, Assign, PointsTo, BidirPointsTo)
    if any(isinstance(i, invalid_types) for i in items):
        return None
    return items

def as_object_inners(items:list[AST]) -> list[AST] | None:
    """determine if the inner items indicate the container is an Object (i.e. no points-to, and should contain at least one assign or declaration)"""
    invalid_types = (PointsTo, BidirPointsTo)
    expected_types = (Assign, Declare)
    if any(isinstance(i, invalid_types) for i in items):
        return None
    if not any(isinstance(i, expected_types) for i in items):
        return None
    return items

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
        case '()' | '{}' | '[]', Void():
            return inner
        case '()', ListOfASTs():
            return Group(inner.asts)
        case '{}', ListOfASTs():
            return Block(inner.asts)
        case '[]', ListOfASTs():
            if (asts:=as_dict_inners(inner.asts)) is not None:
                return Dict(asts)
            elif (asts:=as_bidir_dict_inners(inner.asts)) is not None:
                return BidirDict(asts)
            elif (asts:=as_array_inners(inner.asts)) is not None:
                return Array(asts)
            elif (asts:=as_object_inners(inner.asts)) is not None:
                return ObjectLiteral(inner.asts)
            # elif (asts:=as_array_generator_inners(inner.asts)) is not None:
            #     return ArrayGenerator(asts)
            # elif (asts:=as_dict_generator_inners(inner.asts)) is not None:
            #     return DictGenerator(asts)
            # elif (asts:=as_bidict_generator_inners(inner.asts)) is not None:
            #     return BidirDictGenerator(asts)
            #error cases
            if any(isinstance(i, PointsTo) for i in inner.asts) and not all(isinstance(i, PointsTo) for i in inner.asts):
                raise ValueError(f"ERROR: cannot mix PointsTo with other types in a dict: {inner=}")
            #TBD other known cases
            #otherwise there is an issue with the parser
            raise ValueError(f"INTERNAL ERROR: could not determine container type for {inner=}. Should have been suitably disambiguated by parser...")
        case '()' | '[]' | '(]' | '[)', BareRange():
            return Range(inner.left, inner.right, delims)

        # catch all cases for any type of AST inside a block or range
        case '()', _:
            return Group([inner])
        case '{}', _:
            return Block([inner])
        case '[]', PointsTo():
            return Dict([inner])
        case '[]', BidirPointsTo():
            return BidirDict([inner])
        case '[]', Assign() | Declare():
            return ObjectLiteral([inner])
        case '[]', _:
            # TODO: handle if this should be an object or dictionary instead of an array
            return Array([inner])
        case _:
            pdb.set_trace()
            raise NotImplementedError(f'block parse not implemented for {block.left+block.right}, {type(inner)}')



def parse_type_param(param: TypeParam_t, scope: Scope) -> TypeParam:
    items = parse(param.body, scope)
    if isinstance(items, ListOfASTs):
        return TypeParam(items.asts)
    return TypeParam([items])


def parse_flow(flow: Flow_t, scope: Scope) -> Flowable:

    # special case for closing else clause in a flow chain. Treat as `<if> <true> <clause>`
    if flow.keyword is None:
        return Default(parse_chain(flow.clause, scope))

    assert flow.condition is not None, f"ERROR: flow condition must be present for {flow=}"
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


def parse_declare(declare: Declare_t, scope: Scope) -> Declare:
    expr = parse_chain(declare.expr, scope)
    assert isinstance(expr, (PrototypeIdentifier, Identifier, TypedIdentifier, ReturnTyped, UnpackTarget, Assign)), f'ERROR: expected identifier, typed-identifier, or unpack target for declare expression, got {expr=}'
    match declare:
        case Declare_t(keyword=Keyword_t(src='let')): return Declare(DeclarationType.LET, expr)
        case Declare_t(keyword=Keyword_t(src='const')): return Declare(DeclarationType.CONST, expr)
        # case Declare_t(keyword=Keyword_t(src='local_const')): return Declare(DeclarationType.LOCAL_CONST, expr)
        # case Declare_t(keyword=Keyword_t(src='fixed_type')): return Declare(DeclarationType.FIXED_TYPE, expr)
        case _:
            raise ValueError(f"ERROR: unknown declare keyword {declare.keyword=}. Expected one of {DeclarationType.__members__}. {declare=}")
    pdb.set_trace()
    raise NotImplementedError






################################ Docs Markdown Helpers ################################
opname_map = {
    '@': 'reference',
    '.': 'access',
    '^': 'power',
    '*': 'multiply',
    '/': 'divide',
    '%': 'modulus',
    '+': 'add',
    '-': 'subtract',
    '<<': 'left shift',
    '>>': 'right shift',
    '>>>': 'rotate left no carry',
    '<<<': 'rotate right no carry',
    '<<!': 'rotate left with carry',
    '!>>': 'rotate right with carry',
    '>?': 'greater than',
    '<?': 'less than',
    '>=?': 'greater than or equal',
    '<=?': 'less than or equal',
    '=?': 'equal',
    'and': 'and',
    'nand': 'nand',
    '&': 'and',
    'xor': 'xor',
    'xnor': 'xnor',
    'or': 'or',
    'nor': 'nor',
    '|': 'or',
    '=>': 'function arrow',
    '=': 'bind',
    'else': 'flow alternate',
    ';': 'semicolon',
    'in': 'in',
    'as': 'as',
    'transmute': 'transmute',
    '|>': 'pipe',
    '<|': 'reverse pipe',
    '->': 'right pointer',
    '<->': 'bidir pointer',
    '<-': 'left pointer',
    ':': 'type annotation',

    Comma_t(None): 'comma',
    Juxtapose_t(None): 'unknown juxtapose',
    EllipsisJuxtapose_t(None): 'ellipsis juxtapose',
    RangeJuxtapose_t(None): 'range juxtapose',
    TypeParamJuxtapose_t(None): 'type param juxtapose',
}


def get_precedence_table_markdown() -> str:
    """return a string that is the markdown table for the docs containing all the operators"""
    header = '| Precedence | Operator | Name | Associativity |\n| --- | --- | --- | --- |'

    def get_ops_str(ops: list[Operator_t | ShiftOperator_t | Juxtapose_t | Comma_t]) -> str:
        return '<br>'.join(f'`{op.op if isinstance(op, (Operator_t, ShiftOperator_t)) else op.__class__.__name__[:-2].lower()}`' for op in ops)

    def get_opnames_str(ops: list[Operator_t | ShiftOperator_t | Juxtapose_t | Comma_t]) -> str:
        return '<br>'.join(f'{opname_map.get(op.op, None) if isinstance(op, (Operator_t, ShiftOperator_t)) else op.__class__.__name__[:-2].lower()}' for op in ops)

    def get_row_str(row: tuple[Associativity, list[Operator_t | ShiftOperator_t | Juxtapose_t | Comma_t]]) -> str:
        assoc, group = row
        return f'{get_ops_str(group)} | {get_opnames_str(group)} | {assoc.name}'

    rows = [
        f'| {i} | {get_row_str(row)} |'
        for i, row in reversed([*enumerate(operator_groups)])
    ]

    return header + '\n' + '\n'.join(rows)
