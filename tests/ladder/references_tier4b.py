"""Independent stdlib-only oracles for the tier-4 flagships 97-99 (notes service with a wasm UI,
and a Dewy lexer/Pratt parser). Never reads Dewy sources or output. --write regenerates expected.out.
Each oracle is a separate model of the specified behavior, written from the program's acceptance
statement and protocol rules, not translated from the Dewy code."""
from pathlib import Path
import copy, json, math, sys
from urllib.parse import quote as url_quote
ROOT = Path(__file__).parent
ORACLES = {}


def oracle(name):
    def register(f):
        ORACLES[name] = f
        return f
    return register


# 97 notes service -----------------------------------------------------------------------------

LIMITS = dict(request_line=256, header_bytes=1024, headers=16, body=2048)
REASONS = {200: 'OK', 201: 'Created', 204: 'No Content', 304: 'Not Modified', 400: 'Bad Request',
           404: 'Not Found', 405: 'Method Not Allowed', 409: 'Conflict', 412: 'Precondition Failed',
           413: 'Content Too Large', 414: 'URI Too Long', 415: 'Unsupported Media Type',
           422: 'Unprocessable Content', 431: 'Request Header Fields Too Large', 501: 'Not Implemented',
           505: 'HTTP Version Not Supported'}


def dumps(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))


class HttpError(Exception):
    def __init__(self, status, detail):
        self.status, self.detail = status, detail


class Incomplete(Exception):
    pass


def line_at(data, start, lf):
    if lf == start or data[lf - 1] != 13:
        raise HttpError(400, 'bare LF')
    try:
        return data[start:lf - 1].decode()
    except UnicodeDecodeError:
        raise HttpError(400, 'invalid UTF-8 in head')


def head_lines(data, start, limits):
    lines, at = [], start
    while True:
        lf = data.find(b'\n', at)
        if lf < 0:
            if len(data) - start > limits['header_bytes']:
                raise HttpError(431, 'header section too large')
            raise Incomplete
        if lf + 1 - start > limits['header_bytes']:
            raise HttpError(431, 'header section too large')
        line = line_at(data, at, lf)
        at = lf + 1
        if line == '':
            return lines, at
        lines.append(line)
        if len(lines) > limits['headers']:
            raise HttpError(431, 'too many headers')


TOKEN = set(b'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_')


def parse_header(line):
    if line[:1] in (' ', '\t'):
        raise HttpError(400, 'folded header')
    colon = line.find(':')
    if colon <= 0:
        raise HttpError(400, 'malformed header')
    name = line[:colon]
    if any(b not in TOKEN for b in name.encode()):
        raise HttpError(400, 'invalid header name')
    return name.lower(), line[colon + 1:].strip(' \t')


def lookup(headers, name):
    return next((v for n, v in headers if n == name), None)


def decimal(text, limit):
    if not text:
        raise HttpError(400, 'empty length')
    value = 0
    for ch in text:
        if not '0' <= ch <= '9':
            raise HttpError(400, 'invalid length')
        value = value * 10 + int(ch)
        if value > limit:
            raise HttpError(413, f'body exceeds {limit} bytes')
    return value


def utf8_body(raw):
    try:
        return raw.decode()
    except UnicodeDecodeError:
        raise HttpError(400, 'body is not UTF-8')


def unchunk(data, at, limits):
    out = b''
    while True:
        lf = data.find(b'\n', at)
        if lf < 0:
            raise Incomplete
        digits = line_at(data, at, lf).split(';')[0]
        if not digits or len(digits) > 6 or any(c not in '0123456789abcdefABCDEF' for c in digits):
            raise HttpError(400, 'invalid chunk size')
        size = int(digits, 16)
        if len(out) + size > limits['body']:
            raise HttpError(413, f'body exceeds {limits["body"]} bytes')
        at = lf + 1
        if size == 0:
            _, stop = head_lines(data, at, limits)
            return utf8_body(out), stop
        if at + size + 2 > len(data):
            raise Incomplete
        if data[at + size:at + size + 2] != b'\r\n':
            raise HttpError(400, 'chunk not terminated')
        out += data[at:at + size]
        at += size + 2


def unquote(text, plus):
    raw, out, i = text.encode(), bytearray(), 0
    while i < len(raw):
        b = raw[i]
        if b == 37:
            if i + 2 >= len(raw):
                raise HttpError(400, 'truncated percent escape')
            pair = raw[i + 1:i + 3].decode('latin-1')
            if any(c not in '0123456789abcdefABCDEF' for c in pair):
                raise HttpError(400, 'invalid percent escape')
            out.append(int(pair, 16))
            i += 3
        else:
            out.append(32 if b == 43 and plus else b)
            i += 1
    try:
        return out.decode()
    except UnicodeDecodeError:
        raise HttpError(400, 'invalid UTF-8 in target')


