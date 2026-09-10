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
    assert isinstance(outer, hir.ShortCircuit) and outer.op == 'and'      # `x is? int64 and payload =? 1`
    assert isinstance(outer.left, hir.TypeTest) and outer.left.test_type == 'int64' and not outer.left.negated
    assert outer.right.pos_args[0].type == 'int64'                        # the payload read


def test_not_equal_is_absent_or_different() -> None:
    checked = _check('let x:int64|none = 1\nif x not=? 1 { let a = 0 }')
    outer = _conditions(checked)[0]
    assert isinstance(outer, hir.ShortCircuit) and outer.op == 'or'       # `x isnt? int64 or payload not=? 1`
    assert isinstance(outer.left, hir.TypeTest) and outer.left.negated


def test_equality_narrows_the_binding_like_a_type_test() -> None:
    _check('let f = ():>int64|none => 3\nlet x = f()\nif x =? 3 { let y:int64 = x }')
    _check('let f = ():>int64|none => 3\nlet x = f()\nif x not=? 3 { let a = 0 } else { let y:int64 = x }')
    _check('let g = ():>int64|string => 3\nlet s = g()\nif s =? "a" { let t:string = s } else { let a = 0 }')
    with pytest.raises(TypeCheckError, match='type mismatch'):
        _check('let f = ():>int64|none => 3\nlet x = f()\nif x =? 3 { let a = 0 } else { let y:int64 = x }')


def test_none_is_a_tag_test() -> None:
    checked = _check('let x:int64|none = 1\nif x =? none { let a = 0 }\nif x not=? none { let b = 0 }')
    first, second = _conditions(checked)[:2]
    assert isinstance(first, hir.TypeTest) and first.test_type == 'none' and not first.negated
    assert isinstance(second, hir.TypeTest) and second.test_type == 'none' and second.negated


def test_an_element_compares_through_a_hidden_binding() -> None:
    checked = _check('let xs:array<int64|none> = [1 none]\nif xs[0] =? 1 { let a = 0 }')
    outer = _conditions(checked)[0]
    assert isinstance(outer, hir.Block) and not outer.scoped
    declaration, right, flow = outer.items
    assert isinstance(declaration, hir.Declare) and declaration.name.startswith('__dewy_eq_')
    assert isinstance(right, hir.Declare) and isinstance(right.expr, hir.Integer)
    assert isinstance(flow, hir.ShortCircuit)


def test_string_members_compare_as_strings() -> None:
    _check('let y:int64|string = "a"\nif y =? "a" { let a = 0 }\nif y =? 1 { let b = 0 }')


def test_an_ambiguous_member_is_rejected() -> None:
    with pytest.raises(TypeCheckError, match='ambiguous equality against a union'):
        _check('let x:int64|uint64 = 1\nif x =? 1 { let a = 0 }')


def test_two_cells_compare_after_both_operands_are_captured() -> None:
    checked = _check('let x:int64|none = 1\nlet y:int64|none = 1\nif x =? y { let a = 0 }')
    outer = _conditions(checked)[0]
    assert isinstance(outer, hir.Block)
    left, right, comparison = outer.items
    assert isinstance(left, hir.Declare) and left.expr.name == 'x'
    assert isinstance(right, hir.Declare) and right.expr.name == 'y'
    assert isinstance(comparison, hir.ShortCircuit)


def test_unions_with_different_alternatives_still_require_narrowing() -> None:
    with pytest.raises(NotImplementedYet, match='unions with different alternatives'):
        _check('let x:int64|none = 1\nlet y:string|none = "a"\nif x =? y { let a = 0 }')


def test_none_returning_operand_keeps_its_effects(tmp_path):
    import subprocess
    from dewy.backend.udewy import codegen
    from udewy.cache import cache_artifact
    from udewy.frontend import EntryPointOptions, entry_point

    source = SrcFile(None, '''let calls:int64=0
let next=():>none=>{calls+=1 return none}
let same=(x:int64|none):>bool=>x =? next()
let main=():>int64=>{let answer=same(none) return if answer and calls=?1 42 else 0}
''')
    output = tmp_path / 'none_effects.udewy'
    output.write_text(codegen(source))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, timeout=30, check=False)
    assert result.returncode == 42, result.stderr


def test_standalone_none_crosses_a_parameter_and_local_binding(tmp_path):
    import subprocess
    from dewy.backend.udewy import codegen
    from udewy.cache import cache_artifact
    from udewy.frontend import EntryPointOptions, entry_point

    source = SrcFile(None, '''let keep=(value:none):>none=>value
let main=():>int64=>{let value:none=keep(none) return if value is? none 42 else 0}
''')
    output = tmp_path / 'none_value.udewy'
    output.write_text(codegen(source))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, timeout=30, check=False)
    assert result.returncode == 42, result.stderr
