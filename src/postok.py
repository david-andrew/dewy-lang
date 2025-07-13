from .tokenizer import (
    tokenize, tprint, full_traverse_tokens,
    unary_prefix_operators,
    unary_postfix_operators,
    binary_operators,
    opchain_starters,
    Token,
    Keyword_t, #Undefined_t, Void_t, End_t, New_t,
    WhiteSpace_t, Escape_t,
    Identifier_t, Hashtag_t,
    Block_t, TypeParam_t,
    RawString_t, String_t,
    Integer_t, BasedNumber_t, Boolean_t,
    DotDot_t, DotDotDot_t, Backticks_t,
    Juxtapose_t, Operator_t, ShiftOperator_t, Comma_t,
)

from typing import Generator, overload, cast
from abc import ABC, abstractmethod


import pdb


# A chain is just a list of tokens that is known to be directly parsable as an expression without any other syntax
# i.e. it is the result of calls to `get_next_chain()`
# all other syntax is wrapped up into compound tokens
# it should literally just be a sequence of atoms and operators
from typing import TypeVar
T = TypeVar('T', bound=Token)
class Chain(list[T]):
    """class for explicitly annotating that a token list is a single chain"""

# class Chain[T](list[T]):
#     """class for explicitly annotating that a token list is a single chain"""


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

    def __iter__(self) -> Generator[list[Token], None, None]:
        if self.condition is not None:
            yield self.condition
        yield self.clause


# class Do_t(Token):...


class Return_t(Token):
    def __init__(self, expr: Chain[Token]):
        self.expr = expr

    def __repr__(self) -> str:
        return f'<Return_t: {self.expr}>'

    def __iter__(self) -> Generator[list[Token], None, None]:
        yield self.expr

# class Express_t(Token):...


class Declare_t(Token):
    def __init__(self, keyword: Keyword_t, expr: Chain[Token]):
        self.keyword = keyword
        self.expr = expr

    def __repr__(self) -> str:
        return f"<Declare_t: {self.keyword} {self.expr}>"

    def __iter__(self) -> Generator[list[Token], None, None]:
        yield [self.keyword] #appraently flow doesn't yield the keyword. tbd if it matters...
        yield self.expr


class RangeJuxtapose_t(Operator_t):
    def __init__(self, _):
        super().__init__('')

    def __repr__(self) -> str:
        return "<RangeJuxtapose_t>"

    def __hash__(self) -> int:
        return hash(RangeJuxtapose_t)

    def __eq__(self, other) -> bool:
        return isinstance(other, RangeJuxtapose_t)


class EllipsisJuxtapose_t(Operator_t):
    def __init__(self, _):
        super().__init__('')

    def __repr__(self) -> str:
        return "<EllipsisJuxtapose_t>"

    def __hash__(self) -> int:
        return hash(EllipsisJuxtapose_t)

    def __eq__(self, other) -> bool:
        return isinstance(other, EllipsisJuxtapose_t)


class BackticksJuxtapose_t(Operator_t):
    def __init__(self, _):
        super().__init__('')

    def __repr__(self) -> str:
        return "<BackticksJuxtapose_t>"

    def __hash__(self) -> int:
        return hash(BackticksJuxtapose_t)

    def __eq__(self, other) -> bool:
        return isinstance(other, BackticksJuxtapose_t)


class TypeParamJuxtapose_t(Operator_t):
    def __init__(self, _):
        super().__init__('')

    def __repr__(self) -> str:
        return "<TypeParamJuxtapose_t>"

    def __hash__(self) -> int:
        return hash(TypeParamJuxtapose_t)

    def __eq__(self, other) -> bool:
        return isinstance(other, TypeParamJuxtapose_t)

class OpChain_t(Token):
    def __init__(self, ops:list[Operator_t]):
        assert len(ops) > 1, f"OpChain_t must have at least 2 operators. Got {len(ops)} operators"
        self.ops = ops

    def __repr__(self) -> str:
        return f"<OpChain_t: {''.join(op.op for op in self.ops)}>"

    def __hash__(self) -> int:
        return hash((OpChain_t, tuple(self.ops)))

    def __eq__(self, other) -> bool:
        return isinstance(other, OpChain_t) and self.ops == other.ops

    def __iter__(self) -> Generator[list[Token], None, None]:
        yield cast(list[Token], self.ops)

class BroadcastOp_t(Token):
    def __init__(self, dot:Operator_t, op:Operator_t|OpChain_t):
        assert isinstance(dot, Operator_t) and dot.op == '.', f"VectorizedOp_t must have a '.' operator. Got {dot}"
        self.dot = dot
        self.op = op

    def __repr__(self) -> str:
        return f"<VectorizedOp_t: {self.dot}, {self.op}>"

    def __hash__(self) -> int:
        return hash((BroadcastOp_t, self.dot, self.op))

    def __eq__(self, other) -> bool:
        return isinstance(other, BroadcastOp_t) and self.dot == other.dot and self.op == other.op

    def __iter__(self) -> Generator[list[Token], None, None]:
        yield [self.dot]
        yield [self.op]


