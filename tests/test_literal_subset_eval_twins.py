"""Literal subset ordinals agree in the live and frozen constant evaluators."""
import os
import subprocess

from tests import whole_oracle

from tests.support import ROOT, compiler  # noqa: F401
from tests.test_selfhost_checked_eval import frozen_evaluator  # noqa: F401
from tests import leaf_oracle


def test_literal_subset_eval_twins(compiler, frozen_evaluator, tmp_path):
    source = ROOT / 'tests/cases/literal_subset_bindings/subsets.dewy'
    output = tmp_path / 'program'
    env = {**os.environ, 'DEWY_CORE_LIB': str(ROOT / 'lib'), 'DEWY_EMIT_WORKERS': '1'}
    results = []
    for binary in leaf_oracle.pair(compiler, frozen_evaluator):
        arguments = ['build', source, '-o', output]
        built = subprocess.run([binary, *arguments], env=env, capture_output=True, timeout=120)
        assert built.returncode == 0, built.stderr.decode()
        results.append((built.stdout, built.stderr, output.read_bytes()))
        if len(results) == 1:
            outcome = whole_oracle.build(arguments, 0, built.stdout, built.stderr, [output], tmp_path)
    assert len(results) == 1 or results[0] == results[1]
    leaf_oracle.check_entry(lambda: outcome)
