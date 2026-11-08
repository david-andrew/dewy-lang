"""Selected propagation keeps the same scope, type and return obligations."""
import subprocess
import pytest
from tests.support import compiler  # noqa: F401

PREFIX='A:type=type of error & []\nB:type=type of error & []\nsource=(x:int64):>int64|A|B=>if x =? 0 A[] else if x =? 1 B[] else x\n'
@pytest.mark.parametrize(('body', 'message'), [
    ('bad=(x:int64):>int64=>{let value=source(x) or_throw<A>\nif value is? B return 0\nvalue}\n', 'or_throw cannot propagate A'),
    ('bad=(x:int64):>int64|A=>source(x) or_throw<A>\n', 'B'),
    ('bad=(x:int64):>int64|A|B=>source(x) or_throw<int64>\n', 'not an exception or none'),
    ('let value=source(0) or_throw<A>\n', 'requires an enclosing function'),
    ('bad=()=>{let value:int64?=none\nvalue or_throw<none>}\n', 'cannot propagate none'),
])
def test_batch4_throw_rejections(compiler, tmp_path, body, message):
    source=tmp_path/'rejected.dewy'
    source.write_text(PREFIX+body)
    result=subprocess.run([compiler, 'check', source], capture_output=True, text=True, timeout=60)
    assert result.returncode != 0
    assert message in result.stderr, result.stderr
