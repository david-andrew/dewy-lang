"""Recursive lowering and its frozen twin emit identical programs and diagnostics."""
import json
import subprocess

import pytest

from tests.selfhost_diagnostic_double import diagnostic_status
from tests.support import ROOT, compiler  # noqa: F401
from tests.selfhost_expr_double import compare_leaf
from tests.selfhost_lower_double import modules_for


PROGRAM = r'''$runtime_checks
fib=(n:int64):>int64=>if n <? 2 {n} else {fib(n-1)+fib(n-2)}
inside=(x:int64):>bool=>x >=? -9223372036854775808 and x <=? 9223372036854775807
choose=(x:int64):>int64=>match x {
    <-9223372036854775808> => 1
    <0> => 2
    <9223372036854775807> => 3
    _ => 4
}
main=()=>{
    let xs:array<int64>=[1 2 3]
    xs.insert(4 1)
    xs[1]=fib(6)
    let total:int64=0
    loop x in xs {total+=x}
    let scale=(x:int64):>int64=>x+total
    printl(scale(2))
    let optional:int64?=none
    printl(optional ?? -7)
    let wide:int=18446744073709551615
    printl(uint64<overflow='wrap'>(wide))
    let pair=[left=xs[0] right=xs[1]]
    printl(pair.left+pair.right)
    printl(xs[1..3))
    printl(inside(-1))
    printl(choose(0))
}
'''


@pytest.fixture(autouse=True)
def lowering_library(monkeypatch):
    # The differential compilers live beside their copied modules, away from lib.
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))




def test_lower_group_twins(compiler, tmp_path):
    source, output = tmp_path / 'input.dewy', tmp_path / 'program'
    source.write_text(PROGRAM)
    driver = ("use 'main.jo'\nmain = ():\n    lower_test_cli()\n"
              f'    print(read_file({json.dumps(str(output))}) ?? "")\n')
    image = compare_leaf(compiler, tmp_path, False, driver,
                         extra_stems=('lower_group',),
                         jo_doubles=modules_for(source, output))
    assert image == output.read_bytes() + b'\n'
    ran = subprocess.run([output], capture_output=True, timeout=30)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout == b'16\n-7\n18446744073709551615\n9\n[8 2]\ntrue\n2\n'


def test_lower_group_function_text_twins(compiler, tmp_path):
    # A Sloppy program printing a function shows `<fn>`; only a Sloppy source reaches that text.
    source, output = tmp_path / 'input.jo', tmp_path / 'program'
    source.write_text('f = (x: int) -> int: x\nmain = ():\n    print(f)\n')
    driver = ("use 'main.jo'\nmain = ():\n    lower_test_cli()\n"
              f'    print(read_file({json.dumps(str(output))}) ?? "")\n')
    image = compare_leaf(compiler, tmp_path, False, driver,
                         extra_stems=('lower_group',),
                         jo_doubles=modules_for(source, output))
    assert image == output.read_bytes() + b'\n'
    ran = subprocess.run([output], capture_output=True, timeout=30)
    assert (ran.returncode, ran.stdout) == (0, b'<fn>\n')


@pytest.mark.parametrize(('kind', 'message'), [
    ('nil', 'unsupported expression in codegen (nil)'),
    ('intrinsic', 'intrinsic not supported in codegen'),
])
def test_lower_group_errors(compiler, tmp_path, kind, message):
    source, output = tmp_path / 'input.dewy', tmp_path / 'program'
    source.write_text('main=()=>{}\n')
    modules = modules_for(source, output)
    # A diagnostic service double makes the exact lowerer's message observable
    # without unrelated source-location rendering or process-wide error queues.
    diagnostic_status(modules, 'fatal')
    driver = ("use 'main.jo'\nuse 'ast.jo'\nuse 'types.jo'\n"
              'main = ():\n    lower_test_cli()\n'
              f'    bad = mk(.{kind}, 0)\n    nodes[bad].type = i32(T_INT)\n'
              '    gen_expr(bad)\n    print("unreachable")\n')
    out = compare_leaf(compiler, tmp_path, False, driver, status=41,
                       extra_stems=('lower_group',), jo_doubles=modules)
    assert out == (message + '\n').encode()
