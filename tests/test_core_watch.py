"""Exercise Dewy edit/reload behavior through the inherited native watch loop."""
import codecs
import contextlib
import os
import queue
import re
import signal
import subprocess
import threading
import time
from pathlib import Path

import pytest


def patience(seconds):
    """The limit for a wait that ends as soon as its event arrives: it bounds only a hang.
    A shared machine's load stretches every rebuild, so the limit grows with the load per CPU."""
    try:
        load = os.getloadavg()[0] / (os.cpu_count() or 1)
    except (AttributeError, OSError):
        load = 0.0
    return seconds * (1 + max(load, 0.0))


class Watch:
    def __init__(self, compiler, source, *, game=False, options=None, filters=()):
        env = {k: v for k, v in os.environ.items() if not k.startswith('DEWY_')}
        env.update(DEWY_SOFTWARE='1', DEWY_FRAMES='1000000', DEWY_EMIT_WORKERS='1')
        if game:
            env['DEWY_SCREENSHOT'] = str(source.parent / 'unused.png')
        command = [compiler, *(options or ['watch']), source, *filters]
        self.process = subprocess.Popen(command, cwd=source.parent, env=env,
                                        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.STDOUT, start_new_session=os.name != 'nt')
        self.output = ''
        self.position = 0
        self.chunks = queue.Queue()
        self.decoder = codecs.getincrementaldecoder('utf-8')(errors='replace')
        self.reader = threading.Thread(target=self.read_output, daemon=True)
        self.reader.start()

    def read_output(self):
        # Windows select() cannot wait for subprocess pipes. One reader works
        # on all native hosts and keeps draining while tests save source files.
        try:
            while data := self.process.stdout.read1(16384):
                self.chunks.put(data)
        except OSError as error:
            self.chunks.put(error)
        finally:
            self.chunks.put(b'')

    def expect(self, pattern, timeout=20):
        end = time.monotonic() + patience(timeout)
        while True:
            found = re.search(pattern, self.output[self.position:])
            if found:
                self.position += found.end()
                return found
            remaining = end - time.monotonic()
            assert remaining > 0, f'Expected {pattern!r}:\n{self.output}'
            try:
                data = self.chunks.get(timeout=remaining)
            except queue.Empty:
                pytest.fail(f'Expected {pattern!r}:\n{self.output}')
            if isinstance(data, OSError):
                pytest.fail(f'Cannot read watcher output: {data}\n{self.output}')
            assert data, f'Watcher ended while waiting for {pattern!r}:\n{self.output}'
            self.output += self.decoder.decode(data)

    def close(self):
        try:
            if self.process.poll() is None:
                self.process.stdin.write(b'q\n')
                self.process.stdin.flush()
            self.process.wait(timeout=patience(5))
        except (OSError, subprocess.TimeoutExpired):
            if self.process.poll() is None:
                if os.name == 'nt':
                    subprocess.run(['taskkill', '/PID', str(self.process.pid), '/T', '/F'],
                                   capture_output=True, timeout=5, check=False)
                else:
                    os.killpg(self.process.pid, signal.SIGKILL)
            self.process.wait(timeout=5)
        finally:
            with contextlib.suppress(OSError):
                self.process.stdin.close()
            self.reader.join(timeout=5)
            assert not self.reader.is_alive(), 'watcher left an output pipe open after shutdown'
            self.process.stdout.close()


def save(path, text):
    temporary = path.with_name('.' + path.name + '.tmp')
    temporary.write_text(text)
    temporary.replace(path)


@pytest.fixture(scope='module')
def compiler():
    value = os.environ.get('DEWY_CORE_COMPILER')
    if not value:
        pytest.skip('set DEWY_CORE_COMPILER for watch tests')
    return Path(value).resolve(strict=True)


def test_core_watch_program(compiler, tmp_path):
    source = tmp_path / 'main.dewy'
    save(source, 'main=():>void=>printl"first version"')
    watcher = Watch(compiler, source)
    try:
        watcher.expect('first version')
        save(source, 'main=():>void=>printl"second version"')
        watcher.expect('second version')
    finally:
        watcher.close()