def frame(data, limits=LIMITS):
    """(request, consumed); raises Incomplete or HttpError."""
    lf = data.find(b'\n')
    if lf < 0:
        if len(data) > limits['request_line'] + 2:
            raise HttpError(414, 'request line too long')
        raise Incomplete
    if lf - 1 > limits['request_line']:
        raise HttpError(414, 'request line too long')
    parts = line_at(data, 0, lf).split(' ')
    if len(parts) != 3:
        raise HttpError(400, 'malformed request line')
    method, target, version = parts
    if not method or any(not 'A' <= c <= 'Z' for c in method):
        raise HttpError(400, 'invalid method')
    if not version.startswith('HTTP/'):
        raise HttpError(400, 'malformed request line')
    if version not in ('HTTP/1.1', 'HTTP/1.0'):
        raise HttpError(505, f'unsupported version {version}')
    if not target.startswith('/'):
        raise HttpError(400, 'target must be absolute')
    lines, stop = head_lines(data, lf + 1, limits)
    headers = [parse_header(line) for line in lines]
    if version == 'HTTP/1.1' and lookup(headers, 'host') is None:
        raise HttpError(400, 'missing host')
    coding = lookup(headers, 'transfer-encoding')
    length = None
    for name, value in headers:
        if name == 'content-length':
            n = decimal(value, limits['body'])
            if length is not None and length != n:
                raise HttpError(400, 'conflicting lengths')
            length = n
    body = ''
    if coding is not None:
        if length is not None:
            raise HttpError(400, 'length with transfer coding')
        if coding.lower() != 'chunked':
            raise HttpError(501, f'transfer coding {coding}')
        body, stop = unchunk(data, stop, limits)
    elif length is not None:
        if stop + length > len(data):
            raise Incomplete
        body, stop = utf8_body(data[stop:stop + length]), stop + length
    raw_path, _, raw_query = target.partition('?')
    path = unquote(raw_path, False)
    query = {}
    for pair in raw_query.split('&') if raw_query else []:
        if pair:
            key, _, value = pair.partition('=')
            key = unquote(key, True)
            query[key] = unquote(value, True)
    return dict(method=method, path=path, query=query, version=version, headers=headers, body=body), stop


def encode(status, headers=(), body='', head_only=False, close=False):
    out = f'HTTP/1.1 {status} {REASONS[status]}\r\n' + ''.join(f'{n}: {v}\r\n' for n, v in headers)
    empty = status in (204, 304)
    if not empty:
        out += f'Content-Length: {len(body.encode())}\r\n'
    if close:
        out += 'Connection: close\r\n'
    out += '\r\n'
    if not empty and not head_only:
        out += body
    return out.encode()


ASSETS = {
    '/': ('text/html; charset=utf-8', '<!doctype html>\n<html lang="en">\n<head><meta charset="utf-8">'
          '<title>Dewy Notes</title>\n<link rel="stylesheet" href="/static/notes.css"></head>\n'
          '<body><iframe src="/static/notes_ui.html" title="notes"></iframe></body>\n</html>\n'),
    '/static/notes.css': ('text/css', 'body { margin: 0; background: #0b1622; }\n'
                          'iframe { border: 0; width: 100vw; height: 100vh; }\n'),
    '/static/manifest.json': ('application/json',
                              '{"name":"Dewy Notes","start_url":"/","display":"standalone"}\n'),
}


def fnv1a(text):
    h = 0xcbf29ce484222325
    for b in text.encode():
        h = ((h ^ b) * 0x100000001b3) & (2**64 - 1)
    return f'"{h:016x}"'


class Failure(Exception):
    def __init__(self, status, code, detail):
        self.status, self.code, self.detail = status, code, detail


