"""Borrowed array elements retain value semantics through mutation and escape."""
import os
import subprocess

import pytest

from tests.support import compiler


PROGRAM = '''
read=(a:array<int64>):>int64=>sum(a)
replace=(@a:array<array<int64>>):>int64=>{a=[[90 91]] return 0}
first=(a:array<int64> ignored:int64):>int64=>a[0]
escape=(a:array<array<int64>>):>array<int64>=>{let row=a[0] return row}
main=():>void=>{
 let a:array<array<int64>>=[[1 2] [3 4]]
 let sliced=a[1..]
 $runtime_assert(sliced =? [[3 4]])
 let row=a[0]
 let out=row
 out[0]=50
 $runtime_assert(row =? [1 2] and a[0] =? [1 2] and out =? [50 2])
 let saved=escape(a)
 a[0][0]=70
 $runtime_assert(saved =? [1 2])
 let old=a[0]
 a=[[11 12]]
 $runtime_assert(old =? [70 2])
 let before=a[0]
 $runtime_assert(first(before replace(@a)) =? 11)
 $runtime_assert(a =? [[90 91]])
 let results=[parallel i in [0..257) {let r=a[0] read(r)+i}]
 loop i in [0..257) {$runtime_assert(results[i] =? 181+i)}
 let capture=(i:int64)=>read(a[0])+i
 $runtime_assert(capture(2) =? 183)
}
'''


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True])
def test_borrowed_row_snapshots(compiler, tmp_path, release):
    source = tmp_path / 'rows.dewy'
    source.write_text(PROGRAM)
    output = tmp_path / 'rows'
    build = subprocess.run([compiler, 'build', source, '-o', output,
                            *(['--release'] if release else [])], capture_output=True, text=True)
    assert build.returncode == 0, build.stderr
    for workers in (1, 2):
        run = subprocess.run([output], env=dict(os.environ, SLOPPY_THREADS=str(workers)),
                             capture_output=True, text=True, timeout=30)
        assert run.returncode == 0, run.stderr
