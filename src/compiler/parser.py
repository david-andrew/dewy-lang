# from __future__ import annotations

from dewy import (
    AST, PrototypeAST,
    Undefined, undefined,
    Void, void,
    Identifier,
    Callable,
    Orderable,
    Rangeable,
    Unpackable,
    Iter,
    Iterable,
    Type,
    Arg,
    Tuple,
    Function,
    Builtin,
    Let,
    Bind,
    PackStruct,
    Unpack,
    Block,
    Call,
    String, IString,
    BinOp,
    Equal, NotEqual, Less, LessEqual, Greater, GreaterEqual,
    Add, Sub, Mul, Div, IDiv, Mod, Pow,
    UnaryOp,
    Neg, Inv,
    Bool,
    Flow,
    If,
    Loop,
    In,
    Next,
    Number,
    Range,
    RangeIter,
    Array,
    Scope,
)
from tokenizer import ( tokenize, tprint, traverse_tokens,                       
    unary_prefix_operators,
    unary_postfix_operators,
    binary_operators,
    
    Token,

    WhiteSpace_t,

    Escape_t,

    Identifier_t,
    Block_t,
    TypeParam_t,
    RawString_t,
    String_t,
    Integer_t,
    BasedNumber_t,
    Hashtag_t,
    DotDot_t,

    Keyword_t,

    Juxtapose_t,
    Operator_t,
    ShiftOperator_t,
    Comma_t,
)

from postok import post_process, get_next_chain, is_op, Chain, Flow_t

from utils import based_number_to_int
from dataclasses import dataclass
from typing import Generator
from itertools import groupby, chain as iterchain
from enum import Enum, auto

try:
    from rich import print, traceback; traceback.install(show_locals=True)
except:
    print('rich unavailable for import. using built-in printing')

import pdb




#compiler pipeline steps:
# 1. tokenize
# 2. post tokenization
#    -> invert whitespace to juxtapose
#    -> bundle conditional chains into a single token
#    -> chain operator sequences into a single compount operator
#    -> desugar things, e.g. empty range `..` to `()..()`
# 3. parse tokens to AST
# 4. post parse
#    -> convert PrototypeASTs to concrete AST
#    -> (maybe) set correct scope for exprs that use (e.g. Function)
# 5. type checking, other validation, etc.
# 6. high level optimizations/transformations
# 7. generate code via a backend (e.g. llvm, c, python)
#    -> llvm: convert ast to ssa form, then generate llvm ir from ssa form



@dataclass
class qint:
    """
    quantum int for dealing with precedences that are multiple values at the same time
    qint's can only be strictly greater or strictly less than other values. Otherwise it's ambiguous
    """
    values:set[int]
    def __gt__(self, other:'int|qint') -> bool:
        if isinstance(other, int):
            return all(v > other for v in self.values)
        return all(v > other for v in self.values)
    def __lt__(self, other:'int|qint') -> bool:
        if isinstance(other, int):
            return all(v < other for v in self.values)
        return all(v < other for v in self.values)
    def __ge__(self, other:'int|qint') -> bool: return self.__gt__(other)
    def __le__(self, other:'int|qint') -> bool: return self.__lt__(other)
    def __eq__(self, other:'int|qint') -> bool: return False
        


######### Operator Precedence Table #########
#TODO: class for compund operators, e.g. += -= .+= .-= not=? not>? etc.
#TODO: how to handle unary operators in the table? perhaps make PrefixOperator_t/PostfixOperator_t classes?
#TODO: add specification of associativity for each row
class Associativity(Enum):
    left = auto()    #left-to-right
    right = auto()   #right-to-left
    prefix = auto()
    postfix = auto()
    none = auto()
    fail = auto()

