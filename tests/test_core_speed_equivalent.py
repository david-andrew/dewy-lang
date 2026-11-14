"""An equivalent source control changes implementation language, not input paths or capabilities."""
from pathlib import Path
import pytest
from tools.compiler import speed_equivalent as eq
from tests.support import compiler


def tree(tmp_path):
    root = tmp_path / 'root'
    src = root / 'compiler'
    src.mkdir(parents=True)
    (src / 'main.jo').write_text("use 'leaf.dewy'\nprint(\"leaf.dewy\")\n")
    (src / 'leaf.dewy').write_text('from p"helper.dewy" import f\n')
    (src / 'leaf.jo').write_text("use 'helper.dewy'\n")
    (src / 'helper.dewy').write_text('f=()=>0\n')
    (src / 'helper.jo').write_text('f=(): 0\n')
    return root


def test_equivalent_source_keeps_path_and_changes_imports_only(tmp_path):
    root = tree(tmp_path)
    calls = []
    def count(source):
        compiler = Path(source).parent
        calls.append((source, {p.name: p.read_text() for p in compiler.iterdir()}))
        return (101, 100)[len(calls)-1]
    result = eq.measure(root, tmp_path / 'staged', ('leaf', 'helper'), count)
    assert calls[0][0] == calls[1][0]
    assert calls[1][1]['main.jo'] == "use 'leaf.jo'\nprint(\"leaf.dewy\")\n"
    assert calls[1][1]['leaf.dewy'] == 'from p"helper.jo" import f\n'
    assert calls[1][1]['leaf.jo'] == "use 'helper.jo'\n"
    assert (root / 'compiler/main.jo').read_text() == calls[0][1]['main.jo']
    assert result.ratio == 1.01 and not result.meets_target


def test_equivalent_source_selection_includes_uncommitted_leaves(tmp_path):
    root = tree(tmp_path)
    leaves = eq.selected(root, 'base', ['helper'], lambda *args: 'compiler/helper.dewy\n')
    assert leaves == ('helper', 'leaf')
    with pytest.raises(ValueError, match='missing equivalent'):
        eq.selected(root, None, ['missing'], None)
    with pytest.raises(ValueError, match='invalid'):
        eq.selected(root, None, ['../leaf'], None)
    with pytest.raises(ValueError, match='bootstrap stub'):
        eq.selected(root, None, ['call_forward'], None)


def test_equivalent_source_target_is_not_rounded(capsys):
    result = eq.Equivalent(('leaf',), 1_000_001, 1_000_000)
    eq.report(result)
    assert 'target <=1.00x; not met' in capsys.readouterr().out
    assert not result.meets_target
    assert eq.Equivalent(('leaf',), 99, 100).meets_target
    assert eq.Equivalent(('leaf',), 100, 100).meets_target


def test_equivalent_source_failure_is_not_skipped(tmp_path):
    root = tree(tmp_path)
    calls = []
    def count(source):
        calls.append(source)
        if len(calls) == 2:
            raise RuntimeError('twin cannot compile current source')
        return 100
    with pytest.raises(RuntimeError, match='twin cannot compile'):
        eq.measure(root, tmp_path / 'stage', ('leaf',), count)


def test_source_cost_gate_does_not_round_away_excess(tmp_path, monkeypatch):
    from tools.compiler import speed
    root = tree(tmp_path)
    monkeypatch.setattr(speed, 'ROOT', root)
    monkeypatch.setattr(speed, 'CACHE', tmp_path / 'cache')
    counts = iter((1_000_000, 1_010_001))
    monkeypatch.setattr(speed, 'measure', lambda *args: next(counts))
    base = speed.Toolchain('base', tmp_path / 'compiler', root / 'lib', root)
    failures = []
    speed.source_row(None, None, base, {}, [], 1.0, failures)
    assert len(failures) == 1
    assert failures[0][2] > 1.0


def test_equivalent_source_defaults_to_all_real_twins(tmp_path):
    root = tree(tmp_path)
    (root / 'compiler/call_forward.dewy').write_text('real implementation')
    (root / 'compiler/call_forward.jo').write_text('bootstrap stub')
    for name in eq.FIXED_LAYOUTS:
        (root / 'compiler' / (name + '.dewy')).write_text('literal union layout')
        (root / 'compiler' / (name + '.jo')).write_text('enum layout')
    assert eq.selected(root, None, [], None) == ('helper', 'leaf')
    (root / 'compiler/helper.jo').unlink()
    with pytest.raises(ValueError, match='missing equivalent source'):
        eq.selected(root, None, [], None)


def test_equivalent_source_current_layout_contracts(compiler, tmp_path):
    """The real frozen closure must retain the literal-union types its Dewy stub needs."""
    import shutil
    import subprocess
    root = Path(__file__).resolve().parents[1]
    source = tmp_path / 'compiler'
    shutil.copytree(root / 'compiler', source)
    leaves = eq.selected(root, None, [], None)
    eq.freeze(source, leaves)
    run = subprocess.run([compiler, 'check', source / 'main.jo'],
                         text=True, capture_output=True, timeout=120)
    assert run.returncode == 0, run.stdout + run.stderr


def test_equivalent_source_keeps_imports_inside_templates(tmp_path):
    source = tmp_path / 'compiler'
    source.mkdir()
    template = '# use "leaf.dewy"\ntext="""use "leaf.dewy"\nfrom p"leaf.dewy" import f\n"""\n'
    path = source / 'caller.jo'
    path.write_text(template + 'import "leaf.dewy" as leaf\nuse "leaf.dewy"\n')
    eq.freeze(source, ('leaf',))
    assert path.read_text() == template + 'import "leaf.jo" as leaf\nuse "leaf.jo"\n'
