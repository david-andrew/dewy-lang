"""An early length guard covers masked indices only while its array stays immutable."""
import subprocess

import pytest
from tests.support import compiler  # noqa: F401


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True])
@pytest.mark.parametrize('change', ['', 'xs.truncate(1)'])
def test_guarded_mask_index(compiler, tmp_path, release, change):
    source = tmp_path / 'main.dewy'
    source.write_text('''kernel=(xs:array<int64> count:int64):>int64=>{
    if xs.length <? 4 return 0
    CHANGE
    let sum:int64=0
    loop i in [0..count) {sum+=xs[i%4]}
    return sum
}
printl(kernel([2 3] 8))
printl(kernel([2 3 5 7] 8))
'''.replace('CHANGE', change))
    binary = tmp_path / 'main'
    built = subprocess.run([compiler, 'build', source, '--ir', '-o', binary,
                            *(['--release'] if release else [])], capture_output=True, text=True)
    assert built.returncode == 0, built.stderr
    result = subprocess.run([binary], capture_output=True, text=True)
    if change:
        assert result.returncode != 0, result.stdout + result.stderr
    else:
        assert result.returncode == 0 and result.stdout == '0\n34\n', result.stdout + result.stderr
