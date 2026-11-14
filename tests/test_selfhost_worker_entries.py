"""Worker policy and pipe reads preserve partial chunks, EOF and error behavior across twins."""
import sys
import pytest
from tests.selfhost_narrow import compare_narrow
from tests.support import compiler  # noqa: F401

SERVICES = '''struct ParIn:
    b: u8[]
    i = 0
'''
DRIVER = r'''main = ():
    print("workers:{emit_workers()}")
    assert(par_read(-1).len() == 0)
    fds: i32[] = [-1, -1]
    assert(syscall(293, data(fds), 0) == 0)
    pid = syscall(57)
    assert(pid >= 0)
    if pid == 0:
        syscall(3, int(fds[0]))
        payload = fill(u8(97), 600017)
        __write_fd(int(fds[1]), data(payload), payload.len())
        syscall(3, int(fds[1]))
        syscall(60, 0)
    syscall(3, int(fds[1]))
    bytes = par_read(int(fds[0])); syscall(3, int(fds[0]))
    status = [0]; assert(syscall(61, pid, data(status), 0, 0) == pid and status[0] == 0)
    assert(bytes.len() == 600017 and bytes[0] == 97 and bytes[600016] == 97)
    loop b in bytes: assert(b == 97)
    print("ok")
'''

@pytest.mark.skipif(sys.platform != 'linux', reason='Linux pipe/fork syscall protocol')
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
@pytest.mark.parametrize('workers', ['1', '3', '-2', 'invalid'])
def test_worker_entries_twins(compiler, tmp_path, monkeypatch, release, workers):
    monkeypatch.setenv('DEWY_EMIT_WORKERS', workers)
    out = compare_narrow(compiler, tmp_path, release, ('worker_entries',), DRIVER,
                         doubles={'services.jo': SERVICES}, services=('par',))
    assert out.endswith(b'ok\n')
    if workers != 'invalid': assert out.startswith(f'workers:{workers}\n'.encode())
