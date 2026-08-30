"""Union-typed container members: string-literal unions are string handles; `T | undefined` elements are owned cells."""
import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic import ty
from dewy.semantic.errors import TypeCheckError


def _compile(source: str) -> str:
    return codegen(SrcFile(None, source))


def test_string_literal_unions_are_string_handles() -> None:
    assert ty.string_valued(ty.union(ty.StringLiteralType('0b'), ty.StringLiteralType('0t')))
    assert ty.enum_members(ty.union(ty.StringLiteralType('a'), ty.StringLiteralType('b'))) is None   # not a tag word
    assert ty.enum_members(ty.union(ty.IntegerLiteralType(1), ty.StringLiteralType('fast'))) is not None   # mixed stays one
    emitted = _compile(
        "const P:type = '0b' | '0t'\n"
        'let main = ():>int64 => {\n'
        "    let d:dict<P int64> = ['0b' -> 2]\n"
        "    let keys:array<P> = ['0b' '0t']\n"
        '    return d.length + keys.length\n'
        '}\n'
    )
    assert '_dict' in emitted or 'd:' in emitted   # checks and lowers


def test_optional_elements_are_arena_cells() -> None:
    emitted = _compile(
        'let main = ():>int64 => {\n'
        '    let xs:array<int64|undefined> = [1 undefined]\n'
        "    let d:dict<string int64|undefined> = ['a' -> undefined]\n"
        "    d['b'] = 2\n"
        '    return xs.length + d.length\n'
        '}\n'
    )
    assert 'optional_cell' in emitted   # stores allocate the cells the container owns


def test_aggregate_union_members_stay_unsupported() -> None:
    with pytest.raises(TypeCheckError, match='unsupported array element type'):
        _compile('let main = ():>int64 => {\n    let xs:array<array<int64>|undefined> = []\n    return 0\n}\n')
