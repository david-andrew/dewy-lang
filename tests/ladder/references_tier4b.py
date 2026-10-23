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



# 99 Dewy frontend ------------------------------------------------------------------------------
# Dewy's lexical rules and operator table (docs/LANGUAGE.md, docs/design/precedence.md and the
# compiler's dn_power table), modelled directly over bytes.

PUNCT = sorted(['(', ')', '[', ']', '{', '}', '<', '>', ':', '.', ',', ';', '=', '+', '-', '*', '/', '%', '@', '&',
                '|', '^', '?', '!', '~', '>=?', '<=?', '//=', '<<=', '>>=', '...', '=>', ':>', '->', '=?', '>?',
                '<?', '+=', '-=', '*=', '/=', '^=', '%=', '??', '//', '<<', '>>', '..', '|>', '<|',
                '.not>=?', '.not<=?', '.not=?', '.not>?', '.not<?', '.>=?', '.<=?', './/=', '.+=', '.-=', '.*=',
                './=', '.%=', '.^=', './/', '.=?', '.>?', '.<?', '.+', '.-', '.*', './', '.%', '.^', '&=', '|='],
               key=len, reverse=True)
WORDS = {'let', 'const', 'return', 'break', 'continue', 'import', 'from', 'else', 'if', 'loop', 'match', 'test',
         'not', 'as', 'transmute', 'or', 'xor', 'and', 'in', 'of', 'or_throw', 'nand', 'nor', 'xnor'}
INVERT = {'=?': 'not=?', '<?': 'not<?', '>?': 'not>?', '<=?': 'not<=?', '>=?': 'not>=?', 'in?': 'not in?'}
ASSIGN = {'+=', '-=', '*=', '/=', '//=', '%=', '^=', '<<=', '>>=', '.+=', '.-=', '.*=', './=', './/=', '.%=', '.^=',
          '&=', '|=', 'and=', 'or=', 'xor=', '='}
POWER = {'->': 20, '<|': 24, '|>': 25, '=>': 30, ':>': 40, ':': 45, 'or_throw': 48, 'as': 50, 'transmute': 50,
         'or': 60, 'nor': 60, 'xor': 65, 'xnor': 65, 'and': 70, 'nand': 70, '??': 82, '|': 85, '&': 90, 'in': 95,
         '..': 100, ',': 105, '<<': 110, '>>': 110, '+': 120, '-': 120, '.+': 120, '.-': 120, '*': 130, '/': 130,
         '//': 130, '%': 130, '.*': 130, './': 130, './/': 130, '.%': 130, '^': 140, '.^': 140}
for _c in ['=?', '<?', '>?', '<=?', '>=?']:
    for _form in (_c, 'not' + _c, '.' + _c, '.not' + _c):
        POWER[_form] = 80
POWER.update({'is?': 80, 'isnt?': 80, 'in?': 80, 'not in?': 80}, **{a: 10 for a in ASSIGN})


class FrontError(Exception):
    def __init__(self, stage, offset, message):
        self.stage, self.offset, self.message = stage, offset, message


def ident_start(c):
    return chr(c).isascii() and (chr(c).isalpha() or c == 95) or c >= 128


def ident_part(c):
    return ident_start(c) or 48 <= c <= 57


def block_end(src, i, stop):
    i, depth = i + 2, 1
    while i + 1 < stop:
        if src[i:i + 2] == b'#{':
            depth, i = depth + 1, i + 2
        elif src[i:i + 2] == b'}#':
            depth, i = depth - 1, i + 2
            if depth == 0:
                return i
        else:
            i += 1
    return -1


def quote_end(src, start, stop, nesting=0, raw=False):
    if nesting >= 256:
        raise FrontError('lex', start, 'string interpolation is nested too deeply')
    q = src[start]
    width = 3 if start + 2 < stop and src[start + 1] == q and src[start + 2] == q else 1
    i = start + width
    while i < stop:
        c = src[i]
        if not raw and c == 92:
            i += 2
            continue
        if c == q:
            if width == 1:
                return i + 1
            if i + 2 < stop and src[i + 1] == q and src[i + 2] == q:
                return i + 3
        if not raw and c == 123:
            i = brace_end(src, i + 1, stop, nesting + 1) + 1
            continue
        i += 1
    raise FrontError('lex', start, 'unterminated string')


