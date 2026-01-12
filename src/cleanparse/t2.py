"""
Post processing steps on tokens to prepare them for expression parsiing
"""
from typing import Callable, Literal
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
class TypeParamJuxtapose(Juxtapose): ...

@dataclass
class SemicolonJuxtapose(Juxtapose): ...

@dataclass
class InvertedComparisonOp(t1.InedibleToken):
    op: Literal['=?', '>?', '<?', '>=?', '<=?', 'in?', 'is?', 'isnt?']

@dataclass
class BroadcastOp(t1.InedibleToken):
    op: t1.Operator

@dataclass
class CombinedAssignmentOp(t1.InedibleToken):
    op: t1.Operator|BroadcastOp
    # special case of = operator to the right of another operator


@dataclass
class OpFn(t1.InedibleToken):
    op: t1.Operator|BroadcastOp|CombinedAssignmentOp

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
    t1.Metatag,
    t1.Integer,
    t1.Semicolon,
    OpFn,
    KeywordExpr,
    Flow,
}


# not including t1.Operator
other_infix_tokens: set[type[t1.Token]] = { 
    Juxtapose,
    RangeJuxtapose,
    EllipsisJuxtapose,
    TypeParamJuxtapose,
    SemicolonJuxtapose,
    CombinedAssignmentOp,
    InvertedComparisonOp,
    # BroadcastOp is handled separately because whether or not it is infix depends on the operator being broadcast over
}


binary_ops: set[str] = {
    '+', '-', '*', '/', '//', '%', '^',
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
    'as', 'in', 'transmute', 'of',
}
prefix_ops: set[str] = {
    '~', 'not', '`',
    '+', '-', '*', '/', '//',
}

postfix_ops: set[str] = {
    '`', '?',
}

# simple checks for it t1.Operator
def is_binary_op(token: t1.Token) -> bool:
    return isinstance(token, t1.Operator) and token.symbol in binary_ops or type(token) in other_infix_tokens or (isinstance(token, BroadcastOp) and is_binary_op(token.op))
def is_prefix_op(token: t1.Token) -> bool:
    return isinstance(token, t1.Operator) and token.symbol in prefix_ops or (isinstance(token, BroadcastOp) and is_prefix_op(token.op))
def is_postfix_op(token: t1.Token) -> bool:
    return isinstance(token, t1.Operator) and token.symbol in postfix_ops or (isinstance(token, BroadcastOp) and is_postfix_op(token.op)) # really only `?` could be broadcast

# check for special atoms that get known juxtapose tokens 
def is_dotdot(token: t1.Token) -> bool:
    return isinstance(token, t1.Identifier) and token.name == '..'
def is_dotdotdot(token: t1.Token) -> bool:
    return isinstance(token, t1.Identifier) and token.name == '...'
def is_typeparam(token: t1.Token) -> bool:
    return isinstance(token, t1.Block) and token.delims == '<>'

def get_jux_type(left: t1.Token, right: t1.Token, prev: t1.Token|None) -> type[Juxtapose]:
    """For certain tokens, we alredy know which juxtapose (precedence level) they should have"""
    if is_dotdot(left) or is_dotdot(right):
        return RangeJuxtapose
    elif is_dotdotdot(left) or is_dotdotdot(right):
        return EllipsisJuxtapose
    elif is_typeparam(right) or (is_typeparam(left) and not isinstance(prev, TypeParamJuxtapose)):
        return TypeParamJuxtapose
    elif isinstance(right, t1.Semicolon):
        return SemicolonJuxtapose
    return Juxtapose


def recurse_into(token: t1.Token, func: Callable[[list[t1.Token]], None]) -> None:
    """
    Helper to recursively apply a function to the inner tokens of a token (if it has any)
    It is expected that `func` will call `recurse_into` with itself as the callable.
    """
    if isinstance(token, (t1.Block, t1.ParametricEscape, t1.BasedArray)):
        func(token.inner)
    elif isinstance(token, t1.IString):
        for child in token.content:
            recurse_into(child, func)
    elif isinstance(token, (KeywordExpr, FlowArm)):
        for part in token.parts:
            if isinstance(part, list):
                func(part)
    elif isinstance(token, Flow):
        func(token.arms)
        if token.default is not None:
            func(token.default)

    # else no inner tokens. TODO: would be nice if we could error if there were any unhandled cases with inner tokens...


