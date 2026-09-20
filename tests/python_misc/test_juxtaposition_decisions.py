"""Settled adjacency rules do not guess a callable/numeric precedence."""
import pytest

from dewy.parser import p0, t1
from dewy.reporting import SrcFile
from dewy.semantic import check
from dewy.semantic.errors import UserError


@pytest.mark.parametrize('source', ['x 2', 'x 2.5', '(x)2', '(x)2.5'])
def test_right_number_is_separate(source):
    parsed = p0.parse(SrcFile(None, source))
    assert len(parsed.inner) == 2
    assert isinstance(parsed.inner[1], p0.Atom)
    assert isinstance(parsed.inner[1].item, (t1.Integer, t1.Real))


@pytest.mark.parametrize('body', ['f(2)', 'f(2)^2', '(f)(2)'])
def test_callable_numeric_union_requires_explicit_operation(body):
    source = f'let probe=(f:((int64):>int64)|int64):>int64=>{body}'
    with pytest.raises(UserError, match='ambiguous juxtaposition') as failure:
        check.typecheck_and_resolve(SrcFile(None, source))
    message = str(failure.value)
    assert 'A |> B' in message and 'B <| A' in message and 'A * B' in message
    assert 'parenthes' not in message
