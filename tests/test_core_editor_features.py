"""Language-server features on today's Dewy surface, through the editor protocol."""
import os
from pathlib import Path

import pytest

from tests.test_core_editor import Client as EditorClient


class Client(EditorClient):
    """The editor tests' client, keeping the server's capabilities and answering errors too."""

    def request(self, method, params):
        result = super().request(method, params)
        if method == 'initialize':
            self.capabilities = result['capabilities']
        return result

    def request_raw(self, method, params):
        self.serial += 1
        self.send(method, params, self.serial)
        while True:
            message = self.receive()
            if message.get('id') == self.serial:
                return message
            self.messages.append(message)

MODEL = '''# A deterministic model.
Point:type=[x:float64 y:float64]
World:type=[position:Point score:int64]

# A fresh world.
fresh=():>World=>World[Point[1.0 2.0] 0]

advance=(@world:World dt:float64 pointer:float64):>void=>{
    let before=world.position.y
    world.position.x+=dt*pointer
    world.score+=1
}
'''

GAME = '''from p"model.dewy" import fresh, advance
let world=fresh()
step=(dt:float64):>void=>{
    advance(@world min(dt 0.05) 3.0)
}
test "fresh world" {
    assert(world.score =? 0)
}
test "steps" {
    step(0.1)
    assert(world.score =? 1)
}
main=():>int64=>{
    step(0.1)
    return world.score
}
'''


def compiler_path():
    value = os.environ.get('DEWY_CORE_COMPILER')
    if not value:
        pytest.skip('set DEWY_CORE_COMPILER for the editor checks')
    return Path(value).resolve(strict=True)