# TODO: since we're determining juxtapose placement based on token spans rather than if there were no whitespace tokens between,
#       consider having previous tokenization steps just not insert any whitespace tokens in the first place
#       (this would involve adjustments to t0.tokenize, probably some annotation to make whitespace and comment tokens get thrown away)
def remove_whitespace(tokens: list[t1.Token]) -> None:
    """Remove whitespace tokens from the tokens list (recursively)"""
    tokens[:] = [token for token in tokens if not isinstance(token, t1.Whitespace)]
    for token in tokens:
        recurse_into(token, remove_whitespace)


def insert_juxtapose(tokens: list[t1.Token]) -> None:
    """
    Insert juxtapose tokens between adjacent (atom) tokens if their spans touch (which indicates there was no whitespace between them)
    TODO: this is vaguely inefficient with all the insertions. If this is a performance bottleneck, consider some type of e.g. heap or rope or etc. data structure
          alternatively, just do 1 pass to find where juxtaposes go, and then insert them all at once.

    Note: this function is idempotent, so it can be called multiple times, e.g. before andafter grouping up tokens to the token list
    """
    i = 0
    while i < len(tokens):
        # recursively handle inserting juxtaposes for blocks
        recurse_into(tokens[i], insert_juxtapose)

        # insert juxtapose if adjacent (atom) tokens' spans touch
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



def make_broadcast_operators(tokens: list[t1.Token]) -> None:
    """Convert any . operator next to a unary or binary operator into a broadcast operator"""
    i = 0
    while i < len(tokens):
        token = tokens[i]
        recurse_into(token, make_broadcast_operators)
        
        if isinstance(token, t1.Operator) and token.symbol == '.':
            if len(tokens) > i+1 and (is_binary_op(tokens[i+1]) or is_prefix_op(tokens[i+1])):
                tokens[i:i+2] = [BroadcastOp(Span(token.loc.start, tokens[i+1].loc.stop), tokens[i+1])]
        i += 1


def make_combined_assignment_operators(tokens: list[t1.Token]) -> None:
    """Convert any combined assignment operators into a single token"""
    i = 0
    while i < len(tokens):
        token = tokens[i]
        recurse_into(token, make_combined_assignment_operators)
        
        if is_binary_op(token) or isinstance(token, BroadcastOp):
            if len(tokens) > i+1 and isinstance(tokens[i+1], t1.Operator) and tokens[i+1].symbol == '=':
                tokens[i:i+2] = [CombinedAssignmentOp(Span(token.loc.start, tokens[i+1].loc.stop), token)]
        i += 1


def make_op_functions(tokens: list[t1.Token]) -> None:
    """convert (op) into an identifier token for that operator"""
    i = 0
    while i < len(tokens):
        token = tokens[i]
        recurse_into(token, make_op_functions)
        
        if (isinstance(token, t1.Block) 
            and token.delims == '()' 
            and len(token.inner) == 1 
            and isinstance(token.inner[0], (t1.Operator, BroadcastOp, CombinedAssignmentOp))
        ):
            tokens[i] = OpFn(token.loc, token.inner[0])
        i += 1

def is_stop_keyword(token: t1.Token, stop: set[str]) -> bool:
    """
    Return True if `token` is a keyword whose name is in `stop`.

    `stop` is a set of keyword names that act as delimiters for `collect_expr`/`collect_chunk`:
    when collecting an expression slice, we stop *before* these keywords so the caller can
    interpret them structurally (e.g. `else`, `from`, `import`, `loop`, `do`).
    """
    return isinstance(token, t1.Keyword) and token.name in stop



def collect_chunk(tokens: list[t1.Token], start: int, *, stop_keywords: set[str]) -> tuple[list[t1.Token], int]:
    """
    Collect a single expression chunk starting at `start`. A chunk is basically an atom surrounded by prefix and postfix operators.

    Chunk grammar (informal):
      chunk := prefix_like* atom postfix_like*

    Returns:
      (chunk_tokens, next_index)
    """
    i = start
    out: list[t1.Token] = []

    while i < len(tokens) and not is_stop_keyword(tokens[i], stop_keywords) and is_prefix_op(tokens[i]):
        out.append(tokens[i])
        i += 1

    if i >= len(tokens) or is_stop_keyword(tokens[i], stop_keywords) or isinstance(tokens[i], t1.Semicolon):
        return out, i

    token = tokens[i]
    if isinstance(token, t1.Keyword):
        atom, i = collect_keyword_atom(tokens, i, stop_keywords=stop_keywords)
        out.append(atom)
        while i < len(tokens) and not is_stop_keyword(tokens[i], stop_keywords) and is_postfix_op(tokens[i]):
            out.append(tokens[i])
            i += 1
        return out, i

    if type(token) not in atom_tokens or isinstance(token, t1.Semicolon):
        # TODO: this should be a full error report
        raise ValueError(f"expected primary token, got {token=}")
    out.append(token)
    i += 1
    while i < len(tokens) and not is_stop_keyword(tokens[i], stop_keywords) and is_postfix_op(tokens[i]):
        out.append(tokens[i])
        i += 1
    return out, i


