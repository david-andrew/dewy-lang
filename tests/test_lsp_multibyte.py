"""The language server never panics on multi-byte text or bytes that are not UTF-8: requests at every
UTF-16 column, code actions for messages quoting such text, and incremental edits inside a character."""
import json
import os
import select
import time

import pytest

from tests.support import compiler  # noqa: F401
from tests.test_core_editor import Client

DOCUMENTS = {
    # (an identifier of emoji and CJK letters, a statement whose next line starts with a wide character)
    'wide.dewy': 'Pté:type=struct{xé:int64 y中:int64}\naddé=(aé:int64 b中:int64):>int64=>aé + b中\n'
                 'main=():>void=>{\n    let p=Pté[xé=1 y中=2]\n    let 😀z=addé(p.xé p.y中)\n'
                 '    printl(😀z)\n    printl(missing_é)\n}\n',
    'mixed.dewy': '# héllo 中文\nmain=():>void=>{\n    let é="中😀 e\\u{301}"\n    let x=2.0\n'
                  '    let y:int64=x é\n    let z=x 中, 3.0 😀\n    printl("{é} {y}")\n}\n',
    'keywords.dewy': 'é=(a:int64):>int64=>{\n    loop i in [0..a) { printl(i) }\n    a\n}\n'
                     'if é(1) =? 1 { printl("é") }\nlet 中=1\nconst é2=3\né(中 é2)\n',
}
RAW = [  # bytes that are not UTF-8: stray continuation bytes at the start of a line and of a word
    b'\x80main=():>void=>{\n\x80\n    let a=1\n\xbf\xbf  let b=\x80 2\n    printl(a b\x80)\n}\n',
    b'f\x80=(\xbfa:int64):>int64=>a\nmain=():>void=>{\n    printl(f\x80(1))\n    printl(\xc3)\n}\n',
]
MESSAGES = [
    "unknown name 'é' (did you mean 'è'?)", "unknown name 'appendé' (use `push`)",
    "write `@é` for the function itself", "write `中.é(1)`", "use `and`", "use `not`",
    "cannot modify loop variable 'é'", "cannot modify parameter 'aé'",
    "'é' is changed here but never read afterwards: use `loop @é`",
    "path is not proven to stay inside its base; validate it, `root.confine(é) or_throw`",
    "expected int, found f64", "expected f64, found int", "expected i32, found f64 é",
    "this `;` is attached to the value before it", "expected ", "`", "(did you mean '",
]


class Tolerant(Client):
    """A strict client: every reply must be one JSON document of valid UTF-8 whose Content-Length counts its
    bytes, as clients that refuse anything else require (the server echoes bytes of files that are not UTF-8)."""

    def receive(self):
        deadline = time.monotonic() + 20
        while True:
            if b'\r\n\r\n' in self.buffer:
                header, body = self.buffer.split(b'\r\n\r\n', 1)
                length = int(next(line.split(b':', 1)[1] for line in header.split(b'\r\n')
                                  if line.lower().startswith(b'content-length:')))
                if len(body) >= length:
                    self.buffer = body[length:]
                    return json.loads(body[:length].decode('utf-8', 'strict'))
            remaining = deadline - time.monotonic()
            assert remaining > 0, 'language server response timed out'
            ready, _, _ = select.select([self.process.stdout], [], [], remaining)
            assert ready, 'language server response timed out'
            chunk = os.read(self.process.stdout.fileno(), 65536)
            assert chunk, 'language server exited before responding'
            self.buffer += chunk


def positions(text):
    lines = text.split('\n')
    for number, line in enumerate(lines):
        width = sum(2 if ord(c) > 0xFFFF else 1 for c in line)
        for character in range(width + 2):
            yield number, character


def open_raw(client, uri, data):
    """didOpen carrying bytes as they are: JSON escapes only what it must."""
    escaped = bytearray()
    for byte in data:
        if byte in (0x22, 0x5C) or byte < 0x20:
            escaped += b'\\u%04x' % byte
        else:
            escaped.append(byte)
    head = json.dumps({'jsonrpc': '2.0', 'method': 'textDocument/didOpen', 'params': {'textDocument': {
        'uri': uri, 'languageId': 'dewy', 'version': 1, 'text': '@@'}}}).encode()
    body = head.replace(b'@@', bytes(escaped))
    client.process.stdin.write(f'Content-Length: {len(body)}\r\n\r\n'.encode() + body)
    client.process.stdin.flush()
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        message = client.receive()
        if message.get('method') == 'textDocument/publishDiagnostics' and message['params']['uri'] == uri:
            return message['params']['diagnostics']
    raise AssertionError('no diagnostics')


