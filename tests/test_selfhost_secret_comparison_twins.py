"""Secret equality and ordering use the same lowering in leaves and frozen twins."""

from tests.selfhost_facts_double import compare_facts
from tests.support import compiler  # noqa: F401


def test_secret_comparison_twins(compiler, tmp_path, monkeypatch):
    assert compare_facts(
        compiler, tmp_path, monkeypatch,
        [
            'secrets_taken/compare',
            'secrets_nested/compare',
            'secrets_nested/math_compare',
            'secrets_nested/isolated_record',
        ],
        leaves=('secret_checks', 'lower_group', 'lower_helpers', 'lower_primitives'),
    ) == 4
