"""Editor index queries (references, completions, signatures, hints, files, offered names) agree with
frozen Jo over one language-server session."""
from tests.support import compiler  # noqa: F401
from tests.test_selfhost_lsp_ops import compare_session


def test_ide_index_session(compiler, tmp_path, monkeypatch):
    assert '"textDocument/publishDiagnostics"' in compare_session(compiler, tmp_path, monkeypatch, ('ide_index',))
