"""Local game connections: native peers, browser-compatible messages, and final state."""
import json
import os
import selectors
import shutil
import socket
import struct
import subprocess
from contextlib import contextmanager
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TEXT = 'Dewy café🙂\0' + 'x' * 200
ECHO = '''import net
payload=():>array<uint8>=>{
    let data:array<uint8>=[]
    loop i in [0..512) {data.push(int64(i) as uint8)}
    return data
}
main=(args:array<string>):>int64=>{
    let port=match to_int(args[2]) {value:int64=>value <none>=>0}
    let server=args[1] =? "server"
    let count=0 let peer=-1 let data=payload()
    if server {
        if not net.listen(port) return 1
        printl("ready")
    } else {peer=net.connect("127.0.0.1" port)}
    let deadline=time_ns()+5000000000
    loop time_ns() <? deadline {
        loop event in net.receive() {
            if event.kind =? net.NetKind.joined {
                peer=event.peer
                if server {net.send(peer "hello")}
            } else if event.kind =? net.NetKind.message {
                if server {
                    if count =? 0 {net.send(peer event.text)}
                    else {net.send(peer event.data)}
                } else if count =? 0 {
                    if event.text not=? "hello" return 2
                    net.send(peer TEXT)
                } else if count =? 1 {
                    if event.text not=? TEXT return 3
                    net.send(peer data)
                } else {
                    if event.data not=? data return 4
                    net.close(peer)
                    printl("complete")
                    return 0
                }
                count+=1
            } else if event.kind =? net.NetKind.left {
                if server and count =? 2 {printl("disconnected") return 0}
                return 5
            }
        }
        sleep(0.001)
    }
    return 6
}
'''.replace('TEXT', '"' + TEXT.replace('\0', '\\0') + '"')


@pytest.fixture(scope='module')
def compiler():
    value = os.environ.get('DEWY_CORE_COMPILER')
    if not value:
        pytest.skip('set DEWY_CORE_COMPILER for network checks')
    return Path(value).resolve(strict=True)


def environment():
    return {k: v for k, v in os.environ.items()
            if not k.startswith(('SLOPPY_', 'DEWY_'))
            and k not in ('HOST', 'JOIN', 'INVITE', 'ROOM', 'TURN', 'TURN_SECRET', 'ROLE', 'NAME')}


def free_port():
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        return listener.getsockname()[1]


def ready(process):
    with selectors.DefaultSelector() as selector:
        selector.register(process.stdout, selectors.EVENT_READ)
        assert selector.select(10), 'server did not become ready'
    line = process.stdout.readline()
    assert line == 'ready\n', line


def stop(process):
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)
    process.stdout.close()
    process.stderr.close()


def build(compiler, source, binary, release=False):
    flags = ['--release'] if release else []
    result = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                            capture_output=True, text=True, timeout=30, check=False,
                            env=environment())
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.fixture(scope='module', params=[False, True], ids=['debug', 'release'])
def echo_binary(compiler, tmp_path_factory, request):
    work = tmp_path_factory.mktemp('network-echo')
    source = work / 'main.dewy'
    source.write_text(ECHO)
    binary = work / 'echo'
    build(compiler, source, binary, request.param)
    return binary


