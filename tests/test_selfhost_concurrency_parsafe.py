"""Parallel callback requirements and diagnostics match the frozen twin."""
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
use 'types.jo'
use 'type_ops.dewy'
use 'check.jo'
use 'ast.jo'
use 'util.jo'
use 'node_store.dewy'
use "checker_types.dewy"
use "checker_state.dewy"
main = ():
    selfhost_test_bind()
    init_types()
    fns.resize(3)
    l = locals.len()
    locals.push(Local(name=i32(intern("f")), flags=i32(LF_PARAM), owner=1))
    fns[1].params = [l]
    a = mk(.ident, 0); nodes[a].aux = i32(int(SK.local)); nodes[a].sym = i32(l)
    wrap = mk(.conv, 0); nodes[wrap].a = i32(a)
    assert(parsafe_param(wrap) == (1, 0))
    cap = locals.len()
    locals.push(Local(flags=i32(LF_CAPTURE), outer=i32(l)))
    assert(parsafe_param_local(cap) == (1, 0))
    assert(not parsafe_vouched(a) and not parsafe_vouched_local(cap))
    parsafe_require(1, 0, ParSafeVia(a, 0, 0))
    parsafe_require(1, 0, ParSafeVia(99, 2, 3))
    assert(parsafe_work == [parsafe_key(1, 0)])
    assert(parsafe_req[parsafe_key(1, 0)].site == a)
    assert(parsafe_vouched(wrap) and parsafe_vouched_local(cap))
    d = mk(.fn_, 0); nodes[d].name = i32(intern("__dewy_parallel_test"))
    fns[1].decl = i32(d)
    assert(parsafe_fn_name(1) == "__dewy_parallel_test")
    assert(parsafe_fn_name(2) == "this function")
    assert(parsafe_param_name(1, 0) == "f")
    call = mk(.call, 0); nodes[call].sym = 1
    assert(parsafe_parallel_name(call) == "`parallel`")
    partial = mk(.partial, 0); nodes[partial].sym = 2; nodes[partial].d = 999
    loopn = mk(.for_, 0); nodes[loopn].c = 999; nodes[loopn].d = 999
    block = mk(.block, 0)
    node_set_list(mut nodes, mut lists, block, [call, partial, loopn])
    head: {int: int}; calls: int[]; next: int[]; values: int[]
    parsafe_index(block, head, calls, next, values)
    assert(head[1] == 0 and calls == [call] and next == [-1] and values == [partial])
    # An ordinary non-parameter must not inherit the requirement.
    locals[l].flags = 0
    assert(parsafe_param_local(l) == (0, -1))
    print("parsafe ok")
'''



@pytest.mark.parametrize('optimized', [False, True], ids=['default', 'release'])
def test_concurrency_parsafe_execution(compiler, tmp_path, monkeypatch, optimized):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    modules = modules_for(tmp_path / 'unused.dewy', tmp_path / 'unused', 'concurrency_parsafe')
    bindings = re.findall(r'^    (lower_test_bind_\w+\(\))$', modules['main.jo'], re.M)
    modules['main.jo'] += '\nselfhost_test_bind = ():\n' + ''.join('    ' + b + '\n' for b in bindings)
    out = compare_leaf(compiler, tmp_path, optimized, DRIVER,
                       extra_stems=('concurrency_parsafe',), jo_doubles=modules)
    assert out == b'parsafe ok\n'


@pytest.mark.parametrize('optimized', [False, True], ids=['default', 'release'])
@pytest.mark.parametrize('case', ['two_wrappers', 'inferred_wrappers'])
def test_concurrency_parsafe_program(compiler, tmp_path, monkeypatch, optimized, case):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    source = ROOT / 'tests/cases/parallel_callbacks' / (case + '.dewy')
    output = tmp_path / 'program'
    driver = ("use 'main.jo'\nmain = ():\n    lower_test_cli()\n"
              f'    print(read_file({json.dumps(str(output))}) ?? "")\n')
    image = compare_leaf(compiler, tmp_path, False, driver,
                         extra_stems=('concurrency_parsafe',),
                         jo_doubles=modules_for(source, output, 'concurrency_parsafe',
                                                flags=('--release',) if optimized else ()))
    assert image == output.read_bytes() + b'\n'
    ran = subprocess.run([output], capture_output=True, timeout=30)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout == source.with_suffix('.out').read_bytes()


@pytest.mark.parametrize('case', ['value_use'])
def test_concurrency_parsafe_diagnostics(compiler, tmp_path, monkeypatch, case):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    source = ROOT / 'tests/cases/parallel_callbacks' / (case + '.dewy')
    modules = modules_for(source, tmp_path / 'program', 'concurrency_parsafe')
    modules['util.jo'], count = re.subn(
        r'(?m)^fatal = \(p0: int, msg0: str\):\n(?:[ \t].*\n|\n)*',
        'fatal = (p0: int, msg0: str):\n    print(msg0)\n    exit(41)\n\n',
        modules['util.jo'], count=1)
    assert count == 1
    out = compare_leaf(compiler, tmp_path, False,
                       "use 'main.jo'\nmain = ():\n    lower_test_cli()\n",
                       status=41, extra_stems=('concurrency_parsafe',), jo_doubles=modules)
    assert b'parallel' in out or b'many threads' in out
