"""Parallel lowering preserves scalar jobs, captures and nonzero range offsets."""
import json
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401
from tests.selfhost_expr_double import compare_leaf
from tests.selfhost_lower_double import modules_for
from tools.cores import on_cores

SOURCE = '''
$runtime_checks

fib=(n:int64):>int64=>{
    if n <? 2 {return n}
    let parts=parallel_range(2 (i:int64)=>fib(n-1-i))
    return parts[0]+parts[1]
}
main=():>void=>{
    printl(fib(8))
    let values=[parallel i in [3..7) i*2]
    printl"{values[0]} {values[3]}"
    let narrow=[parallel i in [0..8) int8(i-5)]
    printl"{narrow[0]} {narrow[7]}"
}
'''


@pytest.mark.parametrize('optimized', [False, True], ids=['default', 'release'])
def test_parallel_ops_twins(compiler, tmp_path, monkeypatch, optimized):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    source, output = tmp_path / 'input.dewy', tmp_path / 'program'
    source.write_text(SOURCE)
    driver = ("use 'main.jo'\nmain = ():\n    lower_test_cli()\n"
              f'    print(read_file({json.dumps(str(output))}) ?? "")\n')
    image = compare_leaf(compiler, tmp_path, False, driver,
                         extra_stems=('parallel_ops',),
                         jo_doubles=modules_for(source, output, 'parallel_ops',
                                                flags=('--release',) if optimized else ()))
    assert image == output.read_bytes() + b'\n'
    for workers in (1, 2):
        ran = subprocess.run(on_cores([output], workers), capture_output=True, timeout=30)
        assert ran.returncode == 0, ran.stderr
        assert ran.stdout == b'21\n6 12\n-5 2\n'
