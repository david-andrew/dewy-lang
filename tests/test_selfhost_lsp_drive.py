"""The language server's process code (reading messages, waiting for input, checks in a child
process, the request loop, `lsp --dump` and `lsp --child`) as a Dewy leaf agrees with frozen Jo."""
import json
import subprocess

from tests.selfhost_lsp_double import leaf_compilers, session
from tests.support import ROOT, compiler  # noqa: F401
from tests.test_selfhost_lsp_ops import GAME, MODEL, compare_session


def test_lsp_drive_session_matches_twin(compiler, tmp_path, monkeypatch):
    compare_session(compiler, tmp_path, monkeypatch, ('lsp_drive',))


def replies_and_notices(log):
    """The replies in order, and each document's distinct notifications: after didSave the server
    rechecks once no input is pending, and lowers after a quiet moment, so how many diagnostics
    notifications come, and between which replies, depends on timing (in either build)."""
    messages = json.loads(log)
    replies = [m for m in messages if 'id' in m]
    notices = {}
    for m in messages:
        if 'id' not in m:
            key = (m['method'], m.get('params', {}).get('uri', ''))
            notices.setdefault(key, set()).add(json.dumps(m, sort_keys=True))
    return replies, notices


def test_lsp_drive_notifications_match_twin(compiler, tmp_path, monkeypatch):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    root = tmp_path / 'project'
    root.mkdir()
    (root / 'model.dewy').write_text(MODEL)
    (root / 'game.dewy').write_text(GAME)
    game = (root / 'game.dewy').as_uri()
    folder = {'uri': root.as_uri(), 'name': 'project'}
    steps = [
        ('text', (game, GAME, 1)),
        ('notify', ('textDocument/didSave', {'textDocument': {'uri': game}})),
        ('notify', ('workspace/didChangeWorkspaceFolders', {'event': {'added': [folder], 'removed': []}})),
        ('workspace/symbol', {'query': 'fresh'}),
        ('notify', ('workspace/didChangeWorkspaceFolders', {'event': {'added': [], 'removed': [folder]}})),
        ('notify', ('workspace/didChangeWatchedFiles', {'changes': []})),
        ('textDocument/hover', {'textDocument': {'uri': game}, 'position': {'line': 3, 'character': 6}}),
        ('textDocument/unknownThing', {}),
    ]
    dewy, jo = leaf_compilers(compiler, tmp_path, ('lsp_drive',))
    expected = replies_and_notices(session(jo, root, steps))
    assert replies_and_notices(session(dewy, root, steps)) == expected
    assert len(expected[0]) == 5 and expected[1], expected


def test_lsp_drive_dump_and_child_match_twin(compiler, tmp_path, monkeypatch):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    (tmp_path / 'model.dewy').write_text(MODEL)
    (tmp_path / 'game.dewy').write_text(GAME)
    dewy, jo = leaf_compilers(compiler, tmp_path, ('lsp_drive',))

    def run(binary, args, stdin='', env=()):
        r = subprocess.run([binary, 'lsp', *args], cwd=tmp_path, input=stdin, capture_output=True,
                           text=True, timeout=60, check=False, env={**__import__('os').environ, **dict(env)})
        return r.returncode, r.stdout, r.stderr.replace(str(binary), 'dewy-core')
    for env in ((), (('DEWY_LOWER', '1'),), (('DEWY_WIDE', '1'), ('DEWY_SENTINEL', '1'))):
        got, expected = run(dewy, ['--dump', 'game.dewy'], env=env), run(jo, ['--dump', 'game.dewy'], env=env)
        assert got == expected and expected[1], env
    # (the Windows child's request: each string as "<length>:<bytes>")
    path = str(tmp_path / 'game.dewy')
    edited = GAME.replace('{total} and', '{missing} and')
    parts = [path, path, '000', '0', '1', path, edited]
    request = ''.join(f'{len(p.encode())}:{p}' for p in parts)
    got, expected = run(dewy, ['--child'], request), run(jo, ['--child'], request)
    assert got == expected and 'missing' in expected[1], expected
