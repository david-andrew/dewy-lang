"""Member lowering preserves literal tables, Unicode bytes and fallback paths."""
import json
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401
from tests.selfhost_expr_double import compare_leaf
from tests.selfhost_lower_double import modules_for

SOURCE = '''
$runtime_checks

make=()=>{
    let table:dict<string string>=[]
    loop s in members('aa'|'bbb'|'é'|'💧') {table[s]=s}
    return table
}
printl(make())
loop s in members('aa'|'bbb') {
    let raw=bytes(s)
    $assert raw.length >? 1
    let first=raw[0]
    $assert first >=? 0
}
loop s in members('aa'|'bbb') {
    if s =? 'aa' {continue}
    printl(s)
}
'''


@pytest.mark.parametrize('optimized', [False, True], ids=['default', 'release'])
def test_member_ops_twins(compiler, tmp_path, monkeypatch, optimized):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    source, output = tmp_path / 'input.dewy', tmp_path / 'program'
    source.write_text(SOURCE)
    driver = ("use 'main.jo'\nmain = ():\n    lower_test_cli()\n"
              f'    print(read_file({json.dumps(str(output))}) ?? "")\n')
    image = compare_leaf(compiler, tmp_path, False, driver,
                         extra_stems=('member_ops',),
                         jo_doubles=modules_for(source, output, 'member_ops',
                                                flags=('--release',) if optimized else ()))
    assert image == output.read_bytes() + b'\n'
    ran = subprocess.run([output], capture_output=True, timeout=30)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout == '["aa" -> "aa" "bbb" -> "bbb" "é" -> "é" "💧" -> "💧"]\nbbb\n'.encode()