def ask(client, method, params):
    """The reply to a request, error replies included: the server must answer, not die."""
    client.serial += 1
    client.send(method, params, client.serial)
    while True:
        message = client.receive()
        if message.get('id') == client.serial:
            return message
        client.messages.append(message)


def alive(client):
    reply = ask(client, 'workspace/symbol', {'query': 'a'})
    assert client.process.poll() is None and 'result' in reply
    return reply


def requests_at(uri, text):
    document = {'uri': uri}
    for turn, (line, character) in enumerate(positions(text)):
        position = {'line': line, 'character': character}
        yield 'textDocument/hover', {'textDocument': document, 'position': position}
        yield 'textDocument/definition', {'textDocument': document, 'position': position}
        yield 'textDocument/prepareRename', {'textDocument': document, 'position': position}
        yield 'textDocument/signatureHelp', {'textDocument': document, 'position': position}
        if turn % 3 == 0:  # (the requests that check the program again, at every third position)
            yield 'textDocument/completion', {'textDocument': document, 'position': position}
            yield 'textDocument/rename', {'textDocument': document, 'position': position, 'newName': 'zé'}
            yield 'textDocument/references', {'textDocument': document, 'position': position,
                                              'context': {'includeDeclaration': True}}
        end = {'line': line, 'character': character + 1}
        for message in MESSAGES:
            diagnostic = {'range': {'start': position, 'end': end}, 'message': message, 'severity': 1}
            yield 'textDocument/codeAction', {'textDocument': document, 'range': diagnostic['range'],
                                              'context': {'diagnostics': [diagnostic]}}
    yield 'textDocument/documentSymbol', {'textDocument': document}
    yield 'textDocument/formatting', {'textDocument': document, 'options': {'tabSize': 4, 'insertSpaces': True}}
    yield 'textDocument/inlayHint', {'textDocument': document,
                                     'range': {'start': {'line': 0, 'character': 0}, 'end': {'line': 99, 'character': 0}}}
    yield 'textDocument/codeLens', {'textDocument': document}
    yield 'textDocument/semanticTokens/full', {'textDocument': document}
    yield 'workspace/symbol', {'query': 'é'}


def ask_batch(client, requests):
    """Send the requests together, then wait for every reply (error replies included: the server must
    answer each one, not die). A batch stays far below the pipe's capacity, so neither side blocks."""
    pending = set()
    for method, params in requests:
        client.serial += 1
        client.send(method, params, client.serial)
        pending.add(client.serial)
    replies = {}
    while pending:
        message = client.receive()
        if message.get('id') in pending:
            pending.discard(message['id'])
            replies[message['id']] = message
        else:
            client.messages.append(message)
    return replies


def drive(client, uri, text, batch=32, shard=0, shards=1):
    requests = list(requests_at(uri, text))[shard::shards]
    for start in range(0, len(requests), batch):
        ask_batch(client, requests[start:start + batch])
    alive(client)


SHARDS = 2


@pytest.mark.parametrize('name, shard', [
    pytest.param(name, k, id=f'{name}-{k}of{SHARDS}', marks=pytest.mark.xdist_group(name=f'lsp-multibyte-{name}-{k}'))
    for name in DOCUMENTS for k in range(SHARDS)])
def test_multibyte_documents(compiler, tmp_path, name, shard):
    # (each shard's server gets every second request of the document's list: together, all of them)
    text = DOCUMENTS[name]
    client = Tolerant(compiler, tmp_path)
    try:
        path = tmp_path / name
        path.write_text(text)
        client.set_text(path.as_uri(), text, 1)
        drive(client, path.as_uri(), text, shard=shard, shards=SHARDS)
    finally:
        client.close()


def test_bytes_that_are_not_utf8(compiler, tmp_path):
    client = Tolerant(compiler, tmp_path)
    try:
        for index, data in enumerate(RAW):
            path = tmp_path / f'raw{index}.dewy'
            path.write_bytes(data)
            open_raw(client, path.as_uri(), data)
            drive(client, path.as_uri(), data.decode('utf-8', 'replace'))
    finally:
        client.close()


def test_documents_on_disk_with_multibyte_text(compiler, tmp_path):
    """Files the server reads itself: an import of a module whose text starts with a stray byte."""
    (tmp_path / 'é中.dewy').write_bytes(b'\x80f' + 'é'.encode() + b'=(a:int64):>int64=>a\n\xbfg=():>int64=>1\n')
    main = 'from p"é中.dewy" import (fé)\nmain=():>void=>{\n    printl(fé(1))\n}\n'
    path = tmp_path / 'main.dewy'
    path.write_text(main)
    client = Tolerant(compiler, tmp_path)
    try:
        client.set_text(path.as_uri(), main, 1)
        drive(client, path.as_uri(), main)
    finally:
        client.close()


