"""
Post processing steps on tokens to prepare them for expression parsiing
"""
from typing import Callable
from dataclasses import dataclass
from .reporting import SrcFile, ReportException, Span
from . import t1

# various juxtapose operators, for handling precedence in cases known at tokenization time
@dataclass
class Juxtapose(t1.InedibleToken): ...

@dataclass
class RangeJuxtapose(Juxtapose): ...

@dataclass
class EllipsisJuxtapose(Juxtapose): ...

@dataclass
class BackticksJuxtapose(Juxtapose): ...

@dataclass
class TypeParamJuxtapose(Juxtapose): ...

@dataclass
class InvertedComparisonOp(t1.Operator, t1.InedibleToken): ...

@dataclass
class PrefixChain(t1.InedibleToken):
    chain: list[t1.Operator]  # must be a list of unary prefix operators

@dataclass
class BinopChain(t1.InedibleToken):
    start: t1.Operator
    chain: PrefixChain

@dataclass
class BroadcastOp(t1.InedibleToken):
    op: t1.Operator | BinopChain  # must be a binary operator or an opchain
    # unary broadcasts don't seem like a coherent concept, so ignore them for now.

@dataclass
class CombinedAssignmentOp(t1.InedibleToken):
    op: t1.Operator | BinopChain | BroadcastOp   # must be a binary operator or a binary opchain or a broadcast operator


"""
keywords:
'loop', 'do', 'if', 'else', 'match', 'return', 'yield', 'break', 'continue',
'import', 'from', 'let', 'const', 'local_const', 'overload_only',

patterns:
flows # note that if-else-if/if-else-loop/etc. should all be bundled up into one higher level token
  <loop><expr><expr>
  <do><expr><loop><expr>
  <do><expr><loop><expr><do><expr>
  <if><expr><expr>
<match><expr><expr>
<return>
<return><expr>
<yield>
<yield><expr>
<break>
<break><hashtag>
<continue>
<continue><hashtag>
<import><expr>
<import><expr><from><expr>
<from><expr><import><expr>
<let><expr>
<const><expr>
<local_const><expr>
<overload_only><expr>

"""

@dataclass
class KeywordExpr(t1.InedibleToken):
    parts: list[t1.Keyword | list[t1.Token]]

@dataclass
class FlowArm(t1.InedibleToken):
    parts: list[t1.Keyword | list[t1.Token]]

@dataclass
class Flow(t1.InedibleToken):
    arms: list[FlowArm]
    default: list[t1.Token]|None=None
    

# token categories used by the keyword/flow bundler.
# Atom tokens may be juxtaposed with each other.
atom_tokens: set[type[t1.Token]] = {
    t1.Real,
    t1.String,
    t1.IString,
    t1.Block,
    t1.BasedString,
    t1.BasedArray,
    t1.Identifier,
    t1.Handle,
    t1.Hashtag,
    t1.Integer,
    KeywordExpr,
    Flow,
}


# not including t1.Operator
other_infix_tokens: set[type[t1.Token]] = { 
    Juxtapose,
    RangeJuxtapose,
    EllipsisJuxtapose,
    BackticksJuxtapose,
    TypeParamJuxtapose,
    BinopChain,
    BroadcastOp,
    CombinedAssignmentOp,
}


binary_ops: set[str] = {
    '+', '-', '*', '/', '//', '^',
    '\\',
    '=?', '>?', '<?', '>=?', '<=?', 'in?', 'is?', 'isnt?', '<=>',
    '|', '&', '??',
    '=', '::', ':=',
    '@?',
    '|>', '<|', '=>',
    '->', '<->',
    '.', ',', ':', ':>',
    '<<', '>>', '<<<', '>>>', '<<!', '!>>',
    'and', 'or', 'xor', 'nand', 'nor', 'xnor',
    'as', 'in', 'transmute', 'of', 'mod',
}
prefix_ops: set[str] = {
    '~',
    '+', '-', '*', '/', '//',
    'not',
}

