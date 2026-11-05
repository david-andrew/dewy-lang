"""Mathematical lowering preserves wide values, reset paths and word proofs."""
import json
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401
from tests.selfhost_expr_double import compare_leaf
from tests.selfhost_lower_double import modules_for

CASES = ('bigint/above_int64_paths', 'bigint/word_sum_compare',
         'exact_int/reset', 'exact_int/wide_modulo')


@pytest.mark.parametrize('optimized', [False, True], ids=['default', 'release'])
def test_math_ops_twins(compiler, tmp_path, monkeypatch, optimized):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    source, output = tmp_path / 'input.dewy', tmp_path / 'program'
    imports, calls, expected = [], [], b''
    for index, case in enumerate(CASES):
        name = f'case{index}.dewy'
        (tmp_path / name).write_text((ROOT / 'tests/cases' / (case + '.dewy')).read_text())
        imports.append(f'from p"{name}" import (main as sample{index})')
        calls.append(f'sample{index}()')
        expected += (ROOT / 'tests/cases' / (case + '.out')).read_bytes()
    source.write_text('$runtime_checks\n' + '\n'.join(imports) + '\nmain=()=>{\n' + '\n'.join(calls) + '\n}\n')
    driver = ("use 'main.jo'\nmain = ():\n    lower_test_cli()\n"
              f'    print(read_file({json.dumps(str(output))}) ?? "")\n')
    image = compare_leaf(compiler, tmp_path, False, driver,
                         extra_stems=('math_ops',),
                         jo_doubles=modules_for(source, output, 'math_ops',
                                                flags=('--release',) if optimized else ()))
    assert image == output.read_bytes() + b'\n'
    ran = subprocess.run([output], capture_output=True, timeout=30)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout == expected