@pytest.mark.parametrize('flags', [[], ['--release']])
def test_core_watch_tests(compiler, tmp_path, flags):
    source = tmp_path / 'tests.dewy'
    helper = tmp_path / 'helper.dewy'
    program = '''from p"helper.dewy" import answer
let count=0
main=()=>panic("must not run main")
update=(dt:float64):>void=>panic("must not update")
draw=():>void=>panic("must not draw")
$test
selected_answer = () => {
    count+=1
    $expect count =? 1
    $expect answer() =? 42
}
$test
excluded = () => panic("must not run excluded test")
$runtime_checks
'''
    save(source, program)
    save(helper, 'answer=()=>42')
    watcher = Watch(compiler, source, options=['test', '--watch', *flags], filters=['selected'])
    try:
        watcher.expect('saving a file reruns tests')
        watcher.expect(r'1 passed \(1 not run')
        save(helper, 'answer=()=>43')
        watcher.expect('1 failed, 0 passed')
        save(helper, 'answer=()=>missing_answer')
        watcher.expect("unknown name 'missing_answer'")
        watcher.expect('waiting for changes')
        save(helper, 'answer=()=>42')
        watcher.expect(r'1 passed \(1 not run')
        save(source, program + '\n$test\nselected_again = () => $expect count =? 0\n')
        watcher.expect(r'2 passed \(1 not run')
        watcher.process.stdin.write(b'r\n')
        watcher.process.stdin.flush()
        watcher.expect(r'2 passed \(1 not run')
    finally:
        watcher.close()


@pytest.mark.parametrize('stop', [
    'quit',
    pytest.param('interrupt', marks=pytest.mark.skipif(os.name == 'nt', reason='POSIX signal')),
    'terminate',
])
def test_core_watch_tests_cancel_child(compiler, tmp_path, stop):
    helper = tmp_path / 'process.jo'
    save(helper, '''pid = () -> int:
    when TARGET == "windows": return int(GetCurrentProcessId())
    else: return syscall(39)
''')
    source = tmp_path / 'tests.dewy'
    save(source, '''from p"process.jo" import pid
$test
waiting = () => {
    write_text("child.pid" "{pid()}")
    loop true { sleep(50ms); }
}
''')

    def running(pid):
        if os.name == 'nt':
            import ctypes
            from ctypes import wintypes
            kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            kernel.OpenProcess.restype = wintypes.HANDLE
            kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
            kernel.WaitForSingleObject.restype = wintypes.DWORD
            kernel.CloseHandle.argtypes = [wintypes.HANDLE]
            handle = kernel.OpenProcess(0x100000, False, pid)  # SYNCHRONIZE
            if not handle:
                return False
            try:
                return kernel.WaitForSingleObject(handle, 0) == 258  # WAIT_TIMEOUT
            finally:
                kernel.CloseHandle(handle)
        status = subprocess.run(['ps', '-p', str(pid), '-o', 'stat='], capture_output=True,
                                text=True, timeout=5, check=False).stdout.strip()
        return bool(status) and not status.startswith('Z')

    watcher = Watch(compiler, source, options=['test', '--watch'])
    child = None
    try:
        # (what a test prints is shown only when it fails: its pid file says it is waiting)
        deadline = time.monotonic() + patience(20)
        while not (tmp_path / 'child.pid').exists() or not (tmp_path / 'child.pid').read_text():
            assert time.monotonic() < deadline, 'the test did not start'
            time.sleep(0.05)
        child = int((tmp_path / 'child.pid').read_text())
        assert running(child)
        if stop == 'quit':
            watcher.process.stdin.write(b'q\n')
            watcher.process.stdin.flush()
        elif stop == 'interrupt':
            watcher.process.send_signal(signal.SIGINT)
        else:
            watcher.process.terminate()
        watcher.process.wait(timeout=patience(5))
        deadline = time.monotonic() + patience(3)
        while running(child) and time.monotonic() < deadline:
            time.sleep(0.02)
        assert not running(child), 'quitting test watch left its active test running'
    finally:
        if child is not None and running(child):
            if os.name == 'nt':
                subprocess.run(['taskkill', '/PID', str(child), '/T', '/F'],
                               capture_output=True, timeout=5, check=False)
            else:
                with contextlib.suppress(ProcessLookupError):
                    os.kill(child, signal.SIGKILL)
        watcher.close()


GAME = '''from p"helper.dewy" import label
State:type=[count:int64]
let state=State[0]
let values:array<int64>=[20 22]
pick=()=>values[1]
update=(dt:float64):>void=>{
    state.count+=1
    if frame_number()%10 =? 0 printl"tick count={state.count} label={label()} value={pick()}"
    sleep(5ms);
}
draw=():>void=>clear(BLACK)
$runtime_checks
'''


