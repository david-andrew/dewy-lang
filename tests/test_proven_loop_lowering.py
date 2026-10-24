"""Proving bounds must preserve word induction and shifted-index vectorization."""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401


@pytest.mark.parametrize('release', [False, True])
def test_proven_open_loop_keeps_word_counter(compiler, tmp_path, release):
    source = tmp_path / 'open.dewy'
    source.write_text('''$runtime_checks
fill=(@values:array<int64>):>void=>{
 loop i in 0.. and i <? values.length {values[i]=i as int64}
}
let xs:array<int64>=[9 9 9 9]
fill(@xs)
printl(xs)
''')
    binary = tmp_path / 'open'
    built = subprocess.run([compiler, '--internal-fact-policy=require-static', 'build', source,
                            '--ir', '-o', binary, *(['--release'] if release else [])],
                           capture_output=True, text=True)
    assert built.returncode == 0, built.stderr
    assert 'fn f___mi_compare_' not in built.stdout
    ran = subprocess.run([binary], capture_output=True, text=True)
    assert ran.returncode == 0 and ran.stdout == '[0 1 2 3]\n', ran.stderr


@pytest.mark.parametrize('release', [False, True])
def test_open_loop_rereads_resized_bound(compiler, tmp_path, release):
    source = tmp_path / 'resize.dewy'
    source.write_text('''$runtime_checks
trim=(@values:array<int64>):>void=>{
 loop i in 0.. and i <? values.length {
  values[i]=i as int64
  if i =? 1 values.truncate(2)
 }
}
let xs:array<int64>=[9 9 9 9]
trim(@xs)
printl(xs)
''')
    ran = subprocess.run([compiler, '--internal-fact-policy=require-static',
                          *(['--release'] if release else []), source], capture_output=True, text=True)
    assert ran.returncode == 0 and ran.stdout == '[0 1]\n', ran.stderr


def test_proven_stencil_still_vectorizes(compiler, tmp_path):
    source = tmp_path / 'stencil.dewy'
    source.write_text('''$runtime_checks
step=(center:array<float64>):>array<float64>=>{
 let out=center
 loop j in [1..center.length-1) {out[j]=(center[j-1]+center[j+1])*0.5}
 return out
}
loop n in [2..35) {
 let a=[loop i in [0..n) (i*i) as float64]
 let b=step(a)
 $runtime_assert(b[0] =? a[0] and b[n-1] =? a[n-1])
 loop j in [1..n-1) {$runtime_assert(b[j] =? a[j]+1.0)}
}
''')
    binary = tmp_path / 'stencil'
    built = subprocess.run([compiler, '--internal-fact-policy=require-static', 'build', source,
                            '--release', '--ir', '-o', binary], capture_output=True, text=True)
    assert built.returncode == 0, built.stderr
    assert 'vld ' in built.stdout
    ran = subprocess.run([binary], capture_output=True, text=True)
    assert ran.returncode == 0, ran.stderr