class CombinedAssignmentOp_t(Token):
    def __init__(self, op:Operator_t|OpChain_t|BroadcastOp_t, assign:Operator_t):
        assert isinstance(assign, Operator_t) and assign.op == '=', f"CombinedAssignmentOp_t must have an '=' operator. Got {assign}"
        self.op = op
        self.assign = assign

    def __repr__(self) -> str:
        return f"<CombinedAssignmentOp_t: {self.op}, {self.assign}>"

    def __hash__(self) -> int:
        return hash((CombinedAssignmentOp_t, self.op, self.assign))

    def __eq__(self, other) -> bool:
        return isinstance(other, CombinedAssignmentOp_t) and self.op == other.op and self.assign == other.assign

    def __iter__(self) -> Generator[list[Token], None, None]:
        yield [self.op]
        yield [self.assign]


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
    DotDotDot_t,
    Backticks_t,
    Flow_t,
    # Undefined_t,
    # Void_t,
)

# atoms that can be juxtaposed (so juxtaposes next to them shouldn't be removed)
jux_atoms = (
    DotDot_t,
    DotDotDot_t,
    Backticks_t,
)

non_jux_ops = (
    Operator_t,
    ShiftOperator_t,
    Comma_t
)



class ShouldBreakTracker(ABC):
    @abstractmethod
    def op_breaks_chain(self, token: Token) -> bool: ...

    @abstractmethod
    def view(self, tokens: list[Token]) -> None: ...


class ShouldBreakFlowTracker(ShouldBreakTracker):
    def __init__(self, error_on_break:bool=False):
        self.flows_seen = 0
        self.error_on_break = error_on_break

    def op_breaks_chain(self, token: Token) -> bool:
        # should only be operators
        if isinstance(token, Operator_t) and token.op == 'else':
            if self.flows_seen == 0:
                if self.error_on_break:
                    raise ValueError(f'Encountered an `else` in a context where it is not allowed. {token=}')
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
        #TODO: somewhere around here, need to fix how @ isn't juxtaposable but should be on the left depending on lots of stuff...
        if isinstance(middle, Juxtapose_t) \
        and (isinstance(left, non_jux_ops) or isinstance(right, non_jux_ops))\
        and not isinstance(left, jux_atoms) and not isinstance(right, jux_atoms):
            tokens.pop(i)
            continue
        i += 1


def _get_next_prefixes(tokens: list[Token]) -> tuple[list[Token], list[Token]]:
    prefixes = []
    while len(tokens) > 0 and is_unary_prefix_op(tokens[0]):
        prefixes.append(tokens.pop(0))

    return prefixes, tokens


def _get_next_postfixes(tokens: list[Token]) -> tuple[list[Token], list[Token]]:
    postfixes = []
    while len(tokens) > 0 and is_unary_postfix_op(tokens[0], exclude_semicolon=True):
        postfixes.append(tokens.pop(0))

    return postfixes, tokens


def _get_next_atom(tokens: list[Token]) -> tuple[Token, list[Token]]:
    if len(tokens) == 0:
        raise ValueError(f"ERROR: expected atom, got {tokens=}")

    # TODO: this is going to be unnecessary as expressions will have been bundled up into single tokens
    if isinstance(tokens[0], Keyword_t):
        return _get_next_keyword_expr(tokens)

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
    return isinstance(token, Operator_t) and token.op in unary_prefix_operators \
        or isinstance(token, OpChain_t) and token.ops[0].op in unary_prefix_operators


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
    return isinstance(token, Operator_t) and token.op in binary_operators or isinstance(token, (ShiftOperator_t, Comma_t, Juxtapose_t, RangeJuxtapose_t, EllipsisJuxtapose_t, BackticksJuxtapose_t, TypeParamJuxtapose_t, OpChain_t, BroadcastOp_t, CombinedAssignmentOp_t))


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

    # seeing a common pattern here of a lot of <keyword> <expr> types,
    # could replace it with a function that takes the keyword, and it's class constructor'
    match t:
        case Keyword_t(src='if' | 'loop' | 'lazy'):
            cond, tokens = get_next_chain(tokens, tracker=ShouldBreakFlowTracker(error_on_break=True))
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
            expr, tokens = get_next_chain(tokens, tracker=ShouldBreakFlowTracker())
            return Return_t(expr), tokens
        case Keyword_t(src='express'):
            pdb.set_trace()
            ...
        case Keyword_t(src='let' | 'const' | 'local_const' | 'fixed_type'):
            expr, tokens = get_next_chain(tokens, tracker=ShouldBreakFlowTracker())
            return Declare_t(t, expr), tokens

        # keywords that convert directly to expressions
        case Keyword_t(src='extern'|'new'|'end'|'void'|'undefined'):
            return t, tokens


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