class Notes:
    """The store: notes by id in creation order, a logical clock and revisions."""

    def __init__(self):
        self.notes, self.next_id, self.clock = {}, 1, 0

    def tick(self):
        self.clock += 1
        return self.clock

    @staticmethod
    def tags(raw):
        out = []
        for tag in raw:
            tag = tag.strip().lower()
            if tag not in out:
                out.append(tag)
        return out

    @staticmethod
    def validate(title, body, tags):
        problems = []
        if not title:
            problems.append('title is required')
        if len(title) > 40:
            problems.append('title is longer than 40')
        if len(body) > 400:
            problems.append('body is longer than 400')
        if len(tags) > 4:
            problems.append('more than 4 tags')
        for tag in tags:
            if not tag:
                problems.append('empty tag')
            elif len(tag) > 12:
                problems.append(f"tag '{tag}' is longer than 12")
            elif any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-' for c in tag):
                problems.append(f"tag '{tag}' must be lowercase letters, digits or -")
        if problems:
            raise Failure(422, 'invalid', '; '.join(problems))

    def etag(self, note):
        return f'"{note["id"]}.{note["revision"]}"'

    def get(self, id):
        if id not in self.notes:
            raise Failure(404, 'missing', f'note {id} not found')
        return self.notes[id]

    def guard(self, note, expected):
        if expected and expected != '*' and expected != self.etag(note):
            raise Failure(412, 'stale', f'note {note["id"]} is at {self.etag(note)}')

    def create(self, data):
        title, body, tags = data['title'].strip(), data.get('body', ''), self.tags(data.get('tags', []))
        self.validate(title, body, tags)
        note = dict(id=self.next_id, title=title, body=body, tags=tags, done=data.get('done', False),
                    revision=1, updated=self.tick())
        self.notes[note['id']] = note
        self.next_id += 1
        return note

    def replace(self, id, data, expected=''):
        note = self.get(id)
        self.guard(note, expected)
        title, body, tags = data['title'].strip(), data.get('body', ''), self.tags(data.get('tags', []))
        self.validate(title, body, tags)
        new = dict(id=id, title=title, body=body, tags=tags, done=data.get('done', False),
                   revision=note['revision'] + 1, updated=self.tick())
        self.notes[id] = new
        return new

    def patch(self, id, data, expected=''):
        note = self.get(id)
        self.guard(note, expected)
        title = data['title'].strip() if data.get('title') is not None else note['title']
        body = data['body'] if data.get('body') is not None else note['body']
        tags = self.tags(data['tags']) if data.get('tags') is not None else note['tags']
        self.validate(title, body, tags)
        done = data['done'] if data.get('done') is not None else note['done']
        new = dict(id=id, title=title, body=body, tags=tags, done=done, revision=note['revision'] + 1,
                   updated=self.tick())
        self.notes[id] = new
        return new

    def delete(self, id, expected=''):
        self.guard(self.get(id), expected)
        del self.notes[id]
        self.clock += 1


def small(text):
    return int(text) if 0 < len(text) <= 6 and all('0' <= c <= '9' for c in text) else None


def note_input(body):
    try:
        data = json.loads(body)
    except ValueError:
        return None
    return data if isinstance(data, dict) and isinstance(data.get('title'), str) else None