@pytest.mark.parametrize('client', ['native', 'node'])
def test_core_network_roundtrip(echo_binary, tmp_path, client):
    node = shutil.which('node')
    if client == 'node' and not node:
        pytest.skip('Node is needed for browser-compatible WebSocket checks')
    port = free_port()
    server = subprocess.Popen([echo_binary, 'server', str(port)], env=environment(),
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        ready(server)
        command = [echo_binary, 'client', str(port)]
        if client == 'node':
            script = tmp_path / 'client.cjs'
            script.write_text('''const assert = require('node:assert/strict');
const peer = new WebSocket(`ws://127.0.0.1:${process.argv[2]}`);
peer.binaryType = 'arraybuffer';
const payload = Uint8Array.from({length:512}, (_, i) => i & 255);
let count = 0;
const timer = setTimeout(() => {console.error('connection timed out'); process.exit(1);}, 5000);
peer.onerror = e => {console.error(e.error || e, {count}); process.exit(1);};
peer.onmessage = event => {
    if (count === 0) {assert.equal(event.data, 'hello'); peer.send(TEXT);}
    else if (count === 1) {assert.equal(event.data, TEXT); peer.send(payload);}
    else {assert.deepEqual(new Uint8Array(event.data), payload); peer.close(1000, 'done');}
    count++;
};
peer.onclose = event => {assert.equal(count, 3); assert.ok(event.wasClean); assert.equal(event.code, 1000); assert.equal(event.reason, 'done'); clearTimeout(timer); console.log('complete');};
'''.replace('TEXT', json.dumps(TEXT)))
            command = [node, script, str(port)]
        result = subprocess.run(command, env=environment(), capture_output=True, text=True,
                                timeout=10, check=False)
        assert result.returncode == 0 and result.stdout.strip() == 'complete', result.stdout + result.stderr
        out, err = server.communicate(timeout=5)
        assert server.returncode == 0 and out.strip() == 'disconnected', out + err
    finally:
        stop(server)


@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_netpong_winning_state(compiler, tmp_path, release):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node is needed for the multiplayer game check')
    source = (ROOT / 'examples/netpong.dewy').read_text()
    marker = '    screen = Screen.playing\n'
    assert source.count(marker) == 1
    source = source.replace(marker, marker + '''    score_l=WIN-1
    ball=vec2(1301 360)
    vel=vec2(0 0)
    send_wait=0.02
''')
    # Fix the simulation step so the winning frame falls between send ticks.
    source = source.replace('update = (dt: float64) =>', 'advance_game = (dt: float64) =>')
    source += '\nupdate=(dt:float64)=>advance_game(0.001)\nif hosting {printl("ready")}\n'
    path = tmp_path / 'netpong.dewy'
    path.write_text(source)
    binary = tmp_path / 'netpong'
    build(compiler, path, binary, release)
    port = free_port()
    env = environment()
    env.update(HOST='1', DEWY_NETPONG_PORT=str(port), SLOPPY_SOFTWARE='1', SLOPPY_FRAMES='180')
    server = subprocess.Popen([binary], env=env, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, text=True)
    try:
        ready(server)
        script = tmp_path / 'client.cjs'
        script.write_text('''const assert = require('node:assert/strict');
const peer = new WebSocket(`ws://127.0.0.1:${process.argv[2]}`);
let won = false;
const timer = setTimeout(() => {console.error('winning state was not delivered'); process.exit(1);}, 3000);
peer.onerror = e => {console.error(e.message); process.exit(1);};
peer.onmessage = event => {
    const parts = event.data.split(' ');
    assert.equal(parts[0], 's');
    if (parts[7] !== '7') return;
    assert.equal(parts[5], '7'); assert.equal(parts[6], '0');
    won = true; peer.close();
};
peer.onclose = () => {assert.ok(won, 'host closed without the winning state'); clearTimeout(timer);};
''')
        result = subprocess.run([node, script, str(port)], env=environment(), capture_output=True,
                                text=True, timeout=5, check=False)
        assert result.returncode == 0, result.stdout + result.stderr
    finally:
        stop(server)


@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_core_network_shared_read_buffer(compiler, tmp_path, release):
    binary = tmp_path / 'buffers'
    build(compiler, ROOT / 'tests/fixtures/programs/net_buffer.dewy', binary, release)
    first, first_writer = socket.socketpair()
    second, second_writer = socket.socketpair()
    with first, first_writer, second, second_writer:
        first.setblocking(False)
        second.setblocking(False)
        for i, writer in enumerate([first_writer, second_writer]):
            payload = bytes([40 + i]) * (65536 + i)
            writer.sendall(b'\x82\x7f' + struct.pack('>Q', len(payload)) + payload)
        fds = [first.fileno(), second.fileno()]
        ran = subprocess.run([binary, *map(str, fds)], pass_fds=fds, env=environment(),
                             capture_output=True, text=True, timeout=10, check=False)
        assert ran.returncode == 42, (ran.returncode, ran.stdout, ran.stderr)


@pytest.fixture(scope='module', params=[False, True], ids=['debug', 'release'])
def room_binaries(compiler, tmp_path_factory, request):
    work = tmp_path_factory.mktemp('rooms')
    server, game = work / 'rendezvous', work / 'room_game'
    build(compiler, ROOT / 'tools/compiler/rendezvous.jo', server, request.param)
    build(compiler, ROOT / 'tests/fixtures/programs/room_game.jo', game, request.param)
    return server, game, request.param


@contextmanager
def room_server(binary, work):
    port = free_port()
    rooms = work / 'rooms.txt'
    rooms.write_text('game/SAVED saved-key 1792300000\n')
    env = environment()
    env.update(PORT=str(port), ROOMS=str(rooms), TURN='', TURN_SECRET='', MAX_CLIENTS='20')
    server = subprocess.Popen([binary], env=env, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, text=True)
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(server.stdout, selectors.EVENT_READ)
            assert selector.select(10), 'room server did not become ready'
        line = server.stdout.readline()
        assert line.startswith(f'rendezvous on port {port}: 1 rooms kept'), line
        yield port
    finally:
        stop(server)


def test_core_room_protocol(room_binaries, tmp_path):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node is needed for room protocol checks')
    with room_server(room_binaries[0], tmp_path) as port:
        result = subprocess.run([node, ROOT / 'tests/fixtures/programs/room_protocol.cjs', str(port)],
                                env=environment(), capture_output=True, text=True,
                                timeout=12, check=False)
        assert result.returncode == 0 and result.stdout.strip() == 'complete', result.stdout + result.stderr


def test_core_room_native_peers(room_binaries, tmp_path):
    processes = []
    with room_server(room_binaries[0], tmp_path) as port:
        def start(name, room=''):
            env = environment()
            env.update(DEWY_MATCH_SERVER=f'ws://127.0.0.1:{port}', SLOPPY_SOFTWARE='1',
                       SLOPPY_THREADS='1', SLOPPY_FRAMES='900', ROLE='join' if room else 'host',
                       NAME=name, ROOM=room, XDG_DATA_HOME=str(tmp_path / name))
            process = subprocess.Popen([room_binaries[1]], env=env, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, text=True)
            processes.append(process)
            return process

        try:
            host = start('host')
            with selectors.DefaultSelector() as selector:
                selector.register(host.stdout, selectors.EVENT_READ)
                assert selector.select(10), 'host did not open its room'
            line = host.stdout.readline().strip()
            assert line.startswith('room '), line
            code = line.split()[1]
            start('alice', code.lower())
            start('bob', f'https://example.com/game/?room={code}&server=unused')
            outputs = [p.communicate(timeout=15) for p in processes]
            for process, (out, err) in zip(processes, outputs, strict=True):
                assert process.returncode == 0, out + err
            assert outputs[0][0].splitlines() == ['host got: hello from alice', 'host got: hello from bob']
            assert outputs[1][0].strip() == 'alice got: hello from host'
            assert outputs[2][0].strip() == 'bob got: hello from host'
        finally:
            for process in processes:
                stop(process)


def test_core_room_fragmented_messages(room_binaries, tmp_path):
    with room_server(room_binaries[0], tmp_path) as port, socket.create_connection(('127.0.0.1', port), timeout=3) as peer:
        peer.sendall(b'GET / HTTP/1.1\r\nHost: localhost\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\nSec-WebSocket-Version: 13\r\n\r\n')
        reply = b''
        while b'\r\n\r\n' not in reply:
            reply += peer.recv(4096)
        assert reply.startswith(b'HTTP/1.1 101'), reply

        def frame(op, payload):
            size = len(payload)
            header = bytes([op, 0x80 | size]) if size < 126 else bytes([op, 0xFE]) + struct.pack('!H', size)
            peer.sendall(header + bytes(4) + payload)

        def receive(size):
            data = b''
            while len(data) < size:
                part = peer.recv(size - len(data))
                assert part, data
                data += part
            return data

        # Pong acknowledges a poll between fragments, without a timed sleep.
        frame(0x01, b'pi')
        frame(0x89, b'')
        assert receive(2) == b'\x8a\x00'
        frame(0x80, b'ng')
        assert receive(6) == b'\x81\x04pong'
        # Each fragment fits, but their assembled message exceeds listen's limit.
        frame(0x01, b'x' * 3000)
        frame(0x89, b'')
        assert receive(2) == b'\x8a\x00'
        frame(0x80, b'x' * 3000)
        assert peer.recv(1) == b''


def test_core_online_starter_room(compiler, room_binaries, tmp_path):
    project = tmp_path / 'race'
    made = subprocess.run([compiler, 'new', project, 'online'], capture_output=True,
                          text=True, timeout=5, check=False, env=environment())
    assert made.returncode == 0, made.stdout + made.stderr
    path = project / 'race.dewy'
    source = path.read_text().replace('1280 720)', '320 200)')
    start, end = source.index('my_pad=()'), source.index('update=(dt:float64)')
    source = source[:start] + 'my_pad=():>Pad=>Pad[x=if me()=?0 1 else -1]\n\n' + source[end:]
    source = source.replace('update=(dt:float64)=>{', 'advance_game=(dt:float64)=>{')
    source += '''
import rtc
rtc.rtc_stun_servers=[]
if env("ROLE")=?"host" invite.start(reliable=false)
let wrote=false
let reported=-1.0
let started=time()
update=(dt:float64)=>{
    advance_game(dt)
    if not wrote and invite.__inv_room_state=?"open" {
        printl("room {invite.room_code()}") wrote=true
    }
    if mode=?Mode.online and reported<?0.0 and session.tick>?60 and session.confirmed()>?60 {
        if session.desync>=?0 {printl("desync") exit(1)}
        let snapshot=session.__states[60]
        if snapshot.players[0].pos not=?vec2(748 360) or snapshot.players[1].pos not=?vec2(532 360) {
            printl("wrong movement: {to_json(snapshot)}") exit(3)
        }
        printl("state {to_json(snapshot)}")
        reported=time()
    }
    if reported>?0.0 and time()-reported>?0.25 quit()
    if time()-started>?10.0 {printl("timeout") exit(2)}
}
'''
    path.write_text(source)
    binary = project / 'main'
    build(compiler, path, binary, room_binaries[2])
    processes = []
    with room_server(room_binaries[0], tmp_path) as port:
        def start_peer(role, room=''):
            env = environment()
            env.update(DEWY_MATCH_SERVER=f'ws://127.0.0.1:{port}', SLOPPY_SOFTWARE='1',
                       SLOPPY_THREADS='1', SLOPPY_FRAMES='900', ROLE=role,
                       ROOM=room, XDG_DATA_HOME=str(tmp_path / role))
            process = subprocess.Popen([binary], env=env, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, text=True)
            processes.append(process)
            return process

        try:
            host = start_peer('host')
            with selectors.DefaultSelector() as selector:
                selector.register(host.stdout, selectors.EVENT_READ)
                assert selector.select(10), 'starter host did not open a room'
            line = host.stdout.readline().strip()
            assert line.startswith('room '), line
            start_peer('guest', line.split()[1])
            outputs = [p.communicate(timeout=15) for p in processes]
            for process, (out, err) in zip(processes, outputs, strict=True):
                assert process.returncode == 0, out + err
            assert outputs[0][0].startswith('state '), outputs
            assert outputs[0][0] == outputs[1][0], outputs
        finally:
            for process in processes:
                stop(process)