def narrow_juxtapose(tokens: list[Token]) -> None:
    """
    range juxtapose:
    convert [<token>, <jux>, <..>] into [<token>, <range_jux>, <..>]
    convert [<..>, <jux>, <token>] into [<..>, <range_jux>, <token>]
    if .. doesn't connect to anything on the left or right, connect it to undefined

    ellipsis juxtapose:
    convert [<...>, <jux>, <token>] into [<...>, <ellipsis_jux>, <token>]

    type param juxtapose:
    convert [<token>, <jux>, <type_param>] into [<token>, <type_param_jux>, <type_param>]
    convert [<type_param>, <jux>, <token>] into [<type_param>, <type_param_jux>, <token>]
    """
    range_jux = RangeJuxtapose_t(None)
    ellipsis_jux = EllipsisJuxtapose_t(None)
    backticks_jux = BackticksJuxtapose_t(None)
    type_param_jux = TypeParamJuxtapose_t(None)
    undefined = Keyword_t('undefined') #Undefined_t(None)
    for i, token, stream in (gen := full_traverse_tokens(tokens)):
        left_is_jux = i > 0 and isinstance(stream[i-1], Juxtapose_t)
        right_is_jux = i + 1 < len(stream) and isinstance(stream[i+1], Juxtapose_t)

        # handle range jux
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
                    gen.send(i+3)

        # handle ellipsis jux
        elif isinstance(token, DotDotDot_t):
            # ellipsis can be optionally juxtaposed, but when it is juxtaposed, it may only be juxtaposed on one side
            if left_is_jux and right_is_jux:
                raise ValueError(f"ERROR: ellipsis operator {token} must be juxtaposed on either zero or one side. Got ...{stream[i-2:i+3]}...")
            if left_is_jux:
                stream[i-1] = ellipsis_jux
            if right_is_jux:
                stream[i+1] = ellipsis_jux

        # handle type param jux
        elif isinstance(token, TypeParam_t):
            if left_is_jux:
                stream[i-1] = type_param_jux
            elif right_is_jux:
                stream[i+1] = type_param_jux

        # handle backticks jux
        elif isinstance(token, Backticks_t):
            # only left or right can be juxtaposed, but not both, and not neither
            if (left_is_jux and right_is_jux) or (not left_is_jux and not right_is_jux):
                raise ValueError(f"ERROR: backticks operator {token} must be juxtaposed on a exactly one side. Got ...{stream[i-2:i+3]}...")

            if left_is_jux:
                stream[i-1] = backticks_jux
            elif right_is_jux:
                stream[i+1] = backticks_jux



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


def make_chain_operators(tokens: list[Token]) -> None:
    """Convert consecutive operator tokens into a single opchain token"""
    for i, token, stream in (gen := full_traverse_tokens(tokens)):
        if is_opchain_starter(token):
            j = 1
            while i+j < len(stream) and is_unary_prefix_op(stream[i+j]):
                j += 1
            if j > 1:
                # convert the prefix operators into a single token
                stream[i:i+j] = [OpChain_t([stream[i+k] for k in range(j)])]
                gen.send(i+j)
                continue

def make_broadcast_operators(tokens: list[Token]) -> None:
    """Convert any . operator next to a binary operator or opchain into a broadcast operator"""
    for i, token, stream in (gen := full_traverse_tokens(tokens)):
        if isinstance(token, Operator_t) and token.op == '.':
            if len(stream) > i+1 and is_binop(stream[i+1]) or isinstance(stream[i+1], OpChain_t):
                stream[i:i+2] = [BroadcastOp_t(token, stream[i+1])]
                gen.send(i+2)

def make_combined_assignment_operators(tokens: list[Token]) -> None:
    """Convert any combined assignment operators into a single token"""
    for i, token, stream in (gen := full_traverse_tokens(tokens)):
        if is_binop(token) or isinstance(token, OpChain_t) or isinstance(token, BroadcastOp_t):
            if i+1 < len(stream) and isinstance(stream[i+1], Operator_t) and stream[i+1].op == '=':
                stream[i:i+2] = [CombinedAssignmentOp_t(token, stream[i+1])]
                gen.send(i+2)

def post_process(tokens: list[Token]) -> None:
    """post process the tokens to make them ready for parsing"""

    # remove whitespace, and insert juxtapose tokens
    invert_whitespace(tokens)

    if len(tokens) == 0:
        return

    # combine operator chains into a single operator token
    make_chain_operators(tokens)

    # convert any . operator next to a binary operator or opchain (e.g. .+ .^/-) into a broadcast operator
    make_broadcast_operators(tokens)

    # convert any combined assignment operators (e.g. += -= etc.) into a single token
    make_combined_assignment_operators(tokens)

    # convert juxtapose tokens to more specific types if possible
    narrow_juxtapose(tokens)

    # find any instances of <else> without a flow keyword after, and convert to <else> <if> <true>
    convert_bare_else(tokens)

    # bundle up conditionals into single token expressions
    bundle_conditionals(tokens)

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
