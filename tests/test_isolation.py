"""Ambient isolation must never depend on a source pathname."""
from pathlib import Path
import subprocess

import pytest

from tests.support import compiler


FIXTURES = Path(__file__).parent / 'fixtures/isolation'


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
@pytest.mark.parametrize('name', ['pathname', 'snapshot'])
def test_isolation_pathname(compiler, tmp_path, release, name):
    results = []
    for directory in ('ordinary', 'lib/core'):
        location = tmp_path / directory
        location.mkdir(parents=True)
        source = location / f'{name}.jo'
        source.write_text((FIXTURES / source.name).read_text())
        program = location / 'program'
        built = subprocess.run(
            [compiler, 'build', source, '-o', program,
             *(['--release'] if release else [])],
            capture_output=True, text=True, timeout=60)
        assert built.returncode == 0, built.stdout + built.stderr
        ran = subprocess.run([program], capture_output=True, text=True, timeout=10)
        results.append((ran.returncode, ran.stdout))
        if name == 'pathname':
            assert ran.returncode == 101, ran.stdout + ran.stderr
            assert 'index 2' in ran.stdout + ran.stderr
        else:
            assert ran.returncode == 0, ran.stderr
            assert ran.stdout == '[11, 21, 31]\n[10, 20, 30]\n'
    assert results[0] == results[1]


def build_run(compiler, tmp_path, source, release=False, *, ir=False):
    path = tmp_path / 'case.jo'
    path.write_text(source)
    program = tmp_path / 'program'
    built = subprocess.run(
        [compiler, 'build', path, '-o', program,
         *(['--release'] if release else []), *(['--ir'] if ir else [])],
        capture_output=True, text=True, timeout=60)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([program], capture_output=True, text=True, timeout=10)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    return ran.stdout, built.stdout


SNAPSHOT = '''g: int[] = [10, 20, 30]
saved: int[] = []
snapshot = (): saved = g
{extra}
bump = (xs: mut int[]):
    loop i in [0..xs.len()):
        if i == 0: {operation}
        xs[i] += 1
main = ():
    bump(mut g)
    print(g)
    print(saved)
'''

SNAPSHOT_CASES = {
    'record-callback': ('''struct Holder:
    callback: () -> void
invoke = (h: Holder): h.callback()
wrapper = (): invoke(Holder(snapshot))''', 'wrapper()'),
    'array-callback': ('''invoke = (callbacks: (() -> void)[]): callbacks[0]()
wrapper = (): invoke([snapshot])''', 'wrapper()'),
    'nested-record-array-callback': ('''struct Holder:
    callbacks: (() -> void)[]
invoke = (h: Holder): h.callbacks[0]()
wrapper = (): invoke(Holder([snapshot]))''', 'wrapper()'),
    'partial': ('''capture = (unused: int): snapshot()
wrapper = ():
    cb = capture(_)
    cb(0)''', 'wrapper()'),
    'mutual-recursion': ('''left = (n: int) -> void:
    if n > 0: right(n - 1)
right = (n: int) -> void:
    if n > 0: left(n - 1)
    snapshot()
wrapper = (): left(3)''', 'wrapper()'),
    'default': ('''mark = () -> int:
    snapshot()
    0
wrapper = (x: int = mark()) -> int: x''', 'wrapper()'),
    'defer-normal': ('''wrapper = ():
    defer snapshot()
    pass''', 'wrapper()'),
    'defer-early': ('''wrapper = (early: bool):
    defer snapshot()
    if early: return
    pass''', 'wrapper(true)'),
    'formatter': ('''struct Marker:
    value: int
__fmt = (buf: mut u8[], value: Marker):
    snapshot()
    buf.push(120 as u8)
wrapper = () -> str: "{Marker(0)}"''', 'wrapper()'),
    'aggregate-equality': ('''struct Marker:
    value: int
(==) = (a: Marker, b: Marker) -> bool:
    snapshot()
    a.value == b.value
wrapper = () -> bool: [Marker(1)] == [Marker(1)]''', 'wrapper()'),
    'aggregate-hash': ('''struct Marker:
    value: int
hash = (a: Marker) -> u64:
    snapshot()
    a.value as u64
wrapper = () -> u64: hash([Marker(1)])''', 'wrapper()'),
    'deferred-equality-early': ('''struct Marker:
    value: int
(==) = (a: Marker, b: Marker) -> bool:
    snapshot()
    a.value == b.value
compare = () -> bool: [Marker(1)] == [Marker(1)]
wrapper = (early: bool):
    defer compare()
    if early: return
    pass''', 'wrapper(true)'),
    'map-literal-hash': ('''struct Marker:
    value: int
hash = (a: Marker) -> u64:
    snapshot()
    a.value as u64
wrapper = () -> int:
    items = {Marker(1): 2}
    items.len()''', 'wrapper()'),
    'deferred-hash-normal': ('''struct Marker:
    value: int
hash = (a: Marker) -> u64:
    snapshot()
    a.value as u64
wrapper = ():
    defer hash([Marker(1)])
    pass''', 'wrapper()'),
}


