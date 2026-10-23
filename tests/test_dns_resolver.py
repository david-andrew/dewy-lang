"""The Linux resolver: random ids and source ports, replies checked against the question,
CNAME chains followed, failures reported (no public fallback); a fake name server on loopback."""
import socket
import struct
import subprocess
import sys
import threading

import pytest

from tests.support import compiler  # noqa: F401 (fixture)

PROGRAM = '''import net
main = ():
    port = to_int(args()[1]) ?? 0
    loop host in ["good.test", "Chain.Test.", "missing.test", "noaddr.test", "broken.test", "a..b", "silent.test"]:
        servers = [0x7F000001]
        ip = net.__n_dns(host, servers, port)
        print("{host} {ip} {net.__n_resolve_why}")
    print(net.__n_nameservers("nameserver 10.0.0.1\\n# nameserver 9.9.9.9\\nnameserver ::1\\nnameserver\\t10.0.0.2\\n"))
    print(net.__n_nameservers("search example.com\\n"))
    print(net.__n_nameservers("nameserver ::1\\n"))
'''


def name_bytes(name):
    return b''.join(bytes([len(p)]) + p.encode() for p in name.split('.')) + b'\0'


def question(data):
    at = 12
    labels = []
    while data[at]:
        labels.append(data[at + 1:at + 1 + data[at]].decode())
        at += 1 + data[at]
    return '.'.join(labels), data[12:at + 5]


def reply(query, flags=0x8180, answers=b'', count=0, ident=None, qsection=None):
    ident = struct.unpack('>H', query[:2])[0] if ident is None else ident
    _, asked = question(query)
    section = asked if qsection is None else qsection
    return struct.pack('>HHHHHH', ident, flags, 1, count, 0, 0) + section + answers


def record(owner, kind, data):
    return owner + struct.pack('>HHIH', kind, 1, 60, len(data)) + data


class FakeServer:
    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(('127.0.0.1', 0))
        self.port = self.sock.getsockname()[1]
        self.seen = []
        self.thread = threading.Thread(target=self.serve, daemon=True)
        self.thread.start()

    def serve(self):
        while True:
            try:
                data, peer = self.sock.recvfrom(2048)
            except OSError:
                return
            name, asked = question(data)
            self.seen.append((struct.unpack('>H', data[:2])[0], peer[1], name))
            send = lambda payload: self.sock.sendto(payload, peer)
            if name.lower() == 'good.test':
                ident = struct.unpack('>H', data[:2])[0]
                spoof = record(b'\xc0\x0c', 1, bytes([6, 6, 6, 6]))
                send(reply(data, answers=spoof, count=1, ident=ident ^ 1))           # another id
                send(reply(data, answers=spoof, count=1, qsection=name_bytes('evil.test') + asked[-4:]))
                send(reply(data, flags=0x0100, answers=spoof, count=1))              # not a reply
                send(reply(data, answers=record(b'\xc0\x0c', 1, bytes([10, 1, 2, 3])), count=1))
            elif name.lower() == 'chain.test':
                answers = record(b'\xc0\x0c', 5, name_bytes('real.test'))
                answers += record(name_bytes('other.test'), 1, bytes([6, 6, 6, 6]))
                answers += record(name_bytes('real.test'), 1, bytes([10, 9, 8, 7]))
                send(reply(data, answers=answers, count=3))
            elif name == 'missing.test':
                send(reply(data, flags=0x8183))
            elif name == 'noaddr.test':
                send(reply(data, answers=record(b'\xc0\x0c', 28, bytes(16)), count=1))
            elif name == 'broken.test':
                send(reply(data, answers=b'\xc0\x0c\x00\x01', count=1))
            # (silent.test: no answer)

    def close(self):
        self.sock.close()


@pytest.mark.skipif(not sys.platform.startswith('linux'), reason="Linux's own resolver")
def test_resolver_against_fake_server(compiler, tmp_path):
    source = tmp_path / 'dns.jo'
    source.write_text(PROGRAM)
    binary = tmp_path / 'dns'
    built = subprocess.run([compiler, 'build', source, '-o', binary],
                           capture_output=True, text=True, timeout=60, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    server = FakeServer()
    try:
        ran = subprocess.run([binary, str(server.port)], capture_output=True, text=True, timeout=60,
                             check=False)
    finally:
        server.close()
    assert ran.returncode == 0, ran.stderr
    lines = ran.stdout.splitlines()
    ip = lambda a, b, c, d: (a << 24) | (b << 16) | (c << 8) | d
    assert lines == [
        f'good.test {ip(10, 1, 2, 3)} ',
        f'Chain.Test. {ip(10, 9, 8, 7)} ',
        'missing.test -1 the name server knows no such name',
        'noaddr.test -1 the name server gives no IPv4 address for it',
        'broken.test -1 the name server gives no IPv4 address for it',
        'a..b -1 it is not a name',
        'silent.test -1 no name server answered',
        f'[{ip(10, 0, 0, 1)}, {ip(10, 0, 0, 2)}]',
        f'[{ip(127, 0, 0, 1)}]',
        '[]',
    ]
    ids = [ident for ident, _, _ in server.seen]
    ports = [port for _, port, _ in server.seen]
    assert len(server.seen) == 5 + 3          # (silent.test: asked three times)
    assert len(set(ids)) >= len(ids) - 1 and 0x1234 not in ids
    assert len(set(ports)) >= len(ports) - 1 and 53 not in ports