def test_core_watch_game(compiler, tmp_path):
    source = tmp_path / 'game.dewy'
    helper = tmp_path / 'helper.dewy'
    save(source, GAME)
    save(helper, 'label=()=>"one"')
    watcher = Watch(compiler, source, game=True)
    try:
        before = int(watcher.expect(r'tick count=(\d+) label=one value=22').group(1))
        save(helper, 'label=()=>"two"')
        watcher.expect(r'reloaded in \d+ ms:')
        after = int(watcher.expect(r'tick count=(\d+) label=two value=22').group(1))
        assert after > before, watcher.output
        save(helper, 'label=()=>missing')
        watcher.expect("unknown name 'missing'")
        watcher.expect('keeps running the last version')
        assert int(watcher.expect(r'tick count=(\d+) label=two value=22').group(1)) > after
        save(helper, 'label=()=>"three"')
        watcher.expect(r'reloaded in \d+ ms:')
        before = int(watcher.expect(r'tick count=(\d+) label=three value=22').group(1))
        # Changing a record layout preserves the game's live count; new fields
        # receive their default instead of restarting its global initializer.
        save(source, GAME.replace('count:int64]', 'count:int64 health:int64=100]')
             .replace('value={pick()}', 'value={pick()} health={state.health}'))
        watcher.expect(r'reloaded in \d+ ms:')
        after = int(watcher.expect(r'tick count=(\d+) label=three value=22 health=100').group(1))
        assert after > before, watcher.output
    finally:
        watcher.close()


def test_core_watch_exact_division(compiler, tmp_path):
    source = tmp_path / 'game.dewy'
    helper = tmp_path / 'helper.dewy'
    save(source, GAME)
    save(helper, 'label=()=>"{float64(1.0)/2}"')
    watcher = Watch(compiler, source, game=True)
    try:
        before = int(watcher.expect(r'tick count=(\d+) label=0\.5 value=22').group(1))
        save(helper, 'label=()=>"{1/2}"\n$runtime_checks')
        watcher.expect(r'reloaded in \d+ ms:')
        after = int(watcher.expect(r'tick count=(\d+) label=1/2 value=22').group(1))
        assert after > before, watcher.output
        save(helper, 'label=()=>"{float64(1.0)/2}"')
        watcher.expect(r'reloaded in \d+ ms:')
        final = int(watcher.expect(r'tick count=(\d+) label=0\.5 value=22').group(1))
        assert final > after, watcher.output
    finally:
        watcher.close()


def test_core_watch_function_asset(compiler, tmp_path):
    source = tmp_path / 'main.dewy'
    asset = tmp_path / 'label.txt'
    save(asset, 'first asset')
    save(source, 'main=()=>{let bytes=$include_bytes(p"label.txt") printl(str_from_bytes(bytes))}')
    watcher = Watch(compiler, source)
    try:
        watcher.expect('first asset')
        save(asset, 'second asset')
        watcher.expect('second asset')
    finally:
        watcher.close()


def test_core_watch_startup_asset_write(compiler, tmp_path):
    # The program can update a watched input immediately on startup. Several
    # input directories make installing watches after launch especially racy.
    declarations = []
    for index in range(32):
        directory = tmp_path / f'input{index}'
        directory.mkdir()
        save(directory / 'value.txt', 'first')
        declarations.append(f'let input{index}=$include_bytes(p"input{index}/value.txt")')
    source = tmp_path / 'main.dewy'
    save(source, '\n'.join(declarations) + '''
main=():>void=>{
    let label=str_from_bytes(input31)
    if label =? "first" {write_text("input31/value.txt" "second");}
    printl(label)
}
''')
    watcher = Watch(compiler, source)
    try:
        # The watcher may stop the first run between its write and stdout flush.
        # Recovery to the new embedded value is the behavior under test.
        watcher.expect('second')
    finally:
        watcher.close()


@pytest.mark.parametrize('kind', ['asset', 'import'])
@pytest.mark.parametrize('directory_exists', [False, True], ids=['missing-directory', 'existing-directory'])
@pytest.mark.parametrize('testing', [False, True], ids=['program-watch', 'test-watch'])
def test_core_watch_missing_input(compiler, tmp_path, kind, directory_exists, testing):
    directory = tmp_path / 'inputs' / 'nested'
    if directory_exists:
        directory.mkdir(parents=True)
    source = tmp_path / 'main.dewy'
    if kind == 'asset':
        save(source, 'main=()=>printl(str_from_bytes($include_bytes(p"inputs/nested/value.txt")))')
        dependency = directory / 'value.txt'
        contents = 'recovered input'
    else:
        save(source, 'from p"inputs/nested/helper.dewy" import label\nmain=()=>printl(label())')
        dependency = directory / 'helper.dewy'
        contents = 'label=()=>"recovered input"'
    if testing:
        # (a failed test shows what it printed)
        save(source, source.read_text().replace('main=()=>', '$test\ndependency=()=>{') + '\n$fail}')
    watcher = Watch(compiler, source, options=['test', '--watch'] if testing else ['watch'])
    try:
        watcher.expect('waiting for changes')
        directory.mkdir(parents=True, exist_ok=True)
        save(dependency, contents)
        watcher.expect('recovered input')
    finally:
        watcher.close()


