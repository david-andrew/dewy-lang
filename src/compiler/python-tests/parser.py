# from __future__ import annotations

from dewy import (
    AST, PrototypeAST,
    Undefined, undefined,
    Identifier,
    Callable,
    Orderable,
    Rangeable,
    Unpackable,
    Iter,
    Iterable,
    # Scope,
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
    Neg, Inv,
    Bool,
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

from postok import post_process, get_next_chain, is_op

from utils import based_number_to_int
from dataclasses import dataclass
from typing import Generator
from rich import print, traceback; traceback.install(show_locals=True)

import pdb



# Parsing process:
# list[Token] -> Chain[Chain] -> AST


# [TASKS]
# - have a post tokanization step for combining chains of operators into opchains (e.g. x^/-2, needs to chain the ^/- into a single op)
#   - this is so that split by lowest precedence works because it only considers the precedence of the first operator. it's harder if they're not combined
# - also need to wrap up conditional/etc. blocks into a single token
# - dewy AST stuff:
#   --> every AST needs to have a .eval_type() function that will determine what type the AST evaluates to
#   --> TBD. maybe make it so that dewy ASTs can handle juxtapose by themselves, rather than having to figure it out in the parser? or have there be multiple parser passes over the generated AST...
# - start parsing simple AST expressions, e.g. expr + expr, expr - expr
# - more complicated expressions parsed via split by lowest precedence

#compiler pipeline steps:
# 1. tokenize
# 2. validate block braces
# 3. invert whitespace to juxtapose
# 4. create program ast from tokens
# 5. validation (what kind?). type checking. valid operations. etc.
# 6. high level optimizations/transformations
# 7. generate code via a backend (e.g. llvm, c, python)
#    -> llvm: convert ast to ssa form, then generate llvm ir from ssa form


#expression chains
# build chain one token at a time, decide if it is part of the current expression chain
# once chain is built, split by lowest precedence operator (kept track of during chain building)
# create the node for the operator, and semi-recurse process on the left and right halves 
#  - (the chain already exists, just need to find the lowest precedence operator)





unary_chain_prependers = {
    Operator_t: lambda t: t.op in unary_prefix_operators,
}

#only postifx unary operators are allowed
unary_chain_extenders = {
    Operator_t: lambda t: t.op in unary_postfix_operators,
}

binary_chain_extenders = {
    Juxtapose_t: None,
    Operator_t: lambda t: t.op in binary_operators,
    ShiftOperator_t: None,
    Comma_t: None,
}

def match_single(token:Token, group:dict[type, None|Callable]) -> bool:
    cls = token.__class__
    return cls in group and (group[cls] is None or group[cls](token))





#TODO: determining type of a block
from enum import Enum, auto
class BlockType(Enum):
    Range = auto()
    # Index = auto() #possibly just a special case of range
    Scope = auto()
    Group = auto()
    # Tuple = auto()
    # Call = auto()
    Void = auto() # perhaps just an empty Group type?
    # others?
def determine_block_type(block:Block_t) -> BlockType: ...
    #if contains .., and left/right are any of [( ]), should be a range
    #if contains any commas, and left/right are (), should be a function call or args...this maybe overlaps a bit with group...
    # - for args, only certain expressions are valid
    # - for call, any comma separated expressions are valid. probably require ranges to be wrapped in parens/brackets?
    #if left and right are {}, should be a scope
    #if left and right are (), and tbd other stuff, should be a group
    #if left and right are [], and tbd other stuff, should be an index. Index is the only time that ranges could possibly be naked (i.e. not wrapped in parens/brackets)


# #TODO: custom AST nodes for intermediate steps
# from abc import ABC
# class IntermediateAST(ABC): ...
# class Void(IntermediateAST): ...

# @dataclass
# class Juxtapose(IntermediateAST):
#     left:IntermediateAST|AST
#     right:IntermediateAST|AST

# # @dataclass
# # class Identifier(IntermediateAST):
# #     name:str

# class Tuple(IntermediateAST): ...

# @dataclass
# class UnknownBlock(IntermediateAST):
#     left:str
#     right:str
#     body:list[IntermediateAST|AST]


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
        

def operator_precedence(t:Token) -> int | qint:
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
    <jux range>
    ,                                   //tuple maker
    =? >? <? >=? <=? not=? <=> is? isnt? @?
    and nand &
    xor xnor                            //following C's precedence: and > xor > or
    or nor |
    = .= <op>= .<op>=  (e.g. += .+=)    //right-associative (but technically causes a type error since assignments can't be chained)
    (postfix) ;
    <seq> (i.e. space)
    [LOWEST]

    TODO:
    - add operators: in as transmute |> <| => -> <-> <- :

    [Notes]
    .. for ranges is not an operator, it is an expression. it uses juxtapose to bind to left/right arguments (or empty), and type-checks left and right
    if-else-loop chain expr is more like a single unit, so it doesn't really have a precedence. but they act like they have the lowest precedence since the expressions they capture will be full chains only broken by space/seq
    the unary versions of + - * / % have the same precedence as their binary versions
    """

    match t:
        case Operator_t(op='='):
            return 0
        case Operator_t(op='or'|'nor'):
            return 1
        case Operator_t(op='xor'|'xnor'):
            return 2
        case Operator_t(op='and'|'nand'):
            return 3
        case Operator_t(op='=?'|'>?'|'<?'|'>=?'|'<=?'|'<=?'): #TODO: need to have a parsing step that combines not =? into a single token
            return 4
        case Comma_t():
            return 5
        case ShiftOperator_t(op='<<'|'>>'|'<<<'|'>>>'|'<<!'|'!>>'):
            return 6
        case Operator_t(op='+'|'-'):
            return 7
        case Operator_t(op='*'|'/'|'%'):
            return 8
        case Juxtapose_t():
            return qint({9, 11})
        case Operator_t(op='^'):
            return 10
        case Operator_t(op='.'):
            return 11
        case Operator_t(op='@'):
            return 12
        case _:
            raise ValueError(f"ERROR: expected operator, got {t=}")


#TODO: this needs to consider opchains, and use the precedence of the operator to the left of the chain (other ops are unary prefix ops)
def lowest_precedence_split(tokens:list[Token]) -> list[int]:# TODO: handle ambiguous e.g. list[list[int]] for each option of splitting?
    """
    return the integer index/indices of the lowest precedence operator(s) in the given list of tokens
    """
    #collect all operators and their indices in the list of tokens
    idxs, ops = zip(*[(i,t) for i,t in enumerate(tokens) if isinstance(t, (Operator_t, Comma_t, ShiftOperator_t, Juxtapose_t))])

    if len(ops) == 0:
        return []
    if len(ops) == 1:
        return list(idxs)
    
    ranks = [operator_precedence(op) for op in ops]
    min_rank = min(ranks)

    # verify that the min is strictly less than or equal to all other ranks
    if not all(min_rank <= r for r in ranks):
        #TODO: probably enumerate out all permutations of the ambiguous operators and return all of them as a list of lists of indices
        raise NotImplementedError(f"TODO: ambiguous precedence for {ops=} with {ranks=}")

    return [i for i,r in zip(idxs, ranks) if r == min_rank]

def make_ast_chain(chunks:list[Token], ops:list[Token]) -> AST | PrototypeAST:
    """Create an AST chain from the sequence of ops/chunks"""
    assert len(chunks) == len(ops) + 1, f"ERROR: mismatched lengths for {chunks=} and {ops=}"
    assert len(ops) > 0, f"ERROR: {ops=} is empty"

    if len(ops) == 1:
        assert len(chunks) == 2, f"ERROR: {chunks=} should have length 2"
        op, = ops
        left, right = chunks

        if len(left) == 0 and isinstance(op, Operator_t) and op.op in unary_prefix_operators:
            return parse_unary_prefix_op(op, right)
        if len(right) == 0 and isinstance(op, Operator_t) and op.op in unary_postfix_operators:
            return parse_unary_postfix_op(left, op)
        
        assert len(left) > 0 and len(right) > 0, f"ERROR: {left=} and {right=} should both have length > 0"
        return parse_bin_op(left, op, right)

    pdb.set_trace()


def parse_bin_op(left:list[Token], op:Token, right:list[Token]) -> AST | PrototypeAST:
    """
    create a binary operation AST from the left, op, and right tokens
    """
    left, right = parse_chain(left), parse_chain(right)

    match op:
        case Juxtapose_t():
            return Juxtapose(left, right)
        case Comma_t():
            return Tuple(left, right)
        case ShiftOperator_t(op='<<'):
            return LeftShift(left, right)
        case ShiftOperator_t(op='>>'):
            return RightShift(left, right)
        case ShiftOperator_t(op='<<<'):
            return LeftRotate(left, right)
        case ShiftOperator_t(op='>>>'):
            return RightRotate(left, right)
        case ShiftOperator_t(op='<<!'):
            return LeftRotateCarry(left, right)
        case ShiftOperator_t(op='!>>'):
            return RightRotateCarry(left, right)
        case Operator_t(op='+'):
            return Add(left, right)
        case Operator_t(op='-'):
            return Sub(left, right)
        case Operator_t(op='*'):
            return Mul(left, right)
        case Operator_t(op='/'):
            return Div(left, right)
        case Operator_t(op='%'):
            return Mod(left, right)
        case Operator_t(op='^'):
            return Pow(left, right)
        case _:
            raise NotImplementedError(f"TODO: {op=}")

def parse_unary_prefix_op(op:Token, right:list[Token]) -> AST | PrototypeAST:
    """
    create a unary prefix operation AST from the op and right tokens
    """
    right = parse_chain(right)

    match op:
        case Operator_t(op='+'):
            return right
        case Operator_t(op='-'):
            return Neg(right)
        case Operator_t(op='*'):
            return right
        case Operator_t(op='/'):
            return Inv(right)
        case Operator_t(op='not'):
            raise NotImplementedError(f"TODO: {op=}")
        case Operator_t(op='@'):
            raise NotImplementedError(f"TODO: {op=}")
        case Operator_t(op='...'):
            raise NotImplementedError(f"TODO: {op=}")
        case _:
            raise ValueError(f"INTERNAL ERROR: {op=} is not a unary prefix operator")

 
def parse_unary_postfix_op(left:list[Token], op:Token) -> AST | PrototypeAST:
    """
    create a unary postfix operation AST from the left and op tokens
    """
    left = parse_chain(left)

    match op:
        case Operator_t(op='!'):
            return Fact(left)
        case _:
            raise NotImplementedError(f"TODO: {op=}")

def parse_chain(tokens:list[Token]) -> AST | PrototypeAST:
    """
    Convert a chain of tokens to an AST

    Must be a valid chain as produced by get_next_chain
    """

    #For now, we're just gonna do some simple pattern matching.
    match tokens:
        case [Integer_t(src=str(src))]:
            return Number(int(src))
        
        case [BasedNumber_t(src=str(src))]:
            return Number(based_number_to_int(src))
        
        case [RawString_t(body=str(body))] if body.startswith('r"""') or body.startswith("r'''"):
            return String(body[4:-3])
        case [RawString_t(body=str(body))] if body.startswith('r"') or body.startswith("r'"):
            return String(body[2:-1])
        
        case [String_t(body=[str(body)])]:
            return String(body)
        case [String_t(body=list(body))]:
            parts = []
            for part in body:
                if isinstance(part, str):
                    parts.append(String(part))
                elif isinstance(part, Block_t):
                    parts.append(parse_block(part))
                elif isinstance(part, Escape_t):
                    parts.append(String(part.to_str()))
                else:
                    raise ValueError(f"INTERNAL ERROR: unexpected token in string body: {part=}")
            return IString(parts)

        case [Identifier_t(src=str(src))]:
            return Identifier(src)
        
        case [Block_t(body=list()) as block]:
            return parse_block(block)
        
    
    # Base case
    splits = lowest_precedence_split(tokens)

    #TODO: handle left/right associativity. need to check if ^ or =. otherwise left-associative.

    ast_chunks = []
    ast_ops = []
    for prev, split in zip([0]+splits, splits):
        if isinstance(split, list):
            #TODO: could have something like an ambiguous chain, which takes in all the options. TBD how to handle collapsing to the correct one once type information is known
            raise NotImplementedError("TODO: handle multiple split permutations")
        else:
            ast_chunks.append(tokens[prev:split])
            ast_ops.append(tokens[split])
    ast_chunks.append(tokens[splits[-1]+1:])

    return make_ast_chain(ast_chunks, ast_ops)
    

    pdb.set_trace()
    ...
        
        
        #TODO: lots of other simple cases here

        
        #Happy paths
        # case [Identifier_t(src=str(id)), Juxtapose_t(), String_t()]:
        #     string = parse_chain(tokens[2:])
        #     return Call(id, [string])
        
        # case [Identifier_t(src=str(id)), Juxtapose_t(), Block_t(left='(', right=')', body=[String_t(body=[str(string)])])]:
        #     return Call(id, [String(string)])
        
        # case [Identifier_t(src=str(id)), Juxtapose_t(), Block_t() as block_t]:
        #     block = parse_block(block_t)
        #     #TODO: this really needs to check the type of eval on the block, rather than the raw AST type.
        #     if isinstance(block, (Number,String,IString)):
        #         return Call(id, [block])
        #     else:
        #         pdb.set_trace()
        #         ...



        #TODO: lots of other semi-complex cases here

    
    pdb.set_trace()
    raise Exception(f"INTERNAL ERROR: no match for chain: {tokens=}")
    ...



def parse_block(block:Block_t) -> AST:
    """
    Convert a block to an AST
    """

    match block:
        case Block_t(left='(', right=')', body=[]):
            return Void() # or Undefined?
        case Block_t(left='{', right='}', body=[]):
            return Void() # or Undefined?
        case Block_t(left='(', right=')', body=[Identifier_t() | RawString_t() | String_t() | Integer_t() | BasedNumber_t()] as body):
            return parse_chain(body)
        case Block_t(left='{', right='}', body=[Identifier_t() | RawString_t() | String_t() | Integer_t() | BasedNumber_t()] as body):
            return parse_chain(body)
        
        # parenthesis stripping
        case Block_t(left='(', right=')', body=[Block_t() as block_t]):
            return parse_block(block_t)
        
        case Block_t(left='('|'[', right=')'|']', body=[DotDot_t()]):
            pdb.set_trace()
            return Range()
        
        # scope stripping
        case Block_t(left='{', right='}', body=[Block_t() as block_t]):
            return Block([parse_block(block_t)], newscope=True)
            # Identifier_t,
            # Block_t,
            # TypeParam_t,
            # RawString_t,
            # String_t,
            # Integer_t,
            # BasedNumber_t,
            # Hashtag_t,
            # DotDot_t,



        #catch all case
        case Block_t(left=str(left), right=str(right), body=list(body)):
            seq = []
            while len(body) > 0:
                chain, body = get_next_chain(body)
                seq.append(parse_chain(chain))
            return UnknownBlock(left, right, seq)

    pdb.set_trace()
    ...


#TODO:
# - grouping up keywords + expected chains. perhaps this should be a preparse step, that makes new tokens, Flow_t with their internal groups
#     if <chain> <chain> (optional else <chain>)
#     loop <chain> <chain> (optional else <chain>)
# - split_by_lowest_precedence
# - pattern matching chains e.g. <id> <jux> <str> -> call(id, str), etc. probably handle by split by lowest precedence...
# - parse chain into AST
# - parsing process. each chain -> AST, all wrapped up in a block
# - determining what type a block is based on its contents. especially tuples?
# - stripping parenthesis off of groups (probably only when handling that token -> AST)
# - initially building the AST without type info, and then making a typed AST from that? e.g. 
#     <jux>
#       <id: printl>
#       <str: 'hello world'>
#    ----------------------
#    <call>
#       <id: printl>
#       <str: 'hello world'>




# def parse0(tokens:list[Token]) -> Block:
#     """
#     parse a list of tokens into an AST
#     """
#     #initial parsing pass. may contain intermediate ASTs that need to be further parsed
#     exprs:list[AST] = []
#     while len(tokens) > 0:
#         chain, tokens = get_next_chain(tokens)
#         expr = parse_chain(chain)
#         exprs.append(expr)

#     #TODO: should newscope be true or false? so far this is the outermost block, though in the future it could be nested...
#     #      if it was to be nested though, we'd need to determine what type of block it was...
#     #      perhaps include a newscope flag in the parse signature
#     return Block(exprs, newscope=True)





# @cache
def split_by_lowest_precedence(tokens: list[Token], scope:Scope) -> tuple[list[Token], Token, list[Token]]:
    """
    return the integer index/indices of the lowest precedence operator(s) in the given list of tokens
    """
    #collect all operators and their indices in the list of tokens
    idxs, ops = zip(*[(i,token) for i,token in enumerate(tokens) if is_op(token)])

    if len(ops) == 0:
        return []
    if len(ops) == 1:
        i, = idxs
        op, = ops
        return tokens[:i], op, tokens[i+1:]
    
    #TODO: need to reimpliment handling multiple operations.
    #      also make use of scope to disambiguate ambiguous ops, e.g. juxtapose
    pdb.set_trace()
    # ... old implementation below ...

    ranks = [operator_precedence(op) for op in ops]
    min_rank = min(ranks)

    # verify that the min is strictly less than or equal to all other ranks
    if not all(min_rank <= r for r in ranks):
        #TODO: probably enumerate out all permutations of the ambiguous operators and return all of them as a list of lists of indices
        raise NotImplementedError(f"TODO: ambiguous precedence for {ops=} with {ranks=}")

    return [i for i,r in zip(idxs, ranks) if r == min_rank]

    pdb.set_trace()
    ...

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
    """Convert the ast to either a string or Callable"""

    if isinstance(ast, Identifier):
        return ast.name
    if isinstance(ast, (Builtin, Function)):
        return ast

    raise ValueError(f'Tried to prepare callable expression with unrecognized type {type(ast)}')


def to_call_args(ast:AST) -> Array:
    if not isinstance(ast, Tuple):
        #TODO: some sort of check that ast is a single type...?
        return Array([ast])
    
    # if ast was a tuple, should be able to directly convert to call args as is
    return Array(ast.exprs)
    

def is_callable(ast:AST, scope:Scope) -> bool:
    if isinstance(ast, Identifier):
        #check the type of the identifier in the scope
        if (val:=scope.get(ast.name, undefined)) is not undefined:
            if Type.is_instance(val.type, Callable.type):
                return True
            
    if isinstance(ast, PrototypeAST):
        raise NotImplementedError(f"Currently haven't handled is_callable for case of {type(ast)}")
        
    

    #other cases, e.g. function literals. should be able to use the AST type checking method at this point
    pdb.set_trace()
    ...

# don't need is_multipliable, because that is just the default case.
# also don't have to worry about the user making custom callable types not being parsed correctly,
#    since they should inherit from Callable, making is_callable return true for them!

def parse(tokens:list[Token], scope:Scope, *, newscope:bool=False) -> AST:

    asts = []
    while len(tokens) > 0:
        chain, tokens = get_next_chain(tokens)

        if len(chain) == 1:
            token, = chain
            asts.append(parse_single(token, scope))
            break
        
        left, op, right = split_by_lowest_precedence(chain, scope)
        left, right = parse(left, scope), parse(right, scope)

        match op:
            case Juxtapose_t():
                if is_callable(left, scope):
                    fn = to_callable(left)
                    args = to_call_args(right)
                    asts.append(Call(fn, args))
                else:
                    # assume left/right are multipliable
                    #do left*right
                    pdb.set_trace()
                    ...
            
            case Operator_t(op='='):
                if isinstance(left, Identifier):
                    asts.append(Bind(left.name, right))   
                else:    
                    #TODO: handle other cases, e.g. a.b, a[b], etc.
                    pdb.set_trace()
                    ...

            case _:
                raise NotImplementedError(f'Parsing of operator {op} has not been implemented yet')
    
    
    if len(asts) == 0:
        pdb.set_trace() 
        #perhaps this should raise an exception
        return undefined
    
    if len(asts) == 1:
        ast, = asts
        return ast
    
    return Block(asts, newscope=newscope)

def parse_single(token:Token, scope:Scope) -> AST:
    """Parse a single token into an AST"""
    match token:
        case Identifier_t():
            return Identifier(token.src)
        case String_t():
            if len(token.body) == 1 and isinstance(token.body[0], str):
                return String(token.body[0])
            
            # else handle interpolation strings
            parts = []
            for chunk in token.body:
                if isinstance(chunk, str):
                    parts.append(String(chunk))
                elif isinstance(chunk, Escape_t):
                    #TODO: handle converting escape sequences to a string ast
                    pdb.set_trace()
                else:
                    parts.append(parse(chunk.body, scope, newscope=True))
            return IString(parts)

        
        case _:
            #TODO handle other types...
            pdb.set_trace()
            ...
    
    pdb.set_trace()
    raise NotImplementedError()
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

    # kick of the parser
    ast = parse(tokens, scope)

    # post processing on the parsed AST 
    express_identifiers(ast)
    ensure_no_prototypes(ast)

    return ast
    


def express_identifiers(root:AST) -> AST:
    """
    Convert (in-place) any free floating Identifier AST nodes (PrototypeAST) to Call nodes
    """
    for ast in full_traverse_ast(root):
        if isinstance(ast, Identifier):
            #in place convert Identifier to Call
            call = Call(ast.name)
            ast.__dict__ = call.__dict__
            ast.__class__ = Call


def ensure_no_prototypes(root:AST) -> None:
    """
    Raises an exception if there are any PrototypeAST nodes in the AST
    """
    for ast in full_traverse_ast(root):
        if isinstance(ast, PrototypeAST):
            raise ValueError(f'May not have any PrototypeASTs in a final AST. Found {ast} of type ({type(ast)})')
            
    

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
        case Block(exprs=list(exprs)):
            for expr in exprs:
                yield from full_traverse_ast(expr)

        case Call():
            #handle any arguments
            if root.args is not None:
                for arg in root.args.vals:
                    yield from full_traverse_ast(arg)
        
        case IString(parts=list(parts)):
            for ast in parts:
                yield from full_traverse_ast(ast)

        case Bind():
            yield from full_traverse_ast(root.value)
        
        # do nothing cases
        case String(): ...
        case Identifier(): ...
        
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

    ast = top_level_parse(tokens)
    root = Scope.default()
    res = ast.eval(root)
    if res: print(res)




#TODO: broken. probably set up scope with some default values
def test_many_lines():
    """
    Parse each line of syntax3.dewy one at a time for testing
    """
    #load the syntax3 file and split the lines
    with open('../../../examples/syntax3.dewy') as f:
        lines = f.read().splitlines()

    
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
        root = Scope.default()
        res = ast.eval(root)
        if res: print(res)


def test_hello():
    # line = "'Hello, World!'"
    line = r"""
print'What is your name? '
name = readl
printl'Hello {name}'
"""

    tokens = tokenize(line)
    post_process(tokens)

    #DEBUG
    # tokens = [Identifier_t('printl'), Juxtapose_t(''), Identifier_t('readl')]

    ast = top_level_parse(tokens)
    root = Scope.default()
    ast.eval(root)



if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        test_file(sys.argv[1])
    else:
        # test2()
        test_hello()

    # print("Usage: `python parser.py [path/to/file.dewy>]`")






# from dewy import (
#     hello,
#     hello_func,
#     anonymous_func,
#     hello_name,
#     if_else,
#     if_else_if,
#     hello_loop,
#     unpack_test,
#     range_iter_test,
#     loop_iter_manual,
#     loop_in_iter,
#     nested_loop,
#     block_printing,
# )


# funcs = [hello,
#     hello_func,
#     anonymous_func,
#     hello_name,
#     if_else,
#     if_else_if,
#     hello_loop,
#     unpack_test,
#     range_iter_test,
#     loop_iter_manual,
#     loop_in_iter,
#     nested_loop,
#     block_printing
# ]
# from dewy import Scope
# for func in funcs:
#     src = func.__doc__
#     tokens = tokenize(src)
#     ast = func(Scope.default())
#     print(f'''
# -------------------------------------------------------
# SRC:```{src}```
# TOKENS:
# {tokens}

# AST:
# {repr(ast)}
# -------------------------------------------------------
# ''')

# exit(1)
