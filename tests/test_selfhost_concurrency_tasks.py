"""Task boundaries, protocol dispatch and atomic checks match the frozen twin."""
import json
import re
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401
from tests.selfhost_expr_double import compare_leaf
from tests.selfhost_lower_double import modules_for

DRIVER = r'''
use 'main.jo'
use 'concurrency.jo'
use 'deadlock.jo'
use 'types.jo'
use 'check.jo'
use 'ast.jo'
use 'util.jo'
use 'node_store.dewy'
use "checker_types.dewy"
use "checker_state.dewy"
main = ():
    selfhost_test_bind()
    init_types()
    fns.resize(2); modules.resize(1)
    d = mk(.fn_, 0); nodes[d].mod = 7; nodes[d].name = i32(intern("serve"))
    fns[1].decl = i32(d)
    n = mk(.call, 0); nodes[n].sym = 1
    concurrency_protocol_module = 7
    assert(concurrency_protocol_task_arg(n) == 0)
    nodes[d].name = i32(intern("pipeline"))
    assert(concurrency_protocol_task_arg(n) == 2)
    nodes[d].name = i32(intern("other"))
    assert(concurrency_protocol_task_arg(n) == -1)
    concurrency_protocol_module = -1
    assert(concurrency_protocol_task_arg(n) == -2)
    assert(not concurrency_calls_c())
    add_flag(d, NF_EXTERN); fns[1].clib = "m"
    assert(concurrency_calls_c())
    nodes[d].flags = 0
    assert(not concurrency_calls_c())
    deadlock_atomics = false
    nodes[n].aux = 1
    concurrency_atomic_call(n)
    assert(not deadlock_atomics)
    nodes[n].aux = 0
    concurrency_atomic_call(n)
    assert(deadlock_atomics)
    lit = mk(.int_lit, 0)
    conversion = mk(.conv, 0); nodes[conversion].a = i32(lit)
    concurrency_callback(conversion)
    concurrency_queue_instance(d, T_INT, 0)
    seen: {int: bool}
    concurrency_task_globals(0, seen)
    concurrency_task_globals(9, seen)
    assert(seen.len() == 0)
    fns[1].body = i32(lit)
    concurrency_task_globals(1, seen)
    assert(seen.has(1))
    print("tasks ok")
'''



@pytest.mark.parametrize('optimized', [False, True], ids=['default', 'release'])
def test_concurrency_tasks_execution(compiler, tmp_path, monkeypatch, optimized):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    modules = modules_for(tmp_path / 'unused.dewy', tmp_path / 'unused', 'concurrency_tasks')
    bindings = re.findall(r'^    (lower_test_bind_\w+\(\))$', modules['main.jo'], re.M)
    modules['main.jo'] += '\nselfhost_test_bind = ():\n' + ''.join('    ' + b + '\n' for b in bindings)
    out = compare_leaf(compiler, tmp_path, optimized, DRIVER,
                       extra_stems=('concurrency_tasks',), jo_doubles=modules)
    assert out == b'tasks ok\n'


@pytest.mark.parametrize('optimized', [False, True], ids=['default', 'release'])
@pytest.mark.parametrize('case', ['queues/mpmc_tasks', 'tasks/atomic_add_wrapping'])
def test_concurrency_tasks_program(compiler, tmp_path, monkeypatch, optimized, case):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    source = ROOT / 'tests/cases' / (case + '.dewy')
    output = tmp_path / 'program'
    driver = ("use 'main.jo'\nmain = ():\n    lower_test_cli()\n"
              f'    print(read_file({json.dumps(str(output))}) ?? "")\n')
    image = compare_leaf(compiler, tmp_path, False, driver,
                         extra_stems=('concurrency_tasks',),
                         jo_doubles=modules_for(source, output, 'concurrency_tasks',
                                                flags=('--release',) if optimized else ()))
    assert image == output.read_bytes() + b'\n'
    ran = subprocess.run([output], capture_output=True, timeout=30)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout == source.with_suffix('.out').read_bytes()


@pytest.mark.parametrize('operation,diagnostic', [
    ("a.load'release'", b'load cannot use'),
    ("a.store(1 'acquire')", b'store cannot use'),
    ("a.add(1 'consume')", b'MemoryOrder must be'),
])
def test_concurrency_tasks_diagnostics(compiler, tmp_path, monkeypatch, operation, diagnostic):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    source = tmp_path / 'order.dewy'
    source.write_text(f'main=()=>{{let a=atomic(0) {operation}}}')
    modules = modules_for(source, tmp_path / 'program', 'concurrency_tasks')
    modules['util.jo'], count = re.subn(
        r'(?m)^fatal = \(p0: int, msg0: str\):\n(?:[ \t].*\n|\n)*',
        'fatal = (p0: int, msg0: str):\n    print(msg0)\n    exit(41)\n\n',
        modules['util.jo'], count=1)
    assert count == 1
    out = compare_leaf(compiler, tmp_path, False,
                       "use 'main.jo'\nmain = ():\n    lower_test_cli()\n",
                       status=41, extra_stems=('concurrency_tasks',), jo_doubles=modules)
    assert diagnostic in out