# Exercise hooks directly in a loop too: the storage/uniqueness consumers must
# see implicit effects even when there is no explicit wrapper call to query.
for name, operation in (
    ('aggregate-equality', '[Marker(1)] == [Marker(1)]'),
    ('aggregate-hash', 'hash([Marker(1)])'),
    ('map-literal-hash', '{Marker(1): 2}'),
    ('formatter', '"{Marker(0)}"'),
):
    SNAPSHOT_CASES['direct-' + name] = (SNAPSHOT_CASES[name][0], operation)
for name in ('aggregate-hash', 'formatter'):
    extra = SNAPSHOT_CASES[name][0].replace('wrapper =', 'hook_value =')
    extra += "\nwrapper = ():\n    defer hook_value()\n    return\n"
    SNAPSHOT_CASES['deferred-early-' + name] = (extra, 'wrapper()')


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
@pytest.mark.parametrize('name', SNAPSHOT_CASES)
def test_isolation_hidden_snapshot(compiler, tmp_path, release, name):
    extra, operation = SNAPSHOT_CASES[name]
    source = SNAPSHOT.format(extra=extra, operation=operation)
    out, _ = build_run(compiler, tmp_path, source, release)
    assert out == '[11, 21, 31]\n[10, 20, 30]\n'


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
@pytest.mark.parametrize('operation', ['g.reserve(10000)', 'data(g)'])
def test_isolation_storage_relocation(compiler, tmp_path, release, operation):
    source = '''g: int[] = [10, 20, 30]
saved: int[] = []
relocate = ():
    OPERATION
    g[1] = 99
sum = (xs: mut int[]) -> int:
    total = 0
    loop i in [0..xs.len()):
        if i == 0: relocate()
        total += xs[i]
    total
main = ():
    saved = g
    print(sum(mut g))
    print(saved)
'''.replace('OPERATION', operation)
    out, _ = build_run(compiler, tmp_path, source, release)
    assert out == '139\n[10, 20, 30]\n'


LEAF = '''@noinline
leaf = (i: int) -> int: i + 1
@noinline
wrapper = (i: int) -> int: leaf(i)
sum = (xs: mut int[]) -> int:
    s = 0
    loop i in [0..xs.len()): s += xs[i] + wrapper(i)
    s
main = ():
    xs = [10, 20, 30]
    print(sum(mut xs))
'''


def function_ir(ir, name):
    import re
    return re.search(r'^fn f_' + name + r'_\d+ .*?(?=^fn |\Z)',
                     ir, flags=re.M | re.S).group()


