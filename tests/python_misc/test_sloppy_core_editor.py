"""Exercise the experimental core through the editor's actual LSP protocol."""
import json
import os
import select
import subprocess
import time
from pathlib import Path

import pytest


class Client:
    def __init__(self, compiler, root):
        self.process = subprocess.Popen([compiler, 'lsp'], stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.buffer = b''
        self.messages = []
        self.serial = 0
        self.request('initialize', {'capabilities': {}, 'rootUri': root.as_uri()})
        self.send('initialized', {})

    def send(self, method, params, serial=None):
        obj = {'jsonrpc': '2.0', 'method': method, 'params': params}
        if serial is not None:
            obj['id'] = serial
        body = json.dumps(obj).encode()
        self.process.stdin.write(f'Content-Length: {len(body)}\r\n\r\n'.encode() + body)
        self.process.stdin.flush()

    def receive(self):
        deadline = time.monotonic() + 10
        while True:
            if b'\r\n\r\n' in self.buffer:
                header, body = self.buffer.split(b'\r\n\r\n', 1)
                length = int(next(line.split(b':', 1)[1] for line in header.split(b'\r\n')
                                  if line.lower().startswith(b'content-length:')))
                if len(body) >= length:
                    self.buffer = body[length:]
                    return json.loads(body[:length])
            remaining = deadline - time.monotonic()
            assert remaining > 0, 'language server response timed out'
            ready, _, _ = select.select([self.process.stdout], [], [], remaining)
            assert ready, 'language server response timed out'
            chunk = os.read(self.process.stdout.fileno(), 65536)
            assert chunk, 'language server exited before responding'
            self.buffer += chunk

    def request(self, method, params):
        self.serial += 1
        self.send(method, params, self.serial)
        while True:
            result = self.receive()
            if result.get('id') == self.serial:
                assert 'error' not in result, result
                return result.get('result')
            self.messages.append(result)

    def set_text(self, uri, body, version):
        if version == 1:
            self.send('textDocument/didOpen', {'textDocument': {
                'uri': uri, 'languageId': 'dewy', 'version': version, 'text': body}})
        else:
            self.send('textDocument/didChange', {'textDocument': {'uri': uri, 'version': version},
                                                'contentChanges': [{'text': body}]})
        while True:
            for index, message in enumerate(self.messages):
                params = message.get('params', {})
                if (message.get('method') == 'textDocument/publishDiagnostics'
                        and params.get('uri') == uri and params.get('version') == version):
                    del self.messages[index]
                    return params['diagnostics']
            self.messages.append(self.receive())

    def close(self):
        self.process.kill()
        self.process.communicate(timeout=5)


def test_unsaved_diagnostics_hover_and_definition(tmp_path):
    value = os.environ.get('DEWY_CORE_COMPILER')
    if not value:
        pytest.skip('set DEWY_CORE_COMPILER to the experimental source-level core')
    source = tmp_path / 'main.dewy'
    source.write_text('main=()=>42')
    uri = source.as_uri()
    client = Client(Path(value).resolve(strict=True), tmp_path)
    try:
        good = 'answer=()=>42\nmain=()=>answer()'
        diagnostics = client.set_text(uri, good, 1)
        assert not [d for d in diagnostics if d['severity'] == 1], diagnostics
        position = {'textDocument': {'uri': uri}, 'position': {'line': 1, 'character': 9}}
        hover = client.request('textDocument/hover', position)
        assert hover and 'int' in str(hover), hover
        definition = client.request('textDocument/definition', position)
        if isinstance(definition, list):
            definition = definition[0]
        assert definition['uri'] == uri and definition['range']['start']['line'] == 0, definition
        edits = client.request('textDocument/formatting', {'textDocument': {'uri': uri},
                                                         'options': {'tabSize': 4, 'insertSpaces': True}})
        assert not edits, 'the Sloppy formatter must not rewrite Dewy source'

        bad = '# 🙂\nmain=()=>missing'
        diagnostics = client.set_text(uri, bad, 2)
        errors = [d for d in diagnostics if d['severity'] == 1]
        assert errors and 'unknown' in errors[0]['message'], diagnostics
        assert errors[0]['range']['start']['line'] == 1, errors

        diagnostics = client.set_text(uri, 'main=()=>{', 3)
        assert any(d['severity'] == 1 for d in diagnostics), diagnostics
        diagnostics = client.set_text(uri, good, 4)
        assert not [d for d in diagnostics if d['severity'] == 1], diagnostics
        malformed = 'main=()=>{let text="🙂é" return )}'
        diagnostics = client.set_text(uri, malformed, 5)
        errors = [d for d in diagnostics if d['severity'] == 1]
        assert errors, diagnostics
        expected_column = len(malformed[:malformed.index(')', 8)].encode('utf-16-le')) // 2
        assert errors[0]['range']['start'] == {'line': 0, 'character': expected_column}, errors
        diagnostics = client.set_text(uri, good, 6)
        assert not [d for d in diagnostics if d['severity'] == 1], diagnostics
        assert source.read_text() == 'main=()=>42'
    finally:
        client.close()


def test_vscode_core_client(tmp_path):
    """Run the actual extension transport with VS Code API doubles and a native server."""
    import shutil
    node = shutil.which('node')
    compiler = os.environ.get('DEWY_CORE_COMPILER')
    if node is None or not compiler:
        pytest.skip('Node and DEWY_CORE_COMPILER are needed for the editor client')
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run([node, root / 'tests/fixtures/core_editor/client.cjs',
                             root / 'dewy/vscode-dewy/core-client.js',
                             Path(compiler).resolve(), tmp_path], capture_output=True,
                            text=True, timeout=20, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'restart and close passed' in result.stdout


@pytest.mark.parametrize(('declarations', 'body', 'name', 'expected'), [
    ('', 'let value:uint64=42 return value as int64', 'value', 'uint64'),
    ('', 'let value:array<string>=["answer"] return value.length', 'value', 'array<string>'),
    ('', 'let value:dict<string array<int16>>=[] return value.length', 'value', 'dict<string array<int16>>'),
    ('', 'let value=[y=22 x=20] return value.x+value.y', 'value', '[x: int64 y: int64]'),
    ('combine=(a b=a)=>a+b\n', 'let value=combine(21) return value', 'value', 'int64'),
    ('', 'let value=[loop x in [20 22] x] return value[0]+value[1]', 'value', 'array<int64>'),
    ('', 'let value=[loop key in ["a" "b"] key->21] return value["a"]+value["b"]', 'value', 'dict<string int64>'),
    ('', 'let value:(int64|string)?=none return if value is? none 42 else 1', 'value', '(int64 | string)?'),
    ('Fn:type=(@x:int64):>void\n', 'let value:Fn=(@x:int64):>void=>{x+=1} let n:int64=41 value(@n) return n', 'value', '(@arg0: int64):>void'),
    ('bump=(@x:int64 n:int64=2):>void=>{x+=n}\n', 'let n:int64=40 bump(@n) return n', 'bump', 'bump = (@x: int64 n: int64 = …):>void'),
    ('twice=(x)=>x+x\n', 'return if twice(21.0) =? 42.0 42 else 1', 'twice', 'twice = (x: float64):>float64'),
    ('from p"support.jo" import answer\n', 'return answer(40)', 'answer', 'answer = (x: int64 n: int64 = …):>int64'),
])
def test_dewy_hover_type_spelling(tmp_path, declarations, body, name, expected):
    compiler = os.environ.get('DEWY_CORE_COMPILER')
    if not compiler:
        pytest.skip('set DEWY_CORE_COMPILER to the experimental source-level core')
    # Imported implementation code is displayed in the language being edited.
    (tmp_path / 'support.jo').write_text('answer = (x: int, n: int = 2) -> int: x + n\n')
    source = tmp_path / 'main.dewy'
    source.write_text('main=()=>42')
    text = declarations + 'main=()=>{' + body + '}\n'
    before = text[:text.rindex(name)]
    pos = {'line': before.count('\n'), 'character': len(before.rsplit('\n', 1)[-1])}
    client = Client(Path(compiler).resolve(strict=True), tmp_path)
    try:
        diagnostics = client.set_text(source.as_uri(), text, 1)
        assert not [d for d in diagnostics if d['severity'] == 1], diagnostics
        hover = client.request('textDocument/hover', {'textDocument': {'uri': source.as_uri()}, 'position': pos})
        contents = hover['contents']['value']
        assert contents.startswith('```dewy\n'), contents
        assert expected in contents, contents
    finally:
        client.close()
