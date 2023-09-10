from tokenizer import ( tokenize, tprint, full_traverse_tokens,
    unary_prefix_operators,
    unary_postfix_operators,
    binary_operators,
    opchain_starters,

    Token,

    WhiteSpace_t,

    Escape_t,

    Identifier_t,
    Block_t,
    TypeParam_t,
    RawString_t,
    String_t,
    Integer_t,
    Boolean_t,
    BasedNumber_t,
    Hashtag_t,
    DotDot_t,

    Keyword_t,

    Juxtapose_t,
    Operator_t,
    ShiftOperator_t,
    Comma_t,
)

from enum import Enum, auto


import pdb


"""
TODO:
- full pipeline for hello world:
  [x] tokenize
  [ ] chain (still no typing, just group single expressions together). Actually probably just leave as list[Token], and generate chains again at parse time!
  [ ] parse (building up types based on expressions and types of lowest levels/outside in)
"""


# There is no chain class
# A chain is just a list of tokens that is directly parsable as an expression without any other syntax
# all other syntax is wrapped up into compound tokens
# it should literally just be a sequence of atoms and operators
    

#TODO: replace with 3.12 syntax when released: class Chain[T](list[T]): ...
from typing import TypeVar
T = TypeVar('T')
class Chain(list[T]):
    """class for explicitly annotating that a token list is a single chain"""


# Later Token classes

class Flow_t(Token):
    def __init__(self, keyword:Keyword_t, condition:Chain[Token], clause:Chain[Token]):
        self.keyword = keyword
        self.condition = condition
        self.clause = clause
    def __repr__(self) -> str:
        return f"<Flow_t: {self.keyword}: {self.condition} {self.clause}"

class Do_t(Token):...
class Return_t(Token):...
class Express_t(Token):...
class Declare_t(Token):...


atom_tokens = (
    Identifier_t,
    Integer_t,
    Boolean_t,
    BasedNumber_t,
    RawString_t,
    String_t,
    Block_t,
    TypeParam_t,
    Hashtag_t,
    DotDot_t,
    Flow_t,
)





def invert_whitespace(tokens: list[Token]) -> None:
    """
    removes all whitespace tokens, and insert juxtapose tokens between adjacent pairs (i.e. not separated by whitespace)

    Args:
        tokens (list[Token]): list of tokens to modify. This is modified in place.
    """
    
    #juxtapose singleton token so we aren't wasting memory
    jux = Juxtapose_t(None)
    
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
        if isinstance(middle, Juxtapose_t) and (isinstance(left, (Operator_t, ShiftOperator_t, Comma_t)) or isinstance(right, (Operator_t, ShiftOperator_t, Comma_t))):
            tokens.pop(i)
            continue
        i += 1




def _get_next_prefixes(tokens:list[Token]) -> tuple[list[Token], list[Token]]:
    prefixes = []
    while len(tokens) > 0 and is_unary_prefix_op(tokens[0]): #isinstance(tokens[0], Operator_t) and tokens[0].op in unary_prefix_operators:
        prefixes.append(tokens.pop(0))
    return prefixes, tokens
def _get_next_postfixes(tokens:list[Token]) -> tuple[list[Token], list[Token]]:
    postfixes = []
    while len(tokens) > 0 and is_unary_postfix_op(tokens[0], exclude_semicolon=True):#isinstance(tokens[0], Operator_t) and tokens[0].op in unary_postfix_operators - {';'}:
        postfixes.append(tokens.pop(0))
    return postfixes, tokens
def _get_next_atom(tokens:list[Token]) -> tuple[Token, list[Token]]:
    if len(tokens) == 0:
        raise ValueError(f"ERROR: expected atom, got {tokens=}")

    #TODO: this is going to be unnecessary as expressions will have been bundled up into single tokens
    if isinstance(tokens[0], Keyword_t):
        return _get_next_keyword_expr(tokens)

    if isinstance(tokens[0], atom_tokens):#(Integer_t, BasedNumber_t, String_t, RawString_t, Identifier_t, Hashtag_t, Block_t, TypeParam_t, DotDot_t)):
        return tokens[0], tokens[1:]

    raise ValueError(f"ERROR: expected atom, got {tokens[0]=}")

def _get_next_chunk(tokens:list[Token]) -> tuple[list[Token], list[Token]]:
    chunk = []
    t, tokens = _get_next_prefixes(tokens)
    chunk.extend(t)

    t, tokens = _get_next_atom(tokens)
    if t is None:
        raise ValueError(f"ERROR: expected atom, got {tokens[0]=}")
    chunk.append(t)

    t, tokens = _get_next_postfixes(tokens)
    chunk.extend(t)

    return chunk, tokens

