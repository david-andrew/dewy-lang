"""A landing checks live-only sources and named behavior coverage at the target revision."""
import subprocess

from tools.compiler.twin_guard import check_range


def test_git_range_requires_live_inputs_and_named_test(tmp_path):
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
    base = commit('base')
    (tmp_path / 'compiler/example.dewy').write_text('answer=()=>2\n')
    leaf_only = commit('leaf')
    assert check_range(tmp_path, base, leaf_only) == ['compiler/example.dewy: no named behavior test']
    (tmp_path / 'tests/test_selfhost_example.py').write_text(
        'def test_example():\n    assert compare_builds(...)\n')
    covered = commit('test')
    assert check_range(tmp_path, base, covered) == []
    (tmp_path / 'compiler/example.jo').write_text('answer = () -> int: 2\n')
    frozen = commit('twin')
    assert check_range(tmp_path, covered, frozen) == [
        'compiler/example.jo: historical bootstrap source in the live tree']
    (tmp_path / 'compiler/example.jo').unlink()
    (tmp_path / 'compiler/example.dewy').unlink()
    assert check_range(tmp_path, frozen, commit('remove module')) == []
