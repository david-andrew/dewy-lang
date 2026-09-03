"""`xs.sort(key=… reverse=…)`: keyed sorts, and function literals that take their parameter types from the expected function type."""
import pytest

from dewy.reporting import SrcFile
from dewy.semantic import check, hir, ty
from dewy.semantic.errors import TypeCheckError, UserError


def _check(source: str) -> hir.AST:
    return check.typecheck_and_resolve(SrcFile(None, source))


HIT = 'let Hit = type of any & [length:uint64 name:string]\n'


def _function_literals(node: object) -> list[hir.FunctionLiteral]:
    found: list[hir.FunctionLiteral] = []

    def walk(value: object) -> None:
        if isinstance(value, hir.FunctionLiteral):
            found.append(value)
        if hasattr(value, '__dataclass_fields__'):
            for name in value.__dataclass_fields__:
                walk(getattr(value, name))
        elif isinstance(value, (list, tuple)):
            for item in value:
                walk(item)
        elif isinstance(value, dict):
            for item in value.values():
                walk(item)

    walk(node)
    return found


def test_an_unannotated_key_parameter_takes_the_element_type() -> None:
    checked = _check(HIT + 'let hits:array<Hit> = []\nhits.sort(key=(h) => h.length)')
    key = next(literal for literal in _function_literals(checked) if literal.pos_or_kw_args and literal.pos_or_kw_args[0].name == 'h')
    assert isinstance(key.pos_or_kw_args[0].type, ty.ObjectType)
    assert key.rettype == 'uint64'


def test_contextual_parameter_types_apply_to_any_function_typed_parameter() -> None:
    checked = _check(
        'let keyfn:type = (x:int64):>int64\n'
        'let apply = (xs:array<int64 length>?0> f:keyfn):>int64 => f(xs[0])\n'
        'let xs:array<int64 length>?0> = [3 1 2]\n'
        'let doubled = apply(xs (x) => x * 2)\n'
    )
    literal = next(literal for literal in _function_literals(checked) if literal.pos_or_kw_args and literal.pos_or_kw_args[0].name == 'x')
    assert literal.pos_or_kw_args[0].type == 'int64'


def test_an_annotated_parameter_keeps_its_annotation() -> None:
    with pytest.raises(TypeCheckError, match='type mismatch'):
        _check(HIT + 'let hits:array<Hit> = []\nhits.sort(key=(h:string):>int64 => h.length)')


def test_sorting_non_integer_elements_needs_a_key() -> None:
    with pytest.raises(UserError, match='sorting these elements needs a key') as caught:
        _check(HIT + 'let hits:array<Hit> = []\nhits.sort')
    assert '`Hit` elements have no order of their own' in str(caught.value)
    _check('let xs:array<int64> = [3 1]\nxs.sort\nxs.sort(reverse=true)\nxs.sort(key=(x) => 0 - x)')


def test_a_key_must_return_a_fixed_width_integer() -> None:
    with pytest.raises(UserError, match='a sort key must return a fixed-width integer') as caught:
        _check(HIT + 'let hits:array<Hit> = []\nhits.sort(key=(h) => h.name)')
    assert 'this key returns `string`' in str(caught.value)


def test_keys_of_every_fixed_width_are_accepted() -> None:
    _check(HIT + 'let hits:array<Hit> = []\nhits.sort(key=(h) => (h.length transmute int64) transmute int8 reverse=true)')
    _check('let words:array<string> = []\nwords.sort(key=(w) => w.length)')
    _check('let maybes:array<int64|none> = []\nmaybes.sort(key=(m):>int64 => if m is? int64 m else (-1))')


def test_a_named_function_is_passed_with_at() -> None:
    _check(HIT + 'let by_length = (h:Hit):>uint64 => h.length\nlet hits:array<Hit> = []\nhits.sort(key=@by_length)')
    with pytest.raises(TypeCheckError, match='needs arguments'):
        _check(HIT + 'let by_length = (h:Hit):>uint64 => h.length\nlet hits:array<Hit> = []\nhits.sort(key=by_length)')


def test_sort_keeps_the_length_facts() -> None:
    _check(HIT + 'let hits:array<Hit> = [Hit[length=1 name="a"]]\nhits.sort(key=(h) => h.length)\nlet first = hits[0]')
