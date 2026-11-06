"""Effect graph execution keeps SCCs, delta witnesses and widening generations."""
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
use 'effect_lattice.dewy'
use 'effect_types.dewy'
use 'places.jo'
use 'place_routes.dewy'
use 'types.jo'
use 'check.jo'
use 'isolation.jo'
main = ():
    selfhost_test_bind()
    init_types()
    fns.resize(6)
    effect_graph_reset()
    actual = PlaceIdentity(.global, 0, 7)
    formal = PlaceIdentity(.formal, 2, 1)
    effect_summaries[1].edges = [EffectEdge(2, 71, [actual]), EffectEdge(2, 72, [actual])]
    loop i in [1..33): effect_add(2, EffectEvent(EffectAtom(.write, place_project(formal, i)), 100 + i))
    assert(effect_propagate(1))
    assert(effect_summaries[1].unique == [0] and effect_summaries[1].events.len() == 32)
    assert(not effect_stale(1) and not effect_propagate(1))
    effect_add(2, EffectEvent(EffectAtom(.write, place_project(formal, 33)), 133))
    assert(effect_summaries[2].events.len() == 1 and effect_stale(1))
    assert(effect_propagate(1))
    assert(effect_summaries[1].events == [EffectEvent(EffectAtom(.write, actual), 101, 71, 2)])
    assert(not effect_add(2, EffectEvent(EffectAtom(.write, place_project(formal, 34)), 134)))
    # Distinct roots cannot widen together; capping keeps one opaque witness.
    loop i in [1..35): effect_add(4, EffectEvent(EffectAtom(.write, PlaceIdentity(.global, 0, i)), i))
    assert(effect_summaries[4].capped and effect_summaries[4].events.len() == 33)
    assert(not effect_opaque(4, 99))
    # A self edge reads a snapshot and replays just the appended substitution.
    effect_graph_reset()
    a = PlaceIdentity(.formal, 1, 1)
    b = PlaceIdentity(.formal, 1, 2)
    effect_summaries[1].edges = [EffectEdge(1, 74, [b, a])]
    effect_add(1, EffectEvent(EffectAtom(.write, a), 84))
    assert(effect_propagate(1) and not effect_propagate(1))
    assert(effect_summaries[1].events == [EffectEvent(EffectAtom(.write, a), 84), EffectEvent(EffectAtom(.write, b), 84, 74, 1)])
    # A cached two-node SCC reaches a leaf; discharged cached panics stay absent.
    effect_bodies[1] = EffectBody([EffectEvent(EffectAtom(.alloc), 11)], [], [EffectEdge(2, 12, [])], .none_, 0)
    effect_bodies[2] = EffectBody([], [EffectEvent(EffectAtom(.panic), 21)], [EffectEdge(1, 22, []), EffectEdge(3, 23, [])], .none_, 0)
    effect_bodies[3] = EffectBody([EffectEvent(EffectAtom(.io), 31)], [], [], .none_, 0)
    effect_bounds_proven[21] = true
    effect_plain_cache[123] = true
    effect_ix_nodes = 17
    effect_graph_reset(true)
    assert(effect_bodies.len() == 3 and effect_plain_cache.has(123) and effect_ix_nodes == 17)
    effect_final = true
    effect_visit(1)
    assert(effect_stack.len() == 0)
    loop f in [1..4): assert(effect_summaries[f].done)
    assert(effect_summaries[1].events == [EffectEvent(EffectAtom(.alloc), 11), EffectEvent(EffectAtom(.io), 31, 12, 2)])
    assert(effect_summaries[2].events == [EffectEvent(EffectAtom(.alloc), 11, 22, 1), EffectEvent(EffectAtom(.io), 31, 23, 3)])
    row = effect_function_row(1)
    assert(effect_contracts[row].atoms == [EffectAtom(.alloc), EffectAtom(.io)])
    assert(effect_declared_row(1) == 0 and effect_declared.has(1))
    effect_graph_reset()
    assert(effect_bodies.len() == 0 and effect_plain_cache.len() == 0 and effect_ix_nodes == 0)
    effect_footprints_only = true
    assert(not effect_add(1, EffectEvent(EffectAtom(.alloc), 9)))
    assert(effect_add(1, EffectEvent(EffectAtom(.escape), 10)))
    assert(effect_summaries[1].footprint_opaque)
    effect_stack = [1]
    assert(effect_function_row(1) == effect_top() and effect_stack == [1])
    print("graph ok")
'''


@pytest.mark.parametrize('optimized', [False, True], ids=['default', 'release'])
def test_effect_graph_execution(compiler, tmp_path, monkeypatch, optimized):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    modules = modules_for(tmp_path / 'unused.dewy', tmp_path / 'unused', 'effect_graph')
    bindings = re.findall(r'^    (lower_test_bind_\w+\(\))$', modules['main.jo'], re.M)
    modules['main.jo'] += '\nselfhost_test_bind = ():\n' + ''.join('    ' + b + '\n' for b in bindings)
    out = compare_leaf(compiler, tmp_path, optimized, DRIVER,
                       extra_stems=('effect_graph',), jo_doubles=modules)
    assert out == b'graph ok\n'


@pytest.mark.parametrize('optimized', [False, True], ids=['default', 'release'])
@pytest.mark.parametrize('case', ['summary_budget_widening', 'library_calls_no_traps'])
def test_effect_graph_programs(compiler, tmp_path, monkeypatch, optimized, case):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    source, output = tmp_path / 'input.dewy', tmp_path / 'program'
    source.write_text((ROOT / 'tests/cases/effects' / (case + '.dewy')).read_text())
    driver = ("use 'main.jo'\nmain = ():\n    lower_test_cli()\n"
              f'    print(read_file({json.dumps(str(output))}) ?? "")\n')
    image = compare_leaf(compiler, tmp_path, False, driver,
                         extra_stems=('effect_graph',),
                         jo_doubles=modules_for(source, output, 'effect_graph',
                                                flags=('--release',) if optimized else ()))
    assert image == output.read_bytes() + b'\n'
    ran = subprocess.run([output], capture_output=True, timeout=30)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout == (ROOT / 'tests/cases/effects' / (case + '.out')).read_bytes()
