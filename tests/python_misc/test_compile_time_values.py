"""Compile-time-only values where a runtime value is needed: types and
functions materialize as their spelling; a string is tested for membership
in a literal union at runtime; `chr` and `set"…"`/`set(values)`."""
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic import check, hir, ty
from dewy.semantic.errors import TypeCheckError, UserError
from udewy.frontend import entry_point

from test_cleanparse_udewy_e2e import x86_64_toolchain_available

needs_toolchain = pytest.mark.skipif(not x86_64_toolchain_available(), reason='needs the x86_64 toolchain')
PREFIX = "let BasePrefix:type = '0b' | '0t' | '0x'\n"


def _compile(source: str) -> str:
    return codegen(SrcFile(None, source))


def _main_body(source: str) -> hir.Block:
    root = check.typecheck_and_resolve(SrcFile(None, source), include_prelude=False)
    main = next(item for item in root.items if isinstance(item, hir.Declare) and item.name == 'main')
    return main.expr.body


# ------------------------------------------------------------ spellings

def test_a_type_value_is_its_spelling_where_a_value_is_needed() -> None:
    body = _main_body(PREFIX + 'let main = ():>int64 => {\n    let a = "{BasePrefix}"\n    let b:string = BasePrefix as string\n    return 0\n}\n')
    a, b = (item.expr for item in body.items if isinstance(item, hir.Declare))
    assert isinstance(a, hir.InterpolatedString) and isinstance(a.parts[0], hir.String) and a.parts[0].content == "'0b' | '0t' | '0x'"
    while isinstance(b, hir.RepresentationCast):
        b = b.expr   # the `let`'s annotation materializes the literal
    assert isinstance(b, hir.String) and b.content == "'0b' | '0t' | '0x'"
    emitted = _compile(PREFIX + 'let main = ():>int64 => { printl(BasePrefix)  return 0 }\n')
    assert 'print__string' in emitted   # the generic's value parameter received the spelling


def test_functions_and_overload_sets_spell_their_types() -> None:
    body = _main_body('let f = (a:int64):>int64 => a\nlet g = @f & @f\nlet main = ():>int64 => {\n    let a = "{@f}"\n    let b = "{@g}"\n    return 0\n}\n')
    a, b = (item.expr for item in body.items if isinstance(item, hir.Declare))
    assert a.parts[0].content == '<(a:int64):>int64>'
    assert b.parts[0].content == '<(a:int64):>int64> & <(a:int64):>int64>'


# ------------------------------------------------------------ membership tests

def test_a_string_is_tested_for_membership_in_a_literal_union_at_runtime() -> None:
    body = _main_body(PREFIX + 'let main = ():>int64 => {\n    let src = "0x1f"\n    let p = src[..2)\n    if p is? BasePrefix { let q = p }\n    return 0\n}\n')
    flow = next(item for item in body.items if isinstance(item, hir.Flow))
    condition = flow.arms[0].condition
    assert isinstance(condition, hir.TypeTest)   # not decided: a two-grapheme string may be a member
    narrowed = flow.arms[0].body.items[0].expr
    assert isinstance(narrowed.type, ty.TypeOr) and all(isinstance(m, ty.StringLiteralType) for m in narrowed.type.items)


def test_a_string_that_cannot_be_a_member_is_decided() -> None:
    body = _main_body(PREFIX + 'let main = ():>int64 => {\n    let src = "0x1f"\n    let p = src[..2]\n    if p is? BasePrefix { let q = p }\n    return 0\n}\n')
    assert not any(isinstance(item, hir.Flow) for item in body.items)   # three graphemes: never a two-grapheme member


# ------------------------------------------------------------ chr and set

def test_chr_takes_a_proven_scalar() -> None:
    emitted = _compile('let main = ():>int64 => {\n    loop i in [0x41..0x44) { print(chr(i)) }\n    return 0\n}\n')
    assert 'chr(' in emitted
    with pytest.raises(UserError, match='cannot prove refinement'):
        _compile('let main = (n:int64):>int64 => {\n    print(chr(n))\n    return 0\n}\n')


def test_set_from_a_string_or_an_array() -> None:
    emitted = _compile('let main = ():>int64 => {\n    let digits = set"0123"\n    let odd = set([1 3])\n    return digits.length + odd.length\n}\n')
    assert '_set_of_graphemes(' in emitted and '_set_of_array__int64(' in emitted
    with pytest.raises(TypeCheckError, match='`set` takes a string or an array'):
        _compile('let main = ():>int64 => { let s = set(5)  return 0 }\n')


# ------------------------------------------------------------ the output

@needs_toolchain
def test_materialized_values_print(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]) -> None:
    source = PREFIX + (
        'let f = (a:int64):>int64 => a\n'
        'let main = ():>int64 => {\n'
        '    printl(BasePrefix)\n'
        '    printl"{@f}"\n'
        '    let src = "0x1f"\n'
        '    if src[..2) is? BasePrefix { printl"prefix" } else { printl"no" }\n'
        '    if "zz" isnt? BasePrefix { printl"zz not" }\n'
        '    printl"{chr(65)}{chr(0xE9)}{chr(0x4E2D)}{chr(0x1F600)}"\n'
        '    printl(set"0120")\n'
        '    printl(set([3 1 3]))\n'
        '    return 0\n'
        '}\n'
    )
    udewy_path = tmp_path / 'values.udewy'
    udewy_path.write_text(codegen(SrcFile(None, source)))
    monkeypatch.chdir(tmp_path)
    assert entry_point(udewy_path, []) == 0
    out, _ = capfd.readouterr()
    assert out.splitlines() == [
        "'0b' | '0t' | '0x'",
        '<(a:int64):>int64>',
        'prefix',
        'zz not',
        'Aé中😀',
        'set["0" "1" "2"]',
        'set[3 1]',
    ]
