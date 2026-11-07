"""The editor grammar reads parenthesized function types in a signature."""
import pytest

from tests.test_core_editor_grammar import grammar, scope_of  # noqa: F401


@pytest.mark.parametrize(('line', 'text', 'scope'), [
    ('apply=(f:(int64:>int64) v:int64):>int64=>f(v)', 'apply', 'entity.name.function'),
    ('apply=(f:(int64:>int64) v:int64):>int64=>f(v)', ':>', 'keyword.operator.type.returns'),
    ('apply=(f:(int64:>int64) v:int64):>int64=>f(v)', 'int64', 'support.type.builtin'),
    ('apply=(f:((x:int64 y:int64):>int64)):>int64=>f(1 2)', 'apply', 'entity.name.function'),
    ('apply=(f:((g:(int64:>int64) y:int64):>int64)):>int64=>f(@h 2)', 'apply', 'entity.name.function'),
    ('let f:(int64:>int64)=@g', ':>', 'keyword.operator.type.returns'),
    ('let n:int<(>=? 0)>=1', 'int', 'support.type.builtin'),
])
def test_function_type_scopes(grammar, line, text, scope):  # noqa: F811
    assert any(s.startswith(scope) for s in scope_of(grammar, line, text))
