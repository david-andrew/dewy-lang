"""Flat broadcast operands preserve singleton-axis shape and value snapshots."""
import subprocess

import pytest

from tests.support import compiler


@pytest.mark.parametrize('release', [False, True])
def test_broadcast_singleton_axes_empty_and_evaluation(compiler, tmp_path, release):
    source = tmp_path / 'axes.dewy'
    source.write_text(('''make=(@calls:int64 xs:array<int64>):>array<int64>=>{calls+=1; return xs}
main=()=>{
 loop n in [0..10) {
  let calls:int64=0
  let xs:array<int64>=[loop i in [0..n) (i-5) as int64]
  let row=make(@calls xs)[new ..] .+ 0
  let col=make(@calls xs)[.. new] .+ 0
  $runtime_assert(calls =? 2)
  $runtime_assert(row.shape =? [1 n])
  $runtime_assert(col.shape =? [n (if n =? 0 0 else 1)])
  $runtime_assert(row.data =? xs and col.data =? xs)
  if n >? 0 {
   xs[0]=99
   $runtime_assert(row.data[0] =? -5 and col.data[0] =? -5)
  }
 }
 printl("ok")
}
''') + "\n$runtime_checks\n")
    binary = tmp_path / 'axes'
    built = subprocess.run([compiler, 'build', source, '-o', binary,
                            *(['--release'] if release else [])], capture_output=True, text=True)
    assert built.returncode == 0, built.stderr
    run = subprocess.run([binary], capture_output=True, text=True)
    assert run.returncode == 0 and run.stdout == 'ok\n', run.stdout + run.stderr
