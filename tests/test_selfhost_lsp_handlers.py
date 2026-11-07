"""Language-server handlers (definitions, references, highlights, symbols, formatting, renames, inlay hints,
workspace symbols, offsets and the request queue) agree with frozen Jo over one session."""
from tests.support import compiler  # noqa: F401
from tests.test_selfhost_lsp_ops import compare_session


def test_lsp_handlers_session(compiler, tmp_path, monkeypatch):
    assert '"changes"' in compare_session(compiler, tmp_path, monkeypatch, ('lsp_handlers',))