def test_core_watch_named_language_fallback(compiler, tmp_path):
    source = tmp_path / 'main.dewy'
    jo = tmp_path / 'helper.jo'
    dewy = tmp_path / 'helper.dewy'
    save(source, 'from helper import label\nmain=()=>printl(label())')
    watcher = Watch(compiler, source)
    try:
        watcher.expect('waiting for changes')
        save(jo, 'label = (): "implementation fallback"')
        watcher.expect('implementation fallback')
        save(dewy, 'label=()=>"preferred Dewy module"')
        watcher.expect('preferred Dewy module')
        dewy.unlink()
        watcher.expect('implementation fallback')
    finally:
        watcher.close()


def test_core_watch_new_missing_asset_preserves_game(compiler, tmp_path):
    source = tmp_path / 'game.dewy'
    program = '''let label="original"
let count:int64=0
update=(dt:float64):>void=>{count+=1 if frame_number()%10 =? 0 printl"tick {count} {label}" sleep(5ms);}
draw=():>void=>clear(BLACK)
'''
    save(source, program)
    watcher = Watch(compiler, source, game=True)
    try:
        before = int(watcher.expect(r'tick (\d+) original').group(1))
        save(source, program.replace('"original"', 'str_from_bytes($include_bytes(p"new/assets/label.txt"))'))
        watcher.expect('keeps running the last version')
        after = int(watcher.expect(r'tick (\d+) original').group(1))
        assert after > before, watcher.output
        directory = tmp_path / 'new' / 'assets'
        directory.mkdir(parents=True)
        save(directory / 'label.txt', 'restored')
        watcher.expect(r'reloaded in \d+ ms:')
        assert int(watcher.expect(r'tick (\d+) restored').group(1)) > after, watcher.output
    finally:
        watcher.close()


@pytest.mark.parametrize('imported', [False, True], ids=['local', 'imported'])
@pytest.mark.parametrize('indirect', ['direct', 'helper', 'embedded-helper'])
def test_core_watch_derived_asset(compiler, tmp_path, imported, indirect):
    source = tmp_path / 'game.dewy'
    asset_dir = tmp_path / 'assets' if imported else tmp_path
    asset_dir.mkdir(exist_ok=True)
    asset = asset_dir / 'label.txt'
    save(asset, 'one')
    declaration = '$include_bytes(p"label.txt") as content\n'
    if indirect != 'direct':
        value = 'content'
        if indirect == 'embedded-helper':
            declaration = ''
            value = '$include_bytes(p"label.txt")'
        declaration += (f'read=(depth:int64):>string=>if depth >? 0 again(depth-1) else str_from_bytes({value})\n'
                        'again=(depth:int64):>string=>read(depth)\n')
    if imported:
        save(asset_dir / 'content.dewy', declaration)
        declaration = 'from p"assets/content.dewy" import ' + ('read' if indirect != 'direct' else 'content') + '\n'
    decoded = 'read(1)' if indirect != 'direct' else 'str_from_bytes(content)'
    save(source, declaration + f'let decoded={decoded}\n' + '''
let label="asset={decoded}"
let count:int64=0
update=(dt:float64):>void=>{count+=1 if frame_number()%10 =? 0 printl"tick {count} {label} allocations={alloc_count()}" sleep(5ms);}
draw=():>void=>clear(BLACK)
''')
    watcher = Watch(compiler, source, game=True)
    try:
        before = int(watcher.expect(r'tick (\d+) asset=one').group(1))
        save(asset, 'two')
        watcher.expect(r'reloaded in \d+ ms:')
        match = watcher.expect(r'tick (\d+) asset=two allocations=(\d+)')
        after, allocations = map(int, match.groups())
        assert after > before, watcher.output
        for label in ['three', 'four']:
            save(asset, label)
            watcher.expect(r'reloaded in \d+ ms:')
            match = watcher.expect(r'tick (\d+) asset=' + label + r' allocations=(\d+)')
            count, live = map(int, match.groups())
            assert count > after and live == allocations, watcher.output
            after = count
        asset.unlink()
        watcher.expect('cannot read')
        watcher.expect('keeps running the last version')
        assert int(watcher.expect(r'tick (\d+) asset=four').group(1)) > after
        save(asset, 'restored')
        watcher.expect(r'reloaded in \d+ ms:')
        assert int(watcher.expect(r'tick (\d+) asset=restored').group(1)) > after
    finally:
        watcher.close()


