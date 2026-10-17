"""Local game connections: native peers, browser-compatible messages, and final state."""
import json
import os
import selectors
import shutil
import socket
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TEXT = 'Dewy café🙂\0' + 'x' * 200
ECHO = '''import net
payload=():>array<uint8>=>{
    let data:array<uint8>=[]
    loop i in [0..512) {data.push(i as uint8)}
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
            if not k.startswith(('SLOPPY_', 'DEWY_')) and k not in ('HOST', 'JOIN', 'INVITE')}


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
    source = (ROOT / 'examples/sloppy_core/netpong.dewy').read_text()
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
