"""Proof demand must preserve assertions, diagnostics, and panic boundaries."""
import subprocess
import pytest
from tests.support import compiler  # noqa: F401


@pytest.mark.core_quick
@pytest.mark.parametrize('body,ok', [
    ('f=(xs:array<int64> i:int64):>int64=>{$runtime_checks\nreturn xs[i]}\nprintl(f([1] 2))', False),
    ('f=():>int64=>{$runtime_checks\nlet xs:array<int64>=[1 2]\nreturn xs[1]}\nprintl(f())', True),
    ('f=(x:int64):>int64=>{$runtime_checks\nreturn 10//x}\nprintl(f(0))', False),
    ('f=(x:int64):>int8=>{$runtime_checks\nreturn int8(x)}\nprintl(f(1000))', False),
    ('f=(x:int64):>int64=>{$runtime_checks\nif x <? 0 or x >? 100 return 0; return x+1}\nprintl(f(4))', True),
    ('f=(x:int64):>int64=>{$runtime_checks\nreturn x+1}\nprintl(f(4))', False),
    ('f=(x:int64):>int8=>{$runtime_checks\nif x <? 0 or x >? 100 return 0; return int8(x)}\nprintl(f(4))', True),
    ('f=(x:int64 y:float64):>int64=>{$runtime_checks\nif x <? 0 or x >? 100 return 0; let z:int64=x+1; printl(z); return int64(y)}\nprintl(f(4 1.0))', False),
    ('f=():>int64=>{$runtime_checks\nlet a:array<int64>=[1]\n$assert a[0]=?1\nreturn a[0]}\nprintl(f())', True),
    ('$runtime_checks\nf=(xs:array<int64> i:int64):>int64=>{$runtime_checks=false\nreturn xs[i]}\nprintl(f([1] 2))', False),
])
def test_deferred_body_demand(compiler, tmp_path, body, ok):
    source = tmp_path / 'demand.dewy'
    source.write_text(body + '\n')
    run = subprocess.run([compiler, 'check', source], text=True, capture_output=True)
    assert (run.returncode == 0) == ok, run.stderr
    if not ok:
        assert 'cannot prove' in run.stderr or 'may panic' in run.stderr, run.stderr


@pytest.mark.core_quick
def test_deferred_prototype_warning(compiler, tmp_path):
    source = tmp_path / 'prototype.dewy'
    source.write_text('$prototype\nf=(xs:array<int64> i:int64):>int64=>xs[i]\nprintl(f([1] 0))\n')
    run = subprocess.run([compiler, 'check', source], text=True, capture_output=True)
    assert run.returncode == 0, run.stderr
    assert 'prototype: cannot prove index is in bounds' in run.stderr

@pytest.mark.core_quick
@pytest.mark.parametrize('body,ok', [
    ('if xs.is_empty return 0; return xs[0]', True),
    ('if not xs.is_empty return xs[0]; return 0', True),
    ('if xs.is_empty return 0; xs.clear(); return xs[0]', False),
])
def test_empty_guard_proof(compiler, tmp_path, body, ok):
    source = tmp_path / 'empty.dewy'
    source.write_text(f'first=(@xs:array<int64>):>int64=>{{{body}}}\nlet xs:array<int64>=[7]\nprintl(first(@xs))\n')
    run = subprocess.run([compiler, 'check', source], text=True, capture_output=True)
    assert (run.returncode == 0) == ok, run.stderr


@pytest.mark.core_quick
@pytest.mark.parametrize('use', ['f()', 'let saved=@f'])
def test_sparse_panic_sites_keep_calls_and_handles(compiler, tmp_path, use):
    (tmp_path / 'helper.dewy').write_text('f=():>void=>panic("explicit failure")\n')
    source = tmp_path / 'main.dewy'
    source.write_text('from p"helper.dewy" import f\n' + use + '\n')
    result = subprocess.run([compiler, 'check', source], text=True, capture_output=True)
    assert result.returncode != 0 and 'may panic' in result.stderr, result.stderr
