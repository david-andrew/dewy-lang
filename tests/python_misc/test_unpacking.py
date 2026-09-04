"""`[a b] = value` / `let [a b] = value`: objects unpack by field name; arrays, dictionaries, and sets by position."""
import pytest

from dewy.reporting import SrcFile
from dewy.semantic import check, hir
from dewy.semantic.errors import UserError


def _check(source: str) -> hir.AST:
    return check.typecheck_and_resolve(SrcFile(None, source))


def _declared_names(node: hir.AST) -> list[str]:
    assert isinstance(node, hir.Block)
    return [item.name for item in node.items if isinstance(item, hir.Declare)]


def test_a_bare_unpack_declares_new_names_and_assigns_existing_ones() -> None:
    checked = _check('let pair = [x=1 y=2]\nlet x:int64 = 0\n[y x] = pair\nx = 5\n')
    names = _declared_names(checked)
    assert names.count('x') == 1 and names.count('y') == 1          # `x` assigned, `y` declared
    assigns = [item for item in checked.items if isinstance(item, hir.Assign)]
    assert [assign.target.name for assign in assigns] == ['x', 'x']


def test_objects_unpack_by_name_in_any_order_and_any_subset() -> None:
    checked = _check('let hit = [length=3 name="a"]\nlet [name length] = hit\nlet n:string = name\nlet l:int64 = length\n')
    assert 'name' in _declared_names(checked)
    _check('let hit = [length=3 name="a"]\nlet [length] = hit\n')
    with pytest.raises(UserError, match='no field `z` to unpack') as caught:
        _check('let [z] = [x=1 y=2]\n')
    assert 'the value has fields `x`, `y`' in str(caught.value)
    with pytest.raises(UserError, match='objects unpack by field name'):
        _check('let [[a b]] = [x=[1 2] y=2]\n')
    with pytest.raises(UserError, match='objects unpack by field name'):
        _check('let [x _] = [x=1 y=2]\n')


def test_a_non_binding_source_is_read_once() -> None:
    checked = _check('let f = ():>[x:int64 y:int64] => [x=1 y=2]\nlet [x y] = f()\n')
    names = _declared_names(checked)
    assert any(name.startswith('__dewy_unpack_') for name in names) and 'x' in names and 'y' in names
    checked = _check('let pair = [x=1 y=2]\nlet [x y] = pair\n')
    assert not any(name.startswith('__dewy_unpack_') for name in _declared_names(checked))   # a binding is read directly


def test_arrays_unpack_by_element_when_the_length_is_known() -> None:
    _check('let xs:array<int64 length=3> = [1 2 3]\nlet [a _ c] = xs\nlet s:int64 = a + c\n')
    _check('let xs:array<int64> = []\nxs.push(1)\nlet [a] = xs\n')          # the exact length is a fact
    _check('let grid = [[1 2] [3 4]]\nlet [[a b] [c d]] = grid\nlet s:int64 = a + b + c + d\n')
    with pytest.raises(UserError, match='cannot prove how many elements this array has'):
        _check('let f = ():>array<int64> => [1 2]\nlet ys = f()\nlet [a b] = ys\n')
    with pytest.raises(UserError, match='unpacking must name every element'):
        _check('let [a b] = [1 2 3]\n')


def test_dictionaries_unpack_entries_as_pairs_and_sets_their_members() -> None:
    _check("let d = ['a' -> 1  'b' -> 2]\nlet [[k1 v1] [_ v2]] = d\nlet k:string = k1\nlet v:int64 = v1 + v2\n")
    _check('let s = set[1 2]\nlet [a b] = s\nlet t:int64 = a + b\n')
    with pytest.raises(UserError, match='a dictionary entry is a key and a value'):
        _check("let d = ['a' -> 1]\nlet [k] = d\n")
    with pytest.raises(UserError, match='unpacking must name every entry'):
        _check("let d = ['a' -> 1]\nlet [[k v] [k2 v2]] = d\n")
    with pytest.raises(UserError, match='cannot prove how many entries this dictionary has'):
        _check('let d:dict<int64 int64> = []\nd[1] = 2\nlet [[k v]] = d\n')
    with pytest.raises(UserError, match='unpacking must name every member'):
        _check('let s = set[1 2]\nlet [a] = s\n')


def test_targets_must_be_names_and_values_unpackable() -> None:
    with pytest.raises(UserError, match='unpack targets must be names'):
        _check('let [a 3] = [1 2]\n')
    with pytest.raises(UserError, match='this value cannot be unpacked'):
        _check('let [a b] = 3\n')
