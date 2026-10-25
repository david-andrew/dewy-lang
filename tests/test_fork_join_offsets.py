"""Exact offset folding retains the signed storage boundary and callback bounds."""
import os
import subprocess

import pytest

from tests.support import compiler


@pytest.mark.parametrize('release', [False, True])
@pytest.mark.parametrize('workers', [1, 4])
def test_fork_offsets_and_mutated_index(compiler, tmp_path, release, workers):
    source = tmp_path / 'offsets.dewy'
    source.write_text('''
f=(n:int64):>int64=>{
 if n <? 2 return n
 let r=parallel_range(2 (i:int64)=>f(n-1-i))
 return r[0]+r[1]
}
mutated=(n:int64):>int64=>{
 let r=parallel_range(2 (i:int64)=>{i=-1 return n-1-i})
 return r[0]
}
wide_offset=(n:int64):>int64=>{
 let r=parallel_range(2 (i:int64)=>n-9223372036854775807-i)
 return r[1]
}
main=()=>{
 $runtime_assert f(18) =? 2584
 $runtime_assert mutated(-9223372036854775808) =? -9223372036854775808
 $runtime_assert wide_offset(0) =? -9223372036854775808
 let a=parallel_range(2 (i:int64)=>-9223372036854775806-1-i)
 $runtime_assert a[0] =? -9223372036854775807
 $runtime_assert a[1] =? -9223372036854775808
 printl"ok"
}
$runtime_checks
''')
    binary = tmp_path / 'offsets'
    built = subprocess.run([compiler, 'build', source, '-o', binary] + (['--release'] if release else []),
                           capture_output=True, text=True, timeout=60)
    assert built.returncode == 0, built.stderr
    ran = subprocess.run([binary], env=dict(os.environ, DEWY_THREADS=str(workers)),
                         capture_output=True, text=True, timeout=30)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout == 'ok\n'


@pytest.mark.parametrize('expression,value', [('n-1-i', '-9223372036854775807'),
                                               ('n+1+i', '9223372036854775806')])
def test_fork_offset_overflow(compiler, tmp_path, expression, value):
    source = tmp_path / 'overflow.dewy'
    source.write_text('''
f=(n:int64):>void=>{
 let r=parallel_range(2 (i:int64)=>EXPR)
 printl"{r[0]} {r[1]}"
}
main=()=>{f(VALUE)}
$runtime_checks
'''.replace('EXPR', expression).replace('VALUE', value))
    binary = tmp_path / 'overflow'
    built = subprocess.run([compiler, 'build', source, '--release', '-o', binary],
                           capture_output=True, text=True, timeout=60)
    assert built.returncode == 0, built.stderr
    for workers in (1, 4):
        ran = subprocess.run([binary], env=dict(os.environ, DEWY_THREADS=str(workers)),
                             capture_output=True, text=True, timeout=30)
        assert ran.returncode != 0
        assert 'overflow' in ran.stderr
