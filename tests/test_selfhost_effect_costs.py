"""Effect cost masks, summaries, obligations and signature opacity match the twin."""
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
use 'effect_library.jo'
use 'types.jo'
use 'ast.jo'
use 'expr.jo'
use 'check.jo'
use 'node_store.dewy'
main = ():
    selfhost_test_bind()
    init_types()
    fns.resize(4)
    effect_graph_reset()
    assert(effect_intrinsic_cost(.len) == 0)
    assert(effect_intrinsic_cost(.push) == 44)
    assert(effect_intrinsic_cost(.fmt_struct) == 1028)
    assert(effect_intrinsic_cost(.panic) == 32)
    effect_plan_cost(1, 0, 2044)
    assert(effect_summaries[1].events.len() == 9)
    loop i in [0..9): assert(int(effect_summaries[1].events[i].atom.kind) == i + 2)
    effect_graph_reset()
    effect_plan_cost(1, 0, -1)
    assert(effect_summaries[1].events == [EffectEvent(EffectAtom(.opaque), 0)])
    effect_graph_reset()
    effect_library_summary(1, .allocates_panics, 0)
    assert(effect_summaries[1].events == [EffectEvent(EffectAtom(.alloc), 0), EffectEvent(EffectAtom(.panic), 0)])
    effect_graph_reset()
    n = nodes.len()
    nodes.push(Node(kind=.int_lit, type=i32(T_INT), ival=0))
    assert(not effect_caller_obligation(n))
    effect_failure(1, n)
    assert(effect_bound_sites == [(1, n)])
    effect_bounds_proven[n] = true
    effect_failure(1, n)
    assert(effect_bound_sites.len() == 1)
    effect_bounds(1, n)
    effect_cleanup(1, T_INT, n, PlaceIdentity(.local, 1, 1))
    effect_lower_intrinsic(1, n)
    assert(not effect_map_write(1) and not effect_array_reader(1))
    assert(effect_signature_opaque_by_type(1) and effect_signature_opaque(1))
    print("costs ok")
'''


@pytest.mark.parametrize('optimized', [False, True], ids=['default', 'release'])
def test_effect_costs_execution(compiler, tmp_path, monkeypatch, optimized):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    modules = modules_for(tmp_path / 'unused.dewy', tmp_path / 'unused', 'effect_costs')
    bindings = re.findall(r'^    (lower_test_bind_\w+\(\))$', modules['main.jo'], re.M)
    modules['main.jo'] += '\nselfhost_test_bind = ():\n' + ''.join('    ' + b + '\n' for b in bindings)
    out = compare_leaf(compiler, tmp_path, optimized, DRIVER,
                       extra_stems=('effect_costs',), jo_doubles=modules)
    assert out == b'costs ok\n'


@pytest.mark.parametrize('optimized', [False, True], ids=['default', 'release'])
@pytest.mark.parametrize('case', ['summary_budget_widening', 'library_calls_no_traps'])
def test_effect_costs_programs(compiler, tmp_path, monkeypatch, optimized, case):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    source, output = tmp_path / 'input.dewy', tmp_path / 'program'
    source.write_text((ROOT / 'tests/cases/effects' / (case + '.dewy')).read_text())
    driver = ("use 'main.jo'\nmain = ():\n    lower_test_cli()\n"
              f'    print(read_file({json.dumps(str(output))}) ?? "")\n')
    image = compare_leaf(compiler, tmp_path, False, driver,
                         extra_stems=('effect_costs',),
                         jo_doubles=modules_for(source, output, 'effect_costs',
                                                flags=('--release',) if optimized else ()))
    assert image == output.read_bytes() + b'\n'
    ran = subprocess.run([output], capture_output=True, timeout=30)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout == (ROOT / 'tests/cases/effects' / (case + '.out')).read_bytes()