def is_unary_prefix_op(token:Token) -> bool:
    """
    Determines if a token could be a unary prefix operator.
    Note that this is not mutually exclusive with being a postfix operator or a binary operator.
    """
    return isinstance(token, Operator_t) and token.op in unary_prefix_operators

def is_unary_postfix_op(token:Token, exclude_semicolon:bool=False) -> bool:
    """
    Determines if a token could be a unary postfix operator. 
    Optionally can exclude semicolon from the set of operators.
    Note that this is not mutually exclusive with being a prefix operator or a binary operator.
    """
    if exclude_semicolon:
        return isinstance(token, Operator_t) and token.op in unary_postfix_operators - {';'}
    return isinstance(token, Operator_t) and token.op in unary_postfix_operators

def is_binop(token:Token) -> bool:
    """
    Determines if a token could be a binary operator.
    Note that this is not mutually exclusive with being a prefix operator or a postfix operator.
    """
    return isinstance(token, Operator_t) and token.op in binary_operators or isinstance(token, (ShiftOperator_t, Comma_t, Juxtapose_t))

def is_op(token:Token) -> bool:
    return is_binop(token) or is_unary_prefix_op(token) or is_unary_postfix_op(token)

def is_opchain_starter(token:Token) -> bool:
    return isinstance(token, Operator_t) and token.op in opchain_starters

def _get_next_keyword_expr(tokens:list[Token]) -> tuple[Token, list[Token]]:
    """package up the next keyword expression into a single token"""
    if len(tokens) == 0:
        raise ValueError(f"ERROR: expected keyword expression, got {tokens=}")
    t, tokens = tokens[0], tokens[1:]

    if not isinstance(t, Keyword_t):
        raise ValueError(f"ERROR: expected keyword expression, got {t=}")

    match t:
        case Keyword_t(src='if'|'loop'|'lazy'):
            cond, tokens = get_next_chain(tokens, binop_blacklist={Operator_t('else')})
            clause, tokens = get_next_chain(tokens, binop_blacklist={Operator_t('else')})
            return Flow_t(t, cond, clause), tokens
        case Keyword_t(src='do'):
            clause, tokens = get_next_chain(tokens)
            #assert next token is a do_keyward
            #depending on the keyward, get a condition, or condition+clause
            pdb.set_trace()
            ...
        case Keyword_t(src='return'):
            #TBD how to do this one...
            pdb.set_trace()
            ...
        case Keyword_t(src='express'):
            pdb.set_trace()
            ...
        case Keyword_t(src='let'|'const'):
            expr, tokens = get_next_chain(tokens)
            pdb.set_trace()
            ...
    
    raise NotImplementedError("TODO: handle keyword based expressions")
    # (if | loop) #chain #chain (else (if | loop) #chain #chain)* (else #chain)?
    # return #chain?
    # express #chain
    # (break | continue) #hashtag? //note the hashtag should be an entire chain if present
    # (let | const) #chain


def get_next_chain(tokens:list[Token], binop_blacklist:set[Token]=None) -> tuple[Chain[Token], list[Token]]:
    """
    grab the next single expression chain of tokens from the given list of tokens

    Also wraps up keyword-based expressions (if loop etc.) into a single token

    A chain is represented by the following grammar:
        #chunk = #prefix_op* #atom_expr (#postfix_op - ';')*
        #chain = #chunk (#binary_op #chunk)* ';'?

    Args:
        tokens (list[Token]): list of tokens to grab the next chain from

    Returns:
        next, rest (list[Token], list[Token]): the next chain of tokens, and the remaining tokens
    """
    if binop_blacklist is None: binop_blacklist = set()

    chain = []

    chunk, tokens = _get_next_chunk(tokens)
    chain.extend(chunk)

    while len(tokens) > 0 and is_binop(tokens[0]) and tokens[0] not in binop_blacklist:
        chain.append(tokens.pop(0))
        chunk, tokens = _get_next_chunk(tokens)
        chain.extend(chunk)

    if len(tokens) > 0 and isinstance(tokens[0], Operator_t) and tokens[0].op == ';':
        chain.append(tokens.pop(0))

    return Chain(chain), tokens




# def combine_keywords(tokens: list[Token]) -> None:
#     """
#     combine known keyword pairs into a single keyword

