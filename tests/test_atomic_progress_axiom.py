"""Atomic progress discharges only the accepted bounded int64 increment axiom."""
import subprocess

import pytest

from tests.support import compiler


def check(compiler, tmp_path, source):
    path = tmp_path / 'atomic.dewy'
    path.write_text(source + '\n')
    return subprocess.run([compiler, 'check', path], capture_output=True, text=True)


@pytest.mark.parametrize('step', ['1', '-1', '7'])
def test_atomic_literal_progress(compiler, tmp_path, step):
    source = f'let counter=atomic(0)\nprintl(counter.add({step}))'
    result = check(compiler, tmp_path, source)
    assert result.returncode == 0, result.stderr
    strict = check(compiler, tmp_path, '$no_assumed_bounds\n' + source)
    assert strict.returncode != 0 and 'add' in strict.stderr and 'may panic' in strict.stderr, strict.stderr


def test_atomic_parameter_progress_and_nested_optout(compiler, tmp_path):
    source = 'f=(counter:Atomic<int64> step:int64)=>counter.add(step)\nprintl(f(atomic(0) 3))'
    result = check(compiler, tmp_path, source)
    assert result.returncode == 0, result.stderr
    strict = check(compiler, tmp_path, '$no_assumed_bounds\n' + source)
    assert strict.returncode != 0 and 'may panic' in strict.stderr, strict.stderr
    restored = check(compiler, tmp_path, '$no_assumed_bounds\nf=(counter:Atomic<int64>)=>{\n$no_assumed_bounds=false\ncounter.add(1)\n}\nprintl(f(atomic(0)))')
    assert restored.returncode == 0, restored.stderr


@pytest.mark.parametrize('source', [
    'let counter=atomic(1)\nprintl(counter.add(counter.load()))',
    'let counter=atomic(1)\nlet step=counter.load()\nprintl(counter.add(step))',
    'let counter=atomic<uint64>(0)\nprintl(counter.add(1))',
    '$assume_local_asserts=false\nadd=(value:int64)=>{panic("user failure");value}\nprintl(add(1))',
])
def test_atomic_axiom_keeps_other_failures(compiler, tmp_path, source):
    result = check(compiler, tmp_path, source)
    assert result.returncode != 0 and 'may panic' in result.stderr, result.stderr


def test_atomic_optout_runtime_check_still_traps(compiler, tmp_path):
    path = tmp_path / 'overflow.dewy'
    path.write_text('$runtime_checks\n$no_assumed_bounds\nlet counter=atomic(9223372036854775807)\nprintl(counter.add(1))\n')
    result = subprocess.run([compiler, 'run', path], capture_output=True, text=True)
    assert result.returncode == 101 and not result.stdout, result.stdout + result.stderr


@pytest.mark.parametrize('step', ['step & 7', 'step % 7'])
def test_atomic_bounded_progress_in_effect_row(compiler, tmp_path, step):
    source = f'f=(counter:Atomic<int64> step:int64):>int64 & no panics=>counter.add({step})\nprintl(f(atomic(0) 3))'
    result = check(compiler, tmp_path, source)
    assert result.returncode == 0, result.stderr
    strict = check(compiler, tmp_path, '$no_assumed_bounds\n' + source)
    assert strict.returncode != 0 and 'panic' in strict.stderr, strict.stderr


def test_atomic_literal_does_not_hide_another_panic(compiler, tmp_path):
    source = '$assume_local_asserts=false\nf=(counter:Atomic<int64>):>int64 & no panics=>{counter.add(1);panic("still fails")}\nprintl(f(atomic(0)))'
    result = check(compiler, tmp_path, source)
    assert result.returncode != 0 and 'panic' in result.stderr, result.stderr
