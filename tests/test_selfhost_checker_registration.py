"""Register a module once across a diamond and enter only the selected top-level branch."""
from tests.selfhost_build_double import compare_builds
from tests.support import compiler  # noqa: F401


def test_checker_registration_twins(compiler, tmp_path, monkeypatch):  # noqa: F811
    selected = tmp_path / 'selected.jo'
    selected.write_text('when true:\n    answer = () -> int: 42\n'
                        'else:\n    use "missing.jo"\n'
                        'when false:\n    use "also_missing.jo"\n'
                        'main = ():\n    print(answer())\n')
    paths = (selected, 'tests/cases/modules/cycle_diamond.dewy',
             'tests/cases/target/unsupported_name_folds.dewy')
    results = compare_builds(compiler, tmp_path, monkeypatch, ('checker_registration',), paths)
    assert all(row[2] == 0 for row in results)
