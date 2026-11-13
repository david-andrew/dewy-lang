"""Changed Dewy leaves need a changed frozen twin and a named differential."""

import subprocess

from tools.compiler.twin_guard import changed_leaf_errors, check_range, names_leaf


def test_missing_twin_and_differential_are_reported():
    errors = changed_leaf_errors({'compiler/example.dewy'}, lambda stem: False)
    assert errors == [
        'compiler/example.dewy: frozen twin compiler/example.jo did not change',
        'compiler/example.dewy: no named differential test in tests/test_*.py',
    ]


def test_paired_leaf_with_named_differential_passes():
    assert changed_leaf_errors({'compiler/example.dewy', 'compiler/example.jo'},
                               lambda stem: stem == 'example') == []
    assert names_leaf('tests/test_selfhost_example.py',
                           'assert compare_facts(compiler, tmp_path, monkeypatch, cases)', 'example')
    assert not names_leaf('tests/test_example.py', 'assert value == 1', 'example')
    assert not names_leaf('tests/test_other.py', 'assert compare_builds(...)', 'example')


def test_forwarding_twin_counts_its_seed():
    assert changed_leaf_errors({'compiler/example.dewy', 'compiler/example_seed.jo'},
                               lambda stem: stem == 'example') == []


def test_documented_bootstrap_stub_is_exempt():
    assert changed_leaf_errors({'compiler/call_forward.dewy'}, lambda stem: False) == []


def test_git_range_requires_both_twin_and_named_test(tmp_path):
    def run(*args):
        return subprocess.check_output(['git', '-C', str(tmp_path), *args], text=True).strip()

    def commit(message):
        run('add', '.')
        run('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
            'commit', '-qm', message)
        return run('rev-parse', 'HEAD')

    run('init', '-q')
    (tmp_path / 'compiler').mkdir()
    (tmp_path / 'tests').mkdir()
    (tmp_path / 'compiler/example.dewy').write_text('answer=()=>1\n')
    (tmp_path / 'compiler/example.jo').write_text('answer = () -> int: 1\n')
    base = commit('base')
    (tmp_path / 'compiler/example.dewy').write_text('answer=()=>2\n')
    leaf_only = commit('leaf')
    assert any('did not change' in error for error in check_range(tmp_path, base, leaf_only))
    (tmp_path / 'compiler/example.jo').write_text('answer = () -> int: 2\n')
    no_test = commit('twin')
    assert check_range(tmp_path, base, no_test) == [
        'compiler/example.dewy: no named differential test in tests/test_*.py']
    (tmp_path / 'tests/test_selfhost_example.py').write_text(
        'def test_example():\n    assert compare_builds(...)\n')
    covered = commit('test')
    assert check_range(tmp_path, base, covered) == []
