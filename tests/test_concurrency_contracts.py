"""Transfer, memory order and waiting-lane obligations, including check-only."""
import os
import subprocess

import pytest

from tests.support import compiler


def check(compiler, tmp_path, text, mode='check'):
    source = tmp_path / 'concurrency.dewy'
    source.write_text(text)
    return subprocess.run([compiler, mode, source, *(['-o', tmp_path / 'program'] if mode == 'build' else [])],
                          env=dict(os.environ, SLOPPY_STOP='check') if mode == 'check' else os.environ,
                          capture_output=True, text=True, timeout=60)


@pytest.mark.core_quick
@pytest.mark.parametrize('body', ['sleep(1ms)', 'waiter()'])
def test_parallel_rejects_waiting(compiler, tmp_path, body):
    result = check(compiler, tmp_path,
                   f'waiter=()=>sleep(1ms)\nmain=()=>{{parallel i in [0..2) {{{body}}}}}')
    assert result.returncode != 0
    assert 'parallel body may block' in result.stderr, result.stderr


@pytest.mark.parametrize('body', ['sleep(1ms)', 'waiter()', 'printl"blocked"'])
def test_no_blocks_transitive(compiler, tmp_path, body):
    result = check(compiler, tmp_path,
                   f'waiter=()=>sleep(1ms)\nbad=():>void & no blocks=>{{{body}}}\nmain=()=>{{bad()}}')
    assert result.returncode != 0
    assert 'blocking operation' in result.stderr, result.stderr


@pytest.mark.core_quick
def test_no_blocks_scalar(compiler, tmp_path):
    result = check(compiler, tmp_path,
                   'twice=(n:int64):>int64 & no blocks=>n*2\nmain=()=>{assert(twice(21)=?42)}')
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize('operation,diagnostic', [
    ("a.load'release'", 'load cannot use'),
    ("a.store(1 'acquire')", 'store cannot use'),
    ("a.add(1 'consume')", 'MemoryOrder must be'),
    ("a.load(order)", 'compile-time literal'),
])
def test_invalid_memory_order(compiler, tmp_path, operation, diagnostic):
    result = check(compiler, tmp_path,
                   f'main=()=>{{let a=atomic(0) let order="relaxed" {operation}}}')
    assert result.returncode != 0
    assert diagnostic in result.stderr, result.stderr


@pytest.mark.core_quick
def test_atomic_orders_and_structural_payloads(compiler, tmp_path):
    result = check(compiler, tmp_path, '''
main=()=>{
 let a=atomic(0)
 let payload=[value=[1 2 3] count=a]
 let sums=[parallel i in [0..128) {
   payload.count.add(1 'relaxed')
   sum(payload.value)+i
 }]
 assert(a.load'acquire' =? 128)
 a.store(42 'release')
 assert(a.load() =? 42)
 assert(sums.length =? 128)
}
''', 'build')
    assert result.returncode == 0, result.stderr
    for threads in (1, 2):
        ran = subprocess.run([tmp_path / 'program'], env=dict(os.environ, SLOPPY_THREADS=str(threads)),
                             capture_output=True, text=True, timeout=20)
        assert ran.returncode == 0, ran.stderr


@pytest.mark.parametrize('payload', ['int8', 'uint8', 'int32', 'uint64'])
def test_atomic_fixed_width_wrap(compiler, tmp_path, payload):
    maximum = {'int8': 127, 'uint8': 255, 'int32': 2147483647, 'uint64': 18446744073709551615}[payload]
    expected = {'int8': -128, 'uint8': 0, 'int32': -2147483648, 'uint64': 0}[payload]
    result = check(compiler, tmp_path, f'''
main=()=>{{
 let a=atomic<{payload}>({maximum})
 assert(a.add(1) =? {expected})
 assert(a.load() =? {expected})
 assert(a.compare_swap({expected} 5))
 assert(a.load() =? 5)
}}
''', 'build')
    assert result.returncode == 0, result.stderr
    ran = subprocess.run([tmp_path / 'program'], capture_output=True, text=True, timeout=20)
    assert ran.returncode == 0, ran.stderr


def test_non_atomic_storage_in_product_rejected(compiler, tmp_path):
    (tmp_path / 'handle.jo').write_text('''struct LocalHandle:
    p: *int
make_local = () -> LocalHandle: LocalHandle(null)
read = (h: LocalHandle) -> int: h.p[0]
''')
    result = check(compiler, tmp_path, '''
from p"handle.jo" import make_local, read
main=()=>{
 let record=[nested=[make_local()]]
 let results=[parallel i in [0..2) read(record.nested[0])+i]
}
''')
    assert result.returncode != 0
    assert 'inferred Send/Sync' in result.stderr, result.stderr


@pytest.mark.parametrize('callback,accepted', [('@quiet', True), ('@f', False)])
def test_callback_blocking_contract(compiler, tmp_path, callback, accepted):
    result = check(compiler, tmp_path, f'''
run=(f:<():>void & no blocks>):>void & no blocks=>f()
quiet=():>void=>{{}}
forward=(f:<():>void>):>void=>run({callback})
main=()=>{{forward(@quiet)}}
''')
    assert (result.returncode == 0) == accepted, result.stderr
    if not accepted:
        assert 'effect' in result.stderr, result.stderr


def test_non_sync_global_rejected(compiler, tmp_path):
    (tmp_path / 'handle.jo').write_text('''struct LocalHandle:
    p: *int
shared = LocalHandle(null)
read = () -> int: shared.p[0]
''')
    result = check(compiler, tmp_path, '''
from p"handle.jo" import read
main=()=>{let results=[parallel i in [0..2) read()+i]}
''')
    assert result.returncode != 0
    assert 'inferred Sync' in result.stderr, result.stderr


@pytest.mark.parametrize('constructor,diagnostic', [
    ('Atomic<int64>[]', 'construct Atomic with atomic(value)'),
    ('TaskGroup[]', 'task handles are created by concurrent and spawn'),
    ('Task<int64>[]', 'task handles are created by concurrent and spawn'),
])
def test_synchronized_handles_cannot_forge_private_storage(compiler, tmp_path, constructor, diagnostic):
    result = check(compiler, tmp_path, f'main=()=>{{let handle={constructor}}}')
    assert result.returncode != 0
    assert diagnostic in result.stderr, result.stderr


@pytest.mark.parametrize('body', [
    'let values:array<Atomic<int64> length=2>=[]',
    'let value=CachePadded<Atomic<int64>>[]',
    'let values:array<TaskGroup length=2>=[]',
    'let values:array<CachePadded<Atomic<int64>> length=2>=[]',
    'let values:array<Atomic<int64>>=[] values.resize(2)',
])
def test_zero_fill_cannot_create_synchronized_handles(compiler, tmp_path, body):
    result = check(compiler, tmp_path, f'main=()=>{{{body}}}')
    assert result.returncode != 0
    assert 'zero initialization cannot create private synchronized handles' in result.stderr, result.stderr


def test_explicit_synchronized_elements_and_empty_containers(compiler, tmp_path):
    result = check(compiler, tmp_path, """
main=()=>{
 let values:array<Atomic<int64> length=2>=[atomic(1) atomic(2)]
 let empty:array<Atomic<int64>>=[]
 let padded=CachePadded<Atomic<int64>>[value=atomic(3)]
 assert(values[0].load() =? 1 and padded.value.load() =? 3)
}
""")
    assert result.returncode == 0, result.stderr
