"""Demanded isolation masks, hidden edges and SCC publication match the twin."""
import json
import re
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401
from tests.selfhost_expr_double import compare_leaf
from tests.selfhost_lower_double import modules_for

DRIVER = r'''
use 'main.jo'
use 'isolation.jo'
use 'effects.jo'
use 'effect_graph.dewy'
use 'effect_types.dewy'
use 'types.jo'
use 'check.jo'
use 'ast.jo'
use 'expr.jo'
use 'ownership.jo'
use 'node_store.dewy'
use "checker_types.dewy"
use "checker_state.dewy"
main = ():
    selfhost_test_bind()
    loop k in [NK.int_lit, NK.lambda, NK.block, NK.field, NK.binary, NK.if_, NK.vardecl, NK.array, NK.call, NK.index, NK.arm, NK.pvariant, NK.fnref]:
        assert(isolation_children(k) >= 0)
    assert(isolation_children(.hole) == 0 and isolation_children(.fn_) == -1)
    assert(isolation_intrinsic(.len) and isolation_intrinsic(.hash) and not isolation_intrinsic(.syscall))
    init_types()
    fns.resize(8)
    effect_graph_reset()
    n = nodes.len()
    nodes.push(Node(kind=.int_lit, type=i32(T_INT), ival=1))
    loop f in [1..8):
        fns[f].state = 2
        fns[f].body = i32(n)
        effect_summaries[f].done = true
    # A clean recursive component and a blocked one with a backedge before its blocker.
    effect_summaries[1].edges = [EffectEdge(2, n, [])]
    effect_summaries[2].edges = [EffectEdge(1, n, [])]
    effect_summaries[3].edges = [EffectEdge(4, n, [])]
    effect_summaries[4].edges = [EffectEdge(3, n, []), EffectEdge(5, n, [])]
    effect_summaries[5].isolation = .global_
    effect_summaries[5].isolation_witness = n
    effect_summaries[6].edges = [EffectEdge(99, n, [])]
    fns[7].has_env = true
    isolation_reset()
    assert(isolation_limit == 8 and isolation_serial == 0)
    assert(instance_isolated(1) and ambient_length_stable(2))
    assert(not instance_isolated(3))
    assert(isolation_rows[3].done and isolation_rows[4].done)
    assert(isolation_rows[3].reason == .global_ and isolation_rows[3].witness == n)
    assert(not instance_isolated(6) and isolation_rows[6].reason == .unavailable)
    assert(not instance_isolated(7) and isolation_rows[7].reason == .capture)
    assert(not instance_isolated(0) and not instance_isolated(8))
    # Operation queries and direct hidden dependencies.
    call = nodes.len()
    nodes.push(Node(kind=.call, sym=1))
    assert(ambient_storage_stable(call) and ambient_sharing_stable(call))
    nodes[call].sym = 3
    assert(not isolation_operation(call))
    edges: int[]
    nodes[call].kind = .partial
    assert(isolation_effect(call, edges) == .indirect)
    nodes[call].kind = .addr
    assert(isolation_effect(call, edges) == .raw)
    assert(not isolation_operation(0) and not isolation_operation(nodes.len()))
    # Force the syntax fallback and exercise the generation stamp and child masks.
    effect_summaries[1].done = false
    nodes[call] = Node(kind=.ident, aux=i32(int(SK.global)), type=i32(T_INT))
    fns[1].body = i32(call)
    isolation_reset()
    assert(not instance_isolated(1) and isolation_rows[1].reason == .global_)
    # Lifecycle calls keep insertion order and the depth guard fails closed.
    si = structs.len()
    structs.push(StructInfo(resolved=true))
    record = types.len()
    types.push(TypeInfo(kind=.struct_, st=i32(si), flags=2))
    ownership_decls[1] = 1
    owner_map_copies[record] = 2
    ownership_copies[record] = 3
    ownership_moves[record] = 4
    assert(isolation_hooks(record, edges) and edges == [2, 3, 4])
    assert(not isolation_hooks(record, edges, 33))
    print("isolation ok")
'''


@pytest.mark.parametrize('optimized', [False, True], ids=['default', 'release'])
def test_isolation_ops_execution(compiler, tmp_path, monkeypatch, optimized):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    modules = modules_for(tmp_path / 'unused.dewy', tmp_path / 'unused', 'isolation_ops')
    bindings = re.findall(r'^    (lower_test_bind_\w+\(\))$', modules['main.jo'], re.M)
    modules['main.jo'] += '\nselfhost_test_bind = ():\n' + ''.join('    ' + b + '\n' for b in bindings)
    out = compare_leaf(compiler, tmp_path, optimized, DRIVER,
                       extra_stems=('isolation_ops',), jo_doubles=modules)
    assert out == b'isolation ok\n'


@pytest.mark.parametrize('optimized', [False, True], ids=['default', 'release'])
def test_isolation_ops_program(compiler, tmp_path, monkeypatch, optimized):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    source = tmp_path / 'hooks.dewy'
    source.write_text('$runtime_checks\n' +
                      (ROOT / 'tests/fixtures/isolation/hook_copy.dewy').read_text())
    output = tmp_path / 'program'
    driver = ("use 'main.jo'\nmain = ():\n    lower_test_cli()\n"
              f'    print(read_file({json.dumps(str(output))}) ?? "")\n')
    image = compare_leaf(compiler, tmp_path, False, driver,
                         extra_stems=('isolation_ops',),
                         jo_doubles=modules_for(source, output, 'isolation_ops',
                                                flags=('--release',) if optimized else ()))
    assert image == output.read_bytes() + b'\n'
    ran = subprocess.run([output], capture_output=True, timeout=30)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout == b''
