"""Exact consumers may discard high words only when those words cannot matter."""
import subprocess

import pytest

from tests.support import compiler


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True])
@pytest.mark.parametrize('expression', [
    '(x*x-y*y)%256',
    '(x*x-y*y)&255',
    '((x*x-y*y)//3)%256',
])
def test_exact_low_word(compiler, tmp_path, release, expression):
    values = [(2**63-1, 0), (0, 2**63-1), (-2**63, 2**63-1), (71, -93)]
    source = tmp_path / 'low_word.dewy'
    source.write_text('f=(x:int64 y:int64):>int64=>' + expression + '\n'
                      'main=():>void=>{\n' +
                      '\n'.join(f' printl(f({x} {y}))' for x, y in values) + '\n}\n')
    result = subprocess.run([compiler, *(['--release'] if release else []), source],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    expected = [eval(expression, {'__builtins__': {}}, {'x': x, 'y': y}) for x, y in values]
    assert list(map(int, result.stdout.split())) == expected
