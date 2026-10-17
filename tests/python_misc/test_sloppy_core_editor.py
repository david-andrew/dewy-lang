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


@pytest.mark.parametrize('extension', ['dewy', 'jo'])
def test_bundled_library_unsaved_diagnostics(tmp_path, monkeypatch, extension):
    value = os.environ.get('DEWY_CORE_COMPILER')
    if not value:
        pytest.skip('set DEWY_CORE_COMPILER to the experimental source-level core')
    compiler = Path(value).resolve(strict=True)
    library = tmp_path / 'lib'
    library.mkdir()
    for item in (compiler.parent.parent / 'lib').iterdir():
        (library / item.name).symlink_to(item, target_is_directory=item.is_dir())
    module = library / f'probe.{extension}'
    good = ('good=()=>42\nbad=():>int64=>0\n' if extension == 'dewy'
            else 'good = () -> int: 42\nbad = () -> int: 0\n')
    module.write_text(good)
    project = tmp_path / 'project'
    project.mkdir()
    source = project / 'main.dewy'
    main = 'from probe import good\nmain=()=>good()\n'
    source.write_text(main)
    monkeypatch.setenv('DEWY_CORE_LIB', str(library))
    client = Client(compiler, project)
    try:
        diagnostics = client.set_text(source.as_uri(), main, 1)
        assert not [d for d in diagnostics if d['severity'] == 1], diagnostics
        bad = good.replace('=>0', '=>missing').replace(': 0', ': missing')
        diagnostics = client.set_text(module.as_uri(), bad, 1)
        errors = [d for d in diagnostics if d['severity'] == 1]
        assert errors and any('missing' in d['message'] for d in errors), diagnostics
        diagnostics = client.set_text(module.as_uri(), good, 2)
        assert not [d for d in diagnostics if d['severity'] == 1], diagnostics
        hover = client.request('textDocument/hover', {
            'textDocument': {'uri': module.as_uri()}, 'position': {'line': 0, 'character': 1}})
        assert hover and 'int' in str(hover), hover
        assert module.read_text() == good
    finally:
        client.close()


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
        assert edits and edits[0]['newText'] == 'answer = () => 42\nmain = () => answer()\n', edits

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
        labeled = 'main=()=>{$outer loop true {loop true {break $outer}} return 42}'
        diagnostics = client.set_text(uri, labeled.replace('break $outer', 'break $missing'), 7)
        assert any('unknown loop label' in d['message'] for d in diagnostics), diagnostics
        diagnostics = client.set_text(uri, labeled, 8)
        assert not [d for d in diagnostics if d['severity'] == 1], diagnostics
        fallback = 'main=()=>{loop x in [0..0) {return x} else {return 42}}'
        diagnostics = client.set_text(uri, fallback.replace('return 42', 'return x'), 9)
        assert any("unknown name 'x'" in d['message'] for d in diagnostics), diagnostics
        diagnostics = client.set_text(uri, fallback, 10)
        assert not [d for d in diagnostics if d['severity'] == 1], diagnostics
        diagnostics = client.set_text(uri, 'main=()=>42??0', 11)
        assert any('needs an optional on the left' in d['message'] for d in diagnostics), diagnostics
        diagnostics = client.set_text(uri, 'main=()=>none??42', 12)
        assert not [d for d in diagnostics if d['severity'] == 1], diagnostics
        diagnostics = client.set_text(uri, 'main=()=>{let xs=[42] return xs[end()]}', 13)
        assert any('end is the last index' in d['message'] for d in diagnostics), diagnostics
        assert '$index_end' not in str(diagnostics), diagnostics
        diagnostics = client.set_text(uri, 'main=()=>{let xs=[42] return xs[end]}', 14)
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
    ('', 'let xs=[42] return xs[end]', 'end', 'int64'),
    ('', 'let value=uint8.max return if value >? 0 42 else 1', 'max', 'uint8'),
    ('Byte:type=uint8\n', 'let value=Byte.min return if value =? 0 42 else 1', 'min', 'uint8'),
    ('', 'let value:uint64=42 return value as int64', 'value', 'uint64'),
    ('', 'let value=1/2 return if value =? 1/2 42 else 1', 'value', 'Rational'),
    ('', 'let value=123456789012345678901234567890 return if value >? 1 42 else 1', 'value', 'BigInt'),
    ('', 'let value:array<string>=["answer"] return value.length', 'value', 'array<string>'),
    ('', 'let value:dict<string array<int16>>=[] return value.length', 'value', 'dict<string array<int16>>'),
    ('', 'let value=[y=22 x=20] return value.x+value.y', 'value', '[x: int64 y: int64]'),
    ('', 'let base=[x=20 y=1] let value=[base... y=22] return value.x+value.y', 'value', '[x: int64 y: int64]'),
    ('', 'let value:[y:int64 x:int64]=[x=20 y=22] return value.x+value.y', 'value', '[x: int64 y: int64]'),
    ('combine=(a b=a)=>a+b\n', 'let value=combine(21) return value', 'value', 'int64'),
    ('', 'let value=[loop x in [20 22] x] return value[0]+value[1]', 'value', 'array<int64>'),
    ('', 'let value=[loop key in ["a" "b"] key->21] return value["a"]+value["b"]', 'value', 'dict<string int64>'),
    ('', 'let [value]=[answer=1 value=42] return value', 'value', 'int64'),
    ('', 'let value:(int64|string)?=none return if value is? none 42 else 1', 'value', '(int64 | string)?'),
    ('Fn:type=(@x:int64):>void\n', 'let value:Fn=(@x:int64):>void=>{x+=1} let n:int64=41 value(@n) return n', 'value', '(@arg0: int64):>void'),
    ('bump=(@x:int64 n:int64=2):>void=>{x+=n}\n', 'let n:int64=40 bump(@n) return n', 'bump', 'bump = (@x: int64 n: int64 = …):>void'),
    ('Box:type=<T>[text:T]\n', 'let value=Box<string>["hello"] return value.text.length', 'value', 'Box<string>'),
    ('identity=<T>(x:T):>T=>x\n', 'return identity<int64>(42)', 'identity', 'identity = (x: int64):>int64'),
    ('identity=<T>(x:T):>T=>x\n', 'let callback=identity<int64> return callback(42)', 'identity', 'identity = (x: int64):>int64'),
    ('choose=((value:int64)=>value+2)&((text:string)=>text.length)\n',
     'return choose(40)', 'choose', 'choose = (value: int64):>int64'),
    ('choose=((value:int64)=>value+2)&((text:string)=>text.length)\n',
     'return choose("answer")', 'choose', 'choose = (text: string):>int64'),

    ('', 'let value:Pool<array<int64>>=[] return value.items.length', 'value', 'Pool<array<int64>>'),
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