def brace_end(src, start, stop, nesting):
    i, depth = start, 1
    while i < stop:
        c = src[i]
        if src[i:i + 2] == b'#{':
            e = block_end(src, i, stop)
            if e < 0:
                raise FrontError('lex', i, 'unterminated block comment')
            i = e
        elif c == 35:
            while i < stop and src[i] != 10:
                i += 1
        elif c == 114 and i + 1 < stop and src[i + 1] in b'"\'' and (i == start or not ident_part(src[i - 1])):
            i = quote_end(src, i + 1, stop, nesting, True)
        elif c in b'"\'':
            i = quote_end(src, i, stop, nesting)
        else:
            if c == 123:
                depth += 1
            elif c == 125:
                depth -= 1
                if depth == 0:
                    return i
            i += 1
    raise FrontError('lex', start, 'unterminated string interpolation')


def tokenize(src, begin=0, stop=None):
    """Tokens as dicts: kind, sym (punctuation/keyword spelling or None), start, stop, space, newline."""
    stop = len(src) if stop is None else stop
    out, i, space, newline = [], begin, False, False
    while i < stop:
        c = src[i]
        if c in b' \t\r\n':
            space = True
            while i < stop and src[i] in b' \t\r\n':
                newline = newline or src[i] == 10
                i += 1
            continue
        if src[i:i + 2] == b'#{':
            e = block_end(src, i, stop)
            if e < 0:
                raise FrontError('lex', i, 'unterminated block comment: `#{` needs a matching `}#` (block comments nest)')
            newline = newline or 10 in src[i:e]
            space, i = True, e
            continue
        if c == 35:
            while i < stop and src[i] != 10:
                i += 1
            space = True
            continue
        start, kind, sym = i, 'op', None
        if c == 114 and i + 1 < stop and src[i + 1] in b'"\'':
            i, kind = quote_end(src, i + 1, stop, 0, True), 'rawquoted'
        elif ident_start(c):
            while i < stop and ident_part(src[i]):
                i += 1
            kind, word = 'identifier', src[start:i].decode()
            if word in ('true', 'false'):
                kind = 'boolean'
            if word in ('is', 'isnt', 'in') and i < stop and src[i] == 63:
                word, i, kind = word + '?', i + 1, 'op'
            if kind != 'boolean' and (word in WORDS or kind == 'op'):
                sym = word
            if sym in ('and', 'or', 'xor') and i < stop and src[i] == 61 and src[i + 1:i + 2] not in (b'?', b'>', b'='):
                sym, kind, i = sym + '=', 'op', i + 1
        elif c == 36:
            i += 1
            while i < stop and (chr(src[i]).isascii() and (chr(src[i]).isalnum() or src[i] == 95)):
                i += 1
            if i == start + 1:
                raise FrontError('lex', start, 'expected a name after $')
            kind = 'metatag'
        elif 48 <= c <= 57:
            decimal, digits = True, start
            if c == 48 and i + 1 < stop and src[i + 1] in b'btqsodzxug':
                decimal, i = src[i + 1] == 100, i + 2
                digits = i
            if i < stop and src[i] in b'"\'':
                i, kind = quote_end(src, i, stop), 'based_string'
            else:
                ok = (lambda b: 48 <= b <= 57 or b == 95) if decimal else (lambda b: chr(b).isascii() and (chr(b).isalnum() or b == 95))
                while i < stop and ok(src[i]):
                    i += 1
                if i == digits:
                    raise FrontError('lex', start, 'expected digits after the base prefix')
                kind = 'source_integer' if decimal else 'integer'
                digit = lambda b: 48 <= b <= 57
                if decimal and i + 1 < stop and src[i] == 46 and digit(src[i + 1]):
                    i += 1
                    while i < stop and (digit(src[i]) or src[i] == 95):
                        i += 1
                    kind = 'source_real'
                if decimal and i + 1 < stop and src[i] in b'eE' and (digit(src[i + 1]) or src[i + 1] in b'+-'):
                    i += 1
                    if i < stop and src[i] in b'+-':
                        i += 1
                    first = i
                    while i < stop and (digit(src[i]) or src[i] == 95):
                        i += 1
                    if i == first:
                        raise FrontError('lex', start, 'expected exponent digits')
                    kind = 'source_real'
        elif c in b'"\'':
            i, kind = quote_end(src, i, stop), 'quoted'
        else:
            for text in PUNCT:
                raw = text.encode()
                if src[i:i + len(raw)] == raw and not (text == '>>=' and src[i + 3:i + 4] == b'>'):
                    sym = text
                    break
            if sym is None:
                raise FrontError('lex', start, 'unexpected character in Dewy source')
            i += len(sym.encode())
        out.append(dict(kind=kind, sym=sym, start=start, stop=i, space=space, newline=newline))
        space = newline = False
    out.append(dict(kind='eof', sym=None, start=stop, stop=stop, space=space, newline=newline))
    return out