operator_groups: list[tuple[Associativity, list[Operator_t|ShiftOperator_t|Juxtapose_t|Comma_t]]] = reversed([
    (Associativity.prefix, [Operator_t('@')]),
    (Associativity.left, [Operator_t('.'), Juxtapose_t(None)]),
    (Associativity.right,  [Operator_t('^')]),
    (Associativity.left, [Juxtapose_t(None)]),
    (Associativity.left, [Operator_t('*'), Operator_t('/'), Operator_t('%')]),
    (Associativity.left, [Operator_t('+'), Operator_t('-')]),
    (Associativity.left, [ShiftOperator_t('<<'), ShiftOperator_t('>>'), ShiftOperator_t('<<<'), ShiftOperator_t('>>>'), ShiftOperator_t('<<!'), ShiftOperator_t('!>>')]),
    (Associativity.none,  [Comma_t(None)]),
    (Associativity.left, [Operator_t('=?'), Operator_t('>?'), Operator_t('<?'), Operator_t('>=?'), Operator_t('<=?')]),
    (Associativity.left, [Operator_t('and'), Operator_t('nand'), Operator_t('&')]),
    (Associativity.left, [Operator_t('xor'), Operator_t('xnor')]),
    (Associativity.left, [Operator_t('or'), Operator_t('nor'), Operator_t('|')]),
    (Associativity.right,  [Operator_t('=>')]), # () => () => () => 42
    (Associativity.fail,  [Operator_t('=')]),
    (Associativity.none,  [Operator_t('else')]),
])
precedence_table: dict[Operator_t|ShiftOperator_t|Juxtapose_t|Comma_t, int|qint] = {}
associativity_table: dict[int, Associativity] = {}
for i, (assoc, group) in enumerate(operator_groups):

    #mark precedence level i as the specified associativity
    associativity_table[i] = assoc

    #insert all ops in the row into the precedence table at precedence level i
    for op in group:
        if op not in precedence_table:
            precedence_table[op] = i
            continue
        
        val = precedence_table[op]
        if isinstance(val, int):
            precedence_table[op] = qint({val, i})
        else:
            precedence_table[op] = qint(val.values|{i})