# simple checks for it t1.Operator
def is_binary_op(token: t1.Token) -> bool:
    return isinstance(token, t1.Operator) and token.symbol in binary_ops
def is_prefix_op(token: t1.Token) -> bool:
    return isinstance(token, t1.Operator) and token.symbol in prefix_ops

def is_dotdot(token: t1.Token) -> bool:
    return isinstance(token, t1.Identifier) and token.name == '..'
def is_dotdotdot(token: t1.Token) -> bool:
    return isinstance(token, t1.Identifier) and token.name == '...'
def is_backticks(token: t1.Token) -> bool:
    return isinstance(token, t1.Identifier) and token.name == '`'
def is_typeparam(token: t1.Token) -> bool:
    return isinstance(token, t1.Block) and token.delims == '<>'

def get_jux_type(left: t1.Token, right: t1.Token, prev: t1.Token|None) -> type[Juxtapose]:
    if is_dotdot(left) or is_dotdot(right):
        return RangeJuxtapose
    elif is_dotdotdot(left) or is_dotdotdot(right):
        return EllipsisJuxtapose
    elif is_backticks(left) or is_backticks(right):
        return BackticksJuxtapose
    elif is_typeparam(right) or (is_typeparam(left) and not isinstance(prev, TypeParamJuxtapose)):
        return TypeParamJuxtapose
    return Juxtapose


def recurse_into(token: t1.Token, func: Callable[[list[t1.Token]], None]) -> None:
    """Helper to recursively apply a function to the inner tokens of a token (if it has any)"""
    if isinstance(token, t1.Block):
        func(token.inner)
    elif isinstance(token, t1.IString):
        for child in token.content:
            recurse_into(child, func)
    # TBD if other tokens may have inner tokens


def invert_whitespace(tokens: list[t1.Token]) -> None:
    """
    removes all whitespace tokens, and insert juxtapose tokens between adjacent pairs (i.e. not separated by whitespace)
    TODO: currently a pretty inefficient implementation. consider some type of e.g. heap or rope or etc. data structure if needed

    Args:
        tokens (list[Token]): list of tokens to modify. This is modified in place.
    """

    i = 0
    while i < len(tokens):
        # delete whitespace if it comes up
        if isinstance(tokens[i], t1.Whitespace):
            tokens.pop(i)
            continue

        # recursively handle inverting whitespace for blocks
        recurse_into(tokens[i], invert_whitespace)

        # insert juxtapose if no whitespace between tokens
        if i + 1 < len(tokens) and type(tokens[i]) in atom_tokens and type(tokens[i+1]) in atom_tokens and tokens[i].loc.stop == tokens[i+1].loc.start:
            jux_type = get_jux_type(tokens[i], tokens[i+1], tokens[i-1] if i > 0 else None)
            tokens.insert(i+1, jux_type(t1.Span(tokens[i].loc.stop, tokens[i].loc.stop)))
            i += 1

        # move to next token
        i += 1


def make_inverted_comparisons(tokens: list[t1.Token]) -> None:
    """`not` followed by a comparison operator becomes an inverted comparison operator"""
    i = 0
    while i < len(tokens):
        token = tokens[i]
        recurse_into(token, make_inverted_comparisons)
        
        if isinstance(token, t1.Operator) and token.symbol == 'not':
            if len(tokens) > i+1 and is_binary_op(tokens[i+1]) and tokens[i+1].symbol in {'=?', '>?', '<?', '>=?', '<=?', 'in?', 'is?', 'isnt?'}:
                tokens[i:i+2] = [InvertedComparisonOp(Span(token.loc.start, tokens[i+1].loc.stop), tokens[i+1].symbol)]
        i += 1


