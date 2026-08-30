"""`[loop …]` collects the values a loop body expresses; `.casefold` is the Unicode full case folding."""
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic import check, hir, ty
from dewy.semantic.errors import NotImplementedYet, TypeCheckError, UserError
from udewy.frontend import entry_point

from test_cleanparse_udewy_e2e import x86_64_toolchain_available

needs_toolchain = pytest.mark.skipif(not x86_64_toolchain_available(), reason='needs the x86_64 toolchain')


def _compile(source: str) -> str:
    return codegen(SrcFile(None, source))


def _main_items(body: str) -> list[hir.AST]:
    root = check.typecheck_and_resolve(SrcFile(None, 'let main = ():>int64 => {\n' + body + '\n    return 0\n}\n'))
    main = next(item for item in root.items if isinstance(item, hir.Declare) and item.name == 'main')
    return main.expr.body.items


# ------------------------------------------------------------ the shape

def test_a_capture_declares_and_fills_its_array_before_the_statement() -> None:
    items = _main_items('    let squares = [loop i in [1..5) i * i]')
    hoisted = items[0]
    assert isinstance(hoisted, hir.Block) and not hoisted.scoped
    declaration, loop, statement = hoisted.items
    assert isinstance(declaration, hir.Declare) and declaration.name.startswith('__dewy_capture_')
    assert isinstance(loop, hir.Flow) and isinstance(loop.arms[0], hir.LoopArm)
    body = loop.arms[0].body
    push = body.items[-1] if isinstance(body, hir.Block) else body   # a bare body is the push itself
    assert isinstance(push, hir.FunctionCall) and push.func.name.startswith('_capture_push') and isinstance(push.pos_args[0], hir.Place)
    assert isinstance(statement, hir.Declare) and statement.name == 'squares'
    assert isinstance(statement.expr.type, ty.ArrayType) and statement.expr.type.length is None


def test_a_conditional_body_filters_and_nested_loops_flatten() -> None:
    emitted = _compile('let main = ():>int64 => {\n    let evens = [loop n in [0..10) if n % 2 =? 0 n]\n    let pairs = [loop a in [1..3) loop b in [1..3) a * 10 + b]\n    return evens.length + pairs.length\n}\n')
    assert emitted.count('_capture_push__int64(') == 2


def test_the_element_type_comes_from_the_values_or_the_annotation() -> None:
    items = _main_items('    let words:array<string> = [loop i in [0..3) "x"]')
    assert isinstance(items[0].items[0].annotation, ty.ArrayType)
    with pytest.raises(TypeCheckError, match='loop capture values differ in type'):
        _main_items('    let mixed = [loop i in [0..3) if i =? 0 "x" else i]')


def test_a_loop_that_expresses_nothing_is_an_error() -> None:
    with pytest.raises(UserError, match='this loop expresses no value to capture'):
        _main_items('    let nothing = [loop i in [0..3) { let j = i }]')


def test_a_capture_needs_a_block_body() -> None:
    with pytest.raises(NotImplementedYet, match='loop capture outside a block body'):
        _compile('let f = ():>array<int64> => [loop i in [0..3) i]\n')


def test_sets_and_dictionaries_capture_too() -> None:
    emitted = _compile(
        'let main = ():>int64 => {\n'
        '    let odds = set[loop n in [0..10) if n % 2 =? 1 n]\n'
        '    let lengths = [loop w in ["a" "bb"] w -> w.length]\n'
        '    let named:dict<string int64> = [loop i in [0..3) "{i}" -> i]\n'
        '    return odds.length + lengths.length + named.length\n'
        '}\n'
    )
    assert '_capture_add__int64(' in emitted
    assert '_capture_store__string_int64(' in emitted
    with pytest.raises(UserError, match='a set capture takes members, not pairs'):
        _main_items('    let s = set[loop i in [0..3) i -> i]')
    with pytest.raises(UserError, match='a capture mixes pairs and values'):
        _main_items('    let d = [loop i in [0..3) if i =? 0 i -> i else i]')


# ------------------------------------------------------------ casefold

def test_casefold_is_a_string_method_backed_by_the_table() -> None:
    emitted = _compile('let main = ():>int64 => { return "Straße".casefold.length }\n')
    assert '_string_casefold(' in emitted and 'casefold.bin' in emitted


@needs_toolchain
def test_captures_and_casefold_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]) -> None:
    source = (
        'whitespace = set[" " "\\t" "\\n" "\\r"]\n'
        'controls = [loop i in [0x0..0x20) if chr(i) not in? whitespace chr(i)]\n'
        'printl(controls.length)\n'
        'let main = ():>int64 => {\n'
        '    printl([loop i in [1..5) i * i])\n'
        '    printl([loop w in ["Straße" "ǅ" "HELLO" "ﬁ" "İ"] w.casefold])\n'
        '    printl([loop n in [0..10) if n % 2 =? 0 n])\n'
        '    printl([loop a in [1..3) loop b in [1..3) a * 10 + b])\n'
        '    printl(set[loop i in 0..5 i % 3])\n'
        '    printl([loop w in ["a" "bb"] w -> w.length])\n'
        '    return 0\n'
        '}\n'
    )
    udewy_path = tmp_path / 'capture.udewy'
    udewy_path.write_text(codegen(SrcFile(None, source)))
    monkeypatch.chdir(tmp_path)
    assert entry_point(udewy_path, []) == 0
    out, _ = capfd.readouterr()
    assert out.splitlines() == [
        '29',
        '[1 4 9 16]',
        '["strasse" "ǆ" "hello" "fi" "i̇"]',
        '[0 2 4 6 8]',
        '[11 12 21 22]',
        'set[0 1 2]',
        '["a" -> 1 "bb" -> 2]',
    ]