def operator_precedence(op:Operator_t|ShiftOperator_t|Juxtapose_t|Comma_t) -> int | qint:
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
    ,                                   //tuple maker
    <jux range>                         //TBD, e.g. [first,second..last]
    =? >? <? >=? <=? not=? <=> is? isnt? @?
    and nand &
    xor xnor                            //following C's precedence: and > xor > or
    or nor |
    =>
    = .= <op>= .<op>=  (e.g. += .+=)    //right-associative (but technically causes a type error since assignments can't be chained)
    else
    (postfix) ;
    <seq> (i.e. space)
    [LOWEST]

    TODO:
    - add operators: in as transmute |> <| -> <-> <- :

    [Notes]
    .. for ranges is not an operator, it is an expression. it uses juxtapose to bind to left/right arguments (or empty), and type-checks left and right
    if-else-loop chain expr is more like a single unit, so it doesn't really have a precedence. but they act like they have the lowest precedence since the expressions they capture will be full chains only broken by space/seq
    the unary versions of + - * / % have the same precedence as their binary versions
    """

    #TODO: handling compound operators like +=, .+=, etc.
    # if isinstance(op, CompoundOperator_t):
    #     op = op.base

    try:
        return precedence_table[op]
    except:
        raise ValueError(f"ERROR: expected operator, got {op=}") from None

def operator_associativity(op:Operator_t|ShiftOperator_t|Juxtapose_t|Comma_t|int) -> Associativity:
    if not isinstance(op, int):
        i = operator_precedence(op)
        assert isinstance(i, int), f'Cannot determine associativity of operator ({op}) with multiple precedence levels ({i})'
    else:
        i = op
    try:
        return associativity_table[i]
    except:
        raise ValueError(f"Error: failed to determine associativity for operator {op}") from None


#TODO: this isn't very well integrated into the type system...
# operator_result_type_table = {
#     (Number.type, Add, Number.type): Number,
#     (Number.type, Sub, Number.type): Number,
#     (Number.type, Mul, Number.type): Number,
#     (Number.type, Div, Number.type): Number,
#     (Inv, Number.type): Number,
#     (Neg, Number.type): Number,
#     #TODO: add anything else to the matrix
# }


# @cache
def split_by_lowest_precedence(tokens: Chain[Token], scope:Scope) -> tuple[Chain[Token], Token, Chain[Token]]:
    """
    return the integer index/indices of the lowest precedence operator(s) in the given list of tokens
    """
    assert isinstance(tokens, Chain), f"ERROR: `split_by_lowset_precedence()` may only be called on explicitly known Chain[Token], got {type(tokens)}"

    #collect all operators and their indices in the list of tokens
    idxs, ops = zip(*[(i,token) for i,token in enumerate(tokens) if is_op(token)])

    if len(ops) == 0:
        pdb.set_trace()
        #TODO: how to handle this case?
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
        #TODO: probably enumerate out all permutations of the ambiguous operators and return all of them as a list of lists of indices
        #make use of scope/chain typeof to disambiguate if need be
        raise NotImplementedError(f"TODO: ambiguous precedence for {ops=} with {ranks=}, in token stream {tokens=}")


    # find operators with precedence equal to the current minimum
    op_idxs = [i for i,r in zip(idxs, ranks) if r == min_rank]

    if len(op_idxs) == 1:
        i, = op_idxs
        return Chain(tokens[:i]), tokens[i], Chain(tokens[i+1:])

    # handling when multiple ops have the same precedence, select based on associativity rules
    if isinstance(min_rank, qint):
        assocs = {operator_associativity(i) for i in min_rank.values}
        if len(assocs) > 1:
            raise NotImplementedError(f'TODO: need to type check to deal with multiple/ambiguous operator associativities: {assocs}')
        assoc, = assocs
    else:
        assoc = operator_associativity(min_rank)
    
    match assoc:
        case Associativity.left: i = op_idxs[-1]
        case Associativity.right: i = op_idxs[0]
        case Associativity.prefix: i = op_idxs[0]
        case Associativity.postfix: i = op_idxs[-1]
        case Associativity.none: i = op_idxs[-1] #default to left. handled later in parsing
        case Associativity.fail: raise ValueError(f'Cannot handle multiple given operators in chain {tokens}, as lowest precedence operator is marked as un-associable.')
    
    return Chain(tokens[:i]), tokens[i], Chain(tokens[i+1:])

# @cache
def typeof(chain: list[Token], scope:Scope) -> Type|None: #this should be the same type system`` used in the interpreter!
    # recursively determine the type of the sequence of tokens
    # return none if the sequence does not form a valid type
    # follow a similar process to parsing, breaking down the expressions, etc.

    pdb.set_trace()
    chain, remainder = get_next_chain(chain)
    assert len(remainder) == 0, 'typeof may only be called on single chains of tokens'

    if len(chain) == 1:
        token, = chain
        return typeof_single(token, scope)
        
    # TODO: handle type check for more complicated chains...
    pdb.set_trace()
    left, op, right = split_by_lowest_precedence(chain, scope)
    left_t, right_t = typeof(left, scope), typeof(right, scope)

    pdb.set_trace()



def typeof_single(token:Token, scope:Scope) -> Type|None:

    pdb.set_trace()
    ...

def to_callable(ast:AST) -> str|Callable:
    """Convert the ast to either a string (identifier name) or Callable"""

    if isinstance(ast, Identifier):
        return ast.name
    if isinstance(ast, Callable):
        return ast
    
    # hacky way of dealing with blocks
    if isinstance(ast, Block):
        if len(ast.exprs) == 1:
            return to_callable(ast.exprs[0])
        else:
            pdb.set_trace()
            ...

    raise ValueError(f'Tried to prepare callable expression with unrecognized type {type(ast)}')


def to_call_args(ast:AST) -> Array:
    if isinstance(ast, Void):
        return Array([])
    
    if isinstance(ast, Tuple):
        return Array(ast.exprs)

    #TODO: some sort of check that ast is a valid single type...?
    return Array([ast])
    
    

def is_callable(ast:AST, scope:Scope) -> bool:
    #TODO: make calling typeof on an AST more robust/handle this better

    if isinstance(ast, Identifier):
        #check the type of the identifier in the scope
        if (val:=scope.get(ast.name, undefined)) is not undefined:
            return Type.is_instance(val.type, Callable.type)
        raise ValueError(f'Could not check is_callable. Identifier `{ast}` was undefined in scope.')

    # check if directly callable
    if isinstance(ast, Callable):
        return True
    
    # Non-callable types
    if isinstance(ast, (Number, String, IString)):
        return False

    # TODO: hacky way of dealing with blocks...
    if isinstance(ast, Block):
        if len(ast.exprs) == 1:
            return is_callable(ast.exprs[0], scope)
        else:
            pdb.set_trace()
            ...
    
    if isinstance(ast, PrototypeAST):
        raise NotImplementedError(f"Currently haven't handled is_callable for case of {type(ast)}")
        
    

    #other cases, e.g. function literals. should be able to use the AST type checking method at this point
    pdb.set_trace()
    ...

# don't need is_multipliable, because that is just the default case.
# also don't have to worry about the user making custom callable types not being parsed correctly,
#    since they should inherit from Callable, making is_callable return true for them!

def parse(tokens:list[Token], scope:Scope) -> AST:

    asts = []
    while len(tokens) > 0:
        chain, tokens = get_next_chain(tokens)

        if len(chain) == 1:
            asts.append(parse_single(chain[0], scope))
        else:
            asts.append(parse_chain(chain, scope))
    
    if len(asts) == 0:
        #literally nothing was parsed
        return void
    
    if len(asts) == 1:
        ast, = asts
        return ast
    
    block = Block(asts)
    block.newscope = True
    return block


def parse_single(token:Token, scope:Scope) -> AST:
    """Parse a single token into an AST"""
    match token:
        case Identifier_t():    return Identifier(token.src)
        case Integer_t():       return Number(int(token.src))
        case BasedNumber_t():   return Number(based_number_to_int(token.src))
        case RawString_t():     return String(token.to_str())
        case String_t():        return parse_string(token, scope)
        case Block_t():         return parse_block(token, scope)
        case Flow_t():          return parse_flow(token, scope)
        
        case _:
            #TODO handle other types...
            pdb.set_trace()
            ...
    
    pdb.set_trace()
    raise NotImplementedError()
    ...


def parse_chain(chain:Chain[Token], scope:Scope) -> AST:
    assert isinstance(chain, Chain), f"ERROR: parse chain may only be called on explicitly known Chain[Token], got {type(chain)}"
    
    if len(chain) == 0: return void
    if len(chain) == 1: return parse_single(chain[0], scope)
    
    left, op, right = split_by_lowest_precedence(chain, scope)
    left, right = parse(left, scope), parse(right, scope)

    assert not isinstance(left, Void) or not isinstance(right, Void), f"Internal Error: both left and right returned Void during parse chain, implying chain was invalid: {chain}"

    # 3 cases are prefix expr, postfix expr, or binary expr
    if isinstance(left, Void): return build_unary_prefix_expr(op, right, scope)
    if isinstance(right, Void): return build_unary_postfix_expr(left, op, scope)
    return build_bin_expr(left, op, right, scope)


def build_bin_expr(left:AST, op:Token, right:AST, scope:Scope) -> AST:
    """create a unary prefix expression AST from the op and right AST"""

    match op:
        case Juxtapose_t():
            if is_callable(left, scope):
                fn = to_callable(left)
                args = to_call_args(right)
                return Call(fn, args)
            else:
                # assume left/right are multipliable
                return Mul(left, right, None)

        case Operator_t(op='='):
            if isinstance(left, Identifier):
                return Bind(left.name, right)
            else:
                #TODO: handle other cases, e.g. a.b, a[b], etc.
                #      probably make bind take str|AST as the left-hand-side target
                #      return Bind(left, right)
                pdb.set_trace()
                ...

        case Operator_t(op='=>'):
            if isinstance(left, Void):
                return Function([], right, scope) #TODO: scope needs to be set. not sure if should set here or on a post processing pass...
            elif isinstance(left, Identifier):
                pdb.set_trace()
                ...
            elif isinstance(left, Block):
                pdb.set_trace()
                ...
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

        #comparison operators
        case Operator_t(op='=?'): return Equal(left, right)
        case Operator_t(op='>?'): return Greater(left, right)
        case Operator_t(op='<?'): return Less(left, right)
        case Operator_t(op='>=?'): return GreaterEqual(left, right)
        case Operator_t(op='<=?'): return LessEqual(left, right)
        # case Operator_t(op='in?'): return MemberIn(left, right)
        # case Operator_t(op='is?'): return Is(left, right)
        # case Operator_t(op='isnt?'): return Isnt(left, right)
        # case Operator_t(op='<=>'): return ThreewayCompare(left, right)

        # Boolean Operators

        # Misc Operators
        case Comma_t(): 
            #TODO: combine left or right tuples into a single tuple
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
                #merge left+right as single flow
                assert left.default is None, f'cannot merge left flow with default case. Got {left=}, {right=}'
                default = [right.default] if right.default else []
                return Flow([*left.branches, *right.branches, *default])
            elif isinstance(left, Flow):
                #append right to left
                assert left.default is None, f'cannot merge left flow with default case. Got {left=}, {right=}'
                return Flow([*left.branches, right])
            elif isinstance(right, Flow):
                #prepend left to right
                default = [right.default] if right.default else []
                return Flow([left, *right.branches, *default])
            else:
                #create a new flow out of the left and right
                return Flow([left, right])
        

        case _:
            pdb.set_trace()
            raise NotImplementedError(f'Parsing of operator {op} has not been implemented yet')


def build_unary_prefix_expr(op:Token, right:AST, scope:Scope) -> AST:
    """create a unary prefix expression AST from the op and right AST"""
    match op:
        # normal prefix operators
        case Operator_t(op='+'): return right
        case Operator_t(op='-'): return Neg(right, None)
        case Operator_t(op='*'): return right
        case Operator_t(op='/'): return Inv(right, None)
        case Operator_t(op='not'): raise NotImplementedError(f"TODO: prefix op: {op=}")
        case Operator_t(op='@'):   raise NotImplementedError(f"TODO: prefix op: {op=}")
        case Operator_t(op='...'): raise NotImplementedError(f"TODO: prefix op: {op=}")

        # binary operators that appear to be unary because the left can be void
        case Operator_t(op='=>'): return Function([], right, scope) # => called as unary prefix op means left was ()/void

        case _:
            raise ValueError(f"INTERNAL ERROR: {op=} is not a known unary prefix operator")


def build_unary_postfix_expr(left:AST, op:Token, scope:Scope) -> AST:
    """create a unary postfix expression AST from the left AST and op token"""
    match op:
        # normal postfix operators
        case Operator_t(op='!'): raise NotImplementedError(f"TODO: postfix op: {op=}") #return Fact(left)

        # binary operators that appear to be unary because the right can be void
        case Juxtapose_t(): return Call(to_callable(left), Array([])) # anything juxtaposed with void is treated as a zero-arg call()

        case _:
            raise NotImplementedError(f"TODO: {op=}")

def parse_string(token:String_t, scope:Scope) -> String | IString:
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
            #put any interpolation expressions in a new scope
            ast = parse(chunk.body, scope)
            if isinstance(ast, Block):
                ast.newscope = True
            else:
                ast = Block([ast], newscope=True)
            parts.append(ast)

    # combine any adjacent Strings into a single string (e.g. if there were escapes)
    parts = iterchain(*((''.join(g),) if issubclass(t, str) else (*g,) for t, g in groupby(parts, type)))
    # convert any free strings to ASTs
    parts = [p if not isinstance(p, str) else String(p) for p in parts]

    return IString(parts)


def parse_block(block:Block_t, scope:Scope) -> AST:
    """Convert a block token to an AST"""

    # if new scope block, nest the current scope
    newscope =  block.left == '{' and block.right == '}'
    if newscope:
        scope = Scope(scope)
    
    #parse the inside of the block
    inner = parse(block.body, scope)

    delims = block.left + block.right
    match delims, inner:
        #types returned as is
        case '()'|'{}', String() | IString() | Call() | Function() | Identifier() | Number() | BinOp() | UnaryOp(): #TODO: more types
            return Block([inner], newscope=delims=='{}')
        case '()'|'{}', Void():
            return inner
        case '()'|'{}', Block():
            inner.newscope = delims == '{}'
            return inner
        
        # create class RawRange(PrototypeAST) for representing the inner part of a range without the block delimiters
        # case '()'|'(]'|'[)'|'[]', RawRange(): ...

        # array
        # case '[]', Block() | Tuple(): return Array(inner.exprs)

        case _:
            pdb.set_trace()
            raise NotImplementedError(f'block parse not implemented for {block.left+block.right}, {type(inner)}')


def parse_flow(flow:Flow_t, scope:Scope) -> If|Loop:
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



def top_level_parse(tokens:list[Token], scope:Scope=None) -> AST:
    """
    Parse the sequence of tokens into an AST

    Args:
        tokens (list[Token]): tokens to be parsed
        scope (Scope, optional): The scope to use when determining the type of identified values. Defaults to Scope.default()
    """

    #ensure there is a valid scope to do the parse with
    if scope is None:
        scope = Scope.default()
    
    # kick off the parser
    ast = parse(tokens, scope.copy())

    # post processing on the parsed AST 
    express_identifiers(ast)
    tuples_to_arrays(ast)
    ensure_no_prototypes(ast)
    set_ast_scopes(ast, scope)

    return ast
    


def express_identifiers(root:AST) -> None:
    """
    Convert (in-place) any free floating Identifier AST nodes (PrototypeAST) to Call nodes
    """
    for ast in full_traverse_ast(root):
        if isinstance(ast, Identifier):
            #in place convert Identifier to Call
            call = Call(ast.name)
            ast.__dict__ = call.__dict__
            ast.__class__ = Call

def tuples_to_arrays(root:AST)  -> None:
    """Convert (in-place) any Tuple nodes (PrototypeAST) to Array nodes"""
    #TODO: should be able to specify that the array is const...
    for ast in full_traverse_ast(root):
        if isinstance(ast, Tuple):
            #in place convert Tuple to Array
            arr = Array(ast.exprs)
            ast.__dict__ = arr.__dict__
            ast.__class__ = Array

#TODO: if we make a third conversion function, make a meta conversion function that takes a lambda 
# for how to make the new instance from the old one, and then does the in-place conversion
# def in_place_type_conversion(root:AST, target:PyType[AST], converter: Function[[AST], AST]) -> None
#     for ast in full_traverse_ast(root):
#         if isinstance(ast, target):
#             new = converter(ast)
#             ast.__dict__ = new.__dict__
#             ast.__class__ = target

def ensure_no_prototypes(root:AST) -> None:
    """
    Raises an exception if there are any PrototypeAST nodes in the AST
    """
    for ast in full_traverse_ast(root):
        if isinstance(ast, PrototypeAST):
            raise ValueError(f'May not have any PrototypeASTs in a final AST. Found {ast} of type ({type(ast)})')
            
def set_ast_scopes(root:AST, scope:Scope) -> None:
    #TODO: hacky, just setting function scopes to root scope!
    #      need to handle setting scope to where fn defined.
    #      probably have traverse keep track of scope for given node!
    for ast in full_traverse_ast(root):
        if isinstance(ast, Function):
            ast.scope = scope

def full_traverse_ast(root:AST) -> Generator[AST, None, None]:
    """
    Generator to recursively walk all nodes in the given AST.
    
    While traversing, the user can skip visiting the current node's children by calling `.send(True)`.
    Children nodes are visited after the current node (preorder traversal), so you may modify the children
      during iteration, and the iterator ought to handle it fine.

    e.g.
    ```python
    
    for ast in (gen := full_traverse_ast(root)):
        #do something with current ast node
        #...

        #maybe skip any children of this node
        if should_skip:
            gen.send(True)
    ```

    Do not call `.send()` twice in a row without calling `next()` in between. This will cause unexpected behavior.

    Args:
        root: the ast node to start traversing from

    Yields:
        ast: the current ast node being looked at (and recursively all children nodes)
    """
    
    skip = yield root
    if skip is not None: assert (yield) is None, ".send() may only be called once per iteration"
    if skip is not None: return
    
    match root:
        case Block(exprs=list(exprs)) | Tuple(exprs=list(exprs)):
            for expr in exprs:
                yield from full_traverse_ast(expr)

        case Array(vals=list(vals)):
            for val in vals:
                yield from full_traverse_ast(val)

        case Call():
            #handle expr being called
            if isinstance(root.expr, AST):
                yield from full_traverse_ast(root.expr)
            # else str identifier, which doesn't need to be visited

            #handle any arguments
            if root.args is not None:
                for arg in root.args.vals:
                    yield from full_traverse_ast(arg)
        
        case IString(parts=list(parts)):
            for ast in parts:
                yield from full_traverse_ast(ast)

        case Bind():
            yield from full_traverse_ast(root.value)
        
        case Function():
            for arg in root.args:
                yield from full_traverse_ast(arg.type)
                if arg.val is not None:
                    yield from full_traverse_ast(arg.val)
            yield from full_traverse_ast(root.body)

        case BinOp():
            yield from full_traverse_ast(root.left)
            yield from full_traverse_ast(root.right)

        case UnaryOp():
            yield from full_traverse_ast(root.child)


        case Flow():
            for expr in root.branches:
                yield from full_traverse_ast(expr)
            if root.default is not None:
                yield from full_traverse_ast(root.default)

        case If():
            yield from full_traverse_ast(root.cond)
            yield from full_traverse_ast(root.body)

        case Loop():
            yield from full_traverse_ast(root.cond)
            yield from full_traverse_ast(root.body)


        # do nothing cases
        case String(): ...
        case Identifier(): ...
        case Number(): ...
        case Void(): ...
        
        case _:
            #TODO: unhandled ast type
            pdb.set_trace()
            raise NotImplementedError(f'traversal not implemented for ast type {type(root)}')






def test_file(path:str):
    """Run a given file"""

    with open(path) as f:
        src = f.read()
    
    tokens = tokenize(src)
    post_process(tokens)

    root = Scope.default()
    ast = top_level_parse(tokens, root)
    res = ast.eval(root)
    if res: print(res)




#TODO: broken. probably set up scope with some default values
def test_many_lines():
    """
    Parse each line of syntax3.dewy one at a time for testing
    """
    #load the syntax3 file and split the lines
    with open('../../examples/syntax3.dewyl') as f:
        lines = f.read().splitlines()


    #set up a scope with declarations for all of the variables used in the example file    
    root = Scope.default()
    root.let('x', Number.type)
    root.let('y', Number.type)
    root.let('z', Number.type)

    for line in lines:
        tokens = tokenize(line)
        post_process(tokens)

        # skip empty lines
        if len(tokens) == 0:
            continue

        #print the line, and run it
        print('-'*80)
        print(tokens)

        ast = top_level_parse(tokens)
        print(ast)

        #TODO: maybe later we can run the file. potentially declare all the values used at the top?
        # res = ast.eval(root)
        # if res: print(res)


def test_hello():
    # line = "'Hello, World!'"
    line = r"""