def position(text, needle, offset=0, nth=0):
    index = -1
    for _ in range(nth + 1):
        index = text.index(needle, index + 1)
    index += offset
    line = text.count('\n', 0, index)
    start = text.rfind('\n', 0, index) + 1
    return {'line': line, 'character': len(text[start:index].encode('utf-16-le')) // 2}


@pytest.fixture
def project(tmp_path):
    (tmp_path / 'model.dewy').write_text(MODEL)
    (tmp_path / 'game.dewy').write_text(GAME)
    client = Client(compiler_path(), tmp_path)
    try:
        for name, text in (('model.dewy', MODEL), ('game.dewy', GAME)):
            diagnostics = client.set_text((tmp_path / name).as_uri(), text, 1)
            assert not [d for d in diagnostics if d['severity'] == 1], diagnostics
        yield client, tmp_path
    finally:
        client.close()


def at(path, text, needle, offset=0, nth=0):
    return {'textDocument': {'uri': path.as_uri()}, 'position': position(text, needle, offset, nth)}


def hover_text(client, params):
    result = client.request('textDocument/hover', params)
    return result['contents']['value'] if result else None


def test_dewy_hover_fields_and_imports(project):
    client, root = project
    model = root / 'model.dewy'
    game = root / 'game.dewy'
    # A field written among others shows alone, without the comment above its record.
    text = hover_text(client, at(model, MODEL, 'world.position.x', 7))
    assert text == '```dewy\n(field) position: Point\n```', text
    text = hover_text(client, at(model, MODEL, 'x:float64'))
    assert text == '```dewy\n(field) x: float64\n```', text
    # An imported function's declaration is its header.
    assert 'fresh = ():>World' in hover_text(client, at(game, GAME, 'fresh', 0, 1))
    assert 'A fresh world.' in hover_text(client, at(game, GAME, 'fresh', 0, 1))
    assert 'advance = (@world: World' in hover_text(client, at(game, GAME, 'advance', 0, 0))


def test_dewy_signature_help(project):
    client, root = project
    game = root / 'game.dewy'

    versions = iter(range(2, 100))

    def help_at(text, marker):
        before, after = text.split(marker)
        client.set_text(game.as_uri(), before + after, next(versions))
        return client.request('textDocument/signatureHelp', {
            'textDocument': {'uri': game.as_uri()},
            'position': {'line': before.count('\n'), 'character': len(before.rsplit('\n', 1)[-1])}})

    result = help_at(GAME.replace('advance(@world min(dt 0.05) 3.0)', 'advance(@world §min(dt 0.05) 3.0)'), '§')
    signature = result['signatures'][0]
    assert signature['label'] == 'advance = (@world: World dt: float64 pointer: float64):>void'
    labels = [signature['label'][a:b] for a, b in (p['label'] for p in signature['parameters'])]
    assert labels == ['@world: World', 'dt: float64', 'pointer: float64']
    assert result['activeParameter'] == 1
    assert 'A fresh' not in str(signature)
    # Spaces separate arguments; operators join the words of one argument.
    result = help_at(GAME.replace('advance(@world min(dt 0.05) 3.0)', 'advance(@world dt + 1.0 §3.0)'), '§')
    assert result['activeParameter'] == 2
    result = help_at(GAME.replace('advance(@world min(dt 0.05) 3.0)', 'advance(@world dt §'), '§')
    assert result['activeParameter'] == 2
    # Nested calls answer for the innermost; named arguments for their parameter.
    result = help_at(GAME.replace('advance(@world min(dt 0.05) 3.0)', 'advance(@world min(dt §0.05) 3.0)'), '§')
    assert result['signatures'][0]['label'].startswith('min = (')
    assert result['activeParameter'] == 1
    result = help_at(GAME.replace('advance(@world min(dt 0.05) 3.0)', 'advance(pointer=§'), '§')
    assert result['activeParameter'] == 2


def decode_tokens(client, path, text):
    legend = client.capabilities['semanticTokensProvider']['legend']
    data = client.request('textDocument/semanticTokens/full', {'textDocument': {'uri': path.as_uri()}})['data']
    lines = text.split('\n')
    line = column = 0
    out = {}
    for i in range(0, len(data), 5):
        delta_line, delta_column, length, kind, modifiers = data[i:i + 5]
        column = column + delta_column if delta_line == 0 else delta_column
        line += delta_line
        mods = {m for bit, m in enumerate(legend['tokenModifiers']) if modifiers & (1 << bit)}
        out[(line, lines[line][column:column + length])] = (legend['tokenTypes'][kind], mods)
    return out


def test_dewy_semantic_tokens(tmp_path):
    source = tmp_path / 'main.dewy'
    text = '''main=():>int64=>{
    let xs:array<int64>=[1 2]
    xs.push(3)
    let n=xs.length
    printl(n)
    let s="abc"
    if s.startswith("a") { xs.insert(5 0) }
    return xs.pop(0)+n
}
'''
    source.write_text(text)
    client = Client(compiler_path(), tmp_path)
    try:
        client.set_text(source.as_uri(), text, 1)
        tokens = decode_tokens(client, source, text)
        assert tokens[(0, 'main')] == ('function', {'declaration'})
        assert tokens[(0, 'int64')] == ('type', {'defaultLibrary'})
        assert tokens[(1, 'array')] == ('type', {'defaultLibrary'})
        assert tokens[(1, 'xs')] == ('variable', {'declaration'})
        assert tokens[(2, 'push')] == ('method', {'defaultLibrary'})
        assert tokens[(3, 'length')] == ('property', {'defaultLibrary'})
        assert tokens[(4, 'printl')] == ('function', {'defaultLibrary'})
        assert tokens[(6, 'startswith')] == ('method', {'defaultLibrary'})
        assert tokens[(6, 'insert')] == ('method', {'defaultLibrary'})
        assert tokens[(7, 'pop')] == ('method', {'defaultLibrary'})
    finally:
        client.close()


def test_dewy_inlay_hints(project):
    client, root = project
    model = root / 'model.dewy'
    hints = client.request('textDocument/inlayHint', {
        'textDocument': {'uri': model.as_uri()},
        'range': {'start': {'line': 0, 'character': 0}, 'end': {'line': 99, 'character': 0}}})
    # Typed parameters need no hint; an inferred local does.
    assert [(h['position'], h['label']) for h in hints] == [
        (position(MODEL, 'before', len('before')), ': float64')]


def test_dewy_rename_across_files(project):
    client, root = project
    model = root / 'model.dewy'
    game = root / 'game.dewy'
    # A program in the workspace that is not open uses it too.
    other = root / 'tools' / 'other.dewy'
    other.parent.mkdir()
    other_text = 'from p"../model.dewy" import fresh, advance\nmain=():>int64=>{\n    let w=fresh()\n    advance(@w 1.0 2.0)\n    return w.score\n}\n'
    other.write_text(other_text)
    (root / 'tools' / 'unrelated.dewy').write_text('advance=()=>0\nmain=()=>advance()\n')
    found = client.request('textDocument/references', {**at(model, MODEL, 'advance'), 'context': {'includeDeclaration': True}})
    assert sorted((r['uri'].rsplit('/', 1)[1], r['range']['start']['line']) for r in found) == [
        ('game.dewy', 0), ('game.dewy', 3), ('model.dewy', 7), ('other.dewy', 0), ('other.dewy', 3)]
    prepared = client.request('textDocument/prepareRename', at(game, GAME, 'advance'))
    assert prepared == {'start': position(GAME, 'advance'), 'end': position(GAME, 'advance', len('advance'))}
    edit = client.request('textDocument/rename', {**at(game, GAME, 'advance', 0, 1), 'newName': 'step_world'})
    changes = edit['changes']
    assert sorted(len(edits) for edits in changes.values()) == [1, 2, 2]
    assert other.as_uri() in changes and other.read_text() == other_text
    assert all(e['newText'] == 'step_world' for edits in changes.values() for e in edits)
    assert changes[model.as_uri()][0]['range']['start'] == position(MODEL, 'advance')
    # Renaming to a name that is taken, or a library name, is refused.
    taken = client.request_raw('textDocument/rename', {**at(game, GAME, 'advance', 0, 1), 'newName': 'fresh'})
    assert 'declared already' in taken['error']['message'], taken
    refused = client.request_raw('textDocument/prepareRename', at(game, GAME, 'min'))
    assert 'error' in refused and 'standard library' in refused['error']['message'], refused


def test_dewy_quick_fixes(tmp_path):
    source = tmp_path / 'main.dewy'
    source.write_text('main=()=>0\n')
    client = Client(compiler_path(), tmp_path)

    def fixes(text, version):
        diagnostics = client.set_text(source.as_uri(), text, version)
        errors = [d for d in diagnostics if d['severity'] == 1]
        assert errors, diagnostics
        actions = client.request('textDocument/codeAction', {
            'textDocument': {'uri': source.as_uri()}, 'range': errors[0]['range'],
            'context': {'diagnostics': errors}})
        out = []
        for action in actions:
            (edit,) = action['edit']['changes'][source.as_uri()]
            out.append((action['title'], edit['range']['start'], edit['range']['end'], edit['newText']))
        return out

    try:
        text = 'double=(x:int64):>int64=>x*2\nmain=():>int64=>{\n    let xs:array<int64>=[1 2]\n    let ys=xs.map(double)\n    return ys[0]\n}\n'
        start = position(text, 'double)')
        assert fixes(text, 1) == [('Write `@double` for the function itself', start, start, '@')]
        fixed = text.replace('map(double)', 'map(@double)')
        assert not [d for d in client.set_text(source.as_uri(), fixed, 2) if d['severity'] == 1]
        text = 'main=():>int64=>{\n    let s="hello"\n    return if s.starts_with("h") 1 else 0\n}\n'
        assert fixes(text, 3) == [("Change 'starts_with' to 'startswith'", position(text, 'starts_with'),
                                   position(text, 'starts_with', len('starts_with')), 'startswith')]
        text = 'main=():>int64=>{\n    let xs=[1 2 3]\n    xs.remove(0)\n    return xs[0]\n}\n'
        assert fixes(text, 4) == [("Change 'remove' to 'pop'", position(text, 'remove'),
                                   position(text, 'remove', len('remove')), 'pop')]
        text = 'main=():>int64=>{\n    return abss(-1)\n}\n'
        assert fixes(text, 5)[0][0] == "Change 'abss' to 'abs'"
    finally:
        client.close()


def test_dewy_symbols_and_code_lenses(project):
    client, root = project
    game = root / 'game.dewy'
    symbols = client.request('textDocument/documentSymbol', {'textDocument': {'uri': game.as_uri()}})
    assert [(s['name'], s['kind']) for s in symbols] == [
        ('world', 13), ('step', 12), ('test "fresh world"', 24), ('test "steps"', 24), ('main', 12)]
    lenses = client.request('textDocument/codeLens', {'textDocument': {'uri': game.as_uri()}})
    found = [(lens['range']['start']['line'], lens['command']['title'], lens['command']['command'],
              lens['command']['arguments']) for lens in lenses]
    uri = game.as_uri()
    assert found == [
        (5, 'Run all tests', 'dewy.core.test', [uri]),
        (5, 'Run test', 'dewy.core.runTest', [uri, 'fresh world']),
        (8, 'Run test', 'dewy.core.runTest', [uri, 'steps']),
        (12, 'Run', 'dewy.core.run', [uri]),
        (12, 'Debug', 'dewy.core.debug', [uri]),
    ]
    found = client.request('workspace/symbol', {'query': 'adv'})
    assert [(s['name'], s['location']['uri'].rsplit('/', 1)[1]) for s in found] == [('advance', 'model.dewy')]


def test_dewy_completion_contexts(project):
    client, root = project
    game = root / 'game.dewy'
    (root / 'lib').mkdir()
    (root / 'lib' / 'extra.dewy').write_text('extra=()=>1\n')

    def complete(text, version, trigger=None):
        before, after = text.split('§')
        client.set_text(game.as_uri(), before + after, version)
        params = {'textDocument': {'uri': game.as_uri()},
                  'position': {'line': before.count('\n'), 'character': len(before.rsplit('\n', 1)[-1])}}
        if trigger:
            params['context'] = {'triggerKind': 2, 'triggerCharacter': trigger}
        return {item['label']: item for item in client.request('textDocument/completion', params)['items']}

    items = complete(GAME.replace('p"model.dewy"', 'p"§model.dewy"'), 2, '"')
    assert set(items) == {'model.dewy', 'lib/'}, items
    assert items['model.dewy']['textEdit']['range']['start'] == {'line': 0, 'character': 7}
    items = complete(GAME.replace('p"model.dewy"', 'p"lib/§"'), 3, '/')
    assert set(items) == {'extra.dewy'}, items
    assert complete(GAME.replace('dt:float64):>void', 'dt:float64/§):>void'), 4, '/') == {}
    items = complete(GAME.replace('    step(0.1)\n    return', '    $§\n    return'), 5, '$')
    assert {'assert', 'runtime_assert'} <= set(items), items
    items = complete(GAME.replace('    step(0.1)\n    return', '    or§\n    return'), 6)
    assert 'or_throw' in items and items['or_throw']['kind'] == 14
    assert 'printl' in items and items['printl']['kind'] != 14


def test_vscode_compiler_discovery(tmp_path):
    """The setting, then a bundled toolchain, the installer's launcher and the PATH; no downloads."""
    import shutil
    import subprocess
    node = shutil.which('node')
    if node is None:
        pytest.skip('Node is needed for the extension')
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run([node, root / 'tests/fixtures/core_editor/discovery.cjs',
                             root / 'editors/vscode/compiler.js', tmp_path],
                            capture_output=True, text=True, timeout=20, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'compiler discovery: setting, bundled, installed and PATH passed' in result.stdout