def make_chain_operators(tokens: list[t1.Token]) -> None:
    """Convert consecutive operator tokens into a single opchain token"""
    i = 0
    while i < len(tokens):
        token = tokens[i]
        recurse_into(token, make_chain_operators)
        
        if is_binary_op(token) or (i == 0 and is_prefix_op(token)):
            j = 1
            while i+j < len(tokens) and is_prefix_op(tokens[i+j]):
                j += 1
            if j > 1:
                # Note about distinguishing operators that could be unary or binary:
                # basically if it could be both, treat it as binary unless its the first token (which means it must be unary)
                if is_binary_op(token) and i > 0 and not isinstance(tokens[i-1], t1.Semicolon): # semicolon is a special case that ends the previous expression
                    prefix_chain = PrefixChain(Span(tokens[i+1].loc.start, tokens[i+j-1].loc.stop), tokens[i+1:i+j])
                    tokens[i:i+j] = [BinopChain(Span(tokens[i].loc.start, tokens[i+j-1].loc.stop), token, prefix_chain)]
                else:
                    tokens[i:i+j] = [PrefixChain(Span(tokens[i].loc.start, tokens[i+j-1].loc.stop), tokens[i:i+j])]
        i += 1


def make_broadcast_operators(tokens: list[t1.Token]) -> None:
    """Convert any . operator next to a binary operator or opchain into a broadcast operator"""
    i = 0
    while i < len(tokens):
        token = tokens[i]
        recurse_into(token, make_broadcast_operators)
        
        if isinstance(token, t1.Operator) and token.symbol == '.':
            if len(tokens) > i+1 and (is_binary_op(tokens[i+1]) or is_prefix_op(tokens[i+1]) or isinstance(tokens[i+1], BinopChain)):
                tokens[i:i+2] = [BroadcastOp(Span(token.loc.start, tokens[i+1].loc.stop), tokens[i+1])]
        i += 1


def make_combined_assignment_operators(tokens: list[t1.Token]) -> None:
    """Convert any combined assignment operators into a single token"""
    i = 0
    while i < len(tokens):
        token = tokens[i]
        recurse_into(token, make_combined_assignment_operators)
        
        if is_binary_op(token) or isinstance(token, BinopChain) or isinstance(token, BroadcastOp):
            if len(tokens) > i+1 and isinstance(tokens[i+1], t1.Operator) and tokens[i+1].symbol == '=':
                tokens[i:i+2] = [CombinedAssignmentOp(Span(token.loc.start, tokens[i+1].loc.stop), tokens[i+1])]
        i += 1


def is_stop_keyword(token: t1.Token, stop: set[str]) -> bool:
    return isinstance(token, t1.Keyword) and token.name in stop


def is_atom(token: t1.Token) -> bool:
    """Tokens that can appear where an atom/expression operand is expected."""
    return type(token) in atom_tokens


def is_prefix_like(token: t1.Token) -> bool:
    """Prefix operators or bundled prefix chains."""
    return is_prefix_op(token) or isinstance(token, PrefixChain)


def is_infix_like(token: t1.Token) -> bool:
    """Binary/infix operators or bundled infix operators."""
    return is_binary_op(token) or type(token) in other_infix_tokens


def collect_chunk(tokens: list[t1.Token], start: int, *, stop_keywords: set[str]) -> tuple[list[t1.Token], int]:
    i = start
    out: list[t1.Token] = []

    while i < len(tokens) and not is_stop_keyword(tokens[i], stop_keywords) and is_prefix_like(tokens[i]):
        out.append(tokens[i])
        i += 1

    if i >= len(tokens) or is_stop_keyword(tokens[i], stop_keywords) or isinstance(tokens[i], t1.Semicolon):
        return out, i

    token = tokens[i]
    if isinstance(token, t1.Keyword):
        atom, i = collect_keyword_atom(tokens, i, stop_keywords=stop_keywords)
        out.append(atom)
        return out, i

    if not is_atom(token):
        raise ValueError(f"expected primary token, got {token=}")
    out.append(token)
    return out, i + 1


def collect_expr(tokens: list[t1.Token], start: int, *, stop_keywords: set[str]) -> tuple[list[t1.Token], int]:
    i = start
    out: list[t1.Token] = []

    chunk, i = collect_chunk(tokens, i, stop_keywords=stop_keywords)
    out.extend(chunk)

    while (
        i < len(tokens)
        and not is_stop_keyword(tokens[i], stop_keywords)
        and not isinstance(tokens[i], t1.Semicolon)
        and is_infix_like(tokens[i])
    ):
        out.append(tokens[i])
        i += 1
        chunk, i = collect_chunk(tokens, i, stop_keywords=stop_keywords)
        out.extend(chunk)

    return out, i


