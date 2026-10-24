"""Speculating pure value arms must leave failure guards conditional on selection."""
import subprocess

import pytest

from tests.support import compiler


@pytest.mark.parametrize('release', [False, True])
@pytest.mark.parametrize('reverse', [False, True])
def test_checked_arm_selection(compiler, tmp_path, release, reverse):
    expression = 'if choose x//2 else 3*x+1' if reverse else 'if choose 3*x+1 else x//2'
    safe = 'true' if reverse else 'false'
    bad = 'false' if reverse else 'true'
    prefix = '$runtime_checks\nf=(x:int64 choose:bool):>int64=>{if x >? 0 {return ' + expression + '} else return 0}\n'
    source = tmp_path / 'select.dewy'
    source.write_text(prefix + 'loop x in [1 7 3074457345618258602 9223372036854775807] printl(f(x ' + safe + '))\n')
    result = subprocess.run([compiler, *(['--release'] if release else []), source], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout == '0\n3\n1537228672809129301\n4611686018427387903\n'
    source.write_text(prefix + 'loop x in [3074457345618258602 9223372036854775807] printl(f(x ' + bad + '))\n')
    binary = tmp_path / 'fail'
    built = subprocess.run([compiler, 'build', source, '-o', binary, *(['--release'] if release else [])], capture_output=True, text=True)
    assert built.returncode == 0, built.stderr
    result = subprocess.run([binary], capture_output=True, text=True)
    assert result.returncode != 0
    assert 'overflow' in result.stderr
    assert result.stdout == '9223372036854775807\n'
