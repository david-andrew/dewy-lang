"""Union-typed container members: string-literal unions are string handles; `T | none` elements are owned cells."""
import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic import ty
from dewy.semantic.errors import TypeCheckError, UserError


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
        '    let xs:array<int64|none> = [1 none]\n'
        "    let d:dict<string int64|none> = ['a' -> none]\n"
        "    d['b'] = 2\n"
        '    return xs.length + d.length\n'
        '}\n'
    )
    assert 'optional_cell' in emitted   # stores allocate the cells the container owns


def test_aggregate_union_members_stay_unsupported() -> None:
    with pytest.raises(TypeCheckError, match='unsupported array element type'):
        _compile('let main = ():>int64 => {\n    let xs:array<array<int64>|none> = []\n    return 0\n}\n')


TOKENS = (
    'let Number:type = [text:string value:int64]\n'
    'let Name:type = [text:string]\n'
    'let Token:type = Number | Name\n'
)


def test_object_unions_are_owned_tagged_cells() -> None:
    emitted = _compile(TOKENS + 'let main = ():>int64 => {\n    let ts:array<Token> = [Number("1" 1)]\n    ts.push(Name("x"))\n    let copy:array<Token> = ts\n    return copy.length\n}\n')
    assert 'union_cell' in emitted and 'union_copy' in emitted   # stores allocate cells; copies clone them


def test_object_unions_print_member_by_member() -> None:
    emitted = _compile(TOKENS + 'let main = ():>int64 => {\n    let ts:array<Token> = [Number("1" 1)]\n    printl(ts)\n    let t:Token = ts[0]\n    printl"{t}"\n    return 0\n}\n')
    assert '__dewy_object_string_' in emitted   # each object member has its literal-syntax conversion


def test_union_valued_fields_that_are_not_names_are_hoisted() -> None:
    emitted = _compile(TOKENS + 'let main = ():>int64 => {\n    let ts:array<Token> = [Number("1" 1)]\n    printl"{ts[0]}"\n    return 0\n}\n')
    assert '__dewy_field_' in emitted   # `ts[0]` evaluated once into a hidden local, then tested and read
    with pytest.raises(UserError, match='must be a name here'):
        _compile(TOKENS + 'let f = (ts:array<Token>):>string => "{ts[0]}"\n')   # no statement to hoist before


def test_owned_cell_arrays_release_their_cells() -> None:
    emitted = _compile('let main = ():>int64 => {\n    let xs:array<string|none> = []\n    xs.push"a"\n    return xs.length\n}\n')
    assert 'cell_string_owner' in emitted and '_arena_release(' in emitted   # the payload string by its owner, then the cell
