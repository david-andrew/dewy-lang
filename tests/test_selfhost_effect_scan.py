"""Demanded node and place scans preserve effects, range proofs and ownership routes."""
import json
import re
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401
from tests.selfhost_expr_double import compare_leaf
from tests.selfhost_lower_double import modules_for


DRIVER = r'''
use 'main.jo'
use 'effects.jo'
use 'effect_graph.dewy'
use 'effect_types.dewy'
use 'places.jo'
use 'types.jo'
use 'type_ops.dewy'
use 'check.jo'
use 'ast.jo'
use 'expr.jo'
use 'checker_state.dewy'
use 'node_store.dewy'
use 'isolation.jo'
main = ():
    selfhost_test_bind()
    init_types()
    fns.resize(4)
    effect_graph_reset()
    n = nodes.len()
    nodes.push(Node(kind=.int_lit, type=i32(T_MATH_INT), ival=7))
    assert(effect_small(n) == 7 and effect_small(n, 9) == -1)
    assert(effect_word(n) and effect_integer(n))
    assert(effect_unwidened(n) == n and effect_narrowed(n) == n)
    assert(effect_field_root(n) == n and not effect_temporary_field(n))
    assert(not effect_self_contract(T_INT) and not effect_single_index(n))
    assert(not effect_index_read(n) and not effect_place_inventory(n))
    assert(not effect_range_loop(n) and not effect_big_range_loop(n))
    assert(not effect_fixed_literal(n) and not effect_bare(n))
    assert(not effect_readonly_binding(n) and not effect_oom_frame(n))
    assert(effect_route(n, 33) == PlaceIdentity(.local, 0, 0))
    effect_target_parts(1, 0)
    l = locals.len()
    locals.push(Local(type=i32(T_INT), owner=1, flags=i32(LF_PARAM | LF_MUTPARAM)))
    fns[1].params = [l]
    ref = nodes.len()
    nodes.push(Node(kind=.ident, type=i32(T_INT), aux=i32(int(SK.local)), sym=i32(l)))
    assert(effect_place_inventory(ref))
    assert(effect_route(ref) == PlaceIdentity(.local, 1, l))
    assert(effect_export(1, effect_route(ref)) == PlaceIdentity(.formal, 1, 1))
    effect_access(1, ref, true)
    assert(effect_summaries[1].events == [EffectEvent(EffectAtom(.write, PlaceIdentity(.formal, 1, 1)), ref)])
    effect_isolation_block(1, .node, n)
    effect_isolation_block(1, .global_, ref)
    assert(effect_summaries[1].isolation == .node and effect_summaries[1].isolation_witness == n)
    effect_seen.resize(nodes.len())
    effect_scan_node(1, ref)
    assert(effect_seen[ref] == 1)
    print("scan ok")
'''


@pytest.mark.parametrize('optimized', [False, True], ids=['default', 'release'])
def test_effect_scan_execution(compiler, tmp_path, monkeypatch, optimized):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    modules = modules_for(tmp_path / 'unused.dewy', tmp_path / 'unused', 'effect_scan')
    bindings = re.findall(r'^    (lower_test_bind_\w+\(\))$', modules['main.jo'], re.M)
    modules['main.jo'] += '\nselfhost_test_bind = ():\n' + ''.join('    ' + b + '\n' for b in bindings)
    out = compare_leaf(compiler, tmp_path, optimized, DRIVER,
                       extra_stems=('effect_scan',), jo_doubles=modules)
    assert out == b'scan ok\n'


@pytest.mark.parametrize('optimized', [False, True], ids=['default', 'release'])
@pytest.mark.parametrize('case', ['summary_budget_widening', 'fixed_array_kernels', 'counted_loop_exits'])
def test_effect_scan_programs(compiler, tmp_path, monkeypatch, optimized, case):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    source, output = tmp_path / 'input.dewy', tmp_path / 'program'
    source.write_text((ROOT / 'tests/cases/effects' / (case + '.dewy')).read_text())
    driver = ("use 'main.jo'\nmain = ():\n    lower_test_cli()\n"
              f'    print(read_file({json.dumps(str(output))}) ?? "")\n')
    image = compare_leaf(compiler, tmp_path, False, driver,
                         extra_stems=('effect_scan',),
                         jo_doubles=modules_for(source, output, 'effect_scan',
                                                flags=('--release',) if optimized else ()))
    assert image == output.read_bytes() + b'\n'
    ran = subprocess.run([output], capture_output=True, timeout=30)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout == (ROOT / 'tests/cases/effects' / (case + '.out')).read_bytes()


def test_effect_scan_diagnostics(compiler, tmp_path, monkeypatch):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    source, output = tmp_path / 'input.dewy', tmp_path / 'program'
    source.write_text((ROOT / 'tests/cases/effects/fixed_index_unproved.dewy').read_text())
    modules = modules_for(source, output, 'effect_scan')
    modules['util.jo'], count = re.subn(
        r'(?m)^fatal = \(p0: int, msg0: str\):\n(?:[ \t].*\n|\n)*',
        'fatal = (p0: int, msg0: str):\n    print(msg0)\n    exit(41)\n\n',
        modules['util.jo'], count=1)
    assert count == 1
    driver = "use 'main.jo'\nmain = ():\n    lower_test_cli()\n"
    out = compare_leaf(compiler, tmp_path, False, driver, status=41,
                       extra_stems=('effect_scan',), jo_doubles=modules)
    assert out
