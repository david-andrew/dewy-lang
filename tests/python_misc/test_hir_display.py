"""Tests for HIR tree repr and Dewy pretty-printer."""

import pytest

from dewy.reporting import Span, SrcFile
from dewy.semantic import check, hir, ty
from dewy.semantic.hir_display import hir_to_dewy, hir_to_tree_str, type_to_dewy

LOC = Span(0, 0)


@pytest.mark.parametrize('value', [
    'quote"\u0301 slash\\\u0301 {\u0301missing}',
    ''.join(map(chr, range(32))),
    'é😀\r\n',
])
def test_literal_rendering_round_trips(value):
    literal = hir_to_dewy(hir.String(LOC, 'string', value))
    annotation = type_to_dewy(ty.StringLiteralType(value))
    root = check.typecheck_and_resolve(SrcFile(None, f'let text:{annotation} = {literal}'))
    declaration = next(item for item in root.items if isinstance(item, hir.Declare))
    assert declaration.annotation == ty.StringLiteralType(value)
    assert isinstance(declaration.expr, hir.String)
    assert declaration.expr.content == value


def test_interpolation_rendering_escapes_only_literal_parts():
    prefix = 'literal {missing} "\0'
    suffix = '"\\ end'
    node = hir.InterpolatedString(LOC, 'string', [
        hir.String(LOC, 'string', prefix),
        hir.ExpressedIdentifier(LOC, 'int64', 'x'),
        hir.String(LOC, 'string', suffix),
    ])
    source = f'let x:int64 = 42\nlet text = {hir_to_dewy(node)}'
    root = check.typecheck_and_resolve(SrcFile(None, source))
    declaration = next(item for item in root.items if isinstance(item, hir.Declare) and item.name == 'text')
    assert isinstance(declaration.expr, hir.InterpolatedString)
    assert declaration.expr.parts[0].content == prefix
    assert declaration.expr.parts[-1].content == suffix
    assert isinstance(declaration.expr.parts[1], hir.ExpressedIdentifier)
    assert declaration.expr.parts[1].name == 'x'


def _int(n: int, typ: str = 'int') -> hir.Integer:
    return hir.Integer(LOC, typ, '0d', n)


def _id(name: str, typ: str = 'untyped') -> hir.ExpressedIdentifier:
    return hir.ExpressedIdentifier(LOC, typ, name)


def _call(func: str, *args: hir.AST, typ: str = 'untyped') -> hir.FunctionCall:
    return hir.FunctionCall(LOC, typ, _id(func, 'function'), list(args), {})


def test_tree_declare_and_call_edges():
    expr = _call('__add__', _int(1), _id('x', 'int'), typ='int')
    node = hir.Declare(LOC, 'void', 'let', 'y', None, expr)
    tree = hir_to_tree_str(node)
    assert 'Declare(let y)' in tree
    assert '└── expr: BinOp(+)' in tree
    assert 'left: Integer(1)' in tree
    assert 'right: ExpressedIdentifier(x)' in tree
    assert '├──' in tree
    assert '__add__' not in tree
    # inferred AST.type is not dumped on every node
    assert ': int' not in tree
    assert ': void' not in tree


def test_tree_value_cast_shows_target():
    node = hir.ValueCast(LOC, 'float', _int(1))
    assert hir_to_tree_str(node) == 'ValueCast(as float)\n└── expr: Integer(1)'


def test_tree_declare_annotation():
    node = hir.Declare(LOC, 'void', 'const', 'z', 'int | float', _int(1))
    assert 'Declare(const z:int | float)' in hir_to_tree_str(node)
    assert hir_to_dewy(node) == 'const z:int | float = 1'


def test_dewy_declare_and_literals():
    node = hir.Declare(LOC, 'void', 'let', 'y', None, _int(42))
    assert hir_to_dewy(node) == 'let y = 42'


def test_dewy_binop_infix():
    node = _call('__add__', _int(1), _int(2), typ='int')
    assert hir_to_dewy(node) == '1 + 2'


