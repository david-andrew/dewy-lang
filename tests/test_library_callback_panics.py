"""Library callbacks preserve the module boundary of runtime checks."""
import pytest

from tests.support import compiler  # noqa: F401
from tests.test_library_preconditions import run


@pytest.mark.parametrize('operation', ['min_by', 'max_by'])
def test_external_panicking_key_requires_opt_in(compiler, tmp_path, operation):
    (tmp_path / 'helper.dewy').write_text('''key=(x:int64):>int64=>{
    $runtime_checks
    return [1 2][x]
}
''')
    result = run(compiler, tmp_path, f'''from p"helper.dewy" import key
let values:array<int64>=[1 2]
printl(values.{operation}(@key))
''', 'check')
    assert result.returncode != 0, result.stderr
    assert 'may panic' in result.stderr, result.stderr
