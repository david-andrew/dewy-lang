"""`dewy check` reports the definite-assignment errors a build reports, and no others:
every definite/global-unset golden case checks as it builds, and a test that reads a
global main assigns (tests never run in a build) checks clean."""
import re
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401

CASES = sorted([*(ROOT / 'tests/cases/definite').glob('*.dewy'),
                *(ROOT / 'tests/cases/global').glob('unset_*.dewy')])


def check(compiler, path):  # noqa: F811
    return subprocess.run([compiler, 'check', str(path)], capture_output=True, text=True, timeout=60, check=False)


@pytest.mark.parametrize('case', CASES, ids=lambda p: f'{p.parent.name}/{p.stem}')
def test_check_matches_build(compiler, case):  # noqa: F811
    checked = check(compiler, case)
    err = case.with_suffix('.err')
    if not err.exists():
        assert checked.returncode == 0, checked.stderr
        return
    assert checked.returncode != 0, f'check accepted {case.name}'
    for line in err.read_text().splitlines():
        if line.startswith('/') and line.endswith('/') and len(line) > 1:
            assert re.search(line[1:-1], checked.stderr), (line, checked.stderr)
        elif line:
            assert line in checked.stderr, (line, checked.stderr)


def test_check_skips_test_runs(compiler, tmp_path):  # noqa: F811
    source = tmp_path / 'main.dewy'
    source.write_text('let y:int64\nmain = () => {\n    y = 3\n    printl(y)\n}\n'
                      '$test\nreads = () => $expect y >=? 0\n')
    checked = check(compiler, source)
    assert checked.returncode == 0, checked.stderr
    source.write_text('let y:int64\nif args.length >? 1 { y = 1 }\nprintl(y)\n'
                      '$test\nreads = () => $expect 1 =? 1\n')
    checked = check(compiler, source)
    assert checked.returncode != 0 and "'y' is read before it is given a value" in checked.stderr, checked.stderr