ESCAPES = {'n': 10, 'r': 13, 't': 9, '0': 0, 'a': 7, 'b': 8, 'v': 11, 'f': 12, '\\': 92, '"': 34, "'": 39,
           '{': 123, '}': 125}


class Front:
    """A Pratt parser over the token list; trees are nested lists and strings."""

    def __init__(self, src, tokens):
        self.src, self.toks, self.at, self.angles, self.comma_stop, self.inside = src, tokens, 0, 0, False, 0

    def fail(self, offset, message):
        if self.inside:
            message += ', inside a string interpolation'
        raise FrontError('parse', offset, message)

    def tok(self, k=0):
        return self.toks[self.at + k]

    def text(self, t):
        return self.src[t['start']:t['stop']].decode()

    def can_start(self):
        t = self.tok()
        return t['kind'] != 'eof' and t['sym'] not in (')', ']', '}', '>', '>>', 'else', ';', ',')

    def range_bound(self):
        s = self.tok()['sym']
        return self.can_start() and s not in ('{', 'let', 'const', 'return', 'break', 'continue', 'if', 'loop',
                                              'match') and (POWER.get(s, 0) == 0 or s in ('+', '-'))

    def expect(self, sym):
        if self.tok()['sym'] != sym:
            self.fail(self.tok()['start'], f"expected '{sym}'")
        self.at += 1

    def string(self, t):
        src, raw = self.src, t['kind'] == 'rawquoted'
        opening = t['start'] + 1 if raw else t['start']
        q = src[opening]
        width = 3 if opening + 2 < t['stop'] and src[opening + 1] == q and src[opening + 2] == q else 1
        i, stop = opening + width, t['stop'] - width
        if raw:
            return ('str', src[i:stop].decode())
        parts, data, interpolated = [], bytearray(), False
        while i < stop:
            c = src[i]
            if c == 92:
                i += 1
                if i >= stop:
                    self.fail(i, 'incomplete string escape')
                e = chr(src[i])
                if e == '\n':
                    i += 1
                elif e in 'uU':
                    at, i = i, i + 1
                    braced = i < stop and src[i] == 123
                    i += braced
                    first = i
                    while i < stop and not (braced and src[i] == 125) and not (not braced and i - first == 4):
                        if chr(src[i]) not in '0123456789abcdefABCDEF':
                            self.fail(i, 'expected hexadecimal digits in Unicode escape')
                        if i - first >= 6:
                            self.fail(at, 'Unicode escape has too many digits')
                        i += 1
                    value = int(src[first:i], 16) if i > first else 0
                    if braced:
                        if i == first or i >= stop or src[i] != 125:
                            self.fail(at, "expected 1–6 hex digits and '}' in Unicode escape")
                        i += 1
                    elif i - first != 4:
                        self.fail(at, 'Unicode escape needs four hex digits')
                    if value > 0x10FFFF or 0xD800 <= value <= 0xDFFF:
                        self.fail(at, 'Unicode escape must name a scalar value, not a surrogate or out-of-range code point')
                    data += chr(value).encode()
                elif e in ESCAPES:
                    data.append(ESCAPES[e])
                    i += 1
                else:
                    self.fail(i, 'unsupported string escape')
            elif c == 123:
                interpolated = True
                if data:
                    parts.append(('str', data.decode('utf-8', 'replace')))
                    data = bytearray()
                close = brace_end(src, i + 1, stop, 0)
                saved = (self.toks, self.at, self.angles, self.comma_stop)
                try:
                    inner = tokenize(src, i + 1, close)
                except FrontError as error:
                    self.fail(error.offset, error.message)
                self.toks, self.at, self.angles, self.comma_stop = inner, 0, 0, False
                self.inside += 1
                value = self.expr(0)
                if self.tok()['kind'] != 'eof':
                    self.fail(self.tok()['start'], 'expected one interpolation expression')
                self.inside -= 1
                self.toks, self.at, self.angles, self.comma_stop = saved
                parts.append(value)
                i = close + 1
            else:
                data.append(c)
                i += 1
        if not interpolated:
            return ('str', data.decode('utf-8', 'replace'))
        if data:
            parts.append(('str', data.decode('utf-8', 'replace')))
        return ['interp', *parts]

    def bracketed(self):
        opening = self.tok()
        self.at += 1
        open_ = opening['sym']
        if open_ == '(':
            s = self.tok()['sym']
            partial = s in ('=?', 'not=?', '<?', 'not<?', '>?', 'not>?', '<=?', 'not<=?', '>=?', 'not>=?', 'is?',
                            'isnt?', 'in?', 'not in?', '.', 'as', 'transmute', '*', '/', '//', '%', '^')
            if partial or (s == 'not' and self.tok(1)['sym'] in INVERT):
                body = self.rest('_', 0)
                self.expect(')')
                return ['partial', body]
        if open_ == '<':
            self.angles += 1
        close = {'(': ')', '[': ']', '<': '>'}.get(open_, '}')
        kids, saved = [], self.comma_stop
        self.comma_stop = False
        while True:
            t = self.tok()
            if t['kind'] == 'eof':
                self.fail(opening['start'], f"expected '{close}' before end of file")
            s = t['sym']
            if close == '>' and (s in ('>>', '>>=') or (s == '>?' and not t['space'])):
                rest = self.src[t['start'] + 1:t['stop']].decode()
                self.toks[self.at] = dict(t, sym=rest, start=t['start'] + 1)
                break
            if s == close:
                self.at += 1
                break
            if ((open_ == '[' and s == ')') or (open_ == '(' and s == ']')) and len(kids) == 1 \
                    and isinstance(kids[0], list) and kids[0][0] == '..':
                close = s
                self.at += 1
                break
            before = self.at
            kids.append(self.statement())
            if self.at == before:
                self.fail(self.tok()['start'], 'expected a block element')
        self.comma_stop = saved
        if open_ == '<':
            self.angles -= 1
        return [open_ + close, *kids]

    def flow(self):
        arms = []
        while True:
            word = self.tok()['sym']
            self.at += 1
            condition = self.expr(0)
            if not self.can_start():
                nxt = self.tok()['sym']
                hint = ' (comparisons end with `?`: `x >? y`, `x <=? y`)' if nxt in ('>', '<', '>=?', '<=?') else ''
                self.fail(self.tok()['start'], f"expected a body after '{word}'{hint}")
            arms.append([word, condition, self.expr(0)])
            if self.tok()['sym'] != 'else':
                break
            self.at += 1
            if self.tok()['sym'] in ('if', 'match'):
                continue
            arms.append(self.expr(0))
            break
        return ['flow', *arms]

    def directive(self, t, form):
        self.at += 1
        name, nxt = self.text(t), self.tok()
        if form == 3 or nxt['newline'] or not self.can_start():
            if form == 1:
                self.fail(t['start'], f'`{name}` needs a condition: `{name} condition` or `{name} condition, "message"`')
            return [name, None, None]
        saved, self.comma_stop = self.comma_stop, True
        condition = message = None
        if form == 1:
            listed = nxt['sym'] == '(' and not nxt['space']
            self.at += listed
            condition = self.expr(0)
            if self.tok()['sym'] == ',':
                self.at += 1
                message = self.expr(0)
            if listed:
                self.expect(')')
        else:
            message = self.expr(0)
        self.comma_stop = saved
        return [name, condition, message]

    def atom(self):
        t = self.tok()
        s = t['sym']
        if t['kind'] == 'eof':
            self.fail(t['start'], 'expected an expression')
        if t['kind'] == 'metatag':
            form = {'$assert': 1, '$runtime_assert': 1, '$expect': 1, '$unsafe_assume': 1, '$fail': 2,
                    '$breakpoint': 3}.get(self.text(t), 0)
            if form:
                return self.directive(t, form)
        if s in ('(', '[', '{', '<'):
            return self.bracketed()
        if s in ('if', 'loop', 'match'):
            return self.flow()
        if s in ('let', 'const', 'return', 'break', 'continue', 'import', 'from'):
            return self.statement()
        self.at += 1
        if t['kind'] in ('quoted', 'rawquoted'):
            return self.string(t)
        if s in ('~', '+', '-', '.+', '.-', '@', 'not'):
            return [s, self.expr(160 if s == '@' else 75 if s == 'not' else 125)]
        if s == '..':
            return ['..', None, self.expr(101)] if self.range_bound() else '..'
        word = self.text(t)
        if word == 'type' and self.tok()['sym'] == 'of':
            self.at += 1
            return ['type of', self.expr(91)]
        if t['kind'] == 'op':
            prev = self.toks[self.at - 2]['sym'] if self.at >= 2 else None
            adjacent = self.at >= 2 and not self.toks[self.at - 1]['space']
            hint = ''
            if word == '!':
                hint = ' (`not x` negates, and `x not=? y` asks whether two values differ)'
            elif word == '&' and prev == '&' and adjacent:
                hint = ' (`and` joins conditions: `a and b`)'
            elif word == '|' and prev == '|' and adjacent:
                hint = ' (`or` joins conditions: `a or b`)'
            elif word == '=' and prev in ('=', '=?') and adjacent:
                hint = ' (`=?` compares: `x =? y`; `=` gives a value)'
            elif word in ('>', '<', '>=', '<='):
                hint = ' (comparisons end with `?`: `x >? y`, `x <=? y`)'
            elif word == '*' and prev == '*' and adjacent:
                hint = ' (`^` raises to a power: `x^2`)'
            self.fail(t['start'], f"expected an expression, found '{word}'{hint}")
        return ('num' if t['kind'] in ('source_integer', 'integer', 'source_real') else 'leaf', word)

    def expr(self, minimum):
        return self.rest(self.atom(), minimum)

    def rest(self, left, minimum):
        while True:
            t = self.tok()
            op = t['sym']
            if t['kind'] == 'eof':
                break
            if t['newline'] and POWER.get(op, 0) == 0 and op != 'not':
                break
            if self.angles and (op in ('>>', '>>=', '>=') or (op == '>?' and not t['space'])):
                break
            if op == 'or_throw' and minimum <= 48 or op == '...' and minimum <= 170:
                self.at += 1
                left = [op, left]
                continue
            if not t['space'] and minimum <= 135 and isinstance(left, tuple) and left[0] == 'num' \
                    and (t['kind'] == 'identifier' or op == '('):
                left = ['mul', left, self.expr(136)]
                continue
            if op == '.' and minimum <= 170:
                self.at += 1
                if self.tok()['sym'] == '(' and not self.tok()['space']:
                    left = ['bcall', left, self.bracketed()]
                    continue
                member = self.tok()
                self.at += 1
                if member['kind'] != 'identifier':
                    self.fail(member['start'], 'expected a member name')
                left = ['.', left, ('leaf', self.text(member))]
                continue
            if not t['space'] and op in ('(', '[') and minimum <= 170:
                left = ['call' if op == '(' else 'index', left, self.bracketed()]
                continue
            if not t['space'] and t['kind'] in ('quoted', 'rawquoted') and minimum <= 170:
                self.at += 1
                left = ['call', left, self.string(t)]
                continue
            if not t['space'] and op == '<' and minimum <= 160:
                left = ['tapp', left, self.bracketed()]
                continue
            if op == '?' and minimum <= 140:
                self.at += 1
                left = ['?', left]
                continue
            spaced_not = op == 'not' and self.tok(1)['sym'] in INVERT
            if spaced_not:
                op = INVERT[self.tok(1)['sym']]
            if op == ',' and self.comma_stop:
                break
            strength = POWER.get(op, 0)
            if strength == 0 or strength < minimum:
                break
            if op in ('+', '-') and t['space'] and not self.tok(1)['space']:
                break
            self.at += 1 + spaced_not
            if op == '..':
                left = ['..', left, self.expr(strength + 1) if self.range_bound() else None]
                continue
            right = self.expr(strength if op in ('=>', '^', '.^', '??', '<|') else strength + 1)
            if op == ',':
                left = left + [right] if isinstance(left, list) and left[0] == ',' else [',', left, right]
            elif op in ('nand', 'nor', 'xnor'):
                left = ['not', [{'nand': 'and', 'nor': 'or', 'xnor': 'xor'}[op], left, right]]
            else:
                left = [op, left, right]
        return left

    def statement(self):
        t = self.tok()
        s = t['sym']
        if s in ('let', 'const', 'return', 'break', 'continue', 'import', 'from'):
            self.at += 1
            kids = []
            if s not in ('break', 'continue'):
                if s != 'return' or (self.can_start() and not self.tok()['newline']):
                    kids.append(self.expr(0))
            elif self.tok()['kind'] == 'metatag' and not self.tok()['newline']:
                kids.append(self.atom())
            if s == 'from':
                self.expect('import')
                kids.append(self.expr(0))
            result = [s, *kids]
        else:
            result = self.expr(0)
        if self.tok()['sym'] == ';' and not self.tok()['space']:
            self.at += 1
            result = [';', result, None]
        return result

    def parse(self):
        roots = []
        while self.tok()['kind'] != 'eof':
            before = self.at
            roots.append(self.statement())
            if self.at == before:
                self.fail(self.tok()['start'], 'expected a declaration')
        return roots


