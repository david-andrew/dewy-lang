"""Loop string comparisons inline in default builds and stay callable under -g."""
import platform
import re
import subprocess

import pytest

from tests.support import compiler


@pytest.mark.core_quick
@pytest.mark.parametrize('debug', [False, True])
def test_default_string_inline(compiler, tmp_path, debug):
    if platform.machine().lower() not in ('x86_64', 'amd64'):
        pytest.skip('native string intrinsic is x86-64 only')
    source = tmp_path / 'strings.jo'
    source.write_text('''probe = (a: str, b: str) -> int:
    total = 0
    loop i in [0..4):
        if a == b: total += 10
        if a != b: total += 1
    if a == b: total += 2
    total
main = () -> int:
    if probe("abcdefghijklmnopq", "abcdefghijklmnopq") != 42: return 1
    if probe("abcdefghijklmnopq", "abcdefghijklmnopr") != 4: return 2
    if probe("", "") != 42: return 3
    if probe("", "x") != 4: return 4
    0
''')
    binary = tmp_path / 'strings'
    built = subprocess.run([compiler, 'build', source, '--ir',
                            *(['-g'] if debug else []), '-o', binary],
                           capture_output=True, text=True, timeout=30)
    assert built.returncode == 0, built.stdout + built.stderr
    probe = next(body for body in re.split(r'^fn ', built.stdout, flags=re.MULTILINE)
                 if body.startswith('f_probe_'))
    assert len(re.findall(r'\bstreq\b', probe)) == (0 if debug else 2), probe
    # The comparison following the loop stays independently callable.
    assert len(re.findall(r'\bcall .* c=0 ', probe)) == (3 if debug else 1), probe
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10)
    assert ran.returncode == 0, ran.stdout + ran.stderr
