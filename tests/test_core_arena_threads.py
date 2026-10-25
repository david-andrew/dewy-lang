"""Arena allocation contexts remain local to worker and waiting-task stacks."""
import os
import subprocess

import pytest

from tests.support import compiler


@pytest.mark.parametrize('release', [False, True])
def test_arena_growth_on_workers_and_tasks(compiler, tmp_path, release):
    source = tmp_path / 'arena_threads.dewy'
    (tmp_path / 'workers.jo').write_text('''
# Exercise the worker runtime directly: Dewy's compute-lane checker currently
# classifies arena acquisition as blocking. Each callback owns its arena.
check_workers = ():
    out = fill(0, 65)
    op = data(out)
    work = (lo: int, hi: int):
        arena = Arena()
        loop i in [lo..hi):
            old = __arena_enter(arena)
            total = 0
            if true:
                rows: int[][]
                loop r in [0..37):
                    row: int[]
                    loop c in [0..9): row.push(i + r + c)
                    rows.push(row)
                loop row in rows:
                    loop x in row: total += x
            __arena_leave(old)
            arena.reset()
            op[i] = total
    __fj_run(65, (&work) as *int)
    loop i in [0..65): assert(out[i] == 333 * (i + 22), "worker arena")
''')
    source.write_text('''
from p"workers.jo" import check_workers
$runtime_checks
make=(seed:int64):>array<int64>=>{
    let scratch=Arena[]
    let out:array<int64>=[]
    loop round in [0..5) {
        out=$allocator(@scratch) {
            let rows:array<array<int64>>=[]
            loop r in [0..37) {
                let row:array<int64>=[]
                loop c in [0..9) {row.push(seed+r+c+round)}
                rows.push(row)
            }
            rows[36]
        }
        scratch.reset()
    }
    out
}
main=()=>{
    loop round in [0..3) {check_workers()}
    concurrent {let a=spawn make(100) let b=spawn make(200)}
    if a is? array<int64> {$runtime_assert a[8] =? 148} else {panic("task a failed")}
    if b is? array<int64> {$runtime_assert b[8] =? 248} else {panic("task b failed")}
    check_workers()
    printl"ok"
}
''')
    binary = tmp_path / 'program'
    built = subprocess.run([compiler, 'build', source, '-o', binary,
                            *(['--release'] if release else [])],
                           capture_output=True, text=True, timeout=60)
    assert built.returncode == 0, built.stdout + built.stderr
    for threads in ('1', '4'):
        ran = subprocess.run([binary], env=dict(os.environ, DEWY_THREADS=threads),
                             capture_output=True, text=True, timeout=30)
        assert ran.returncode == 0, ran.stdout + ran.stderr
        assert ran.stdout == 'ok\n'
