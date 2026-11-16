"""Release null checks found by their fault: opt_rewrite.dewy and its frozen twin build the same program."""
import json
import subprocess

from tests.support import ROOT, compiler  # noqa: F401
from tests.selfhost_expr_double import compare_leaf
from tests.selfhost_lower_double import modules_for


def test_opt_rewrite_nullchk_twins(compiler, tmp_path, monkeypatch):  # noqa: F811
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    source, output = tmp_path / 'input.dewy', tmp_path / 'program'
    source.write_text((ROOT / 'tests/cases/null_fault/param.dewy').read_text())
    driver = ("use 'main.jo'\nmain = ():\n    lower_test_cli()\n"
              f'    print(read_file({json.dumps(str(output))}) ?? "")\n')
    image = compare_leaf(compiler, tmp_path, False, driver, extra_stems=('opt_rewrite',),
                         jo_doubles=modules_for(source, output, 'opt_rewrite', flags=('--release',)))
    assert image == output.read_bytes() + b'\n'
    ran = subprocess.run([output], capture_output=True, timeout=30)
    assert ran.returncode == 101, ran.stderr
    assert b'index 3 out of bounds (length 0: it is empty)' in ran.stderr
