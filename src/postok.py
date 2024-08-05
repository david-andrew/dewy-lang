from .tokenizer import (
    tokenize, tprint, full_traverse_tokens,
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
    Undefined_t,
    Void_t,
    End_t,
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

from typing import Generator, overload
from abc import ABC


import pdb


# There is no chain class
# A chain is just a list of tokens that is directly parsable as an expression without any other syntax
# all other syntax is wrapped up into compound tokens
# it should literally just be a sequence of atoms and operators


# TODO: replace with 3.12 syntax when released: class Chain[T](list[T]): ...
from typing import TypeVar
T = TypeVar('T')


class Chain(list[T]):
    """class for explicitly annotating that a token list is a single chain"""


############### NEW TOKENS CREATED BY POST-TOKENIZATION PROCESS ###############

class Flow_t(Token):
    @overload
    def __init__(self, keyword: None, condition: None, clause: Chain[Token]): ...  # closing else
    @overload
    def __init__(self, keyword: Keyword_t, condition: Chain[Token], clause: Chain[Token]): ...  # if, loop, lazy

    def __init__(self, keyword: Keyword_t | None, condition: Chain[Token] | None, clause: Chain[Token]):
        if keyword is None and condition is not None:
            raise ValueError("closing else should have no condition. `keyword` and `condition` should both be None")
        self.keyword = keyword
        self.condition = condition
        self.clause = clause

    def __repr__(self) -> str:
        return f"<Flow_t: {self.keyword}: {self.condition} {self.clause}>"

    def __iter__(self) -> Generator[Token, None, None]:
        if self.condition is not None:
            yield self.condition
        yield self.clause


# class Do_t(Token):...
# class Return_t(Token):...
# class Express_t(Token):...
# class Declare_t(Token):...


class RangeJuxtapose_t(Token):
    def __init__(self, _): ...

    def __repr__(self) -> str:
        return "<RangeJuxtapose_t>"

    def __hash__(self) -> int:
        return hash(RangeJuxtapose_t)

    def __eq__(self, other) -> bool:
        return isinstance(other, RangeJuxtapose_t)


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
    Undefined_t,
)


class ShouldBreakTracker(ABC):
    def op_breaks_chain(self, token: Token) -> bool:
        raise NotImplementedError("op_breaks_chain must be implemented by subclass")

    def view(self, tokens: list[Token]) -> None:
        raise NotImplementedError("view must be implemented by subclass")


class ShouldBreakFlowTracker(ShouldBreakTracker):
    def __init__(self):
        self.flows_seen = 0

    def op_breaks_chain(self, token: Token) -> bool:
        # should only be operators
        if isinstance(token, Operator_t) and token.op == 'else':
            if self.flows_seen == 0:
                return True
            self.flows_seen -= 1

        return False

    def view(self, tokens: list[Token]) -> None:
        # view each token without any ability to do anything
        # keep track of how many flows we've seen
        for token in tokens:
            if isinstance(token, Flow_t) and token.keyword is not None:
                self.flows_seen += 1
            if isinstance(token, Operator_t) and token.op == 'else':
                raise ValueError("should not be seeing else here")
            if isinstance(token, Keyword_t) and token.src in ('if', 'loop', 'lazy'):
                raise ValueError("should not be seeing if/loop/lazy here. Everything should be bundled up into a flow")


def invert_whitespace(tokens: list[Token]) -> None:
    """
    removes all whitespace tokens, and insert juxtapose tokens between adjacent pairs (i.e. not separated by whitespace)

    Args:
        tokens (list[Token]): list of tokens to modify. This is modified in place.
    """

    # juxtapose singleton token so we aren't wasting memory
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

    # finally, remove juxtapose tokens next to operators that are not whitespace sensitive
    i = 1
    while i < len(tokens) - 1:
        left, middle, right = tokens[i-1:i+2]
        if isinstance(middle, Juxtapose_t) and (isinstance(left, (Operator_t, ShiftOperator_t, Comma_t)) or isinstance(right, (Operator_t, ShiftOperator_t, Comma_t))):
            tokens.pop(i)
            continue
        i += 1


def _get_next_prefixes(tokens: list[Token]) -> tuple[list[Token], list[Token]]:
    prefixes = []
    # isinstance(tokens[0], Operator_t) and tokens[0].op in unary_prefix_operators:
    while len(tokens) > 0 and is_unary_prefix_op(tokens[0]):
        prefixes.append(tokens.pop(0))
    return prefixes, tokens