def collect_flow_arm(tokens: list[t1.Token], start: int, *, stop_keywords: set[str]) -> tuple[FlowArm, int]:
    kw = tokens[start]
    if not isinstance(kw, t1.Keyword):
        raise ValueError(f"expected flow keyword, got {kw=}")
    i = start + 1

    if kw.name == "do":
        pre, i = collect_expr(tokens, i, stop_keywords=stop_keywords | {"loop"})
        if i >= len(tokens) or not (isinstance(tokens[i], t1.Keyword) and tokens[i].name == "loop"):
            raise ValueError("`do` must be followed by `loop`")
        loop_kw = tokens[i]
        i += 1
        cond, i = collect_expr(tokens, i, stop_keywords=stop_keywords | {"do"})
        parts: list[t1.Keyword | list[t1.Token]] = [kw, pre, loop_kw, cond]
        if i < len(tokens) and isinstance(tokens[i], t1.Keyword) and tokens[i].name == "do":
            do2 = tokens[i]
            i += 1
            post, i = collect_expr(tokens, i, stop_keywords=stop_keywords)
            parts.extend([do2, post])
        return FlowArm(Span(kw.loc.start, tokens[i - 1].loc.stop), parts), i

    if kw.name in {"if", "match"}:
        cond, i = collect_expr(tokens, i, stop_keywords=stop_keywords)
        clause, i = collect_expr(tokens, i, stop_keywords=stop_keywords)
        parts: list[t1.Keyword | list[t1.Token]] = [kw, cond, clause]
        return FlowArm(Span(kw.loc.start, tokens[i - 1].loc.stop), parts), i

    if kw.name == "loop":
        cond, i = collect_expr(tokens, i, stop_keywords=stop_keywords)
        clause, i = collect_expr(tokens, i, stop_keywords=stop_keywords)
        parts: list[t1.Keyword | list[t1.Token]] = [kw, cond, clause]
        return FlowArm(Span(kw.loc.start, tokens[i - 1].loc.stop), parts), i

    raise ValueError(f"unexpected flow keyword {kw.name!r}")


def collect_flow(tokens: list[t1.Token], start: int, *, stop_keywords: set[str]) -> tuple[Flow, int]:
    i = start
    arms: list[FlowArm] = []
    default: list[t1.Token] | None = None

    while True:
        arm, i = collect_flow_arm(tokens, i, stop_keywords=stop_keywords | {"else"})
        arms.append(arm)

        if i >= len(tokens) or not (isinstance(tokens[i], t1.Keyword) and tokens[i].name == "else"):
            break
        i += 1  # consume else (not stored; `else` is structural)

        if i < len(tokens) and isinstance(tokens[i], t1.Keyword) and tokens[i].name in {"if", "loop", "match", "do"}:
            continue

        default, i = collect_expr(tokens, i, stop_keywords=stop_keywords | {"else"})
        break

    if default is not None:
        end = arms[-1].loc.stop if not default else default[-1].loc.stop
    else:
        end = arms[-1].loc.stop
    return Flow(Span(tokens[start].loc.start, end), arms, default), i


