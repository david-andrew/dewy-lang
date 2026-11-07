"""Language-server requests (completions, signatures, semantic tokens, symbols, checks, uses, import
targets and paths) agree with frozen Jo over one language-server session."""
from tests.support import compiler  # noqa: F401
from tests.test_selfhost_lsp_ops import compare_session


def test_lsp_requests_session(compiler, tmp_path, monkeypatch):
    assert '"textDocument/publishDiagnostics"' in compare_session(compiler, tmp_path, monkeypatch, ('lsp_requests',))
