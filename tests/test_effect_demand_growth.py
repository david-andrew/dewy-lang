"""Effect demands cover AST nodes appended after an early callable summary."""
import re

import pytest

from tests.support import ROOT, compiler  # noqa: F401
from tests.selfhost_expr_double import compare_leaf
from tests.selfhost_lower_double import modules_for


DRIVER = r'''
use 'main.jo'
use 'ast.jo'
use 'effects.jo'
use 'effect_types.dewy'
use 'effect_graph.dewy'
use 'check.jo'
use 'types.jo'
use 'type_ops.dewy'
main = ():
    selfhost_test_bind()
    init_types()
    fns.resize(3)
    effect_bodies[1] = EffectBody()
    assert(effects_demand(1))
    first = effect_seen.len()
    loop i in [0..2000): mk(.int_lit, 0)
    body = mk(.int_lit, 0)
    fns[2].state = 2
    fns[2].ret = i32(T_VOID)
    fns[2].body = i32(body)
    assert(nodes.len() > first)
    assert(effects_demand(2))
    assert(effect_seen.len() == nodes.len() and effect_seen[body] == 2)
    assert(effect_summaries[1].done and effect_summaries[2].done)
    assert(effect_summaries[1].events.len() == 0 and effect_summaries[2].events.len() == 0)
    print("demand growth ok")
'''


@pytest.mark.parametrize('optimized', [False, True], ids=['default', 'release'])
def test_effect_demand_growth(compiler, tmp_path, monkeypatch, optimized):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    monkeypatch.delenv('DEWY_INTERNAL_EFFECT_POLICY', raising=False)
    modules = modules_for(tmp_path / 'unused.dewy', tmp_path / 'unused', 'effect_control')
    bindings = re.findall(r'^    (lower_test_bind_\w+\(\))$', modules['main.jo'], re.M)
    modules['main.jo'] += '\nselfhost_test_bind = ():\n' + ''.join('    ' + b + '\n' for b in bindings)
    assert compare_leaf(compiler, tmp_path, optimized, DRIVER,
                        extra_stems=('effect_control',), jo_doubles=modules) == b'demand growth ok\n'