def test_isolation_leaf_recovers_bounds(compiler, tmp_path):
    out, ir = build_run(compiler, tmp_path, LEAF, ir=True)
    assert out == '66\n'
    # A retained bounds check uses unsigned index >= length and the panic call.
    # Signed loop-control comparisons remain. This is an optimization assertion,
    # independent of pathname, result constant folding, or runtime success alone.
    assert ' = geu ' not in function_ir(ir, 'sum')
    unsafe = LEAF.replace('@noinline\nleaf', 'global: int[] = []\n@noinline\nleaf')
    unsafe = unsafe.replace('i + 1', 'i + 1 + global.len()')
    _, ir = build_run(compiler, tmp_path, unsafe, ir=True)
    assert ' = geu ' in function_ir(ir, 'sum')


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_isolation_generic_instances(compiler, tmp_path, release):
    source = '''g: int[] = [10, 20, 30]
saved: int[] = []
hook = (value: int) -> int: value
hook = (callback: () -> void) -> int:
    callback()
    0
invoke[T] = (value: T) -> int: hook(value)
snapshot = (): saved = g
bump = (xs: mut int[]):
    loop i in [0..xs.len()):
        invoke(0)
        if i == 0: invoke(snapshot)
        xs[i] += 1
main = ():
    bump(mut g)
    print(g)
    print(saved)
'''
    out, _ = build_run(compiler, tmp_path, source, release)
    assert out == '[11, 21, 31]\n[10, 20, 30]\n'


def test_isolation_summary_graph(compiler, tmp_path):
    program = tmp_path / 'summary'
    built = subprocess.run(
        [compiler, 'build', FIXTURES / 'summary_graph.jo', '-o', program],
        capture_output=True, text=True, timeout=60)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([program], capture_output=True, text=True, timeout=10)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert ran.stdout == 'summary graph ok\n'


def test_isolation_relocated_library(compiler, tmp_path):
    import os
    import shutil
    library = compiler.parent.parent / 'lib'
    relocated = tmp_path / 'relocated-bundle'
    shutil.copytree(library, relocated)
    source = tmp_path / 'leaf.jo'
    source.write_text(LEAF.replace('leaf(i)', 'abs(i)'))
    results = []
    for lib in (library, relocated):
        program = tmp_path / 'program'
        built = subprocess.run(
            [compiler, 'build', source, '--ir', '-o', program],
            env={**os.environ, 'DEWY_CORE_LIB': str(lib)},
            capture_output=True, text=True, timeout=60)
        assert built.returncode == 0, built.stdout + built.stderr
        ran = subprocess.run([program], capture_output=True, text=True, timeout=10)
        assert ran.returncode == 0, ran.stderr
        decision = function_ir(built.stdout, 'sum').count(' = geu ')
        results.append((ran.stdout, decision))
    assert results == [('63\n', 0), ('63\n', 0)]


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_isolation_actual_argument_exclusions(compiler, tmp_path, release):
    source = '''g: int[] = [10, 20, 30]
saved: int[] = []
keep = (xs: int[]) -> int[]: xs
relocate = (xs: mut int[]):
    xs.reserve(10000)
    xs[1] = 99
bump = (xs: mut int[]):
    loop i in [0..xs.len()):
        if i == 0:
            saved = keep(xs)
            relocate(mut xs)
        xs[i] += 1
main = ():
    bump(mut g)
    print(g)
    print(saved)
'''
    out, _ = build_run(compiler, tmp_path, source, release)
    assert out == '[11, 100, 31]\n[10, 20, 30]\n'


def test_isolation_safe_recursive_wrapper(compiler, tmp_path):
    source = LEAF.replace(
        'leaf = (i: int) -> int: i + 1',
        '''leaf = (i: int) -> int: if i == 0: 1 else: right(i - 1) + 1
@noinline
right = (i: int) -> int: if i == 0: 1 else: leaf(i - 1) + 1''')
    out, ir = build_run(compiler, tmp_path, source, ir=True)
    assert out == '66\n'
    assert ' = geu ' not in function_ir(ir, 'sum')


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_isolation_raw_assignment_target(compiler, tmp_path, release):
    source = '''g: int[] = [10, 20, 30]
saved: int[] = []
slot = &g
sum = (xs: mut int[]) -> int:
    total = 0
    loop i in [0..xs.len()):
        if i == 0: slot[0] = [100, 200, 300]
        total += xs[i]
    total
main = ():
    saved = g
    print(sum(mut g))
    print(saved)
'''
    out, _ = build_run(compiler, tmp_path, source, release)
    assert out == '600\n[10, 20, 30]\n'
