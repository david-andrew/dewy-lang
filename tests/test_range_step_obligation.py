"""A stepped range's step, its second value minus its first, must be nonzero (docs/LANGUAGE.md,
loops): under no traps (docs/design/no_traps.md) it is an obligation, proven by facts (distinct
literals, a guard ordering the two values or `step not=? 0`), else an error under `$bulletproof`,
and a runtime check that makes its function panic (docs/design/effects.md) under
`$runtime_checks` or by default. Loops, comprehensions and stored ranges alike."""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401


def run(compiler, tmp_path, source, command='check'):
    (tmp_path / 'main.dewy').write_text(source)
    return subprocess.run([compiler, command, 'main.dewy'], text=True, capture_output=True, timeout=60, cwd=tmp_path)


MAIN = 'main = ():>(void | OutOfMemory) & no panics => {\n    let k = args().length - 1\n'

FORMS = {
    'loop': '    loop i in [0, k..10] printl(i)\n',
    'descending': '    loop i in [10, 10 - k..0] printl(i)\n',
    'comprehension': '    printl([loop i in [1, k..9] i])\n',
    'stored': '    let r = [0, k..10]\n    printl(r)\n',
}


@pytest.mark.parametrize('form', sorted(FORMS))
def test_unguarded_rejected_bulletproof(compiler, tmp_path, form):
    result = run(compiler, tmp_path, '$bulletproof\n' + MAIN + FORMS[form] + '}\n')
    assert result.returncode != 0 and 'cannot prove the range step is nonzero' in result.stderr, result.stdout + result.stderr


@pytest.mark.parametrize('scope', ['', '$runtime_checks\n'], ids=['default', 'runtime_checks'])
@pytest.mark.parametrize('form', ['loop', 'comprehension', 'stored'])
def test_unguarded_panics(compiler, tmp_path, scope, form):
    result = run(compiler, tmp_path, scope + MAIN + FORMS[form] + '}\n')
    assert result.returncode != 0 and ('may panic' if scope else 'cannot prove') in result.stderr, result.stdout + result.stderr
    assert 'the range step is nonzero' in result.stderr, result.stderr


def test_zero_step_refuted(compiler, tmp_path):
    result = run(compiler, tmp_path, '$bulletproof\n' + MAIN + '    let a = k\n    loop i in [a, a..10] printl(i)\n}\n')
    assert result.returncode != 0 and 'the range step is zero' in result.stderr, result.stdout + result.stderr


def test_closed_row_needs_the_guard(compiler, tmp_path):
    body = '{\n    let t:int64 = 0\n    %s\n    t\n}\n'
    bad = '$runtime_checks\nf = (a:int64):>int64 & no_effects => ' + body % 'loop i in [0, a..10] t += i' + 'main = () => printl(f(2))\n'
    result = run(compiler, tmp_path, bad)
    assert result.returncode != 0 and 'possible failure exceeds' in result.stderr, result.stdout + result.stderr
    good = '$runtime_checks\nf = (a:int64):>int64 & no_effects => ' + body % 'if a >? 0 { loop i in [0, a..10] t += i }' + 'main = () => printl(f(2))\n'
    result = run(compiler, tmp_path, good, 'run')
    assert result.returncode == 0 and result.stdout == '30\n', result.stdout + result.stderr


ACCEPT = '$bulletproof\n' + MAIN + '''    let t = 0
    loop i in [0, 3..10] t += i
    if k >? 0 { loop i in [0, k..10] t += i }
    let step = k - 3
    if step not=? 0 { loop i in [0, step..12] t += i }
    if step <? 0 { loop i in [12, 12 + step..0] t += i }
    printl"{t} {[loop i in [9, 7..1] i]} {[2, 4..8]}"
}
'''


@pytest.mark.core_quick
def test_guarded_accepted(compiler, tmp_path):
    result = run(compiler, tmp_path, ACCEPT, 'run')
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout == '48 [9 7 5 3 1] [2,4..8]\n', result.stdout
