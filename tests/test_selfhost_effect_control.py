"""Effect demand, reset, finalization and witness diagnostics match frozen code."""
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
use 'effect_types.dewy'
use 'effect_graph.dewy'
use 'concurrency.jo'
use 'places.jo'
use 'place_routes.dewy'
use 'types.jo'
use 'type_ops.dewy'
use 'ast.jo'
use 'check.jo'
use 'facts.jo'
use 'util.jo'
use "checker_state.dewy"
use "node_store.dewy"
main = ():
    selfhost_test_bind()
    init_types()
    concurrency_calls = [1]; concurrency_tasks = [2]; parsafe_fns[3] = true
    concurrency_runtime_needed = true; effect_declared[4] = 5
    effects_reset()
    assert(concurrency_calls.len() == 0 and concurrency_tasks.len() == 0 and parsafe_fns.len() == 0)
    assert(not concurrency_runtime_needed and effect_declared.len() == 0)
    fns.resize(4)
    fns[1].state = 2
    seen: int[]
    effect_prepare(1, seen, 0)
    assert(seen == [1])
    effect_prepare_node(0, seen, 0)
    effect_prepare(1, seen, 0)
    assert(seen == [1])
    effect_bodies[1] = EffectBody([EffectEvent(EffectAtom(.alloc), 0)], [], [], .none_, 0)
    assert(effects_demand(1) and not effects_demand(0) and not effects_demand(4))
    assert(effect_summaries[1].events == [EffectEvent(EffectAtom(.alloc), 0)])
    n = mk(.fn_, 0); nodes[n].name = i32(intern("root"))
    fns[1].decl = i32(n)
    assert(effects_demand_late(1) and effect_seen.len() == nodes.len())
    assert(effect_name(1) == "root" and effect_name(2) == "<helper>" and not effect_root(1))
    param = mk(.param, 0); nodes[param].name = i32(intern("target")); set_list(n, [param])
    formal = PlaceIdentity(.formal, 1, 1)
    field = place_project(formal, intern("field"))
    assert(effect_place_name(formal) == "target" and effect_place_name(field) == "target.field")
    assert(effect_place_name(PlaceIdentity(.local, 0, 0)) == "unknown place")
    effect_summaries[2].events = [EffectEvent(EffectAtom(.alloc), 0, n, 1)]
    assert(effect_witness(1, EffectEvent(EffectAtom(.alloc), 0, n, 2)) == "root -> <helper> -> root (recursive component)")
    effect_settle_bounds()
    effect_discharge_bounds()
    assert(effect_contracts_hold(false))
    effects_finalize()
    effects_active = true
    effects_finalize()
    assert(effect_final)
    print("control ok")
'''


@pytest.mark.parametrize('optimized', [False, True], ids=['default', 'release'])
def test_effect_control_execution(compiler, tmp_path, monkeypatch, optimized):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    monkeypatch.delenv('DEWY_INTERNAL_EFFECT_POLICY', raising=False)
    modules = modules_for(tmp_path / 'unused.dewy', tmp_path / 'unused', 'effect_control')
    bindings = re.findall(r'^    (lower_test_bind_\w+\(\))$', modules['main.jo'], re.M)
    modules['main.jo'] += '\nselfhost_test_bind = ():\n' + ''.join('    ' + b + '\n' for b in bindings)
    out = compare_leaf(compiler, tmp_path, optimized, DRIVER,
                       extra_stems=('effect_control',), jo_doubles=modules)
    assert out == b'control ok\n'


@pytest.mark.parametrize('optimized', [False, True], ids=['default', 'release'])
@pytest.mark.parametrize('case', ['fixed_array_kernels', 'library_calls_no_traps'])
def test_effect_control_programs(compiler, tmp_path, monkeypatch, optimized, case):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    source, output = tmp_path / 'input.dewy', tmp_path / 'program'
    source.write_text((ROOT / 'tests/cases/effects' / (case + '.dewy')).read_text())
    driver = ("use 'main.jo'\nmain = ():\n    lower_test_cli()\n"
              f'    print(read_file({json.dumps(str(output))}) ?? "")\n')
    image = compare_leaf(compiler, tmp_path, False, driver,
                         extra_stems=('effect_control',),
                         jo_doubles=modules_for(source, output, 'effect_control',
                                                flags=('--release',) if optimized else ()))
    assert image == output.read_bytes() + b'\n'
    ran = subprocess.run([output], capture_output=True, timeout=30)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout == (ROOT / 'tests/cases/effects' / (case + '.out')).read_bytes()


@pytest.mark.parametrize('case', ['cost', 'recursive'])
def test_effect_control_diagnostics(compiler, tmp_path, monkeypatch, case):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    source, output = tmp_path / 'input.dewy', tmp_path / 'program'
    source.write_text((ROOT / 'tests/fixtures/effects' / (case + '.dewy')).read_text())
    modules = modules_for(source, output, 'effect_control')
    modules['util.jo'], count = re.subn(
        r'(?m)^fatal = \(p0: int, msg0: str\):\n(?:[ \t].*\n|\n)*',
        'fatal = (p0: int, msg0: str):\n    print(msg0)\n    exit(41)\n\n',
        modules['util.jo'], count=1)
    assert count == 1
    driver = "use 'main.jo'\nmain = ():\n    lower_test_cli()\n"
    out = compare_leaf(compiler, tmp_path, False, driver, status=41,
                       extra_stems=('effect_control',), jo_doubles=modules)
    assert b'effect contract violation' in out
