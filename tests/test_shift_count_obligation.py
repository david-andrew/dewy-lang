"""An `int` shifted by a negative count fails (docs/LANGUAGE.md, bitwise operators): under no traps
(docs/design/no_traps.md) a signed count is an obligation, `count >=? 0`, proven by facts, else an
error under `$bulletproof`, and a runtime check that makes its function panic (docs/design/effects.md)
under `$runtime_checks` or by default. A fixed width's count is unsigned: total."""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401


def run(compiler, tmp_path, source, command='check'):
    (tmp_path / 'main.dewy').write_text(source)
    return subprocess.run([compiler, command, 'main.dewy'], text=True, capture_output=True, timeout=60, cwd=tmp_path)


MAIN = 'main = ():>(void | OutOfMemory) & no panics => {\n    let n = 3 - args().length\n    let x = 5\n'

FORMS = {
    'left': '    printl(x << n)\n',
    'right': '    printl(x >> n)\n',
    'compound': '    x <<= n\n    printl(x)\n',
    'int64_count': '    let m:int64 = 2\n    if args().length >? 7 m = -1\n    printl(x >> m)\n',
}


@pytest.mark.parametrize('form', sorted(FORMS))
def test_unguarded_rejected_bulletproof(compiler, tmp_path, form):
    result = run(compiler, tmp_path, '$bulletproof\n' + MAIN + FORMS[form] + '}\n')
    assert result.returncode != 0 and 'cannot prove the shift count is >= 0' in result.stderr, result.stdout + result.stderr


@pytest.mark.parametrize('scope', ['', '$runtime_checks\n'], ids=['default', 'runtime_checks'])
@pytest.mark.parametrize('op', ['<<', '>>'])
def test_unguarded_panics(compiler, tmp_path, scope, op):
    source = f'{scope}f = (x:int n:int):>int => x {op} n\nmain = ():>void & no panics => printl(f(1 3))\n'
    result = run(compiler, tmp_path, source)
    assert result.returncode != 0 and 'may panic' in result.stderr, result.stdout + result.stderr
    assert 'the shift count is >= 0' in result.stderr, result.stderr


def test_negative_count_refuted(compiler, tmp_path):
    result = run(compiler, tmp_path, '$bulletproof\n' + MAIN + '    printl(x << (n - 10))\n}\n')
    assert result.returncode != 0 and 'the shift count is negative' in result.stderr, result.stdout + result.stderr


def test_closed_row_needs_the_guard(compiler, tmp_path):
    bad = 'f = (x:int n:int):>(int | OutOfMemory) & allocates => x << n\nmain = () => printl(f(1 3))\n'
    result = run(compiler, tmp_path, bad)
    assert result.returncode != 0 and 'possible failure exceeds' in result.stderr, result.stdout + result.stderr


ACCEPT = '''$bulletproof
g = (x:int n:int):>(int | OutOfMemory) & allocates => if n >=? 0 x << n else 0
h = (x:int n:uint8):>(int | OutOfMemory) & allocates => x >> n
''' + MAIN + '''    let y = x
    if n >=? 0 {
        y <<= n
        printl(x << n)
    }
    printl"{y} {x << 2} {g(3 4)} {g(3 (-1))} {h(256 4)} {int64(7) << n}"
}
'''


@pytest.mark.core_quick
def test_guarded_accepted(compiler, tmp_path):
    result = run(compiler, tmp_path, ACCEPT, 'run')
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout == '20\n20 20 48 0 16 28\n', result.stdout
