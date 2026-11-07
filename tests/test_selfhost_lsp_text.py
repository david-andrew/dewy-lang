"""Language-server text helpers (UTF-16 positions, offsets, names, words, indentation, hovers, edits,
closing and publishing) agree with frozen Jo over one language-server session."""
from tests.support import compiler  # noqa: F401
from tests.test_selfhost_lsp_ops import compare_session


def test_lsp_text_session(compiler, tmp_path, monkeypatch):
    assert '"textDocument/publishDiagnostics"' in compare_session(compiler, tmp_path, monkeypatch, ('lsp_text',))
