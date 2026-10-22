"""Scoped jobs survive promotion, nested helping, wraparound and failure."""
import os
import subprocess

import pytest

from tests.support import compiler


def build(compiler, tmp_path, source, suffix='dewy'):
    path = tmp_path / f'fork_join.{suffix}'
    path.write_text(source)
    binary = tmp_path / 'fork_join'
    result = subprocess.run([compiler, 'build', path, '--release', '-o', binary],
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    return binary


def run(binary, workers):
    return subprocess.run([binary], env=dict(os.environ, SLOPPY_THREADS=str(workers)),
                          capture_output=True, text=True, timeout=30)


@pytest.mark.core_quick
@pytest.mark.parametrize('scalar', ['int64', 'float32', 'float64'])
def test_scalar_tree_and_nested_collectors(compiler, tmp_path, scalar):
    binary = build(compiler, tmp_path, '''
tree=(n:int64 offset:int64):>TYPE=>{
 if n =? 0 return TYPE(offset%17)
 let parts=[parallel i in [0..2) tree(n-1 offset*2+i)]
 return parts[0]-parts[1]*TYPE(0.5)
}
main=()=>{
 loop round in [0..4) {
  let values=[parallel i in [0..17) [parallel j in [0..5) tree(12 i*5+j)]]
  loop i in [0..17) {loop j in [0..5) {printl"{values[i][j]}"}}
 }
 return 0
}
'''.replace('TYPE(0.5)', 'TYPE(2)' if scalar == 'int64' else 'TYPE(0.5)').replace('TYPE', scalar))
    serial = run(binary, 1)
    assert serial.returncode == 0, serial.stderr
    for _ in range(3):
        parallel = run(binary, 2)
        assert parallel.returncode == 0, parallel.stderr
        assert parallel.stdout == serial.stdout


@pytest.mark.parametrize('managed', [False, True])
def test_panic_in_nested_job(compiler, tmp_path, managed):
    body = ('let rows=[parallel k in [0..17) [parallel j in [0..129) '
            '{if k =? 16 and j =? 128 panic("nested fork failure") j}]]\n'
            'printl"{rows.length}"' if managed else
            'let parts=[parallel i in [0..2) {if i =? 1 panic("nested fork failure") fib(27)}]\n'
            'printl"{parts[0]+parts[1]}"')
    binary = build(compiler, tmp_path, '''
fib=(n:int64):>int64=>{if n <? 2 return n return fib(n-1)+fib(n-2)}
main=()=>{BODY return 0}
'''.replace('BODY', body))
    for workers in (1, 2):
        result = run(binary, workers)
        assert result.returncode != 0
        assert 'nested fork failure' in result.stderr


def test_deque_wraparound_and_full_fallback(compiler, tmp_path):
    # Exercise owner/thief ends and full-ring behavior without depending on
    # which OS worker happens to run during a short test.
    binary = build(compiler, tmp_path, '''
main = () -> int:
    __fj_ctl = __os_pages(64) as *int
    q = __os_pages(__fj_WORDS * 8) as *int
    loop round in [0..12):
        loop i in [0..__fj_CAP): assert(__fj_push(q, (i + 1) as *int))
        assert(not __fj_push(q, 123 as *int))
        loop i in [0..__fj_CAP / 2): assert(__fj_steal(q) as int == i + 1)
        i = __fj_CAP
        loop i > __fj_CAP / 2:
            assert(__fj_pop(q) as int == i)
            i -= 1
        assert(__fj_pop(q) == null)
        assert(__fj_steal(q) == null)
        assert(__fj_push(q, 42 as *int))
        assert(__fj_pop(q) as int == 42)
        assert(__fj_push(q, 43 as *int))
        assert(__fj_steal(q) as int == 43)
    return 0
''', 'jo')
    result = run(binary, 1)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize('scalar', ['int8', 'int16', 'int32', 'uint8', 'uint16', 'uint32'])
def test_scalar_job_result_width(compiler, tmp_path, scalar):
    expression = 'i-5' if scalar.startswith('int') else 'i+128'
    binary = build(compiler, tmp_path, '''
main=()=>{
 let values=[parallel i in [0..8) TYPE(EXPR)]
 printl"{values[0]} {values[3]} {values[7]}"
 return 0
}
'''.replace('TYPE', scalar).replace('EXPR', expression))
    serial = run(binary, 1)
    parallel = run(binary, 2)
    assert serial.returncode == parallel.returncode == 0, serial.stderr + parallel.stderr
    assert parallel.stdout == serial.stdout
    assert serial.stdout == ('-5 -2 2\n' if scalar.startswith('int') else '128 131 135\n')


@pytest.mark.parametrize("managed", [False, True])
def test_fused_scalar_region_helpers(compiler, tmp_path, managed):
    import platform
    import sys
    from tests.test_core_fused_determinism import build as fused_build
    if not sys.platform.startswith('linux') or platform.machine().lower() not in ('x86_64', 'amd64'):
        pytest.skip('fused emission is x86-64 Linux only')
    source = tmp_path / 'fused.dewy'
    program = '''
fork=(n:int64):>int64=>{
 if n <? 2 return n
 let parts=[parallel i in [0..2) fork(n-1-i)]
 return parts[0]+parts[1]
}
main=():>void=>{printl"{fork(25)}"}
'''
    if managed:
        program = program.replace(':>int64=>', ':>array<int64>=>').replace('return n', 'return [n]').replace('return parts[0]+parts[1]', 'return [parts[0][0]+parts[1][0]]').replace('fork(25)}', 'fork(25)[0]}')
    source.write_text(program)
    one, _ = fused_build(compiler, source, tmp_path / 'one', 1, SLOPPY_EMIT_FORCE='1')
    two, log = fused_build(compiler, source, tmp_path / 'two', 2,
                           SLOPPY_EMIT_FORCE='1', SLOPPY_PAR_TIME='1')
    assert 'fused: 2 workers' in log, log
    assert two == one
    result = run(tmp_path / 'two', 2)
    assert result.returncode == 0, result.stderr
    assert result.stdout == '75025\n'


@pytest.mark.core_quick
def test_managed_region_ownership(compiler, tmp_path):
    binary = build(compiler, tmp_path, '''
tree=(a:array<int64> depth:int64):>array<int64>=>{
 if depth =? 0 return a
 let parts=[parallel i in [0..2) tree(a depth-1)]
 if depth%2 =? 0 return parts[1]
 let left=parts[0]
 left[0]+=1
 assert(parts[1][0] =? a[0]+(depth-1)//2)
 return left
}
work=():>void=>{
 let input:array<int64>=[10 20 30]
 let output=tree(input 12)
 assert(input =? [10 20 30])
 assert(output =? [16 20 30])
}
main=()=>{
 work()
 let before=alloc_count()
 loop i in [0..12) {work()}
 assert(alloc_count() =? before)
 return 0
}
''')
    for workers in (1, 2):
        result = run(binary, workers)
        assert result.returncode == 0, result.stdout + result.stderr


def test_promoted_tail_is_split(compiler, tmp_path):
    # Force one promoted wide job, with no OS scheduling or timing assertion.
    # Its parallel entry only accepts leaves; the serial entry accepts chunks.
    binary = build(compiler, tmp_path, '''
leaf = (j: *int):
    assert(j[3] - j[2] == 1)
    (j[4] as *int)[j[2] - 3] = j[2] * 7
serial = (j: *int):
    loop i in [j[2]..j[3]): (j[4] as *int)[i - 3] = i * 7
main = () -> int:
    __fj_ctl = __os_pages(64) as *int
    __fj_deques = __os_pages(__fj_WORDS * 8) as *int
    __fj_deques[35] = 1 << 62  # no secondary promotion in this deterministic test
    output = fill(0, 8)
    a: (*int) -> void = leaf
    b: (*int) -> void = serial
    job = __fj_Job(((&a) as *int)[0], 0, 3, 11, data(output) as int,
                  ((&b) as *int)[0], 0, 1, 0, 0)
    __fj_execute((&job) as *int)
    assert(job.done == 1)
    loop i in [0..8): assert(output[i] == (i + 3) * 7)
    return 0
''', 'jo')
    result = run(binary, 1)
    assert result.returncode == 0, result.stdout + result.stderr


def test_scope_entry_promotes_before_first_body(compiler, tmp_path):
    binary = build(compiler, tmp_path, '''
body = (j: *int): (j[4] as *int)[0] = 42
main = () -> int:
    root = __fj_enter()
    entry: (*int) -> void = body
    fn = ((&entry) as *int)[0]
    value = 0
    job = __fj_Job(fn, 0, 0, 1, (&value) as int, fn, 0, 0, 0, 0)
    __fj_link((&job) as *int)
    assert(job.promoted == 1)
    __fj_join((&job) as *int)
    __fj_leave(root)
    assert(value == 42)
    return 0
''', 'jo')
    result = run(binary, 2)
    assert result.returncode == 0, result.stdout + result.stderr
