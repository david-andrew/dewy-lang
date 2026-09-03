"""`x =? v` on a tagged cell compares the tag and then the payload; `x =? none` is a tag test."""
import pytest

from dewy.reporting import SrcFile
from dewy.semantic import check, hir
from dewy.semantic.errors import NotImplementedYet, TypeCheckError


def _check(source: str) -> hir.AST:
    return check.typecheck_and_resolve(SrcFile(None, source))


def _conditions(node: object) -> list[hir.AST]:
    found: list[hir.AST] = []

    def walk(value: object) -> None:
        if isinstance(value, hir.IfArm):
            found.append(value.condition)
        if hasattr(value, '__dataclass_fields__'):
            for name in value.__dataclass_fields__:
                walk(getattr(value, name))
        elif isinstance(value, (list, tuple)):
            for item in value:
                walk(item)

    walk(node)
    return found


def test_a_binding_compares_by_tag_then_payload() -> None:
    checked = _check('let x:int64|none = 1\nif x =? 1 { let a = 0 }')
    outer = _conditions(checked)[0]
    assert isinstance(outer, hir.Flow)                      # `if x is? int64 { payload =? 1 } else false`
    test = outer.arms[0].condition
    assert isinstance(test, hir.TypeTest) and test.test_type == 'int64' and not test.negated
    assert isinstance(outer.default, hir.Bool) and outer.default.value is False


def test_not_equal_defaults_to_true_when_the_member_is_absent() -> None:
    checked = _check('let x:int64|none = 1\nif x not=? 1 { let a = 0 }')
    outer = _conditions(checked)[0]
    assert isinstance(outer, hir.Flow) and isinstance(outer.default, hir.Bool) and outer.default.value is True


def test_none_is_a_tag_test() -> None:
    checked = _check('let x:int64|none = 1\nif x =? none { let a = 0 }\nif x not=? none { let b = 0 }')
    first, second = _conditions(checked)[:2]
    assert isinstance(first, hir.TypeTest) and first.test_type == 'none' and not first.negated
    assert isinstance(second, hir.TypeTest) and second.test_type == 'none' and second.negated


def test_an_element_compares_through_a_hidden_binding() -> None:
    checked = _check('let xs:array<int64|none> = [1 none]\nif xs[0] =? 1 { let a = 0 }')
    outer = _conditions(checked)[0]
    assert isinstance(outer, hir.Block) and not outer.scoped
    declaration, flow = outer.items
    assert isinstance(declaration, hir.Declare) and declaration.name.startswith('__dewy_eq_')
    assert isinstance(flow, hir.Flow)


def test_string_members_compare_as_strings() -> None:
    _check('let y:int64|string = "a"\nif y =? "a" { let a = 0 }\nif y =? 1 { let b = 0 }')


def test_an_ambiguous_member_is_rejected() -> None:
    with pytest.raises(TypeCheckError, match='ambiguous equality against a union'):
        _check('let x:int64|uint64 = 1\nif x =? 1 { let a = 0 }')


def test_two_cells_are_not_compared_yet() -> None:
    with pytest.raises(NotImplementedYet, match='equality between two union values'):
        _check('let x:int64|none = 1\nlet y:int64|none = 1\nif x =? y { let a = 0 }')