@pytest.mark.parametrize("generic", [False, True])
def test_core_watch_closure_asset_keeps_capture(compiler, tmp_path, generic):
    source = tmp_path / 'game.dewy'
    asset = tmp_path / 'label.txt'
    save(asset, 'one')
    program = '''make=()=>{let count:int64=0
return ($capture count)=>{count+=1 return "{count}:{str_from_bytes($include_bytes(p\"label.txt\"))}"}}
let next=make()
update=(dt:float64):>void=>{if frame_number()%10 =? 0 printl(next()) sleep(5ms);}
draw=():>void=>clear(BLACK)
'''
    if generic:
        program = program.replace('return ($capture count)=>', 'return <T>(unused:T $capture count)=>').replace('next()', 'next(0)')
    save(source, program)
    watcher = Watch(compiler, source, game=True)
    try:
        before = int(watcher.expect(r'(\d+):one').group(1))
        save(asset, 'two')
        watcher.expect(r'reloaded in \d+ ms:')
        after = int(watcher.expect(r'(\d+):two').group(1))
        assert after > before, watcher.output
    finally:
        watcher.close()


def test_core_watch_shader(compiler, tmp_path):
    """Reload both GPU source and software shader functions without resetting play."""
    shader = tmp_path / 'shaders.dewy'

    def shading(color):
        return '''V:type=[pos:vec2]
U:type=[scale:float32]
Out:type=[pos:vec4]
vs=(v:V u:U):>Out=>Out(vec4(v.pos*u.scale 0 1))
fs=(v:Out u:U):>vec4=>''' + color + '\n'

    save(shader, shading('vec4(1 0 0 1)'))
    source = tmp_path / 'game.dewy'
    save(source, '''from p"shaders.dewy" import V, U, vs, fs
let shading=shader(@vs @fs)
let program=make_shader(shading)
let triangle=mesh([V(vec2(-1 -1)) V(vec2(3 -1)) V(vec2(-1 3))])
let count:int64=0
main=():>void=>window("Shader reload" 64 64)
update=(dt:float64):>void=>{count+=1 sleep(5ms);}
draw=():>void=>{
clear(BLACK) program.draw(triangle U(1))
if count%10 =? 0 {
let pixels=screenshot().pixels
let index=(32*64+32)*4
printl"tick {count} program={program.prog} color={pixels[index]},{pixels[index+1]},{pixels[index+2]}"
}
}
$runtime_checks
''')
    watcher = Watch(compiler, source, game=True)
    try:
        before = watcher.expect(r'tick (\d+) program=(\d+) color=255,0,0')
        for color, pixel in [('vec4(0 0 1 1)', '0,0,255'), ('vec4(0 1 0 1)', '0,255,0')]:
            save(shader, shading(color))
            watcher.expect(r'reloaded in \d+ ms:')
            after = watcher.expect(r'tick (\d+) program=(\d+) color=' + pixel)
            assert int(after[1]) > int(before[1]), watcher.output
            assert after[2] != before[2], 'The generated GPU program must also be recreated'
            before = after
    finally:
        watcher.close()


def test_core_watch_generic_closure_layout_keeps_old_cleanup(compiler, tmp_path):
    """A saved concrete selection keeps copy/drop code for its old environment."""
    source = tmp_path / 'game.dewy'
    program = '''make=()=>{let count=0 let word="kept"
return <T>(unused:T $capture count)=>{count+=1; "{word}:{count}"}}
let next=make()<int64>
update=(dt:float64):>void=>{
next(0);
if frame_number()%10 =? 0 {let copy=@next printl(copy(0))}
sleep(5ms);
}
draw=():>void=>clear(BLACK)
'''
    save(source, program)
    watcher = Watch(compiler, source, game=True)
    try:
        before = int(watcher.expect(r'kept:(\d+)').group(1))
        # Same lambda source identity, different capture-discovery order:
        # old layout [count, word], new layout [word, count]. The existing
        # concrete function value still owns the old environment and headers.
        save(source, program.replace('count+=1; "{word}:{count}"',
                                     'let label=word count+=1; "{label}:{count}"'))
        watcher.expect(r'reloaded in \d+ ms:')
        after = int(watcher.expect(r'kept:(\d+)').group(1))
        assert after > before, watcher.output
        assert int(watcher.expect(r'kept:(\d+)').group(1)) > after, watcher.output
    finally:
        watcher.close()
