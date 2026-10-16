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
