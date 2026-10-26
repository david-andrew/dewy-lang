"""Inclusive capture runs at the signed-word endpoint, with the 256-value cap."""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401
from tests.test_selfhost_int_domains import DRIVER, ROOT, MIN, MAX


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_capture_endpoint(compiler, tmp_path, release):  # noqa: F811
    commands, expected = [], []
    for hi in (MIN + 256, -1, MAX):
        for size in (1, 2, 255, 256, 257):
            lo = hi - size + 1
            commands += ['R', 'W 1 0 0 0']
            commands += [f'W 1 1 {v} 0' for v in range(lo, hi + 1)]
            commands += ['W 2 4 1 0', 'W 3 4 2 0', 'D 3', 'S']
            expected += ['states 3']
            for binding in (3, 2, 1, 3):
                commands += [f'Q {binding}']
                if size > 256 and binding != 1:
                    expected += ['[] ']
                else:
                    label = str(lo) if lo == hi else f'{lo}..{hi}'
                    expected += [f'[{lo}, {hi}] {label}']
    steps = tmp_path / 'steps'
    steps.write_text('\n'.join(commands) + '\n')
    for module in ('int_domains.dewy', 'int_domains.jo'):
        source, binary = tmp_path / f'{module}.jo', tmp_path / f'{module}.bin'
        source.write_text(DRIVER.read_text().replace("use '../../../compiler/int_domains.jo'",
                          f"use '{ROOT / 'compiler' / module}'"))
        built = subprocess.run([compiler, 'build', source, '-o', binary, *(['--release'] if release else [])],
                               capture_output=True, text=True, timeout=120)
        assert built.returncode == 0, built.stdout + built.stderr
        ran = subprocess.run([binary, steps], capture_output=True, text=True, timeout=30)
        assert ran.returncode == 0, ran.stdout + ran.stderr
        assert ran.stdout == '\n'.join(expected) + '\n'
