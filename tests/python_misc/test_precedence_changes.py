"""The 2026-08-31 precedence moves (dewy/semantic/precedence.md)."""
import re

import pytest

from dewy.parser import p0, t1, t2
from dewy.reporting import SrcFile
from dewy.semantic import check, hir
from dewy.semantic.errors import UserError


def _expression(source: str) -> p0.AST:
    block, _ = check._parse_module(SrcFile(None, source + '\n'))
    return block.inner[0]


def _shape(node: p0.AST) -> str:
    if isinstance(node, p0.BinOp):
        symbol = node.op.symbol if isinstance(node.op, t1.Operator) else 'jux' if 'Juxtapose' in type(node.op).__name__ else type(node.op).__name__
        return f'({_shape(node.left)} {symbol} {_shape(node.right)})'
    if isinstance(node, p0.Prefix):
        return f'({node.op.symbol} {_shape(node.item)})'   # type: ignore[union-attr]
    if isinstance(node, p0.Postfix):
        return f'({_shape(node.item)} {node.op.symbol})'   # type: ignore[union-attr]
    if isinstance(node, p0.Block):
        return '[' + ' '.join(_shape(item) for item in node.inner) + ']' if node.kind == '[]' else f'({" ".join(_shape(item) for item in node.inner)})'
    if isinstance(node, p0.Atom):
        text = getattr(node.item, 'name', None) or getattr(node.item, 'symbol', None)
        if text is None:
            number = re.search(r'<Number: (.*?)>', str(node.item))
            text = number.group(1) if number else str(node.item)
        return text
    return type(node).__name__


def test_word_not_sits_below_the_comparisons_and_tilde_stays_high() -> None:
    assert _shape(_expression('not x =? y')) == '(not (x =? y))'
    assert _shape(_expression('not a and b')) == '((not a) and b)'
    assert _shape(_expression('~flags =? 0')) == '((~ flags) =? 0)'
    inverted = _expression('x not =? y')
    assert isinstance(inverted, p0.BinOp) and isinstance(inverted.op, t2.InvertedComparisonOp)


def test_type_of_is_a_prefix_above_intersection() -> None:
    assert _shape(_expression('Name = type of Token & [text:string]')) == '(Name = ((type of Token) & [(text : string)]))'
    assert _shape(_expression('Name = type of any')) == '(Name = (type of any))'
    # a generic bound keeps the loose infix `of`
    assert _shape(_expression('f = <T of A & B>(x:T):>T => x')).startswith('(f = ((')
    bound = _expression('T of A & B')
    assert _shape(bound) == '(T of (A & B))'


def test_or_throw_takes_the_whole_left_expression() -> None:
    assert _shape(_expression('f(x) * 2 or_throw')) == '(((f jux (x)) * 2) or_throw)'
    assert _shape(_expression('f(x) or_throw * 2')) == '(((f jux (x)) or_throw) * 2)'
    assert _shape(_expression('bytes as string | none or_throw')) == '((bytes as (string | none)) or_throw)'


def _check(source: str) -> hir.Block:
    return check.typecheck_and_resolve(SrcFile(None, source))


def test_comparison_chains_desugar_to_and_with_one_evaluation() -> None:
    root = _check(
        'let count:int64 = 0\n'
        'let mid = (v:int64):>int64 => { count += 1\n return v }\n'
        'let main = ():>int64 => {\n'
        '    let x = 5\n'
        '    let ok = 0 <? x <? 10\n'
        '    let once = 0 <=? mid(x) <? 6\n'
        '    return 0\n'
        '}'
    )
    main = root.items[-1].expr.body   # type: ignore[union-attr]
    once = next(item for item in main.items if isinstance(item, hir.Block) and any(isinstance(inner, hir.Declare) and inner.name == 'once' for inner in item.items))
    hoisted = [item for item in once.items if isinstance(item, hir.Declare) and item.name.startswith('__dewy_chain_')]
    assert len(hoisted) == 1 and isinstance(hoisted[0].expr, hir.FunctionCall)


def test_a_chain_reads_one_way_and_tests_do_not_chain() -> None:
    with pytest.raises(UserError, match='changes direction'):
        _check('let x = 5\nlet bad = 0 <? x >? 10')
    with pytest.raises(UserError, match='does not chain'):
        _check('let x = 5\nlet bad = x is? int64 <? 10')
    with pytest.raises(UserError, match='does not chain'):
        _check('let x = 5\nlet bad = 0 <? x not =? 3')
    _check('let x = 5\nlet ok = 0 <? x =? 5 <=? 5')


def test_a_computed_interior_operand_is_hoisted_at_module_level_too() -> None:
    root = _check('let f = (v:int64):>int64 => v\nlet ok = 0 <? f(3) <? 10')
    # the hoisted local and the declaration share an unscoped block
    statement = next(item for item in root.items if isinstance(item, hir.Block) and not item.scoped)
    hoisted = [item for item in statement.items if isinstance(item, hir.Declare) and item.name.startswith('__dewy_chain_')]
    assert len(hoisted) == 1 and isinstance(hoisted[0].expr, hir.FunctionCall)
