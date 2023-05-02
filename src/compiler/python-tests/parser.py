from dewy import (
    AST, 
    Undefined,
    Callable,
    Orderable,
    Rangeable,
    Unpackable,
    Iter,
    Iterable,
    # BArg,
    # Scope,
    Type,
    Arg,
    Function,
    Builtin,
    Let,
    Bind,
    PackStruct,
    Unpack,
    Block,
    Call,
    String,
    IString,
    BinOp,
    Equal,
    NotEqual,
    Less,
    LessEqual,
    Greater,
    GreaterEqual,
    Add,
    Sub,
    # Mul,
    # Div,
    Bool,
    If,
    Loop,
    In,
    Next,
    Number,
    Range,
    RangeIter,
    Vector,

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

from utils import based_number_to_int

import pdb


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



valid_brace_pairs = {
    '{': '}',
    '(': ')]',
    '[': '])',
    # '<': '>'
}

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

chain_atoms = {
    Identifier_t,
    Integer_t,
    BasedNumber_t,
    RawString_t,
    String_t,
    Block_t,
    TypeParam_t,
    Hashtag_t,
    DotDot_t,
}

# keep track of operators that are sensitive to whitespace (i.e. we cannot safely fold adjacent whitespace/juxtaposition tokens into the operator)
whitespace_sensitive_operators = unary_prefix_operators & unary_postfix_operators | binary_operators & (unary_prefix_operators | unary_postfix_operators)


#juxtapose singleton token so we aren't wasting memory
jux = Juxtapose_t(None)



def validate_block_braces(tokens:list[Token]) -> None:
    """
    Checks that all blocks have valid open/close pairs.

    For example, ranges may have differing open/close pairs, e.g. [0..10), (0..10], etc.
    But regular blocks must have matching open/close pairs, e.g. { ... }, ( ... ), [ ... ]
    Performs some validation, without knowing if the block is a range or a block. 
    So more validation is needed when the actual block type is known.

    Raises:
        AssertionError: if a block is found with an invalid open/close pair
    """
    for token in traverse_tokens(tokens):
        if isinstance(token, Block_t):
            assert token.left in valid_brace_pairs, f'INTERNAL ERROR: left block opening token is not a valid token. Expected one of {[*valid_brace_pairs.keys()]}. Got \'{token.left}\''
            assert token.right in valid_brace_pairs[token.left], f'ERROR: mismatched opening and closing braces. For opening brace \'{token.left}\', expected one of \'{valid_brace_pairs[token.left]}\''
        


def invert_whitespace(tokens: list[Token]) -> None:
    """
    removes all whitespace tokens, and insert juxtapose tokens between adjacent pairs (i.e. not separated by whitespace)

    Args:
        tokens (list[Token]): list of tokens to modify. This is modified in place.
    """
    i = 0
    while i < len(tokens):
        # delete whitespace if it comes up
        if isinstance(tokens[i], WhiteSpace_t):
            tokens.pop(i)
            continue

        # recursively handle inverting whitespace for blocks
        if isinstance(tokens[i], (Block_t, TypeParam_t)):
            invert_whitespace(tokens[i].body)
        elif isinstance(tokens[i], String_t):
            for child in tokens[i].body:
                if isinstance(child, Block_t):
                    invert_whitespace(child.body)

        # insert juxtapose if no whitespace between tokens
        if i + 1 < len(tokens) and not isinstance(tokens[i + 1], WhiteSpace_t):
            tokens.insert(i + 1, jux)
            i += 1
        i += 1

    #finally, remove juxtapose tokens next to operators that are not whitespace sensitive
    i = 1
    while i < len(tokens) - 1:
        left,middle,right = tokens[i-1:i+2]
        if isinstance(middle, Juxtapose_t) and isinstance(left, Operator_t) and left.op not in whitespace_sensitive_operators and isinstance(right, Operator_t) and right.op not in whitespace_sensitive_operators:
            tokens.pop(i)
            continue
        i += 1



#TODO: determining type of a block
from enum import Enum, auto
class BlockType(Enum):
    Range = auto()
    Scope = auto()
    Group = auto()
    Args = auto()
    Call = auto()
    Index = auto()
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



#TODO: handle context, namely blocks based on what the left/right brackets are, since some chains are only valid in certain contexts

#TODO: get next chain needs to recursively call itself to handle conditionals/loops/etc. keyword based syntax
def get_next_chain(tokens:list[Token]) -> tuple[list[Token], list[Token]]:
    """
    grab the next single expression chain of tokens from the given list of tokens

    Args:
        tokens (list[Token]): list of tokens to grab the next chain from

    Returns:
        next, rest (list[Token], list[Token]): the next chain of tokens, and the remaining tokens
    """
    i = 0
    while i < len(tokens):
        token = tokens[i]
        cls = token.__class__
        
        
        #TODO: replace with: if empty chain, or current is binary op, while next is unary prepender, keep going until we have an atom
        #if chain is empty, is token a chain starter. else error.
        if i == 0:
            #TODO: can also be a unary_chain_prepender
            if cls not in chain_atoms:
                pdb.set_trace()
                raise ValueError(f"ERROR: unexpected token at start of chain: {token=}")
            i += 1
            continue
        
        if match_single(token, unary_chain_extenders): #cls in unary_chain_extenders:
            i += 1
            continue

        #check if the token after is a valid token type to be
        if match_single(token, binary_chain_extenders): #token.__class__ in binary_chain_extenders:
            assert i+1 < len(tokens), f"ERROR: unexpected end of tokens after binary extender: {token=}"
            token = tokens[i+1]
            cls = token.__class__
            if cls not in chain_atoms:
                raise ValueError(f"ERROR: unexpected token after binary extender: {token=}")
            i += 2
            continue

        #TODO: handling of keyword chains...

        #TODO: handling opchaining. basically can be a binary operator followed by any number of unary operators, followed by an atom

        
        #else end of chain
        break
        
    return tokens[:i], tokens[i:]



def split_at_lowest_precedence(tokens:list[Token]) -> tuple[list[Token], Token, list[Token]]:
    ...


def parse_chain(tokens:list[Token]) -> AST:
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
        
        case [RawString_t(body=str(body))]:
            if body.startswith('r"""') or body.startswith("r'''"):
                return String(body[4:-3])
            assert body.startswith('r"') or body.startswith("r'"), f"INTERNAL ERROR: raw string body does not start with r\" or r'. Got {body=}"
            return String(body[2:-1])
        
        case [String_t(body=[str(body)])]:
            return String(body)
            ...
        #TODO: lots of other simple cases here

        
        #Happy paths
        case [Identifier_t(src=str(id)), Juxtapose_t(), String_t(body=[str(string)])]:
            return Call(id, [String(string)])
        
        # case [Identifier_t(src=str(id)), Juxtapose_t(), Block_t(left='(', right=')', body=[String_t(body=[str(string)])])]:
        #     return Call(id, [String(string)])
        
        case [Identifier_t(src=str(id)), Juxtapose_t(), Block_t() as block_t]:
            block = parse_block(block_t)
            if isinstance(block, (Number,String,IString)):
                return Call(id, [block])
            else:
                pdb.set_trace()
                ...

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
            pdb.set_trace()
            return Void() # or Undefined?
        case Block_t(left='(', right=')', body=[Identifier_t() | RawString_t() | String_t() | Integer_t() | BasedNumber_t()]):
            return parse_chain(block.body)
            # Identifier_t,
            # Block_t,
            # TypeParam_t,
            # RawString_t,
            # String_t,
            # Integer_t,
            # BasedNumber_t,
            # Hashtag_t,
            # DotDot_t,
            pdb.set_trace()


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






def parse(tokens:list[Token]) -> AST:
    """
    parse a list of tokens into an AST
    """
    # chains = []
    exprs:list[AST] = []
    while len(tokens) > 0:
        chain, tokens = get_next_chain(tokens)
        expr = parse_chain(chain)
        exprs.append(expr)

    #TODO: should newscope be true or false? so far this is the outermost block, though in the future it could be nested...
    #      if it was to be nested though, we'd need to determine what type of block it was...
    #      perhaps include a newscope flag in the parse signature
    return Block(exprs, newscope=True)

    
    






def test():
    import sys

    try:
        path = sys.argv[1]
    except IndexError:
        raise ValueError("Usage: `python parser.py path/to/file.dewy>`")


    with open(path) as f:
        src = f.read()

    tokens = tokenize(src)
    # print(f'matched tokens:')
    # tprint(Block_t(left='{', right='}', body=tokens))
    # print('\n\n\n')

    # ensure that all blocks have valid open/close pairs
    validate_block_braces(tokens)

    # remove whitespace, and insert juxtapose tokens
    invert_whitespace(tokens)
    # print(f'juxtaposed tokens:')
    # tprint(Block_t(left='{', right='}', body=tokens))

    # parse tokens into an AST
    ast = parse(tokens)
    # print(f'parsed ast: {ast}')

    #TODO: restructuring, type checking, optimizations, etc.

    # run the program
    root = Scope.default()
    ast.eval(root)


if __name__ == "__main__":
    test()







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
