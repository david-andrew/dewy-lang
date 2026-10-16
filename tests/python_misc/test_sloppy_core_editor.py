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
