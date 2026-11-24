"""Literal subset ordinals agree in the live and frozen constant evaluators."""
import os
import subprocess

from tests import whole_oracle

from tests.support import ROOT, compiler  # noqa: F401
from tests import leaf_oracle


def test_literal_subset_eval_twins(compiler, tmp_path):
    source = ROOT / 'tests/cases/literal_subset_bindings/subsets.dewy'
    output = tmp_path / 'program'
    env = {**os.environ, 'DEWY_CORE_LIB': str(ROOT / 'lib'), 'DEWY_EMIT_WORKERS': '1'}
    arguments = ['build', source, '-o', output]
    built = subprocess.run([compiler, *arguments], env=env, capture_output=True, timeout=120)
    assert built.returncode == 0, built.stderr.decode()
    leaf_oracle.check_entry(lambda: whole_oracle.build(arguments, 0, built.stdout, built.stderr, [output], tmp_path))