class Service:
    ROUTES = [('/api/health', ['GET']), ('/api/notes', ['GET', 'POST']), ('/api/notes/batch', ['POST']),
              ('/api/notes/{id}', ['GET', 'PUT', 'PATCH', 'DELETE']), ('/api/tags', ['GET']),
              ('/api/stats', ['GET'])]
    BODIES = {('/api/notes', 'POST'), ('/api/notes/batch', 'POST'), ('/api/notes/{id}', 'PUT'),
              ('/api/notes/{id}', 'PATCH')}

    def __init__(self):
        self.store, self.requests, self.errors = Notes(), 0, 0

    def json(self, status, value, extra=()):
        return status, [('Content-Type', 'application/json'), *extra], dumps(value)

    def fail(self, status, code, detail, extra=()):
        return self.json(status, {'error': code, 'detail': detail}, extra)

    def note(self, status, note):
        extra = [('ETag', self.store.etag(note))]
        if status == 201:
            extra.append(('Location', f'/api/notes/{note["id"]}'))
        return self.json(status, note, extra)

    def listing(self, query):
        tag, done, text, sort, limit, offset = '', None, '', 'id', 10, 0
        for key, value in query.items():
            if key == 'tag':
                tag = value.strip().lower()
            elif key == 'done':
                if value not in ('true', 'false'):
                    raise Failure(400, 'query', 'done must be true or false')
                done = value == 'true'
            elif key == 'q':
                text = value
            elif key == 'sort':
                if value not in ('id', 'title', 'updated'):
                    raise Failure(400, 'query', 'sort must be id, title or updated')
                sort = value
            elif key == 'limit':
                n = small(value)
                if n is None or not 1 <= n <= 50:
                    raise Failure(400, 'query', 'limit must be 1 to 50')
                limit = n
            elif key == 'offset':
                n = small(value)
                if n is None:
                    raise Failure(400, 'query', 'offset must be a whole number')
                offset = n
            else:
                raise Failure(400, 'query', f"unknown parameter '{key}'")
        chosen = [n for n in self.store.notes.values()
                  if (not tag or tag in n['tags']) and (done is None or n['done'] == done)
                  and (not text or text.lower() in n['title'].lower() or text.lower() in n['body'].lower())]
        if sort == 'title':
            chosen.sort(key=lambda n: n['title'].lower())
        elif sort == 'updated':
            chosen.sort(key=lambda n: -n['updated'])
        start = min(offset, len(chosen))
        return {'total': len(chosen), 'offset': offset, 'limit': limit,
                'items': chosen[start:min(start + limit, len(chosen))]}

    def batch(self, body):
        try:
            ops = json.loads(body)
        except ValueError:
            raise Failure(400, 'json', 'invalid JSON body')
        if not ops or len(ops) > 8:
            raise Failure(422, 'batch', 'a batch has 1 to 8 ops')
        draft, ids = copy.deepcopy(self.store), []
        for i, op in enumerate(ops):
            try:
                kind = op['op']
                if kind == 'create':
                    if op.get('note') is None:
                        raise Failure(422, 'invalid', 'create needs a note')
                    ids.append(draft.create(op['note'])['id'])
                elif kind == 'patch':
                    if op.get('patch') is None:
                        raise Failure(422, 'invalid', 'patch needs a patch')
                    ids.append(draft.patch(op.get('id', 0), op['patch'])['id'])
                elif kind == 'delete':
                    draft.delete(op.get('id', 0))
                    ids.append(op.get('id', 0))
                else:
                    raise Failure(422, 'invalid', f"unknown op '{kind}'")
            except Failure as failure:
                raise Failure(failure.status, 'batch', f'op {i}: {failure.detail}')
        self.store = draft
        return {'applied': len(ids), 'ids': ids}

    def handle(self, pattern, method, request, id):
        headers, store = request['headers'], self.store
        if pattern == '/api/health':
            return self.json(200, {'ok': True, 'notes': len(store.notes)})
        if pattern == '/api/tags':
            counts = {}
            for note in store.notes.values():
                for tag in note['tags']:
                    counts[tag] = counts.get(tag, 0) + 1
            ordered = sorted(sorted(counts.items()), key=lambda item: -item[1])
            return self.json(200, {'tags': [{'name': n, 'count': c} for n, c in ordered]})
        if pattern == '/api/stats':
            return self.json(200, {'requests': self.requests, 'errors': self.errors, 'notes': len(store.notes)})
        if pattern == '/api/notes/batch':
            return self.json(200, self.batch(request['body']))
        if pattern == '/api/notes':
            if method == 'GET':
                return self.json(200, self.listing(request['query']))
            data = note_input(request['body'])
            if data is None:
                raise Failure(400, 'json', 'invalid JSON body')
            return self.note(201, store.create(data))
        expected = lookup(headers, 'if-match') or ''
        if method == 'GET':
            note = store.get(id)
            if lookup(headers, 'if-none-match') == store.etag(note):
                return 304, [('ETag', store.etag(note))], ''
            return self.note(200, note)
        if method == 'DELETE':
            store.delete(id, expected)
            return 204, [], ''
        if method == 'PUT':
            data = note_input(request['body'])
            if data is None:
                raise Failure(400, 'json', 'invalid JSON body')
            return self.note(200, store.replace(id, data, expected))
        try:
            data = json.loads(request['body'])
        except ValueError:
            raise Failure(400, 'json', 'invalid JSON body')
        return self.note(200, store.patch(id, data, expected))

    def dispatch(self, request):
        path, method, headers = request['path'], request['method'], request['headers']
        if '..' in path.split('/'):
            return self.fail(400, 'path', 'dot segments are not allowed')
        if path in ASSETS:
            kind, body = ASSETS[path]
            tag = fnv1a(body)
            if method not in ('GET', 'HEAD'):
                return self.fail(405, 'method', f'{method} is not allowed', [('Allow', 'GET, HEAD')])
            if lookup(headers, 'if-none-match') == tag:
                return 304, [('ETag', tag)], ''
            return 200, [('Content-Type', kind), ('ETag', tag)], body
        for pattern, methods in self.ROUTES:
            want, have = pattern.split('/'), path.split('/')
            if len(want) != len(have):
                continue
            id, ok = 0, True
            for w, h in zip(want, have):
                if w == '{id}':
                    n = small(h)
                    ok = ok and bool(n)
                    id = n or 0
                elif w != h:
                    ok = False
            if not ok:
                continue
            wanted = 'GET' if method == 'HEAD' else method
            if wanted not in methods:
                allow = ', '.join(m for name in methods for m in ([name, 'HEAD'] if name == 'GET' else [name]))
                return self.fail(405, 'method', f'{method} is not allowed', [('Allow', allow)])
            kind = lookup(headers, 'content-type') or ''
            if (pattern, wanted) in self.BODIES and not (kind == 'application/json'
                                                        or kind.startswith('application/json;')):
                return self.fail(415, 'media', 'send application/json')
            try:
                return self.handle(pattern, wanted, request, id)
            except Failure as failure:
                return self.fail(failure.status, failure.code, failure.detail)
        return self.fail(404, 'route', f'no route for {path}')

    def route(self, request):
        response = self.dispatch(request)
        self.requests += 1
        if response[0] >= 400:
            self.errors += 1
        return response