@pytest.mark.parametrize(('text', 'wanted', 'absent'), [
    ('main=()=>{let value=uint8.§ return 42}', {'min': 'uint8', 'max': 'uint8'}, ['length']),
    ('Byte:type=uint8\nmain=()=>{let value=Byte.§ return 42}', {'min': 'uint8', 'max': 'uint8'}, ['length']),
    ('Number:type=<T>(T)\nmain=()=>{let value=Number<int16>.§ return 42}', {'min': 'int16', 'max': 'int16'}, []),
    ('main=()=>{let value=float64.§ return 42}', {}, ['min', 'max']),
    ('main=()=>{let answer:int64=42 return ans§}', {'answer': 'int64', 'printl': None}, ['struct', 'mut', 'while']),
    ('main=()=>{let point=[x=42 y=2] return point.§}', {'x': 'int64', 'y': 'int64'}, ['struct']),
    ('main=()=>{let ratio=1/2 ratio.§}', {'numerator': 'BigInt', 'denominator': 'BigInt'}, []),
    ('main=()=>{let ratio=1/2 rat§}', {'ratio': 'Rational'}, ['$dewy_rational']),
    ('main=()=>{let huge=18446744073709551616 hu§}', {'huge': 'BigInt'}, ['__dewy$bigint', '$dewy_bigint']),
    ('main=()=>{let point=[x=42] point.§', {'x': 'int64'}, []),
    ('main=()=>{let value:in§=42 return value}', {'int64': 'type', 'string': 'type', 'array': 'array<Element>'}, ['int', 'i64', 'str', 'struct']),
    ('main=()=>{let values=[20 22] values.§}', {'length': 'int64', 'push': 'builtin'}, []),
    ('main=()=>{let text="hello" text.§}', {'length': 'int64'}, ['push', 'pop', 'resize']),
    ('main=()=>{let values=["a"->42] values.§}', {'length': 'int64', 'get': None}, ['slots', 'hashes', 'gone', 'ngone']),
    ('identity=<T>(x:T):>T=>x\nmain=()=>{iden§}',
     {'identity': 'identity = <T>(x: T):>T'}, []),
    ('helper=(@value:int64 amount:int64=2):>void=>{value+=amount}\nmain=()=>{hel§}',
     {'helper': 'helper = (@value: int64 amount: int64 = …):>void'}, []),
    ('from p"support.jo" import answer\nmain=()=>{ans§}',
     {'answer': 'answer = (x: int64 n: int64 = …):>int64'}, []),
    ('main=()=>{let café=[value=42] let text="🙂 {café.§}" return 42}', {'value': 'int64'}, []),
    ('main=()=>42 # ans§', {}, ['printl', 'struct']),
    ('main=()=>{let text="ans§" return 42}', {}, ['printl', 'struct']),
    ('main=()=>{let text=r"{ans§}" return 42}', {}, ['printl']),
    ('main=()=>{let text="""line "quoted"\nans§""" return 42}', {}, ['printl']),
    ("main=()=>{let text='''line 'quoted'\nans§''' return 42}", {}, ['printl']),
    ('main=()=>{let text=r"""line\n{ans§}""" return 42}', {}, ['printl']),
    ('main=()=>{let text="\\u{12§}" return 42}', {}, ['printl']),
    ('main=()=>{let point=[x=42] let text="""answer {point.§}""" return 42}', {'x': 'int64'}, []),
    ('main=()=>{let point=[x=42] let text="{r"{literal}"} {point.§}" return 42}', {'x': 'int64'}, []),
    ('main=()=>{let text="{ # ans§\n42}" return 42}', {}, ['printl']),
    ('main=()=>{let point=[x=42] let text="{{point.§}}" return 42}', {'x': 'int64'}, []),
])
def test_dewy_completions(tmp_path, text, wanted, absent):
    compiler = os.environ.get('DEWY_CORE_COMPILER')
    if not compiler:
        pytest.skip('set DEWY_CORE_COMPILER for the editor checks')
    (tmp_path / 'support.jo').write_text('answer = (x: int, n: int = 2) -> int: x + n\n')
    source = tmp_path / 'main.dewy'
    source.write_text('main=()=>42')
    before, after = text.split('§')
    position = {'line': before.count('\n'),
                'character': len(before.rsplit('\n', 1)[-1].encode('utf-16-le')) // 2}
    client = Client(Path(compiler).resolve(strict=True), tmp_path)
    try:
        client.set_text(source.as_uri(), before + after, 1)
        response = client.request('textDocument/completion', {
            'textDocument': {'uri': source.as_uri()}, 'position': position,
        })
        items = {item['label']: item for item in response['items']}
        for name, detail in wanted.items():
            assert name in items, (name, items)
            if detail is not None:
                assert items[name].get('detail') == detail, items[name]
        assert not any(name in items for name in absent), items
        if not wanted:
            assert not items, items
        # Completion checks must restore the editor snapshot after inserting a sentinel.
        diagnostics = client.set_text(source.as_uri(), 'main=()=>42', 2)
        assert not [d for d in diagnostics if d['severity'] == 1], diagnostics
        assert source.read_text() == 'main=()=>42'
    finally:
        client.close()
