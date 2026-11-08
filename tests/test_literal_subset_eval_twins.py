"""Literal subset ordinals agree in the live and frozen constant evaluators."""
import os
import subprocess

from tests.support import ROOT, compiler  # noqa: F401
from tests.test_selfhost_checked_eval import frozen_evaluator  # noqa: F401


def test_literal_subset_eval_twins(compiler, frozen_evaluator, tmp_path):
    source = ROOT / 'tests/cases/literal_subset_bindings/subsets.dewy'
    output = tmp_path / 'program'
    env = {**os.environ, 'DEWY_CORE_LIB': str(ROOT / 'lib'), 'DEWY_EMIT_WORKERS': '1'}
    results = []
    for binary in (compiler, frozen_evaluator):
        built = subprocess.run([binary, 'build', source, '-o', output],
                               env=env, capture_output=True, timeout=120)
        assert built.returncode == 0, built.stderr.decode()
        results.append((built.stdout, built.stderr, output.read_bytes()))
    assert results[0] == results[1]
