"""Error values: `type of error`, error alternatives in unions, and `or_throw`."""
import pytest

from dewy.reporting import SrcFile
from dewy.semantic import check, hir, ty
from dewy.semantic.errors import NotImplementedYet, UserError

ERRORS = 'let NotFound:type = type of error\nlet Invalid:type = type of error\n'


def _declared(source: str) -> dict[str, hir.Declare]:
    root = check.typecheck_and_resolve(SrcFile(None, source))
    return {item.name: item for item in root.items if isinstance(item, hir.Declare)}


def test_minted_error_types_are_nominal_subtypes_of_error() -> None:
    declared = _declared(ERRORS)
    assert declared['NotFound'].expr.value == 'NotFound'
    system = ty.TypeSystem()
    assert system.is_subtype('NotFound', 'error') and system.is_subtype('NotFound', ty.EXCEPTION_TYPE)
    assert not system.is_subtype('NotFound', 'Invalid') and not system.is_subtype('NotFound', 'undefined')


def test_the_error_value_is_spelled_with_the_type_name() -> None:
    declared = _declared(ERRORS + 'let e = NotFound\nlet r:int64|NotFound = NotFound\n')
    assert isinstance(declared['e'].expr, hir.ErrorValue) and declared['e'].expr.type == 'NotFound'


def test_only_errors_and_objects_can_be_minted_for_now() -> None:
    with pytest.raises(NotImplementedYet, match='mintable so far: error types, and object types'):
        _declared('let Weird:type = type of int64\n')


def test_is_error_narrows_the_whole_family() -> None:
    _declared(ERRORS + '''
let lookup = (id:int64):>int64|NotFound|Invalid => if id >? 0 id else NotFound
let safe = (id:int64):>int64 => {
    let r = lookup(id)
    if r is? error { return 0 }
    return r
}
''')


def test_or_throw_propagates_and_narrows() -> None:
    declared = _declared(ERRORS + '''
let lookup = (id:int64):>int64|NotFound|undefined => if id >? 0 id else NotFound
let twice = (id:int64):>int64|NotFound|Invalid|undefined => {
    let first = lookup(id) or_throw
    return first * 2
}
''')
    body = declared['twice'].expr.body
    first = next(item for item in body.items if isinstance(item, hir.Declare) and item.name == 'first')
    assert isinstance(first.expr, hir.OrThrow)
    assert first.expr.type == 'int64'
    assert set(first.expr.exception_type.items) == {'NotFound', 'undefined'}


def test_or_throw_needs_an_exception_alternative_and_a_matching_result_type() -> None:
    with pytest.raises(UserError, match='nothing to propagate'):
        _declared('let f = (x:int64):>int64|undefined => x or_throw\n')
    with pytest.raises(UserError, match='does not return `NotFound`'):
        _declared(ERRORS + 'let lookup = (id:int64):>int64|NotFound => id\nlet f = (id:int64):>int64|undefined => lookup(id) or_throw\n')
    with pytest.raises(UserError, match='always returns'):
        _declared(ERRORS + 'let f = (e:NotFound|undefined):>int64|NotFound|undefined => { let v = e or_throw return 0 }\n')
    with pytest.raises(UserError, match='no declared result type'):
        _declared(ERRORS + 'let lookup = (id:int64):>int64|NotFound => id\nlet f = (id:int64) => lookup(id) or_throw\n')


def test_arithmetic_checks_against_a_union_result_type() -> None:
    _declared(ERRORS + 'let f = (id:int64):>int64|NotFound => id * 2\n')