def _get_next_postfixes(tokens: list[Token]) -> tuple[list[Token], list[Token]]:
    postfixes = []
    # isinstance(tokens[0], Operator_t) and tokens[0].op in unary_postfix_operators - {';'}:
    while len(tokens) > 0 and is_unary_postfix_op(tokens[0], exclude_semicolon=True):
        postfixes.append(tokens.pop(0))
    return postfixes, tokens


def _get_next_atom(tokens: list[Token]) -> tuple[Token, list[Token]]:
    if len(tokens) == 0:
        raise ValueError(f"ERROR: expected atom, got {tokens=}")

    # TODO: this is going to be unnecessary as expressions will have been bundled up into single tokens
    if isinstance(tokens[0], Keyword_t):
        return _get_next_keyword_expr(tokens)

    # (Integer_t, BasedNumber_t, String_t, RawString_t, Identifier_t, Hashtag_t, Block_t, TypeParam_t, DotDot_t)):
    if isinstance(tokens[0], atom_tokens):
        return tokens[0], tokens[1:]

    raise ValueError(f"ERROR: expected atom, got {tokens[0]=}")


def _get_next_chunk(tokens: list[Token]) -> tuple[list[Token], list[Token]]:
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


def is_unary_prefix_op(token: Token) -> bool:
    """
    Determines if a token could be a unary prefix operator.
    Note that this is not mutually exclusive with being a postfix operator or a binary operator.
    """
    return isinstance(token, Operator_t) and token.op in unary_prefix_operators


def is_unary_postfix_op(token: Token, exclude_semicolon: bool = False) -> bool:
    """
    Determines if a token could be a unary postfix operator. 
    Optionally can exclude semicolon from the set of operators.
    Note that this is not mutually exclusive with being a prefix operator or a binary operator.
    """
    if exclude_semicolon:
        return isinstance(token, Operator_t) and token.op in unary_postfix_operators - {';'}
    return isinstance(token, Operator_t) and token.op in unary_postfix_operators


def is_binop(token: Token) -> bool:
    """
    Determines if a token could be a binary operator.
    Note that this is not mutually exclusive with being a prefix operator or a postfix operator.
    """
    return isinstance(token, Operator_t) and token.op in binary_operators or isinstance(token, (ShiftOperator_t, Comma_t, Juxtapose_t, RangeJuxtapose_t))


def is_op(token: Token) -> bool:
    return is_binop(token) or is_unary_prefix_op(token) or is_unary_postfix_op(token)


def is_opchain_starter(token: Token) -> bool:
    return isinstance(token, Operator_t) and token.op in opchain_starters


def _get_next_keyword_expr(tokens: list[Token]) -> tuple[Token, list[Token]]:
    """package up the next keyword expression into a single token"""
    if len(tokens) == 0:
        raise ValueError(f"ERROR: expected keyword expression, got {tokens=}")
    t, tokens = tokens[0], tokens[1:]

    if not isinstance(t, Keyword_t):
        raise ValueError(f"ERROR: expected keyword expression, got {t=}")

    match t:
        case Keyword_t(src='if' | 'loop' | 'lazy'):
            cond, tokens = get_next_chain(tokens)
            clause, tokens = get_next_chain(tokens, tracker=ShouldBreakFlowTracker())
            return Flow_t(t, cond, clause), tokens
        case Keyword_t(src='closing_else'):
            clause, tokens = get_next_chain(tokens, tracker=ShouldBreakFlowTracker())
            return Flow_t(None, None, clause), tokens
        case Keyword_t(src='do'):
            clause, tokens = get_next_chain(tokens)
            # assert next token is a do_keyward
            # depending on the keyward, get a condition, or condition+clause
            pdb.set_trace()
            ...
        case Keyword_t(src='return'):
            # TBD how to do this one...
            pdb.set_trace()
            ...
        case Keyword_t(src='express'):
            pdb.set_trace()
            ...
        case Keyword_t(src='let' | 'const'):
            expr, tokens = get_next_chain(tokens)
            pdb.set_trace()
            ...

    raise NotImplementedError("TODO: handle keyword based expressions")
    # return #chain?
    # yield #chain
    # (break | continue) #hashtag? //note the hashtag should be an entire chain if present
    # (let | const) #chain


