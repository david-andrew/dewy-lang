"""Emission primitives preserve cached identities, bytes and generated programs."""
import json
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401
from tests.selfhost_expr_double import compare_leaf
from tests.selfhost_lower_double import modules_for


def test_lower_primitives_state_twins(compiler, tmp_path, monkeypatch):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    source, output = tmp_path / 'input.dewy', tmp_path / 'program'
    source.write_text('main=()=>{}\n')
    driver = r'''use 'main.jo'
use 'lower.jo'
use 'lower_functions.dewy'
use 'ir.jo'
use 'ir_types.dewy'
use 'types.jo'
use 'fused.jo'
use 'source_types.dewy'
use 'util.jo'
main = ():
    lower_test_cli()
    fused_on = false
    fi = files.len()
    files.push(SrcFile(path = "/é/🦊.dewy", src = "a\nb", is_dewy = true))
    assert(loc_str(mkpos(fi, 2)) == "🦊.dewy:2")
    rodata = []; ro_starts = []; str_off = {}
    a = str_data("é🦊")
    assert(a == 0 and rodata[8] == 6 and rodata[16] == 7 and rodata.len() == 31)
    assert(str_data("é🦊") == a and str_data("") == 32)
    assert(rodata.len() == 57 and rodata[40] == 0 and rodata[48] == 1)
    helper_slots = []; helper_count = 0; helper_lf = {}; lfuncs = []
    loop i in [0..100): assert(lf_helper(HK.drop, T_INT, i) == i)
    loop i in [0..100): assert(lf_helper(HK.drop, T_INT, i) == i)
    assert(helper_count == 100 and lfuncs.len() == 100 and helper_slots.len() == 256)
    assert(lfuncs[0].name == "__h_drop_0" and lfuncs[99].name == "__h_drop_99")
    begin_fn("primitive_test", 0)
    assert(e_call_nr0(12, -1) == -1)
    e_call_nr1(12, 10, -1); e_call_nr2(12, 20, 21, -1)
    e_call_nr3(12, 30, 31, 32, -1); e_call_nr4(12, 40, 41, 42, 43, -1)
    e_call_nr(12, [50, 51, 52, 53, 54], -1)
    assert(ir.code.len() == 6 and ir.args.len() == 15)
    loop i in [0..6):
        assert(ir.code[i].op == .call and ir.code[i].dst == -1 and ir.code[i].b == i and ir.code[i].c == 1)
    assert(ir.args[0] == 10 and ir.args[14] == 54)
    print("ok")
'''
    out = compare_leaf(compiler, tmp_path, False, driver,
                       extra_stems=('lower_primitives',),
                       jo_doubles=modules_for(source, output, 'lower_primitives'))
    assert out == b'ok\n'


@pytest.mark.parametrize('optimized', [False, True], ids=['default', 'release'])
def test_lower_primitives_program_twins(compiler, tmp_path, monkeypatch, optimized):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    source, output = tmp_path / 'input.dewy', tmp_path / 'program'
    source.write_text((ROOT / 'tests/cases/singleton/string_set_words.dewy').read_text())
    driver = ("use 'main.jo'\nmain = ():\n    lower_test_cli()\n"
              f'    print(read_file({json.dumps(str(output))}) ?? "")\n')
    image = compare_leaf(compiler, tmp_path, False, driver,
                         extra_stems=('lower_primitives',),
                         jo_doubles=modules_for(source, output, 'lower_primitives',
                                                flags=('--release',) if optimized else ()))
    assert image == output.read_bytes() + b'\n'
    ran = subprocess.run([output], capture_output=True, timeout=30)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout == (ROOT / 'tests/cases/singleton/string_set_words.out').read_bytes()