def collect_expr(tokens: list[t1.Token], start: int, *, stop_keywords: set[str]) -> tuple[list[t1.Token], int]:
    """
    Collect a single expression chain starting at `start`.

    This does not parse precedence; it only groups tokens into a contiguous chain that
    is directly consumable by a later expression parser (Pratt, etc.).

    Chain grammar (informal):
      expr := chunk (infix_op chunk)*

    Stops before:
    - any keyword in `stop_keywords`
    - a semicolon token

    Returns:
      (expr_tokens, next_index)
    """
    i = start
    out: list[t1.Token] = []

    chunk, i = collect_chunk(tokens, i, stop_keywords=stop_keywords)
    if not chunk:
        return out, i
    out.extend(chunk)

    while i < len(tokens) and not is_stop_keyword(tokens[i], stop_keywords) and not isinstance(tokens[i], t1.Semicolon):
        if not is_binary_op(tokens[i]):
            break
        out.append(tokens[i])
        i += 1
        chunk, i = collect_chunk(tokens, i, stop_keywords=stop_keywords)
        out.extend(chunk)

    return out, i


def collect_flow_arm(tokens: list[t1.Token], start: int, *, stop_keywords: set[str]) -> tuple[FlowArm, int]:
    """
    Collect a single flow arm (if/loop/match/do-loop) into a `FlowArm`.

    The result is a mostly-unstructured "syntax skeleton":
      FlowArm.parts := [Keyword, expr, Keyword, expr, ...]

    Notes:
    - This function consumes the arm's starting keyword at `tokens[start]`.
    - It does not include `else` (that delimiter is handled by `collect_flow`).
    - Each `expr` entry is a `list[t1.Token]` produced by `collect_expr`.
    """
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
    """
    Collect an entire flow expression (if/loop/match/do-loop with optional else chains).

    Structure:
    - `Flow.arms` is a list of `FlowArm` tokens (each arm retains its own keywords).
    - `Flow.default` is either None or a token list for the final default expression.

    `else` is treated as structural and is consumed but not stored.
    """
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
    """
    Collect a keyword-driven expression into a single atom token.

    Returns:
      (atom_token, next_index)

    The returned atom token is either:
    - `Flow` for flow keywords (`if`, `loop`, `match`, `do`)
    - `KeywordExpr` for other keywords

    `KeywordExpr.parts` is a "syntax skeleton" alternating between structural keywords
    and collected expression token lists, e.g.:
      - `return <expr>`              -> [return_kw, expr]
      - `from <expr> import <expr>`  -> [from_kw, expr, import_kw, expr]
    """
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
        if i < len(tokens) and isinstance(tokens[i], t1.Metatag):
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
    """
    Walk `tokens` and replace any keyword-started expression with a single atom token.

    This is a post-tokenization bundling pass. It is recursive: blocks and interpolated
    strings are traversed, so keyword expressions are bundled at all nesting levels.

    `else` is not bundled as a standalone atom; it is only consumed structurally by
    `collect_flow`.
    """

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
    remove_whitespace(tokens)
    insert_juxtapose(tokens)

    # combine not with comparison operators into a single token
    make_inverted_comparisons(tokens)
    # convert any . operator next to a binary operator (e.g. .+ .^/-) into a broadcast operator
    make_broadcast_operators(tokens)
    # convert any combined assignment operators (e.g. += -= etc.) into a single token
    make_combined_assignment_operators(tokens)
    # convert any (op) into an identifier token for that operator (e.g. (+=) -> +=)
    make_op_functions(tokens)

    # bundle up keyword expressions and flows into single atom tokens
    bundle_keyword_exprs(tokens)
    insert_juxtapose(tokens)  # insert juxtapose between any keyword/flow expressions that got added
                              # can't skip first insert_juxtapose because they are necessary operators 
                              # to allow bundle_keyword_exprs to work properly


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