#     TBD on some of these
#     do loop -> do_loop
#     do lazy -> do_lazy
#     else if -> else_if
#     else loop -> else_loop
#     else lazy -> else_lazy
#     """

#     for i, token, stream in (gen := full_traverse_tokens(tokens)):
#         if isinstance(token, Keyword_t):
#             raise NotImplementedError

def desugar_ranges(tokens: list[Token]) -> None:
    """fill in empty expressions on the left/right of any range `..` that lacks left or right operands"""
    #TODO: also maybe put range in a group with []
    for i, token, stream in (gen := full_traverse_tokens(tokens)):
        if isinstance(token, DotDot_t):
            raise NotImplementedError



def bundle_conditionals(tokens: list[Token]) -> None:
    """Convert sequences of tokens that represent conditionals (if, loop, etc.) into a single expression token"""
    
    #TODO: should scan through, and if it finds a conditional, raise the not implemented error
    #TODO: need to check that nested conditionals as well as chained conditionals are handled properly
    #      e.g. `if a b`, `if a b else if c d else f`, `if a if b c else d`
    
    for i, token, stream in (gen := full_traverse_tokens(tokens)):
        if isinstance(token, Keyword_t):
            #TODO: handle bundling up the keyword into an expression
            raise NotImplementedError


def chain_operators(tokens: list[Token]) -> None:
    """Convert consecutive operator tokens into a single opchain token"""
    """
    A chain is represented by the following grammar:
        #chunk = #prefix_op* #atom_expr (#postfix_op - ';')*
        #chain = #chunk (#binary_op #chunk)* ';'?

        #prefix_op = '+' | '-' | '*' | '/' | 'not' | '@' | '...'
        #postfix_op = '?' | '`' | ';'
        #binary_op = '+' | '-' | '*' | '/' | '%' | '^'
          | '=?' | '>?' | '<?' | '>=?' | '<=?' | 'in?' | 'is?' | 'isnt?' | '<=>'
          | '|' | '&'
          | 'and' | 'or' | 'nand' | 'nor' | 'xor' | 'xnor' | '??'
          | '=' | ':=' | 'as' | 'in' | 'transmute'
          | '@?'
          | '|>' | '<|' | '=>'
          | '->' | '<->' | '<-'
          | '.' | ':'
    """

    # TODO: skip for now. not needed by hello world
    # also may not be necessary if we use a pratt parser. was necessary for split by lowest precedence parser

    for i, token, stream in (gen := full_traverse_tokens(tokens)):

        #TODO: this is not a correct way to detect these. need to verify that the operators are in between two #chunks
        #   this will be conservative, but for now it will let us do a hello world happy path
        if is_opchain_starter(token):
            j = 1
            while i+j < len(stream) and is_unary_prefix_op(stream[i+j]):
                j+=1
            if j > 1:
                pdb.set_trace()
                raise NotImplementedError('opchaining has not been implemented yet')


def post_process(tokens: list[Token]) -> None:
    """post process the tokens to make them ready for parsing"""

    # remove whitespace, and insert juxtapose tokens
    invert_whitespace(tokens)

    if len(tokens) == 0: return

    # combine known keyword pairs into a single keyword
    # combine_keywords(tokens) # possibly handled by bundling conditionals...

    # bundle up conditionals into single token expressions
    #TODO: can put this in after get_next_chain can bundle as it goes. Basically this would just make any work it does finding flow permenant
    # bundle_conditionals(tokens)

    # combine operator chains into a single operator token
    chain_operators(tokens)

    # desugar ranges
    desugar_ranges(tokens)


    # make the actual list of chains

    # based on types, replace jux with jux_mul or jux_call
    # TODO: actually this probably would need to be done during parsing, since we can't get a type for a complex/compound expression...

    # print(tokens)



def test():
    with open('../../../examples/hello.dewy') as f:
        src = f.read()

    tokens = tokenize(src)

    #chainer process
    post_process(tokens)

    pdb.set_trace()
    ...
    

def test2():
    """gauntlet of multiple tests from example file"""
    with open('../../../examples/syntax3.dewyl') as f:
        lines = f.readlines()

    # filter out empty lines
    lines = [l for line in lines if (l := line.strip())]

    for line in lines:
        tokens = tokenize(line)

        #chainer process
        post_process(tokens)

        #other stuff? pass to the parser? etc.

    pdb.set_trace()
    ...


def test_hello():
    line = "printl'Hello, World!'"

    tokens = tokenize(line)
    post_process(tokens)

    pdb.set_trace()
    ...


if __name__ == '__main__':
    # test()
    # test2()
    test_hello()