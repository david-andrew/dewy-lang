"""Scoped allocation checks, promotion and capacity proofs match frozen code."""
import json
import subprocess

import pytest

from tests.selfhost_diagnostic_double import diagnostic_status
from tests.support import ROOT, compiler  # noqa: F401
from tests.selfhost_expr_double import compare_leaf
from tests.selfhost_lower_double import modules_for


@pytest.mark.parametrize('optimized', [False, True], ids=['default', 'release'])
@pytest.mark.parametrize('case', ['promote_values', 'strict_capacity', 'nested'])
def test_arena_ops_programs(compiler, tmp_path, monkeypatch, optimized, case):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    source, output = tmp_path / 'input.dewy', tmp_path / 'program'
    source.write_text((ROOT / 'tests/cases/arena' / (case + '.dewy')).read_text())
    driver = ("use 'main.jo'\nmain = ():\n    lower_test_cli()\n"
              f'    print(read_file({json.dumps(str(output))}) ?? "")\n')
    image = compare_leaf(compiler, tmp_path, False, driver,
                         extra_stems=('arena_ops',),
                         jo_doubles=modules_for(source, output, 'arena_ops',
                                                flags=('--release',) if optimized else ()))
    assert image == output.read_bytes() + b'\n'
    ran = subprocess.run([output], capture_output=True, timeout=30)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout == (ROOT / 'tests/cases/arena' / (case + '.out')).read_bytes()


@pytest.mark.parametrize('case,expected', [
    ('reject_outer_push', b'declared outside the expression'),
    ('reject_explicit_copies', b'.copy()'),
    ('reject_closure_result', b'cannot be copied yet'),
    ('reject_strict_capacity', b'not proven to fit its arena'),
])
def test_arena_ops_diagnostics(compiler, tmp_path, monkeypatch, case, expected):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    source, output = tmp_path / 'input.dewy', tmp_path / 'program'
    source.write_text((ROOT / 'tests/cases/arena' / (case + '.dewy')).read_text())
    modules = modules_for(source, output, 'arena_ops')
    diagnostic_status(modules, 'fatal')
    driver = "use 'main.jo'\nmain = ():\n    lower_test_cli()\n    print(\"unreachable\")\n"
    out = compare_leaf(compiler, tmp_path, False, driver, status=41,
                       extra_stems=('arena_ops',), jo_doubles=modules)
    assert expected in out and b'unreachable' not in out
