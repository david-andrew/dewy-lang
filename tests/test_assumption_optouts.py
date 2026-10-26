"""Convenience assumptions: default behavior, scoped opt-out, and repair text."""

import subprocess

import pytest

from tests.support import compiler  # noqa: F401


def check(compiler, tmp_path, source):
    path = tmp_path / 'main.dewy'
    path.write_text(source)
    return subprocess.run([compiler, 'check', path], capture_output=True, text=True, timeout=60)


@pytest.mark.core_quick
@pytest.mark.parametrize('expression,setup', [
    ('count + step',
     'f=(step:int64):>int64=>{let count:int64=0;loop i in [0..10) {count+=step};return count}\n'
     'main=()=>printl(f(1))'),
    ('xs.length*16',
     'f=(xs:array<int64>):>int64=>xs.length*16\n'
     'main=()=>printl(f([1 2 3]))'),
])
def test_no_assumed_bounds_demand_proof_with_repair(compiler, tmp_path, expression, setup):
    default = check(compiler, tmp_path, '$runtime_checks=false\n' + setup + '\n')
    assert default.returncode == 0, default.stderr

    strict = check(compiler, tmp_path, '$no_assumed_bounds\n$runtime_checks=false\n' + setup + '\n')
    assert strict.returncode != 0, strict.stderr
    assert 'cannot prove exact integer result fits int64' in strict.stderr
    assert f'nothing bounds `{expression}`' in strict.stderr
    assert 'help: compute it in `int`' in strict.stderr
    assert 'bound the operands with a guard' in strict.stderr


@pytest.mark.core_quick
def test_local_assert_optout_demand_proof_with_repair(compiler, tmp_path):
    body = ('checked=(x:int64):>int64=>{$runtime_assert x >? 0;x}\n'
            'main=():>void=>printl(checked(3))\n')
    default = check(compiler, tmp_path, '$runtime_checks=false\n' + body)
    assert default.returncode == 0, default.stderr

    strict = check(compiler, tmp_path, '$assume_local_asserts=false\n$runtime_checks=false\n' + body)
    assert strict.returncode != 0, strict.stderr
    assert 'calling `checked` may panic' in strict.stderr
    assert 'prove what it checks before the call' in strict.stderr
    assert 'opt in to the check with `$runtime_checks`' in strict.stderr


@pytest.mark.core_quick
def test_external_paths_optout_current_warning_and_repair(compiler, tmp_path):
    body = 'main=()=>{let f=p(args()[0]);printl(f.exists)}\n$runtime_checks\n'
    default = check(compiler, tmp_path, body)
    assert default.returncode == 0, default.stderr
    assert 'confine_external_paths' not in default.stderr

    strict = check(compiler, tmp_path, '$confine_external_paths\n' + body)
    assert strict.returncode == 0, strict.stderr
    assert 'warning: `f` is not proven to stay inside a base' in strict.stderr
    assert 'root.confine(f) or_throw' in strict.stderr
    assert 'if root.contains(f)' in strict.stderr
