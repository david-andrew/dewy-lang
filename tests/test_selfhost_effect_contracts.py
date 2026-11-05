"""Effect row resolution, substitution and callable qualification match the twin."""
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
use 'types.jo'
use 'ast.jo'
use 'util.jo'
use "node_store.dewy"
use "dewy_reader_types.dewy"
main = ():
    selfhost_test_bind()
    init_types()
    empty = effect_intern([])
    io = effect_intern([EffectAtom(.io)])
    alloc = effect_intern([EffectAtom(.alloc)])
    both = effect_intern([EffectAtom(.alloc), EffectAtom(.io)])
    assert(effect_subst(0, []) == 0 and effect_subst(io, []) == io)
    e = effect_type(io)
    assert(tkind(e) == .effect and types[e].st == i32(io))
    p = mk_param(0)
    generic = effect_intern([EffectAtom(.alloc)], [], [p])
    assert(effect_subst(generic, [e]) == both)
    assert(effect_subst(generic, [], true) == generic)
    base = mk_fn([T_INT], T_INT, 0)
    assert(mk_callable_contract(base, 0) == base)
    wrapped = mk_callable_contract(base, io, 1)
    assert(callable_base(wrapped) == base and callable_contract(wrapped) == io)
    rewrapped = mk_callable_contract(wrapped, empty)
    assert(types[rewrapped].bits == 1 and callable_base(rewrapped) == base)
    assert(callable_base(base) == base and callable_contract(base) == 0)
    assert(effect_contract_fits(wrapped, wrapped))
    seen: int[]
    assert(effect_qualified_type(mk_array(wrapped), seen))
    seen = []; assert(not effect_qualified_type(mk_tuple([T_INT, T_STR]), seen))
    seen = fill(-1, 64); assert(effect_qualified_type(T_INT, seen))
    binds: int[] = [0]
    assert(effect_match(both, generic, binds))
    assert(tkind(binds[0]) == .effect and effect_contracts[int(types[binds[0]].st)].atoms == [EffectAtom(.io)])
    assert(effect_match(alloc, 0, binds) and not effect_match(0, alloc, binds))
    assert(effect_match(alloc, alloc, binds) and not effect_match(io, alloc, binds))
    formal = effect_intern([EffectAtom(.write, PlaceIdentity(.formal, 0, 1))])
    assert(not effect_match(formal, generic, binds))
    # Syntax rows: closed positive and empty rows, and open negative rows.
    n = nodes.len()
    nodes.push(Node(kind=.fn_))
    assert(effect_contract(n, [], [], 0) == 0 and effect_decl_contract(n, []) == 0)
    nodes[n].sval = i32(effect_syntax.len())
    effect_syntax.push([EffectSyntax(.io)])
    assert(effect_contract(n, [], [], 0) == io and effect_decl_contract(n, []) == io)
    nodes[n].kind = .tname; nodes[n].aux = -8
    assert(effect_argument(n) == e and effect_generic_argument(n) == e)
    nodes[n].sval = i32(effect_syntax.len())
    effect_syntax.push([])
    assert(effect_contract(n, [], [], 0) == empty)
    nodes[n].sval = i32(effect_syntax.len())
    effect_syntax.push([EffectSyntax(kind=.alloc, negative=true)])
    negative = effect_contract(n, [], [], 0)
    assert(effect_contracts[negative].open and effect_contracts[negative].exclusions == [EffectAtom(.alloc)])
    # Mutable formal labels become owner-free ordinals, exactly once per atom.
    label = intern("target")
    param = nodes.len()
    nodes.push(Node(kind=.param, name=i32(label), flags=i32(NF_MUT)))
    set_list(n, [param])
    nodes[n].kind = .fn_
    nodes[n].sval = i32(effect_syntax.len())
    effect_syntax.push([EffectSyntax(kind=.write, path=[label]), EffectSyntax(kind=.write, path=[label])])
    row = effect_decl_contract(n, [T_INT])
    assert(effect_contracts[row].atoms == [EffectAtom(.write, PlaceIdentity(.formal, 0, 1))])
    print("contracts ok")
'''


@pytest.mark.parametrize('optimized', [False, True], ids=['default', 'release'])
def test_effect_contracts_execution(compiler, tmp_path, monkeypatch, optimized):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    modules = modules_for(tmp_path / 'unused.dewy', tmp_path / 'unused', 'effect_contracts')
    bindings = re.findall(r'^    (lower_test_bind_\w+\(\))$', modules['main.jo'], re.M)
    modules['main.jo'] += '\nselfhost_test_bind = ():\n' + ''.join('    ' + b + '\n' for b in bindings)
    out = compare_leaf(compiler, tmp_path, optimized, DRIVER,
                       extra_stems=('effect_contracts',), jo_doubles=modules)
    assert out == b'contracts ok\n'


@pytest.mark.parametrize('optimized', [False, True], ids=['default', 'release'])
@pytest.mark.parametrize('case', ['places', 'callable_return'])
def test_effect_contracts_programs(compiler, tmp_path, monkeypatch, optimized, case):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    source, output = tmp_path / 'input.dewy', tmp_path / 'program'
    source.write_text((ROOT / 'tests/fixtures/effects' / (case + '.dewy')).read_text())
    driver = ("use 'main.jo'\nmain = ():\n    lower_test_cli()\n"
              f'    print(read_file({json.dumps(str(output))}) ?? "")\n')
    image = compare_leaf(compiler, tmp_path, False, driver,
                         extra_stems=('effect_contracts',),
                         jo_doubles=modules_for(source, output, 'effect_contracts',
                                                flags=('--release',) if optimized else ()))
    assert image == output.read_bytes() + b'\n'
    ran = subprocess.run([output], capture_output=True, timeout=30)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout == {'places': b'8 8 42\n', 'callable_return': b'42\n'}[case]
