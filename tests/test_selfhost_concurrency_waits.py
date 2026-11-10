"""Waiting queries settle clean closures without publishing recursive optimism."""
import re

import pytest

from tests.selfhost_diagnostic_double import diagnostic_status
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
use 'expr.jo'
use 'node_store.dewy'
use "checker_types.dewy"
use "checker_state.dewy"
main = ():
    selfhost_test_bind()
    init_types()
    modules.resize(1)
    fns.resize(5)
    loop f in [1..5):
        fns[f].decl = i32(mk(.fn_, 0))
    one = mk(.call, 0); nodes[one].sym = 1
    two = mk(.call, 0); nodes[two].sym = 2
    fns[1].body = i32(two); fns[2].body = i32(one)
    assert(not concurrency_fn_blocks(1))
    assert(concurrency_block_memo.has(1) and concurrency_block_memo.has(2))
    assert(not concurrency_block_memo[1] and not concurrency_block_memo[2])
    op = mk(.int_lit, 0); nodes[op].ival = 0
    syscall = mk(.intrinsic, 0); nodes[syscall].aux = i32(int(IN.syscall))
    node_set_list(mut nodes, mut lists, syscall, [op])
    block = mk(.block, 0)
    node_set_list(mut nodes, mut lists, block, [one, syscall])
    fns[2].body = i32(block)
    concurrency_block_memo.clear()
    assert(concurrency_fn_blocks(1))
    assert(concurrency_block_memo[1] and not concurrency_block_memo.has(2))
    assert(concurrency_fn_blocks(2))
    seen: {int: bool}
    assert(concurrency_blocks(0, seen) and concurrency_blocks(99, seen))
    assert(concurrency_blocks(3, seen))
    loop number in [39, 60, 186, 204, 228]:
        nodes[op].ival = number
        seen.clear()
        assert(not concurrency_blocks_node(syscall, seen))
    nodes[op].ival = 0
    seen.clear()
    assert(concurrency_blocks_node(syscall, seen))
    region = mk(.parallel_region, 0); nodes[region].a = i32(syscall)
    seen.clear()
    assert(concurrency_blocks_node(region, seen))
    loop k in [NK.lambda, NK.fnref, NK.partial]:
        n = mk(k, 0); nodes[n].a = i32(syscall)
        assert(not concurrency_blocks_node(n, seen))
    assert(not concurrency_blocks_node(0, seen))
    print("waiting ok")
'''


@pytest.mark.parametrize('optimized', [False, True], ids=['default', 'release'])
def test_concurrency_waits_execution(compiler, tmp_path, monkeypatch, optimized):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    modules = modules_for(tmp_path / 'unused.dewy', tmp_path / 'unused', 'concurrency_waits')
    bindings = re.findall(r'^    (lower_test_bind_\w+\(\))$', modules['main.jo'], re.M)
    modules['main.jo'] += '\nselfhost_test_bind = ():\n' + ''.join('    ' + b + '\n' for b in bindings)
    out = compare_leaf(compiler, tmp_path, optimized, DRIVER,
                       extra_stems=('concurrency_waits',), jo_doubles=modules)
    assert out == b'waiting ok\n'


@pytest.mark.parametrize('case', ['parallel_callbacks/blocking_callback', 'channels/parallel_wait'])
def test_concurrency_waits_diagnostics(compiler, tmp_path, monkeypatch, case):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    source = ROOT / 'tests/cases' / (case + '.dewy')
    modules = modules_for(source, tmp_path / 'program', 'concurrency_waits')
    diagnostic_status(modules, 'fatal')
    out = compare_leaf(compiler, tmp_path, False,
                       "use 'main.jo'\nmain = ():\n    lower_test_cli()\n",
                       status=41, extra_stems=('concurrency_waits',), jo_doubles=modules)
    assert b'parallel body may block' in out
