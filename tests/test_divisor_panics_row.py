"""A divisor is the caller's obligation (docs/design/effects.md, the `panics` effect): where the
scope keeps it as a runtime check, its function panics, so `& no panics` rejects an unguarded
`//`, `%` or exact `/` outside a no-traps scope too, and accepts a guarded one."""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401


def run(compiler, tmp_path, source, command='check'):
    (tmp_path / 'main.dewy').write_text(source)
    return subprocess.run([compiler, command, 'main.dewy'], text=True, capture_output=True, timeout=60, cwd=tmp_path)


BODIES = {
    'floor_int64': ('a:int64 b:int64', 'int64', 'a // b'),
    'mod_int64': ('a:int64 b:int64', 'int64', 'a % b'),
    'floor_int': ('a:int b:int', 'int', 'a // b'),
    'exact': ('a:int b:int', 'float64', 'float64(a / b)'),
}


@pytest.mark.parametrize('scope', ['', '$runtime_checks\n'], ids=['default', 'runtime_checks'])
@pytest.mark.parametrize('name', sorted(BODIES))
def test_unguarded_divisor_panics(compiler, tmp_path, name, scope):
    params, result, body = BODIES[name]
    source = f'{scope}f = ({params}):>{result} & no panics => {body}\nmain = () => printl(f(1 0))\n'
    out = run(compiler, tmp_path, source)
    assert out.returncode != 0 and 'divisor is nonzero' in out.stderr, out.stdout + out.stderr


def test_guarded_divisor_no_panics(compiler, tmp_path):
    source = 'f = (a:int64 b:int64):>int64 & no panics => if b not=? 0 a // b else 0\nmain = () => printl(f(7 2))\n'
    out = run(compiler, tmp_path, source, 'run')
    assert out.returncode == 0 and out.stdout == '3\n', out.stdout + out.stderr
