"""A differential language-server session publishes the same messages however long the client pauses:
lowering in the server's pauses (which would publish again, with the call-style warning once more) is
off in these sessions, so leaf and twin builds compare equal on a loaded machine too."""
import time

import tests.selfhost_lsp_double as double
from tests.support import compiler  # noqa: F401
from tests.test_selfhost_lsp_ops import GAME, MODEL


def test_pauses_publish_nothing_more(compiler, tmp_path, monkeypatch):
    root = tmp_path / 'project'
    root.mkdir()
    (root / 'model.dewy').write_text(MODEL)
    (root / 'game.dewy').write_text(GAME)
    model, game = (root / 'model.dewy').as_uri(), (root / 'game.dewy').as_uri()
    at = {'textDocument': {'uri': game}, 'position': {'line': 3, 'character': 6}}
    steps = [('text', (model, MODEL, 1)), ('text', (game, GAME, 1)), ('textDocument/hover', at),
             ('text', (game, GAME.replace('{total} and', '{missing} and'), 2)),
             ('textDocument/hover', at), ('textDocument/definition', at)]
    prompt = double.session(compiler, root, steps)
    assert 'drop the `()`: `fresh` gives a value' in prompt
    plain = double.Recorder.set_text

    def paused(self, *args):
        result = plain(self, *args)
        time.sleep(0.6)  # (twice the server's quiet interval)
        return result
    monkeypatch.setattr(double.Recorder, 'set_text', paused)
    assert double.session(compiler, root, steps) == prompt
