"""Check address-ordered groups and nested waits through the compiler CLI."""
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401

CASES = ROOT / 'tests/cases/no_deadlocks'


def check(compiler, source, expected=()):
    result = subprocess.run([compiler, 'check', source], capture_output=True, text=True, timeout=60)
    assert (result.returncode != 0) == bool(expected), result.stderr
    for text in expected:
        assert text in result.stderr, result.stderr


@pytest.mark.parametrize('name', ['certified_locks', 'lock_order/compatible_lock_orders'])
def test_compatible_lock_order(compiler, name):
    check(compiler, CASES / f'{name}.dewy')


@pytest.mark.parametrize('name', ['mixed_lock_order', 'transitive_lock_order'])
def test_conflicting_lock_order(compiler, name):
    source = CASES / 'lock_order' / f'{name}.dewy'
    check(compiler, source, source.with_suffix('.err').read_text().splitlines())


def test_lock_order_aliases(compiler, tmp_path):
    program = (CASES / 'lock_order/transitive_lock_order.dewy').read_text()
    source = tmp_path / 'array_handles.dewy'
    source.write_text(program.replace('pair(x y) or_throw;',
                                     'let handles=[x y] pair(handles[0] handles[1]) or_throw;'))
    check(compiler, source, ['mixes lock orders', 'use `lock_all` on all these paths'])


def test_lock_order_opt_out(compiler, tmp_path):
    program = (CASES / 'lock_order/transitive_lock_order.dewy').read_text()
    source = tmp_path / 'opted_out.dewy'
    source.write_text('$no_deadlocks\n' + program.replace('    $no_deadlocks\n', '    $no_deadlocks=false\n')
                      .replace('    let [a b]', '    $no_deadlocks=false\n    let [a b]')
                      .replace('    let a =', '    $no_deadlocks=false\n    let a ='))
    check(compiler, source)
