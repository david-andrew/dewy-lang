"""Function setup, body lowering and final IR insertion match the frozen leaf."""
import json
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401
from tests.selfhost_expr_double import compare_leaf
from tests.selfhost_lower_double import modules_for


@pytest.mark.parametrize('optimized', [False, True], ids=['default', 'release'])
def test_lower_functions_program_twins(compiler, tmp_path, monkeypatch, optimized):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    source, output = tmp_path / 'input.dewy', tmp_path / 'program'
    source.write_text((ROOT / 'tests/cases/ownership/recursive_owner_copy.dewy').read_text())
    driver = ("use 'main.jo'\nmain = ():\n    lower_test_cli()\n"
              f'    print(read_file({json.dumps(str(output))}) ?? "")\n')
    image = compare_leaf(compiler, tmp_path, False, driver,
                         extra_stems=('lower_functions',),
                         jo_doubles=modules_for(source, output, 'lower_functions',
                                                flags=('--release',) if optimized else ()))
    assert image == output.read_bytes() + b'\n'
    ran = subprocess.run([output], capture_output=True, timeout=30)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout == b'ok\n'


def test_lower_functions_finish_twins(compiler, tmp_path, monkeypatch):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    source, output = tmp_path / 'input.dewy', tmp_path / 'program'
    source.write_text('main=()=>{}\n')
    driver = r'''use 'main.jo'
use 'lower.jo'
use 'ir.jo'
use 'ir_types.dewy'
use 'util.jo'
use 'facts.jo'
use 'exact.jo'
use 'exact_guards.jo'
use 'math_lower.jo'
main = ():
    lower_test_cli()
    begin_fn("finish_test", 0)
    assert(not eg_active and not math_has_mutable and not math_writes_ready)
    assert(exact_lower_active == (exact_nodes.len() > 0))
    assert(lower_zeros.len() == 0 and lower_length_guards.len() == 0)
    assert(find_bytes_set(intern("unrelated")) == -1)
    assert(find_bytes_set(intern("__memchr")) == -2)
    assert(find_bytes_set(intern("__find_newline")) == 0x0A0A0A0A)
    ir.code = [Ins(.nop), Ins(.ret)]
    lower_has_nops = false
    lower_finish(); assert(ir.code.len() == 2)
    lower_has_nops = true
    lower_finish(); assert(ir.code.len() == 1 and ir.code[0].op == .ret)
    ir.code = [Ins(.nop), Ins(.ret)]
    lower_zeros = [LowerZero((1 << 32) | 2, 20, 2), LowerZero(1, 10, 1), LowerZero((1 << 32) | 1, 30, 3)]
    lower_finish()
    assert(ir.code.len() == 4)
    assert(ir.code[0].op == .zeroslots and ir.code[0].a == 10)
    assert(ir.code[1].op == .zeroslots and ir.code[1].a == 30)
    assert(ir.code[2].op == .zeroslots and ir.code[2].a == 20)
    assert(ir.code[3].op == .ret)
    print("ok")
'''
    out = compare_leaf(compiler, tmp_path, False, driver,
                       extra_stems=('lower_functions',),
                       jo_doubles=modules_for(source, output, 'lower_functions'))
    assert out == b'ok\n'