def test_edits_inside_a_character(compiler, tmp_path):
    """Incremental changes address UTF-16 columns: one inside an emoji's surrogate pair, one between marks."""
    text = 'main=():>void=>{\n    let s="😀é中"\n    printl(s)\n}\n'
    path = tmp_path / 'edit.dewy'
    path.write_text(text)
    client = Tolerant(compiler, tmp_path)
    try:
        client.set_text(path.as_uri(), text, 1)
        version = 1
        for start, end in [(13, 14), (14, 14), (15, 17), (16, 18), (12, 20), (13, 99), (0, 1)]:
            version += 1
            client.send('textDocument/didChange', {'textDocument': {'uri': path.as_uri(), 'version': version},
                                                  'contentChanges': [{'range': {
                                                      'start': {'line': 1, 'character': start},
                                                      'end': {'line': 1, 'character': end}}, 'text': 'é'}]})
            ask(client, 'textDocument/documentSymbol', {'textDocument': {'uri': path.as_uri()}})
        alive(client)
    finally:
        client.close()


# Byte sequences that are not UTF-8, each the start of a family: a stray continuation byte, truncated
# two-, three- and four-byte sequences, overlong forms, surrogates, beyond U+10FFFF, never-valid bytes.
INVALID = [b'\x80', b'\xbf\xbf', b'\xc3', b'\xe4\xb8', b'\xf0\x9f\x98', b'\xc0\x80', b'\xe0\x80\x80',
           b'\xed\xa0\x80', b'\xf4\x90\x80\x80', b'\xf8\x88\x80\x80\x80', b'\xff\xfe', b'\xc3\xa9\x80\xe4\xb8\xad',
           b'\xe4\xb8x', b'\xf0\x9f\x98\x80\xf0\x9f']


def every_string(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from every_string(item)
    elif isinstance(value, list):
        for item in value:
            yield from every_string(item)


def test_replies_quoting_bytes_that_are_not_utf8_are_valid_json(compiler, tmp_path):
    """Names in files on disk that hold stray bytes (a client's own text cannot: it reads as empty) come back
    with U+FFFD for each maximal subpart, what a WHATWG decoder gives, in a reply a strict client accepts."""
    expected = {}
    for index, bad in enumerate(INVALID):
        name = f'zq{index}'.encode() + bad + b'x'
        (tmp_path / f'mod{index}.dewy').write_bytes(
            b'# ' + bad + b' comment\n' + name + b'=(a' + bad + b':int64):>int64=>1\nconst K' + bad + b'=3\n')
        expected[name.decode('utf-8', 'replace')] = bad
    main = 'main=():>void=>{\n    printl(1)\n}\n'
    path = tmp_path / 'main.dewy'
    path.write_text(main)
    client = Tolerant(compiler, tmp_path)
    try:
        client.set_text(path.as_uri(), main, 1)
        names = set(every_string(ask(client, 'workspace/symbol', {'query': 'zq'})['result']))
        assert set(expected) <= names, (sorted(set(expected) - names), sorted(names))
        names = set(every_string(ask(client, 'workspace/symbol', {'query': ''})['result']))
        assert {'K' + bad.decode('utf-8', 'replace') for bad in INVALID} <= names
        drive(client, path.as_uri(), main)
    finally:
        client.close()


def test_valid_text_in_replies_is_unchanged(compiler, tmp_path):
    """Valid text passes byte for byte: names with an emoji, CJK, a combining mark, a character outside the BMP."""
    names = ['é中😀', 'e\u0301x', '\U0001f600\U0001f601', 'z\u4e2dz', 'w\U00010348']
    for index, name in enumerate(names):
        (tmp_path / f'ok{index}.dewy').write_text(f'zq{name}=(a:int64):>int64=>1\n')
    main = 'main=():>void=>{\n    printl(1)\n}\n'
    path = tmp_path / 'main.dewy'
    path.write_text(main)
    client = Tolerant(compiler, tmp_path)
    try:
        client.set_text(path.as_uri(), main, 1)
        got = set(every_string(ask(client, 'workspace/symbol', {'query': 'zq'})['result']))
        assert {f'zq{name}' for name in names} <= got, got
    finally:
        client.close()
