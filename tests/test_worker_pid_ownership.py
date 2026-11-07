"""Exercise the actual cancellation code with recycled PIDs, without OS signals."""
import re
import platform
import subprocess
import sys
import textwrap

import pytest

from tests.support import ROOT, compiler


def function(path, name):
    text = (ROOT / path).read_text()
    return re.search(rf'(?m)^{name} = .*?(?=^\w|\Z)', text, re.S).group()


@pytest.mark.parametrize('emitted', [False, True])
@pytest.mark.skipif(not sys.platform.startswith('linux') or platform.machine().lower() not in ('x86_64', 'amd64'),
                    reason='partitioned checking only runs on x86-64 Linux')
def test_worker_cancel_retires_children(compiler, tmp_path, emitted):
    source = function('compiler/pcheck.jo', 'pc_cancel')
    if 'pc_reap(' in source:
        source += function('compiler/pcheck.jo', 'pc_reap')
    fused = (ROOT / 'compiler/fused.jo').read_text()
    start = fused.index('            syscall(3, fds[w])\n')
    end = fused.index('            if st[0] & 0xFFFF', start)
    source += 'reap_emission = (w: int):\n' + textwrap.indent(
        textwrap.dedent(fused[start:end]), '    ')
    # All process operations are simulated, including an immediate PID reuse
    # after wait. A second cancel must neither signal nor close retired handles.
    source = source.replace('syscall(', 'fake_syscall(').replace('data(st)', '0')
    source = '''pc_child = -1
pc_active = true
pc_pids: int[] = [101, -1, 102]
pc_fds: int[] = [201, -1, 202]
pids: int[] = [101, -1, 102]
fds: int[] = [201, -1, 202]
live: {int: bool} = {101: true, 102: true}
closed: {int: bool}
signals = 0
interrupted = false
fake_syscall = (op: int, a: int, b: int = 0, c: int = 0, d: int = 0) -> int:
    if op == 62:
        if not (live.get(a) ?? false): exit(41)
        signals += 1
    if op == 3:
        if closed.has(a): exit(42)
        closed[a] = true
    if op == 61:
        if not interrupted:
            interrupted = true
            return -4
        if not (live.get(a) ?? false): return -10
        live[a] = false
        return a
    0
''' + source + f'''
main = ():
    {'reap_emission(0)' if emitted else 'pass'}
    pc_cancel()
    pc_cancel()
    if signals != {1 if emitted else 2} or live[101] or live[102]: exit(43)
    print("retired")
'''
    path = tmp_path / 'cancel.jo'
    path.write_text(source)
    built = subprocess.run([compiler, 'build', path, '-o', tmp_path / 'cancel'],
                           capture_output=True, text=True, timeout=60)
    assert built.returncode == 0, built.stderr
    run = subprocess.run([tmp_path / 'cancel'], capture_output=True, text=True, timeout=10)
    assert run.returncode == 0, (run.returncode, run.stderr)
    assert run.stdout.strip() == 'retired'


@pytest.mark.parametrize('wait_result', [0, 101, -10])
def test_watch_interrupt_checks_child_ownership(compiler, tmp_path, wait_result):
    text = (ROOT / 'lib/std/watch.jo').read_text()
    start = text.index('    __watch_test_interrupt = ')
    end = text.index('\n__watch_on', start)
    handler = textwrap.dedent(text[start:end]).replace('syscall(', 'fake_syscall(')
    handler = handler.replace('&status', '0').replace('__exit(', 'finish(')
    source = f'''pid_slot = [101]
__watch_test_pid: *int
signals = 0
fake_syscall = (op: int, a: int, b: int = 0, c: int = 0, d: int = 0) -> int:
    if op == 61: return {wait_result}
    if op == 62:
        if {wait_result} != 0 or a != -101: exit(41)
        signals += 1
    0
finish = (status: int):
    if status != 143 or signals != {int(wait_result == 0)}: exit(42)
    exit(0)
{handler}
main = ():
    __watch_test_pid = data(pid_slot)
    __watch_test_interrupt(15, null, null)
'''
    path = tmp_path / 'watch.jo'
    path.write_text(source)
    built = subprocess.run([compiler, 'build', path, '-o', tmp_path / 'watch'],
                           capture_output=True, text=True, timeout=60)
    assert built.returncode == 0, built.stderr
    run = subprocess.run([tmp_path / 'watch'], capture_output=True, text=True, timeout=10)
    assert run.returncode == 0, (run.returncode, run.stderr)
