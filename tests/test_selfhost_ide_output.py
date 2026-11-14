"""Diagnostic replay and buffered language-server output agree with frozen ownership."""
from tests.selfhost_build_double import compare_builds
from tests.test_selfhost_lsp_ops import compare_session
from tests.support import ROOT, compiler  # noqa: F401


def test_ide_output_session(compiler, tmp_path, monkeypatch):
    assert '"textDocument/publishDiagnostics"' in compare_session(compiler, tmp_path, monkeypatch, ('ide_output',))


def test_ide_output_error_replay_twins(compiler, tmp_path, monkeypatch):
    (tmp_path / 'errors.dewy').write_text('first=()=>missing_one()\nsecond=()=>missing_two()\nmain=()=>{first(); second();}\n')
    paths = ['errors.dewy']
    paths += [str(p.relative_to(ROOT)) for p in sorted((ROOT / 'tests/cases/type_error').glob('*.dewy'))[:5]]
    results = compare_builds(compiler, tmp_path, monkeypatch, ('ide_output',), paths,
                             flags=((), ('--release',)))
    assert results[0][2] != 0 and 'missing_one' in results[0][4]