print'What is your name? '
name = readl
printl'Hello {name}'
a = 4(5)
b = -5
c = /4
d = 1,2,3,4,5
printl'a={a}, b={b}, c={c} d={d}'
"""

    tokens = tokenize(line)
    post_process(tokens)

    #DEBUG
    # tokens = [Identifier_t('printl'), Juxtapose_t(''), Identifier_t('readl')]

    ast = top_level_parse(tokens)
    root = Scope.default()
    ast.eval(root)


def test_example_progs():
    from dewy import hello, hello_func, anonymous_func, hello_name, if_else, if_else_if, hello_loop, unpack_test, range_iter_test, loop_iter_manual, loop_in_iter, nested_loop, block_printing

    funcs = [hello, hello_func, anonymous_func, hello_name, if_else, if_else_if, hello_loop, unpack_test, range_iter_test, loop_iter_manual, loop_in_iter, nested_loop, block_printing]

    for func in funcs:
        src = func.__doc__
        print(f'Parsing source:\n{src}\n')
        tokens = tokenize(src)
        post_process(tokens)

        ast = top_level_parse(tokens)
        root = Scope.default()
        ast.eval(root)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        test_file(sys.argv[1])
    else:
        # test_hello()
        # test_example_progs()
        test_many_lines()

    # print("Usage: `python parser.py [path/to/file.dewy>]`")






