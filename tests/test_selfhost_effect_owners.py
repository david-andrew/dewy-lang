"""Loan services and ownership hook edges match the frozen twin."""
import json
import re
import subprocess

import pytest

from tests.selfhost_diagnostic_double import diagnostic_status
from tests.support import ROOT, compiler  # noqa: F401
from tests.selfhost_expr_double import compare_leaf
from tests.selfhost_lower_double import modules_for


DRIVER = r'''
use 'main.jo'
use 'effects.jo'
use 'effect_graph.dewy'
use 'effect_types.dewy'
use 'types.jo'
use 'type_ops.dewy'
use 'check.jo'
use 'ast.jo'
use 'ownership.jo'
use 'node_store.dewy'
use "checker_types.dewy"
main = ():
    selfhost_test_bind()
    init_types()
    fns.resize(4)
    effect_graph_reset()
    n = nodes.len()
    nodes.push(Node(kind=.int_lit, type=i32(T_INT), ival=1))
    effect_owner_init(1, n, n)
    assert(loan_host_events(1).len() == 0)
    p = PlaceIdentity(.global, 0, 17)
    si = structs.len()
    structs.push(StructInfo(resolved=true))
    record = types.len()
    types.push(TypeInfo(kind=.struct_, st=i32(si), flags=2))
    owner_map_copies[record] = 2
    effect_owner_components(1, record, n, p, true)
    assert(effect_summaries[1].edges == [EffectEdge(2, n, [p])])
    # Fixed arrays preserve move, dynamic arrays clear it, and copy edges precede moves.
    owner_map_copies.clear()
    ownership_copies[record] = 2
    ownership_moves[record] = 3
    effect_owner_components(1, mk_array(record), n, p, true)
    assert(effect_summaries[1].edges.len() == 2)
    effect_owner_components(1, mk_fixed(record, 2), n, p, true)
    assert(effect_summaries[1].edges.len() == 4)
    assert(effect_summaries[1].edges[3] == EffectEdge(3, n, [p]))
    effect_owner_components(1, record, n, p, true, 33)
    assert(loan_host_events(1) == [EffectEvent(EffectAtom(.opaque), n)])
    assert(loan_host_route(n) == PlaceIdentity(.local, 0, 0))
    assert(loan_host_append(n, p).declaration == 0)
    assert(not loan_host_demand(0))
    print("owners ok")
'''


@pytest.mark.parametrize('optimized', [False, True], ids=['default', 'release'])
def test_effect_owners_execution(compiler, tmp_path, monkeypatch, optimized):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    modules = modules_for(tmp_path / 'unused.dewy', tmp_path / 'unused', 'effect_owners')
    bindings = re.findall(r'^    (lower_test_bind_\w+\(\))$', modules['main.jo'], re.M)
    modules['main.jo'] += '\nselfhost_test_bind = ():\n' + ''.join('    ' + b + '\n' for b in bindings)
    out = compare_leaf(compiler, tmp_path, optimized, DRIVER,
                       extra_stems=('effect_owners',), jo_doubles=modules)
    assert out == b'owners ok\n'


@pytest.mark.parametrize('optimized', [False, True], ids=['default', 'release'])
@pytest.mark.parametrize('case', ['composed_hooks', 'fixed_hooks'])
def test_effect_owners_programs(compiler, tmp_path, monkeypatch, optimized, case):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    source, output = tmp_path / 'input.dewy', tmp_path / 'program'
    source.write_text((ROOT / 'tests/cases/ownership' / (case + '.dewy')).read_text())
    driver = ("use 'main.jo'\nmain = ():\n    lower_test_cli()\n"
              f'    print(read_file({json.dumps(str(output))}) ?? "")\n')
    image = compare_leaf(compiler, tmp_path, False, driver,
                         extra_stems=('effect_owners',),
                         jo_doubles=modules_for(source, output, 'effect_owners',
                                                flags=('--release',) if optimized else ()))
    assert image == output.read_bytes() + b'\n'
    ran = subprocess.run([output], capture_output=True, timeout=30)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout == (ROOT / 'tests/cases/ownership' / (case + '.out')).read_bytes()


@pytest.mark.parametrize('entry', ['loan_error', 'loan_host_error'])
def test_effect_owners_diagnostics(compiler, tmp_path, monkeypatch, entry):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    modules = modules_for(tmp_path / 'unused.dewy', tmp_path / 'unused', 'effect_owners')
    diagnostic_status(modules, 'fatal')
    driver = "use 'main.jo'\nmain = ():\n    " + entry + '(0, "borrow escaped")\n'
    out = compare_leaf(compiler, tmp_path, False, driver, status=41,
                       extra_stems=('effect_owners',), jo_doubles=modules)
    expected = b'scoped loan: borrow escaped\n' if entry == 'loan_error' else b'borrow escaped\n'
    assert out == expected
