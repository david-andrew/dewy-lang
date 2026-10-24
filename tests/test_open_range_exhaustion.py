"""An open range must prove exhaustion unreachable, or expose its panic."""
import subprocess
import pytest
from tests.support import compiler  # noqa: F401


def check(compiler, tmp_path, source):
    path = tmp_path / 'range.dewy'
    path.write_text(source)
    return subprocess.run([compiler, 'check', str(path)], capture_output=True, text=True, timeout=60)


@pytest.mark.parametrize('start', [
    'int8(0)', 'int8(127)', 'int32(0)', 'int32(2147483647)',
    'uint8(0)', 'uint8(255)', 'uint32(0)', 'uint32(4294967295)',
    'int64(9223372036854775807)',
])
@pytest.mark.parametrize('policy', ['', '$no_assumed_bounds\n'])
def test_exhaustion_is_not_unreachable(compiler, tmp_path, start, policy):
    result = check(compiler, tmp_path, policy + f'f=():>void & no panics => {{loop i in {start}.. {{let x=i;}}}}\nmain=()=>f()\n')
    assert result.returncode != 0, result.stdout + result.stderr


@pytest.mark.parametrize('start,limit', [('int8(0)', '100'), ('int32(0)', '100'), ('int64(0)', '100')])
@pytest.mark.parametrize('policy', ['', '$no_assumed_bounds\n'])
def test_guarded_narrow_range(compiler, tmp_path, start, limit, policy):
    result = check(compiler, tmp_path, policy + f'f=():>void & no panics => {{loop i in {start}.. {{if i >=? {limit} break}}}}\nmain=()=>f()\n')
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.core_quick
def test_small_word_progress_has_opt_out(compiler, tmp_path):
    source = 'f=():>void & no panics => {loop i in int64(0).. {let x=i;}}\nmain=()=>f()\n'
    result = check(compiler, tmp_path, source)
    assert result.returncode == 0, result.stdout + result.stderr
    result = check(compiler, tmp_path, '$no_assumed_bounds\n' + source)
    assert result.returncode != 0, result.stdout + result.stderr


@pytest.mark.parametrize('second', ['9223372036854775807', '-9223372036854775808'])
def test_huge_step_is_not_progress(compiler, tmp_path, second):
    result = check(compiler, tmp_path, f'f=():>void & no panics => {{loop i in [int64(0), int64({second})..] {{let x=i;}}}}\nmain=()=>f()\n')
    assert result.returncode != 0, result.stdout + result.stderr


@pytest.mark.parametrize('join', ['and', 'or'])
def test_combined_exhaustion(compiler, tmp_path, join):
    source = f'f=():>void & no panics => {{let start:int8=126; loop i in [start..] {join} j in [0..4) {{let x=i;}}}}\nmain=()=>f()\n'
    result = check(compiler, tmp_path, source)
    assert result.returncode != 0, result.stdout + result.stderr


def test_guarded_combined(compiler, tmp_path):
    source = 'f=():>void & no panics => {loop i in [int8(0)..] and j in [0..4) and i <? 10 {}}\nmain=()=>f()\n'
    result = check(compiler, tmp_path, source)
    assert result.returncode == 0, result.stdout + result.stderr


def test_mutated_visible_counter_does_not_prove_hidden_counter(compiler, tmp_path):
    result = check(compiler, tmp_path, 'f=():>void & no panics => {loop i in int8(0).. {i = 0}}\nmain=()=>f()\n')
    assert result.returncode != 0, result.stdout + result.stderr


def test_panic_message_does_not_confer_exemption(compiler, tmp_path):
    result = check(compiler, tmp_path, 'f=():>void & no panics => panic("range exhausted its integer type")\nmain=()=>f()\n')
    assert result.returncode != 0, result.stdout + result.stderr