def test_dewy_precedence_parens():
    # (1 + 2) * 3
    add = _call('__add__', _int(1), _int(2), typ='int')
    mul = _call('__mul__', add, _int(3), typ='int')
    assert hir_to_dewy(mul) == '(1 + 2) * 3'

    # 1 + 2 * 3  — no parens around mul
    mul2 = _call('__mul__', _int(2), _int(3), typ='int')
    add2 = _call('__add__', _int(1), mul2, typ='int')
    assert hir_to_dewy(add2) == '1 + 2 * 3'


def test_dewy_function_call_args():
    node = hir.FunctionCall(
        LOC, 'untyped',
        _id('f', 'function'),
        [_int(1), _id('x')],
        {'flag': hir.Bool(LOC, 'bool', True)},
    )
    assert hir_to_dewy(node) == 'f(1 x flag=true)'


def test_dewy_value_cast():
    node = hir.ValueCast(LOC, 'float', _int(1))
    assert hir_to_dewy(node) == '1 as float'


def test_dewy_assign_and_transmute():
    assignment = hir.Assign(LOC, 'void', _id('x', 'int'), '+=', _int(1))
    transmute = hir.Transmute(LOC, 'int', hir.Bool(LOC, 'bool', True))

    assert hir_to_tree_str(assignment).startswith('Assign(+=)')
    assert hir_to_dewy(assignment) == 'x += 1'
    assert hir_to_tree_str(transmute) == 'Transmute(int)\n└── expr: Bool(True)'
    assert hir_to_dewy(transmute) == 'true transmute int'


def test_dewy_prefix_comparison_and_void():
    prefix = _call('__not__', hir.Bool(LOC, 'bool', True), typ='bool')
    comparison = _call('__ne__', _int(1), _int(2), typ='bool')
    returned = hir.Return(LOC, 'never', hir.Void(LOC, 'void'))

    assert hir_to_dewy(prefix) == 'not true'
    assert hir_to_dewy(comparison) == '1 not=? 2'
    assert hir_to_dewy(returned) == 'return void'


def test_dewy_function_literal():
    body = _int(0)
    node = hir.FunctionLiteral(
        LOC, 'function',
        [hir.Param('a', 'int'), hir.Param('b', 'int')],
        [],
        None,
        'int',
        body,
    )
    assert hir_to_dewy(node) == '(a:int b:int):>int => 0'


def test_dewy_declare_function_block_indent():
    body = hir.Block(LOC, 'void', [hir.Return(LOC, 'void', _int(42))], scoped=True)
    fn = hir.FunctionLiteral(LOC, 'function', [], [], None, 'int', body)
    node = hir.Declare(LOC, 'void', 'let', 'fn', None, fn)
    assert hir_to_dewy(node) == 'let fn = ():>int => {\n    return 42\n}'
    assert hir_to_dewy(node, indent=2) == 'let fn = ():>int => {\n  return 42\n}'


def test_dewy_width_wraps_long_call():
    args = [_id(f'arg{i}') for i in range(8)]
    node = hir.FunctionCall(LOC, 'untyped', _id('f', 'function'), args, {})
    wide = hir_to_dewy(node, width=120)
    narrow = hir_to_dewy(node, width=20)
    assert '\n' not in wide
    assert '\n' in narrow
    assert 'f(' in narrow


def test_ast_repr_str_hooks():
    node = _call('__add__', _int(1), _int(2), typ='int')
    assert 'BinOp(+)' in repr(node)
    assert str(node) == '1 + 2'


def test_dewy_overload():
    f0 = hir.FunctionLiteral(LOC, 'function', [], [], None, 'int', _int(42))
    f1 = hir.FunctionLiteral(
        LOC, 'function',
        [hir.Param('a', 'int')], [], None, 'int',
        _id('a', 'int'),
    )
    node = hir.OverloadedFunction(LOC, 'multifunction', [f0, f1])
    tree = hir_to_tree_str(node)
    assert 'OverloadedFunction(2)' in tree
    assert 'alternates[0]: FunctionLiteral(:>int)' in tree
    assert 'alternates[1]: FunctionLiteral(:>int)' in tree
    # `=>` binds looser than `&`, so each alternate needs parens
    assert hir_to_dewy(node) == '(():>int => 42) & ((a:int):>int => a)'
