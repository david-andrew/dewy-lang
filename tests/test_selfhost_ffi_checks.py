"""Foreign boundary checks preserve C layouts and unsafe diagnostics."""
import json
import subprocess

import pytest

from tests.selfhost_diagnostic_double import diagnostic_status
from tests.support import ROOT, compiler  # noqa: F401
from tests.selfhost_expr_double import compare_leaf
from tests.selfhost_lower_double import modules_for


@pytest.mark.parametrize('optimized', [False, True], ids=['default', 'release'])
@pytest.mark.parametrize('case', ['record_layout', 'ptr_round_trip'])
def test_ffi_checks_programs(compiler, tmp_path, monkeypatch, optimized, case):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    source, output = tmp_path / 'input.dewy', tmp_path / 'program'
    source.write_text((ROOT / 'tests/cases/ffi' / (case + '.dewy')).read_text())
    driver = ("use 'main.jo'\nmain = ():\n    lower_test_cli()\n"
              f'    print(read_file({json.dumps(str(output))}) ?? "")\n')
    image = compare_leaf(compiler, tmp_path, False, driver,
                         extra_stems=('ffi_checks',),
                         jo_doubles=modules_for(source, output, 'ffi_checks',
                                                flags=('--release',) if optimized else ()))
    assert image == output.read_bytes() + b'\n'
    ran = subprocess.run([output], capture_output=True, timeout=30)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout == (ROOT / 'tests/cases/ffi' / (case + '.out')).read_bytes()


@pytest.mark.parametrize('case,expected', [('extern_needs_unsafe', b'unsafe boundary'), ('record_layout_managed', b'has no C layout'), ('extern_math_int', b'cannot cross the C boundary'), ('extern_array', b'cannot cross the C boundary')])
def test_ffi_checks_diagnostics(compiler, tmp_path, monkeypatch, case, expected):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    source, output = tmp_path / 'input.dewy', tmp_path / 'program'
    source.write_text((ROOT / 'tests/cases/ffi' / (case + '.dewy')).read_text())
    modules = modules_for(source, output, 'ffi_checks')
    diagnostic_status(modules, 'fatal')
    driver = "use 'main.jo'\nmain = ():\n    lower_test_cli()\n    print(\"unreachable\")\n"
    out = compare_leaf(compiler, tmp_path, False, driver, status=41,
                       extra_stems=('ffi_checks',), jo_doubles=modules)
    assert expected in out and b'unreachable' not in out
