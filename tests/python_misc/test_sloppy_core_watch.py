"""Exercise Dewy edit/reload behavior through the inherited native watch loop."""
import os
import re
import select
import signal
import subprocess
import time
from pathlib import Path

import pytest


class Watch:
    def __init__(self, compiler, source, *, game=False):
        env = {k: v for k, v in os.environ.items() if not k.startswith(('DEWY_', 'SLOPPY_'))}
        if frontend := os.environ.get('DEWY_CORE_FRONTEND'):
            env['DEWY_CORE_FRONTEND'] = frontend
        env.update(SLOPPY_SOFTWARE='1', SLOPPY_FRAMES='1000000', SLOPPY_EMIT_WORKERS='1')
        if game:
            env['SLOPPY_SCREENSHOT'] = str(source.parent / 'unused.png')
        self.process = subprocess.Popen([compiler, 'watch', source], cwd=source.parent, env=env,
                                        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.STDOUT, start_new_session=True)
        self.output = ''
        self.position = 0

    def expect(self, pattern, timeout=10):
        end = time.monotonic() + timeout
        while True:
            found = re.search(pattern, self.output[self.position:])
            if found:
                self.position += found.end()
                return found
            remaining = end - time.monotonic()
            assert remaining > 0, f'Expected {pattern!r}:\n{self.output}'
            ready, _, _ = select.select([self.process.stdout], [], [], remaining)
            assert ready, f'Expected {pattern!r}:\n{self.output}'
            data = os.read(self.process.stdout.fileno(), 16384)
            assert data, f'Watcher ended while waiting for {pattern!r}:\n{self.output}'
            self.output += data.decode(errors='replace')

    def close(self):
        try:
            self.process.stdin.write(b'q\n')
            self.process.stdin.flush()
            self.process.wait(timeout=5)
        except (BrokenPipeError, subprocess.TimeoutExpired):
            os.killpg(self.process.pid, signal.SIGKILL)
            self.process.wait(timeout=5)
        finally:
            self.process.stdin.close()
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


GAME = '''from p"helper.dewy" import label
State:type=[count:int64]
let state=State[0]
let values:array<int64>=[20 22]
pick=()=>values[1]
update=(dt:float64):>void=>{
    state.count+=1
    if frame_number()%10 =? 0 printl"tick count={state.count} label={label()} value={pick()}"
    sleep(0.005)
}
draw=():>void=>clear(BLACK)
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
    save(helper, 'label=()=>"{1.0/2}"')
    watcher = Watch(compiler, source, game=True)
    try:
        before = int(watcher.expect(r'tick count=(\d+) label=0\.5 value=22').group(1))
        save(helper, 'label=()=>"{1/2}"')
        watcher.expect(r'reloaded in \d+ ms:')
        after = int(watcher.expect(r'tick count=(\d+) label=1/2 value=22').group(1))
        assert after > before, watcher.output
        save(helper, 'label=()=>"{1.0/2}"')
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
        watcher.expect('second asset', timeout=3)
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
    if label =? "first" {write_file("input31/value.txt" "second");}
    printl(label)
}
''')
    watcher = Watch(compiler, source)
    try:
        watcher.expect('first')
        watcher.expect('second', timeout=3)
    finally:
        watcher.close()


@pytest.mark.parametrize('kind', ['asset', 'import'])
@pytest.mark.parametrize('directory_exists', [False, True], ids=['missing-directory', 'existing-directory'])
def test_core_watch_missing_input(compiler, tmp_path, kind, directory_exists):
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
    watcher = Watch(compiler, source)
    try:
        watcher.expect('waiting for changes')
        directory.mkdir(parents=True, exist_ok=True)
        save(dependency, contents)
        watcher.expect('recovered input', timeout=3)
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
        watcher.expect('implementation fallback', timeout=3)
        save(dewy, 'label=()=>"preferred Dewy module"')
        watcher.expect('preferred Dewy module', timeout=3)
        dewy.unlink()
        watcher.expect('implementation fallback', timeout=3)
    finally:
        watcher.close()


def test_core_watch_new_missing_asset_preserves_game(compiler, tmp_path):
    source = tmp_path / 'game.dewy'
    program = '''let label="original"
let count:int64=0
update=(dt:float64):>void=>{count+=1 if frame_number()%10 =? 0 printl"tick {count} {label}" sleep(0.005)}
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
let label="asset="+decoded
let count:int64=0
update=(dt:float64):>void=>{count+=1 if frame_number()%10 =? 0 printl"tick {count} {label} allocations={alloc_count()}" sleep(0.005)}
draw=():>void=>clear(BLACK)
''')
    watcher = Watch(compiler, source, game=True)
    try:
        before = int(watcher.expect(r'tick (\d+) asset=one').group(1))
        save(asset, 'two')
        watcher.expect(r'reloaded in \d+ ms:')
        match = watcher.expect(r'tick (\d+) asset=two allocations=(\d+)', timeout=3)
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


def test_core_watch_closure_asset_keeps_capture(compiler, tmp_path):
    source = tmp_path / 'game.dewy'
    asset = tmp_path / 'label.txt'
    save(asset, 'one')
    save(source, '''make=()=>{let count:int64=0
return ()=>{count+=1 return "{count}:{str_from_bytes($include_bytes(p\"label.txt\"))}"}}
let next=make()
update=(dt:float64):>void=>{if frame_number()%10 =? 0 printl(next()) sleep(0.005)}
draw=():>void=>clear(BLACK)
''')
    watcher = Watch(compiler, source, game=True)
    try:
        before = int(watcher.expect(r'(\d+):one').group(1))
        save(asset, 'two')
        watcher.expect(r'reloaded in \d+ ms:')
        after = int(watcher.expect(r'(\d+):two').group(1))
        assert after > before, watcher.output
    finally:
        watcher.close()
