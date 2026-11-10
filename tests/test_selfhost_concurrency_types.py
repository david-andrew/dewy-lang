"""Transfer claims and zero-initialization checks retain the frozen behavior."""
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
use 'concurrency.jo'
use 'types.jo'
use 'type_ops.dewy'
use 'check.jo'
use 'ast.jo'
use 'node_store.dewy'
use "checker_types.dewy"
main = ():
    selfhost_test_bind()
    init_types()
    seen: {int: bool}
    assert(concurrency_transfer(T_INT, seen))
    seen.clear()
    assert(not concurrency_transfer(T_RAWPTR, seen))
    seen.clear()
    assert(concurrency_transfer(mk_array(T_INT), seen, true))
    seen.clear()
    assert(not concurrency_transfer(mk_array(T_RAWPTR), seen))
    seen.clear()
    assert(concurrency_zeroable(mk_array(T_RAWPTR), seen))
    seen.clear()
    assert(concurrency_zeroable(mk_fixed(T_INT, 0), seen))
    assert(not concurrency_builtin_type(T_INT, "Atomic"))
    concurrency_reason = "blocked"
    assert(concurrency_why() == " (blocked)" and concurrency_why() == "")
    # A recursive record is visited once; opting out still blocks the root query.
    d = nodes.len()
    nodes.push(Node(kind=.struct_))
    si = structs.len()
    start = fields.len()
    structs.push(StructInfo(name="Recursive", resolved=true, decl=i32(d), fields=i32(start), nfields=1))
    t = types.len()
    types.push(TypeInfo(kind=.struct_, st=i32(si), flags=2))
    fields.push(Field(type=i32(t)))
    seen.clear()
    assert(concurrency_transfer(t, seen) and seen.has(t))
    seen.clear()
    assert(concurrency_zeroable(t, seen))
    transfer_tags[d] = TRANSFER_SEND_CLAIM | TRANSFER_SYNC_CLAIM | TRANSFER_UNSAFE
    transfer_claim_pos[d] = 0
    concurrency_claim_check(si)
    assert(transfer_claims_checked.has(d))
    concurrency_claims_finalize()
    transfer_tags[d] = TRANSFER_SEND_OFF
    seen.clear()
    assert(not concurrency_transfer(t, seen))
    assert(concurrency_why().len() > 0 and concurrency_reason == "")
    seen.clear()
    assert(concurrency_transfer(t, seen, true))
    print("transfer ok")
'''


@pytest.mark.parametrize('optimized', [False, True], ids=['default', 'release'])
def test_concurrency_types_execution(compiler, tmp_path, monkeypatch, optimized):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    modules = modules_for(tmp_path / 'unused.dewy', tmp_path / 'unused', 'concurrency_types')
    bindings = re.findall(r'^    (lower_test_bind_\w+\(\))$', modules['main.jo'], re.M)
    modules['main.jo'] += '\nselfhost_test_bind = ():\n' + ''.join('    ' + b + '\n' for b in bindings)
    out = compare_leaf(compiler, tmp_path, optimized, DRIVER,
                       extra_stems=('concurrency_types',), jo_doubles=modules)
    assert out == b'transfer ok\n'


@pytest.mark.parametrize('optimized', [False, True], ids=['default', 'release'])
@pytest.mark.parametrize('case', ['claim_verified', 'sync_optout_sends'])
def test_concurrency_types_program(compiler, tmp_path, monkeypatch, optimized, case):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    source = ROOT / 'tests/cases/transfer' / (case + '.dewy')
    output = tmp_path / 'program'
    driver = ("use 'main.jo'\nmain = ():\n    lower_test_cli()\n"
              f'    print(read_file({json.dumps(str(output))}) ?? "")\n')
    image = compare_leaf(compiler, tmp_path, False, driver,
                         extra_stems=('concurrency_types',),
                         jo_doubles=modules_for(source, output, 'concurrency_types',
                                                flags=('--release',) if optimized else ()))
    assert image == output.read_bytes() + b'\n'
    ran = subprocess.run([output], capture_output=True, timeout=30)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout == source.with_suffix('.out').read_bytes()


@pytest.mark.parametrize('case', ['send_optout', 'claim_bad'])
def test_concurrency_types_diagnostics(compiler, tmp_path, monkeypatch, case):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    source = ROOT / 'tests/cases/transfer' / (case + '.dewy')
    modules = modules_for(source, tmp_path / 'program', 'concurrency_types')
    diagnostic_status(modules, 'fatal')
    out = compare_leaf(compiler, tmp_path, False,
                       "use 'main.jo'\nmain = ():\n    lower_test_cli()\n",
                       status=41, extra_stems=('concurrency_types',), jo_doubles=modules)
    assert b'unsafe boundary' in out if case == 'claim_bad' else b'opts out of Send' in out
