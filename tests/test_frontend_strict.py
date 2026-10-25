"""DEWY_FRONTEND=strict stops wherever the reference grammar would re-read a statement: these
programs read directly throughout (compare mode agrees), and these mistakes are reported by the
direct parser itself, exactly as the reference path reports them."""
import os
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401

DIRECT = [
    'tests/cases/numeric/matrix_slices.dewy',
    'tests/cases/numeric/matrix_stepped_read.dewy',
    'tests/cases/refinements/nonzero.dewy',
    'tests/cases/ffi/intrinsic.dewy',
    'tests/cases/partial/operator_global.dewy',
    'tests/cases/match/lookup_int_results.dewy',
    'tests/cases/directives/no_hidden_costs.dewy',
    'tests/ladder/99_dewy_frontend/design.dewy',
    'lib/new/dewy/platformer.dewy',
]

REPORTED = [
    'unpack/default_reserved', 'end/reserved_unpack', 'unpack/duplicate', 'unpack/leaf_duplicate',
    'unpack/nested_duplicate', 'unpack/loop_duplicate', 'unpack/param_nested_duplicate',
    'unpack/param_duplicate', 'closure/capture_mixed_duplicate', 'closure/capture_parameter_conflict',
    'closure/capture_parameter_conflict_reversed', 'closure/capture_unpack_conflict',
    'closure/shared_duplicate',
]


def check(compiler, source, mode=None):
    env = dict(os.environ)
    env.pop('DEWY_FRONTEND', None)
    if mode:
        env['DEWY_FRONTEND'] = mode
    return subprocess.run([compiler, 'check', source], cwd=ROOT, env=env, capture_output=True, text=True,
                          timeout=120)


@pytest.mark.parametrize('source', DIRECT)
def test_reads_directly(compiler, source):
    for mode in ('strict', 'compare'):
        result = check(compiler, source, mode)
        assert result.returncode == 0, f'{mode}: {result.stdout}{result.stderr}'


@pytest.mark.parametrize('case', REPORTED)
def test_reports_directly(compiler, case):
    source = f'tests/cases/{case}.dewy'
    expected = (ROOT / 'tests' / 'cases' / f'{case}.err').read_text().strip()
    default = check(compiler, source)
    strict = check(compiler, source, 'strict')
    assert default.returncode != 0 and expected in default.stdout + default.stderr
    assert (strict.returncode, strict.stdout, strict.stderr) == (default.returncode, default.stdout, default.stderr)