class Conn:
    def __init__(self):
        self.pending, self.closed = b'', False

    def feed(self, service, chunk):
        if self.closed:
            return b''
        self.pending += chunk
        out = b''
        while not self.closed:
            try:
                request, used = frame(self.pending)
            except Incomplete:
                break
            except HttpError as error:
                service.requests += 1
                service.errors += 1
                out += encode(error.status, [('Content-Type', 'application/json')],
                              dumps({'error': 'http', 'detail': error.detail}), close=True)
                self.pending, self.closed = b'', True
                break
            self.pending = self.pending[used:]
            status, headers, body = service.route(request)
            connection = (lookup(request['headers'], 'connection') or '').lower()
            close = connection != 'keep-alive' if request['version'] == 'HTTP/1.0' else connection == 'close'
            out += encode(status, headers, body, head_only=request['method'] == 'HEAD', close=close)
            self.closed = close
        return out

    def finish(self, service):
        if self.closed or not self.pending:
            self.closed = True
            return b''
        self.closed, self.pending = True, b''
        service.requests += 1
        service.errors += 1
        return encode(400, [('Content-Type', 'application/json')],
                      dumps({'error': 'http', 'detail': 'incomplete request'}), close=True)


def show(out, data):
    try:
        text = data.decode()
    except UnicodeDecodeError:
        out.append(f'  <{len(data)} bytes, not UTF-8>')
        return
    out.extend(f'  {line}'.rstrip() for line in text.replace('\r\n', '\n').split('\n'))


