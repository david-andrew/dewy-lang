"""The strict bundle composes real bound obligations with static policy."""
import subprocess

import pytest

from tests.support import compiler


def check(compiler, tmp_path, source):
    path = tmp_path / 'strict.dewy'
    path.write_text(source)
    return subprocess.run([compiler, 'check', path], capture_output=True, text=True)


def test_bulletproof_empty_and_proven_counter(compiler, tmp_path):
    result = check(compiler, tmp_path, '''$bulletproof
f=(n:int64):>int64=>{let count:int64=0;loop count <? n {count+=1};return count}
main=():>void=>{f(10);}
''')
    assert result.returncode == 0, result.stderr


def test_bulletproof_rejects_unproven_counter(compiler, tmp_path):
    result = check(compiler, tmp_path, '''$bulletproof
f=(step:int64):>int64=>{let count:int64=0;loop i in [0..10) {count+=step};return count}
main=():>void=>{f(1);}
''')
    assert result.returncode != 0 and 'fits int64' in result.stderr, result.stderr


def test_bulletproof_finite_float_contract(compiler, tmp_path):
    result = check(compiler, tmp_path, '''$bulletproof
f=(x:float64):>float64=>x*x
main=():>void=>{f(1.0);}
''')
    assert result.returncode != 0 and ('finite' in result.stderr or 'infinity' in result.stderr), result.stderr


@pytest.mark.parametrize('old', ['assume_counter_progress=false', 'assume_array_length_bound=false'])
def test_provisional_bounds_tags_are_not_aliases(compiler, tmp_path, old):
    result = check(compiler, tmp_path, f'${old}\nmain=()=>{{}}\n')
    assert result.returncode != 0


def test_bulletproof_disables_local_assert_assumption(compiler, tmp_path):
    result = check(compiler, tmp_path, '''$bulletproof
main=()=>{
$assume_local_asserts
}
''')
    assert result.returncode != 0 and '$assume_local_asserts=false' in result.stderr, result.stderr
