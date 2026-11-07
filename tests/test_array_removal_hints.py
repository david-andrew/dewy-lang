"""Array removal hints lead directly to a valid call; maps keep their API."""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401


@pytest.mark.parametrize('name', ['remove_at', 'remove', 'delete', 'erase', 'Remove'])
def test_array_removal_hints(compiler, tmp_path, name):
    path = tmp_path / 'remove.dewy'
    path.write_text(f'let xs = [10 20 30]\nxs.{name}(1)\nprintl(xs)\n')
    checked = subprocess.run([compiler, 'check', path], capture_output=True, text=True, timeout=30)
    assert checked.returncode == 1, checked.stderr
    assert '`xs.pop(i)`' in checked.stderr, checked.stderr
    assert '`remove(i)`' not in checked.stderr
    path.write_text('let xs = [10 20 30]\nprintl(xs.pop(1))\nprintl(xs)\n')
    ran = subprocess.run([compiler, 'run', path], capture_output=True, text=True, timeout=30)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout == '20\n[10 30]\n'


def test_array_removal_map_control(compiler, tmp_path):
    path = tmp_path / 'map.dewy'
    path.write_text('let values:dict<string int64> = ["a" -> 10]\nprintl(values.remove("a"))\nprintl(values.remove("a"))\n')
    ran = subprocess.run([compiler, 'run', path], capture_output=True, text=True, timeout=30)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout == 'true\nfalse\n'