def pieces(data, count):
    size = -(-len(data) // count)
    return [data[i:i + size] for i in range(0, len(data), size)]


def req(method, target, headers=(), body=''):
    head = f'{method} {target} HTTP/1.1\r\nHost: notes.local\r\n' + ''.join(f'{h}\r\n' for h in headers)
    if body:
        head += f'Content-Length: {len(body.encode())}\r\n'
    return f'{head}\r\n{body}'.encode()


def jreq(method, target, body, headers=()):
    return req(method, target, ['Content-Type: application/json', *headers], body)


def wire_cases():
    yield 'health', [req('GET', '/api/health')]
    yield 'index page', [req('GET', '/')]
    yield 'cached stylesheet', [req('GET', '/static/notes.css', [f'If-None-Match: {fnv1a(ASSETS["/static/notes.css"][1])}'])]
    yield 'head of manifest', [req('HEAD', '/static/manifest.json')]
    part1, part2 = '{"title":"  Buy milk ","tags":["Home","errands","home"]', ',"body":"2 litres"}'
    chunked = ('POST /api/notes HTTP/1.1\r\nHost: notes.local\r\nContent-Type: application/json\r\n'
               'Transfer-Encoding: chunked\r\n\r\n'
               f'{len(part1.encode()):x}\r\n{part1}\r\n{len(part2.encode()):X};ext=1\r\n{part2}\r\n0\r\nX-Trailer: 1\r\n\r\n')
    yield 'chunked create', pieces(chunked.encode(), 4)
    yield 'wrong media type', [req('POST', '/api/notes', ['Content-Type: text/plain'], 'title=x')]
    yield 'malformed json', [jreq('POST', '/api/notes', '{"title":')]
    yield 'invalid fields', [jreq('POST', '/api/notes', '{"title":"   ","tags":["ok","Not Ok!","a","b","c"]}')]
    yield 'unicode create', [jreq('POST', '/api/notes',
                                  '{"title":"Café plans ☕","body":"line one\\nline two","tags":["food"]}')]
    yield 'conditional get', [req('GET', '/api/notes/1', ['If-None-Match: "1.1"'])]
    yield 'stale put', [jreq('PUT', '/api/notes/1', '{"title":"Milk"}', ['If-Match: "1.9"'])]
    yield 'patch done', [jreq('PATCH', '/api/notes/1', '{"done":true}', ['If-Match: "1.1"'])]
    yield 'bad filter', [req('GET', '/api/notes?done=maybe')]
    yield 'unknown parameter', [req('GET', '/api/notes?colour=red')]
    yield 'missing note', [req('DELETE', '/api/notes/99')]
    yield 'zero id', [req('GET', '/api/notes/0')]
    batch = [{'op': 'create', 'note': {'title': 'Write report', 'tags': ['work', 'urgent']}},
             {'op': 'create', 'note': {'title': 'Plan trip', 'tags': ['travel', 'work']}},
             {'op': 'patch', 'id': 2, 'patch': {'tags': ['food', 'paris']}}]
    yield 'batch', [jreq('POST', '/api/notes/batch', dumps(batch))]
    failing = [{'op': 'create', 'note': {'title': 'Ghost'}}, {'op': 'delete', 'id': 42}]
    yield 'failed batch rolls back', [jreq('POST', '/api/notes/batch', dumps(failing))]
    yield 'list after batch', [req('GET', '/api/notes?sort=title&limit=2&offset=1')]
    yield 'search', [req('GET', '/api/notes?q=PLAN&tag=work')]
    yield 'tags', [req('GET', '/api/tags')]
    yield 'method not allowed', [req('PATCH', '/api/health')]
    yield 'dot segments', [req('GET', '/static/%2e%2e/secret')]
    yield 'no route', [req('GET', '/nowhere%20here')]
    stream = (req('GET', '/api/notes/2') + jreq('PATCH', '/api/notes/2', '{"title":"Café plans"}')
              + req('DELETE', '/api/notes/3', ['Connection: close']) + req('GET', '/api/health'))
    yield 'pipelined', pieces(stream, 7)
    yield 'http/1.0 closes', [b'GET /api/health HTTP/1.0\r\n\r\nGET /api/health HTTP/1.0\r\n\r\n']
    yield 'request line too long', [f'GET /{"a" * 300} HTTP/1.1\r\n'.encode()]
    yield 'endless request line', [f'GET /{"b" * 400}'.encode()]
    yield 'too many headers', [req('GET', '/api/health', [f'X-Header-{i}: {i}' for i in range(20)])]
    yield 'header section too large', [req('GET', '/api/health', [f'X-Big: {"c" * 1100}'])]
    yield 'body too large', [b'POST /api/notes HTTP/1.1\r\nHost: a\r\nContent-Type: application/json\r\n'
                             b'Content-Length: 99999\r\n\r\n']
    yield 'chunked too large', [b'POST /api/notes HTTP/1.1\r\nHost: a\r\nTransfer-Encoding: chunked\r\n\r\nfff\r\n']
    yield 'http/2', [b'GET / HTTP/2.0\r\nHost: a\r\n\r\n']
    yield 'bare LF', [b'GET / HTTP/1.1\nHost: a\n\n']
    yield 'missing host', [b'GET / HTTP/1.1\r\n\r\n']
    yield 'conflicting lengths', [b'POST /api/notes HTTP/1.1\r\nHost: a\r\nContent-Length: 2\r\n'
                                  b'Content-Length: 3\r\n\r\n{}']
    yield 'unknown coding', [b'POST /api/notes HTTP/1.1\r\nHost: a\r\nTransfer-Encoding: gzip\r\n\r\n']
    yield 'folded header', [b'GET / HTTP/1.1\r\nHost: a\r\n  folded\r\n\r\n']
    yield 'lowercase method', [b'get / HTTP/1.1\r\nHost: a\r\n\r\n']
    yield 'bad escape', [req('GET', '/api/notes?q=%zz')]
    yield 'body not utf-8', [b'PUT /api/notes/1 HTTP/1.1\r\nHost: a\r\nContent-Type: application/json\r\n'
                             b'Content-Length: 3\r\n\r\n{\xff}']
    yield 'truncated body', [b'POST /api/notes HTTP/1.1\r\nHost: a\r\nContent-Type: application/json\r\n'
                             b'Content-Length: 10\r\n\r\n{}']
    yield 'stats', [req('GET', '/api/stats')]


def parse_responses(data):
    """Client-side framing of complete responses (Content-Length bodies)."""
    out = []
    while True:
        head_end = data.find(b'\r\n\r\n')
        if head_end < 0:
            return out, data
        lines = data[:head_end].decode().split('\r\n')
        status = int(lines[0].split(' ')[1])
        headers = dict(parse_header(line) for line in lines[1:])
        length = int(headers.get('content-length', '0'))
        if head_end + 4 + length > len(data):
            return out, data
        out.append((status, data[head_end + 4:head_end + 4 + length].decode()))
        data = data[head_end + 4 + length:]


class NotesUi:
    """The UI state machine, as the acceptance statement describes it."""

    def __init__(self):
        self.items, self.total, self.tag, self.search = [], 0, '', ''
        self.title, self.tags, self.cursor, self.detail, self.banner, self.outbox = '', '', 0, None, '', []

    def list_call(self):
        path = '/api/notes?sort=title&limit=20'
        if self.tag:
            path += '&tag=' + url_quote(self.tag, safe='')
        if self.search:
            path += '&q=' + url_quote(self.search, safe='')
        return ('list', 'GET', path, '', '')

    def current(self):
        return self.items[self.cursor] if 0 <= self.cursor < len(self.items) else None

    def event(self, kind, arg=None):
        note = self.current()
        if kind in ('boot', 'clear'):
            self.tag = self.search = ''
            self.outbox.append(self.list_call())
        elif kind == 'title':
            self.title = arg
        elif kind == 'tags':
            self.tags = arg
        elif kind == 'submit':
            draft = {'title': self.title, 'tags': [t for t in self.tags.split(' ') if t], 'done': False}
            self.outbox.append(('create', 'POST', '/api/notes', dumps(draft), ''))
        elif kind == 'move':
            if self.items:
                self.cursor = max(0, min(len(self.items) - 1, self.cursor + arg))
        elif kind in ('toggle', 'rename') and note:
            change = {'done': not note['done']} if kind == 'toggle' else {'title': arg}
            self.outbox.append(('save', 'PATCH', f'/api/notes/{note["id"]}', dumps(change),
                                f'"{note["id"]}.{note["revision"]}"'))
        elif kind == 'open' and note:
            self.outbox.append(('open', 'GET', f'/api/notes/{note["id"]}', '', ''))
        elif kind == 'remove' and note:
            self.outbox.append(('remove', 'DELETE', f'/api/notes/{note["id"]}', '', ''))
        elif kind == 'tag':
            self.tag = arg
            self.outbox.append(self.list_call())
        elif kind == 'search':
            self.search = arg
            self.outbox.append(self.list_call())

    @staticmethod
    def view(note):
        return {k: note.get(k, d) for k, d in
                (('id', 0), ('title', ''), ('body', ''), ('tags', []), ('done', False), ('revision', 0))}

    def receive(self, purpose, status, body):
        def problem():
            try:
                return json.loads(body).get('detail', '')
            except ValueError:
                return f'HTTP {status}'
        if purpose == 'list':
            if status != 200:
                self.banner = f'Cannot load notes: {problem()}'
                return
            page = json.loads(body)
            self.items, self.total = [self.view(n) for n in page['items']], page['total']
            self.cursor = max(0, min(self.cursor, len(self.items) - 1))
            if self.detail and all(n['id'] != self.detail['id'] for n in self.items):
                self.detail = None
        elif purpose == 'create':
            if status == 201:
                self.banner = f'Created #{json.loads(body)["id"]}'
                self.title = self.tags = ''
                self.outbox.append(self.list_call())
            else:
                self.banner = f'Cannot save: {problem()}'
        elif purpose == 'save':
            if status == 200:
                note = self.view(json.loads(body))
                self.items = [note if n['id'] == note['id'] else n for n in self.items]
                if self.detail and self.detail['id'] == note['id']:
                    self.detail = note
                self.banner = f'Saved #{note["id"]} (rev {note["revision"]})'
                self.outbox.append(self.list_call())
            elif status == 412:
                self.banner = 'Changed elsewhere; reloaded'
                self.outbox.append(self.list_call())
            else:
                self.banner = f'Cannot save: {problem()}'
        elif purpose == 'open':
            if status == 200:
                self.detail = self.view(json.loads(body))
            else:
                self.banner = f'Cannot open: {problem()}'
        elif purpose == 'remove':
            self.banner = {204: 'Deleted', 404: 'Already gone'}.get(status, f'Cannot delete: {problem()}')
            self.outbox.append(self.list_call())

    def render(self):
        def rule(label):
            text = f'── {label} '
            return text + '─' * max(0, 44 - len(text))
        shown = f'{self.total}' if len(self.items) == self.total else f'{len(self.items)} of {self.total}'
        lines = [rule(f'Dewy Notes: {shown}'), f'filter: tag={self.tag or "any"} search="{self.search}"',
                 f'new: "{self.title}" tags="{self.tags}"']
        if not self.items:
            lines.append('  (no notes)')
        for i, n in enumerate(self.items):
            title = n['title'][:19] + '…' if len(n['title']) > 20 else n['title']
            mark, box = '>' if i == self.cursor else ' ', '[x]' if n['done'] else '[ ]'
            lines.append(f'{mark}{box} #{n["id"]} {title:<20} {" ".join(n["tags"])}'.rstrip())
        if self.detail:
            lines.append(rule(f'#{self.detail["id"]} rev {self.detail["revision"]}'))
            lines.append(self.detail['title'])
            if self.detail['body']:
                lines.extend(f'  {line}' for line in self.detail['body'].split('\n'))
        if self.banner:
            lines.append(f'! {self.banner}')
        return lines


def wire(call):
    purpose, method, path, body, if_match = call
    head = f'{method} {path} HTTP/1.1\r\nHost: notes.local\r\nAccept: application/json\r\n'
    if if_match:
        head += f'If-Match: {if_match}\r\n'
    if body or method in ('POST', 'PUT', 'PATCH'):
        head += f'Content-Type: application/json\r\nContent-Length: {len(body.encode())}\r\n'
    return f'{head}\r\n{body}'.encode()


@oracle('97_notes_service')
def notes_service():
    service, out = Service(), []
    for label, chunks in wire_cases():
        out.append(f'== {label}')
        conn, replies = Conn(), b''
        for chunk in chunks:
            replies += conn.feed(service, chunk)
        show(out, replies + conn.finish(service))
    ui, conn, log, pending = NotesUi(), Conn(), [], b''

    def step(kind, arg=None):
        nonlocal pending
        ui.event(kind, arg)
        while ui.outbox:
            call = ui.outbox.pop(0)
            replies = b''.join(conn.feed(service, piece) for piece in pieces(wire(call), 2))
            responses, pending = parse_responses(pending + replies)
            for status, body in responses:
                log.append(f'{call[1]} {call[2]} -> {status}')
                ui.receive(call[0], status, body)

    def screen(label):
        out.append(f'## {label}')
        out.extend(f'  {line}' for line in log)
        out.extend(f'| {line}' for line in ui.render())
        log.clear()
    step('boot')
    screen('boot')
    for kind, arg in [('title', 'Call the bank'), ('tags', 'money Urgent'), ('submit', None), ('title', '   '),
                      ('submit', None)]:
        step(kind, arg)
    screen('create, then an invalid draft')
    for kind, arg in [('title', 'Water plants'), ('tags', 'home'), ('submit', None), ('move', 1), ('toggle', None),
                      ('open', None)]:
        step(kind, arg)
    screen('toggle and open')
    step('tag', 'work')
    screen('filter by tag')
    step('clear')
    step('search', 'CAFÉ')
    screen('search')
    step('clear')
    step('move', -10)
    step('open')
    other = Conn()
    body = '{"body":"skim"}'
    edit = (f'PATCH /api/notes/1 HTTP/1.1\r\nHost: b\r\nContent-Type: application/json\r\n'
            f'Content-Length: {len(body)}\r\n\r\n{body}').encode()
    log.append(f'other client: {len(other.feed(service, edit))} bytes back')
    step('rename', 'Buy oat milk')
    step('rename', 'Buy oat milk')
    screen('stale rename, then retry')
    step('move', 2)
    gone = other.feed(service, b'DELETE /api/notes/5 HTTP/1.1\r\nHost: b\r\n\r\n')
    log.append(f'other client: {len(gone)} bytes back')
    step('remove')
    step('remove')
    screen('delete, racing another client')
    out.append('## server')
    show(out, Conn().feed(service, b'GET /api/stats HTTP/1.1\r\nHost: a\r\n\r\n'))
    return '\n'.join(out)


@oracle('98_notes_listen')
def notes_listen():
    """The same service over loopback sockets: each client's bytes in order, answers until close."""
    service, out = Service(), []
    create = '{"title":"Socket note","tags":["net"]}'
    sessions = [
        ('split create, then close', [
            'POST /api/notes HTTP/1.1\r\nHost: lo',
            f'cal\r\nContent-Type: application/json\r\nContent-Length: {len(create)}\r\n\r\n{create[:10]}',
            f'{create[10:]}GET /api/notes/1 HTTP/1.1\r\nHost: local\r\nConnection: close\r\n\r\n']),
        ('framing error closes', ['GET /api/health HTTP/1.1\r\nHost: local\r\n\r\nGET / HTTP/9\r\n\r\n']),
        ('http/1.0', ['GET /api/stats HTTP/1.0\r\n\r\n']),
    ]
    for label, parts in sessions:
        out.append(f'== {label}')
        conn = Conn()
        show(out, b''.join(conn.feed(service, part.encode()) for part in parts))
    out.append(f'accepted {len(sessions)}')
    return '\n'.join(out)


if __name__ == '__main__':
    failed = False
    for name, make in ORACLES.items():
        text = make() + '\n'
        target = ROOT / name / 'expected.out'
        if '--write' in sys.argv:
            target.write_text(text)
        elif not target.exists() or target.read_text() != text:
            print(f'{name}: expected.out differs from the oracle')
            failed = True
    sys.exit(1 if failed else 0)
