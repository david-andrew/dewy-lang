"""A queued game handshake must take priority over its first source edit."""
import contextlib
import os
import shlex
import signal

import pytest

from tests.selfhost_lsp_double import leaf_compilers
from tests.support import ROOT, compiler  # noqa: F401
from tests.test_core_watch import Watch, save


PROGRAM = '''main=()=>{
    printl("before window")
    loop not file_exists("release") {sleep(1ms);}
    window("readiness race" 128 128) or_throw
}
make=()=>{let count=0 let word="kept"
return <T>(unused:T $capture count)=>{count+=1; "{word}:{count}"}}
let next=make()<int64>
update=(_dt:float64):>void=>{
    next(0);
    if frame_number()%10 =? 0 {let copy=@next printl(copy(0))}
    sleep(5ms);
}
draw=():>void=>clear(BLACK)
'''


def ready_and_edit(binary, directory):
    directory.mkdir()
    source = directory / 'game.dewy'
    save(source, PROGRAM)
    # Watch deliberately strips DEWY_* from its environment. The wrapper adds
    # tracing and the library path for the independently built twin drivers.
    wrapper = directory / 'logged-watch'
    wrapper.write_text('#!/bin/sh\n'
                       f'DEWY_CORE_LIB={shlex.quote(str(ROOT / "lib"))} '
                       'DEWY_WATCH_LOG=1 DEWY_NO_AUDIO=1 exec '
                       f'{shlex.quote(str(binary))} "$@"\n')
    wrapper.chmod(0o755)
    watcher = Watch(wrapper, source, game=True)
    try:
        watcher.expect('before window')
        # Stop only the controller, before the game opens its window and sends
        # its handshake. Its child keeps running; no scheduling delay is assumed.
        os.kill(watcher.process.pid, signal.SIGSTOP)
        pid, status = os.waitpid(watcher.process.pid, os.WUNTRACED)
        assert pid == watcher.process.pid and os.WIFSTOPPED(status)
        (directory / 'release').touch()
        before = int(watcher.expect(r'kept:(\d+)').group(1))
        save(source, PROGRAM.replace('count+=1; "{word}:{count}"',
                                     'let label=word count+=1; "{label}:{count}"'))
        # Both file and ready events are now pending. An unnecessary restart
        # would discard the captured state instead of patching the old closure.
        os.kill(watcher.process.pid, signal.SIGCONT)
        event = watcher.expect(r'reloaded in \d+ ms:|starting again \(pid')
        assert event.group(0).startswith('reloaded'), watcher.output
        after = int(watcher.expect(r'kept:(\d+)').group(1))
        later = int(watcher.expect(r'kept:(\d+)').group(1))
        assert before < after < later, watcher.output
        return watcher.output.count('before window'), watcher.output.count('reloaded in ')
    finally:
        # Never leave a stopped watcher behind, including an assertion failure.
        with contextlib.suppress(ProcessLookupError):
            os.kill(watcher.process.pid, signal.SIGCONT)
        watcher.close()


@pytest.mark.skipif(os.name == 'nt', reason='POSIX poll ordering; uses SIGSTOP')
def test_watch_drive_pending_readiness_matches_twin(compiler, tmp_path):  # noqa: F811
    dewy, jo = leaf_compilers(compiler, tmp_path, ('watch_drive',))
    assert ready_and_edit(jo, tmp_path / 'jo') == ready_and_edit(dewy, tmp_path / 'dewy') == (1, 1)
