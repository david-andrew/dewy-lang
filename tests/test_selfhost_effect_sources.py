"""Callable provenance, storage erasure and inference match the frozen twin."""
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
use 'effect_contracts.dewy'
use 'effect_lattice.dewy'
use 'effect_types.dewy'
use 'types.jo'
use 'ast.jo'
use 'expr.jo'
use 'node_store.dewy'
main = ():
    selfhost_test_bind()
    init_types()
    io = effect_intern([EffectAtom(.io)])
    base = mk_fn([T_INT], T_INT, 0)
    wrapped = mk_callable_contract(base, io)
    assert(effect_storage_type(wrapped) == base)
    nested = mk_opt(mk_fixed(mk_array(wrapped), 3))
    assert(effect_storage_type(nested) == mk_opt(mk_fixed(mk_array(base), 3)))
    assert(effect_storage_type(T_INT) == T_INT)
    assert(effect_source_row(0) == effect_top())
    n = nodes.len()
    nodes.push(Node(kind=.ident, type=i32(wrapped)))
    assert(effect_source_row(n) == io and effect_source_row(n, [], 17) == effect_top())
    assert(effect_infer_callable(n, wrapped) == wrapped)
    assert(effect_infer_callable(n, base) == wrapped)
    arr = nodes.len()
    nodes.push(Node(kind=.array))
    set_list(arr, [n, n])
    assert(effect_source_row(arr, [-1]) == io)
    field = nodes.len()
    nodes.push(Node(kind=.index, a=i32(arr)))
    assert(effect_source_row(field) == io)
    call = nodes.len()
    nodes.push(Node(kind=.call, aux=2))
    set_list(call, [n])
    assert(effect_source_row(call, [0]) == io)
    conv = nodes.len()
    nodes.push(Node(kind=.conv, a=i32(n)))
    assert(effect_source_row(conv) == io)
    unknown = nodes.len()
    nodes.push(Node(kind=.ident, type=i32(base)))
    before = effect_obligations.len()
    qualified = effect_infer_callable(unknown, wrapped)
    assert(callable_base(qualified) == base and callable_contract(qualified) == effect_top())
    assert(effect_obligations.len() == before + 1)
    assert(effect_obligations[before].source == unknown + 1)
    nodes[unknown].type = i32(T_INT)
    assert(nodes[unknown + 1].type == i32(base))
    print("sources ok")
'''


@pytest.mark.parametrize('optimized', [False, True], ids=['default', 'release'])
def test_effect_sources_execution(compiler, tmp_path, monkeypatch, optimized):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    modules = modules_for(tmp_path / 'unused.dewy', tmp_path / 'unused', 'effect_sources')
    bindings = re.findall(r'^    (lower_test_bind_\w+\(\))$', modules['main.jo'], re.M)
    modules['main.jo'] += '\nselfhost_test_bind = ():\n' + ''.join('    ' + b + '\n' for b in bindings)
    out = compare_leaf(compiler, tmp_path, optimized, DRIVER,
                       extra_stems=('effect_sources',), jo_doubles=modules)
    assert out == b'sources ok\n'


@pytest.mark.parametrize('optimized', [False, True], ids=['default', 'release'])
@pytest.mark.parametrize('case', ['callable_return', 'callable_field', 'callable_recover'])
def test_effect_sources_programs(compiler, tmp_path, monkeypatch, optimized, case):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    source, output = tmp_path / 'input.dewy', tmp_path / 'program'
    source.write_text((ROOT / 'tests/fixtures/effects' / (case + '.dewy')).read_text())
    driver = ("use 'main.jo'\nmain = ():\n    lower_test_cli()\n"
              f'    print(read_file({json.dumps(str(output))}) ?? "")\n')
    image = compare_leaf(compiler, tmp_path, False, driver,
                         extra_stems=('effect_sources',),
                         jo_doubles=modules_for(source, output, 'effect_sources',
                                                flags=('--release',) if optimized else ()))
    assert image == output.read_bytes() + b'\n'
    ran = subprocess.run([output], capture_output=True, timeout=30)
    assert ran.returncode == (2 if case == 'callable_field' else 0), ran.stderr
    assert ran.stdout == (b'42\n' if case == 'callable_return' else b'')