def get_next_chain(tokens: list[Token], *, tracker: ShouldBreakTracker = None, op_blacklist: set[Token] = None) -> tuple[Chain[Token], list[Token]]:
    """
    grab the next single expression chain of tokens from the given list of tokens

    Also wraps up keyword-based expressions (if loop etc.) into a single token

    A chain is represented by the following grammar:
        #chunk = #prefix_op* #atom_expr (#postfix_op - ';')*
        #chain = #chunk (#binary_op #chunk)* ';'?

    Args:
        tokens (list[Token]): list of tokens to grab the next chain from
        tracker (ShouldBreakTracker, optional): tracker for complex analysis to determine if an operator should break the chain. Defaults to None.
        op_blacklist (set[Token], optional): simpler handler for operators that should break the chain. Defaults to None.

    Returns:
        next, rest (list[Token], list[Token]): the next chain of tokens, and the remaining tokens
    """

    if op_blacklist is None:
        op_blacklist = set()

    chain = []

    # grab the first chunk and let the tracker view it
    chunk, tokens = _get_next_chunk(tokens)
    chain.extend(chunk)
    if tracker is not None:
        tracker.view(chunk)

    while len(tokens) > 0 and is_binop(tokens[0]) and (tracker is None or not tracker.op_breaks_chain(tokens[0])) and tokens[0] not in op_blacklist:
        # get the operator, and continuing chunk, then let the tracker view it
        chain.append(tokens.pop(0))
        chunk, tokens = _get_next_chunk(tokens)
        chain.extend(chunk)
        if tracker is not None:
            tracker.view(chunk)

    # if there's a semicolon, it ends the chain
    if len(tokens) > 0 and isinstance(tokens[0], Operator_t) and tokens[0].op == ';':
        chain.append(tokens.pop(0))

    return Chain(chain), tokens


def regularize_ranges(tokens: list[Token]) -> None:
    """
    convert [<token>, <jux>, <..>] into [<token>, <range_jux>, <..>]
    convert [<..>, <jux>, <token>] into [<..>, <range_jux>, <token>]
    if .. doesn't connect to anything on the left or right, connect it to undefined
    """
    range_jux = RangeJuxtapose_t(None)
    undefined = Undefined_t(None)
    for i, token, stream in (gen := full_traverse_tokens(tokens)):
        if isinstance(token, DotDot_t):
            if i + 1 < len(stream):
                if isinstance(stream[i+1], Juxtapose_t):
                    stream[i+1] = range_jux
                else:
                    stream[i+1:i+1] = [range_jux, undefined]
            if i > 0:
                if isinstance(stream[i-1], Juxtapose_t):
                    stream[i-1] = range_jux
                else:
                    stream[i:i] = [undefined, range_jux]
                    gen.send(i+2)


def convert_bare_else(tokens: list[Token]) -> None:
    """
    convert any instances of `else` without a flow keyword after, and convert to `else` `if` `true`
    """
    for i, token, stream in (gen := full_traverse_tokens(tokens)):
        if isinstance(token, Operator_t) and token.op == 'else':
            if i+1 < len(stream) and isinstance(stream[i+1], Keyword_t) and stream[i+1].src in ('if', 'loop', 'lazy'):
                continue
            # stream[i+1:i+1] = [Keyword_t('if'), Boolean_t('true')]
            stream.insert(i+1, Keyword_t('closing_else'))


def bundle_conditionals(tokens: list[Token]) -> None:
    """
    Convert sequences of tokens that represent conditionals (if, loop, etc.) into a single expression token
    """
    for i, token, stream in (gen := full_traverse_tokens(tokens)):
        if isinstance(token, Keyword_t) and token.src in ('if', 'loop', 'lazy'):
            flow_chain, tokens = get_next_chain(stream[i:])
            stream[i] = flow_chain[0]
            stream[i+1:] = [*flow_chain[1:], *tokens]


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

        # TODO: this is not a correct way to detect these. need to verify that the operators are in between two #chunks
        #   this will be conservative, but for now it will let us do a hello world happy path
        if is_opchain_starter(token):
            j = 1
            while i+j < len(stream) and is_unary_prefix_op(stream[i+j]):
                j += 1
            if j > 1:
                pdb.set_trace()
                raise NotImplementedError('opchaining has not been implemented yet')


def post_process(tokens: list[Token]) -> None:
    """post process the tokens to make them ready for parsing"""

    # remove whitespace, and insert juxtapose tokens
    invert_whitespace(tokens)

    if len(tokens) == 0:
        return

    # find any instances of <else> without a flow keyword after, and convert to <else> <if> <true>
    convert_bare_else(tokens)

    # bundle up conditionals into single token expressions
    bundle_conditionals(tokens)

    # combine operator chains into a single operator token
    chain_operators(tokens)

    # desugar ranges
    regularize_ranges(tokens)

    # make the actual list of chains

    # based on types, replace jux with jux_mul or jux_call
    # TODO: actually this probably would need to be done during parsing, since we can't get a type for a complex/compound expression...


def test():
    with open('../../../examples/hello.dewy') as f:
        src = f.read()

    tokens = tokenize(src)

    # chainer process
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

        # chainer process
        post_process(tokens)

        # other stuff? pass to the parser? etc.

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