def collect_keyword_atom(tokens: list[t1.Token], start: int, *, stop_keywords: set[str]) -> tuple[t1.Token, int]:
    kw = tokens[start]
    if not isinstance(kw, t1.Keyword):
        raise ValueError(f"expected keyword, got {kw=}")

    if kw.name in {"if", "loop", "match", "do"}:
        return collect_flow(tokens, start, stop_keywords=stop_keywords)

    i = start + 1
    if kw.name in {"return", "yield"}:
        if i >= len(tokens) or is_stop_keyword(tokens[i], stop_keywords) or isinstance(tokens[i], t1.Semicolon):
            return KeywordExpr(kw.loc, [kw]), i
        expr, i = collect_expr(tokens, i, stop_keywords=stop_keywords)
        return KeywordExpr(Span(kw.loc.start, expr[-1].loc.stop), [kw, expr]), i

    if kw.name in {"break", "continue"}:
        if i < len(tokens) and isinstance(tokens[i], t1.Hashtag):
            ht = tokens[i]
            return KeywordExpr(Span(kw.loc.start, ht.loc.stop), [kw, [ht]]), i + 1
        return KeywordExpr(kw.loc, [kw]), i

    if kw.name in {"let", "const", "local_const", "overload_only"}:
        expr, i = collect_expr(tokens, i, stop_keywords=stop_keywords)
        return KeywordExpr(Span(kw.loc.start, expr[-1].loc.stop), [kw, expr]), i

    if kw.name == "import":
        first, i = collect_expr(tokens, i, stop_keywords=stop_keywords | {"from"})
        if i < len(tokens) and isinstance(tokens[i], t1.Keyword) and tokens[i].name == "from":
            from_kw = tokens[i]
            i += 1
            second, i = collect_expr(tokens, i, stop_keywords=stop_keywords)
            return KeywordExpr(Span(kw.loc.start, second[-1].loc.stop), [kw, first, from_kw, second]), i
        return KeywordExpr(Span(kw.loc.start, first[-1].loc.stop), [kw, first]), i

    if kw.name == "from":
        first, i = collect_expr(tokens, i, stop_keywords=stop_keywords | {"import"})
        if i >= len(tokens) or not (isinstance(tokens[i], t1.Keyword) and tokens[i].name == "import"):
            raise ValueError("`from` must be followed by `import`")
        import_kw = tokens[i]
        i += 1
        second, i = collect_expr(tokens, i, stop_keywords=stop_keywords)
        return KeywordExpr(Span(kw.loc.start, second[-1].loc.stop), [kw, first, import_kw, second]), i

    return KeywordExpr(kw.loc, [kw]), i


def bundle_keyword_exprs(tokens: list[t1.Token]) -> None:

    i = 0
    while i < len(tokens):
        token = tokens[i]
        recurse_into(token, bundle_keyword_exprs)

        if isinstance(token, t1.Keyword) and token.name not in {"else"}:
            atom, j = collect_keyword_atom(tokens, i, stop_keywords={"else"})
            tokens[i:j] = [atom]
            i += 1
            continue

        i += 1


def postok(srcfile: SrcFile) -> list[t1.Token]:
    """apply postprocessing steps to the tokens"""
    tokens = t1.tokenize(srcfile)
    postok_inner(tokens)
    return tokens


def postok_inner(tokens: list[t1.Token]) -> None:
    """apply postprocessing steps to the tokens"""
    # remove whitespace and insert juxtapose tokens
    invert_whitespace(tokens)

    # combine not with comparison operators into a single token
    make_inverted_comparisons(tokens)
    # combine operator chains into a single operator token
    make_chain_operators(tokens)
    # convert any . operator next to a binary operator or opchain (e.g. .+ .^/-) into a broadcast operator
    make_broadcast_operators(tokens)
    # convert any combined assignment operators (e.g. += -= etc.) into a single token
    make_combined_assignment_operators(tokens)

    # bundle up keyword expressions and flows into single atom tokens
    bundle_keyword_exprs(tokens)
    invert_whitespace(tokens)  # insert juxtapose between any keyword/flow expressions that got added


def test():
    from ..myargparse import ArgumentParser
    from .t0 import tokens_to_report # mildly hacky but Token2's duck-type to what this expects
    from pathlib import Path
    parser = ArgumentParser()
    parser.add_argument('path', type=Path, required=True, help='path to file to tokenize')
    args = parser.parse_args()
    path: Path = args.path
    src = path.read_text()
    srcfile = SrcFile(path, src)
    try:
        tokens = postok(srcfile)
    except ReportException as e:
        print(e.report)
        exit(1)
    
    print(tokens_to_report(tokens, srcfile))

if __name__ == '__main__':
    test()