def count_nodes(node):
    if node is None:
        return 0
    if isinstance(node, (str, tuple)):
        return 1
    return 1 + sum(count_nodes(k) for k in node[1:])


def show_string(value):
    out = ''
    for ch in value:
        out += {'"': '\\"', '\\': '\\\\', '\n': '\\n', '\t': '\\t'}.get(ch, ch if ord(ch) >= 32 else f'\\x{ord(ch):02x}')
    return f'"{out}"'


def sexpr(node):
    if node is None:
        return '_'
    if isinstance(node, str):
        return node
    if isinstance(node, tuple):
        return show_string(node[1]) if node[0] == 'str' else node[1]
    head, kids = node[0], [sexpr(k) for k in node[1:]]
    return f'({head} {" ".join(kids)})' if kids else f'({head})'


TAGS = {'op': '', 'identifier': 'id', 'boolean': 'bool', 'quoted': 'str', 'rawquoted': 'raw', 'based_string': 'based',
        'metatag': 'meta', 'source_integer': 'int', 'integer': 'radix', 'source_real': 'real'}


@oracle('99_dewy_frontend')
def dewy_frontend():
    corpus = (ROOT / '99_dewy_frontend' / 'corpus.txt').read_text()
    entries, out, tokens_seen, nodes_seen, errors = [], [], 0, 0, 0
    for line in corpus.split('\n'):
        if line.startswith('### '):
            entries.append([line[4:], []])
        elif entries:
            entries[-1][1].append(line)
    entries[-1][1] = '\n'.join(entries[-1][1]).rstrip().split('\n')
    for name, lines in entries:
        src = '\n'.join(lines).encode()
        out.append(f'### {name}')
        try:
            toks = tokenize(src)
            words = []
            for t in toks[:-1]:
                mark = '^' if t['newline'] else '_' if t['space'] else ''
                text = src[t['start']:t['stop']].decode()
                tag = TAGS[t['kind']]
                label = text if not tag else f'kw:{text}' if t['kind'] == 'identifier' and t['sym'] else f'{tag}:{text}'
                words.append(mark + label)
            tokens_seen += len(toks) - 1
            out.append('  tokens ' + ' '.join(words))
            front = Front(src, toks)
            roots = front.parse()
            nodes_seen += sum(count_nodes(r) for r in roots)
            out.extend(f'  tree {sexpr(r)}' for r in roots)
        except FrontError as error:
            errors += 1
            start = src.rfind(b'\n', 0, error.offset) + 1
            stop = src.find(b'\n', error.offset)
            stop = len(src) if stop < 0 else stop
            line = src[:error.offset].count(b'\n') + 1
            column = len(src[start:error.offset].decode('utf-8', 'replace')) + 1
            out.append(f'  {error.stage} error {line}:{column}: {error.message}')
            out.append(f'  | {src[start:stop].decode()}')
            out.append(f'  | {" " * (column - 1)}^')
    out.append(f'entries {len(entries)}, tokens {tokens_seen}, nodes {nodes_seen}, errors {errors}')
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
