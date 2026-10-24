"""A float converted to an integer keeps its value (docs/design/decisions.md, Floats (Q8)), so NaN,
an infinity or a value outside the target fails: under no traps (docs/design/no_traps.md) the
conversion is an obligation. Proven by the float facts (a guard whose comparisons hold only for
numbers in range, or `$finite_floats` for `int`), else an error under `$bulletproof`, and a runtime
check that makes its function panic (docs/design/effects.md) under `$runtime_checks` or by default."""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401


def run(compiler, tmp_path, source, command='check'):
    (tmp_path / 'main.dewy').write_text(source)
    return subprocess.run([compiler, command, 'main.dewy'], text=True, capture_output=True, timeout=60, cwd=tmp_path)


MAIN = 'main = ():>(void | OutOfMemory) & no panics => {\n    let x = 2.5\n    if args().length >? 5 x = 1e300\n'

FORMS = {
    'call': '    printl(int64(x))\n',
    'as': '    printl(x as uint8)\n',
    'int32': '    printl(int32(x))\n',
    'uint64': '    printl(uint64(x))\n',
}


@pytest.mark.parametrize('form', sorted(FORMS))
def test_unguarded_rejected_bulletproof(compiler, tmp_path, form):
    result = run(compiler, tmp_path, '$bulletproof\n' + MAIN + FORMS[form] + '}\n')
    assert result.returncode != 0 and 'range for the conversion to ' in result.stderr, result.stdout + result.stderr
    assert 'help: NaN, an infinity or a value out of range fails' in result.stderr, result.stderr


@pytest.mark.parametrize('scope', ['', '$runtime_checks\n'], ids=['default', 'runtime_checks'])
@pytest.mark.parametrize('target', ['int64', 'uint8', 'int'])
def test_unguarded_panics(compiler, tmp_path, scope, target):
    source = f'{scope}f = (x:float64):>{target} => {target}(x)\nmain = ():>void & no panics => printl(f(2.5))\n'
    result = run(compiler, tmp_path, source)
    assert result.returncode != 0 and ('may panic' if scope else 'cannot prove') in result.stderr, result.stdout + result.stderr
    assert 'for the conversion to ' + target in result.stderr, result.stderr


# A closed row that excludes failure: unproven, the conversion may fail.
def test_closed_row_needs_the_guard(compiler, tmp_path):
    bad = '$runtime_checks\nf = (x:float64):>int64 & no_effects => int64(x)\nmain = () => printl(f(2.5))\n'
    result = run(compiler, tmp_path, bad)
    assert result.returncode != 0 and 'possible failure exceeds' in result.stderr, result.stdout + result.stderr
    good = '$runtime_checks\nf = (x:float64):>int64 & no_effects => if -10.0 <=? x and x <? 10.0 int64(x) else 0\nmain = () => printl(f(2.5))\n'
    result = run(compiler, tmp_path, good, 'run')
    assert result.returncode == 0 and result.stdout == '2\n', result.stdout + result.stderr


# `not (x >=? 0.0)` holds for NaN too: outside `$no_nan` (which `$bulletproof` includes), a guard
# of negated comparisons proves no range.
def test_negated_guard_does_not_exclude_nan(compiler, tmp_path):
    source = ('f = (x:float64):>uint8 => {\n    if x <? 0.0 or x >=? 256.0 return 0\n    x as uint8\n}\n'
              'main = ():>void & no panics => printl(f(2.5))\n')
    result = run(compiler, tmp_path, source)
    assert result.returncode != 0 and 'cannot prove' in result.stderr, result.stdout + result.stderr
    assert 'within the uint8 range' in result.stderr, result.stderr
    result = run(compiler, tmp_path, '$no_nan\n' + source)
    assert result.returncode == 0, result.stdout + result.stderr


ACCEPT = '''$bulletproof
a = (x:float64):>int64 => if -1000.0 <=? x and x <? 1000.0 int64(x) else -1
b = (x:float64):>uint8 => {
    if not (0.0 <=? x and x <? 256.0) return 0
    x as uint8
}
c = (x:float64):>uint64 => if 0.0 <=? x and x <? 1.8e19 uint64(x) else 0
d = (x:float64):>(int | OutOfMemory) & allocates => if -1e300 <=? x and x <=? 1e300 int(x) else 0
main = ():>(void | OutOfMemory) & no panics => {
    printl"{a(-999.9)} {a(5000.0)} {a(NAN)} {b(255.9)} {b(-0.5)} {c(1.7e19)} {d(-2.5)} {d(INF)}"
}
'''


@pytest.mark.core_quick
def test_guarded_accepted(compiler, tmp_path):
    result = run(compiler, tmp_path, ACCEPT, 'run')
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout == '-999 -1 -1 255 0 17000000000000000000 -2 0\n', result.stdout


def test_finite_floats_proves_int(compiler, tmp_path):
    source = '$finite_floats\nf = (x:float64):>int => int(x)\nmain = ():>void & no panics => printl(f(2.5))\n'
    result = run(compiler, tmp_path, source, 'run')
    assert result.returncode == 0 and result.stdout == '2\n', result.stdout + result.stderr
