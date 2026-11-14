"""Tasks start, wait and end on the machine running the tests (the CI host-smoke job's Windows,
macOS and arm64 Linux runners, as well as x86-64 Linux): many short groups reuse task slots,
whose stacks are only given back once their threads have ended, and tasks hand values to each
other through channels, waking each other on every host's wait (futex, __ulock, WaitOnAddress)."""
import subprocess
import sys

from tests.support import compiler  # noqa: F401 (fixture)

CHURN = '''main = () => {
    let total = atomic(0)
    loop round in [0..300) {
        concurrent {
            loop x in [0..8) spawn total.add(1)
        }
    }
    printl(total.load)
}
'''

PING_PONG = '''$runtime_checks
bounce = (inbox:Channel<int64> outbox:Channel<int64> rounds:int64):>int64 | Closed<int64> | Unsent<int64> | Canceled => {
    let last:int64 = 0
    loop k in [0..rounds) {
        last = inbox.receive or_throw
        outbox.send(last + 1) or_throw
    }
    last
}
main = ():>void | Closed<int64> | Unsent<int64> | Canceled | OutOfMemory => {
    let a = channel<int64>(1)
    let b = channel<int64>(1)
    a.send(0) or_throw
    concurrent {
        let left = spawn bounce(a b 2000)
        let right = spawn bounce(b a 2000)
    }
    printl"{left or_throw} {right or_throw} {a.receive or_throw}"
}
'''


def run(compiler, tmp_path, source):
    (tmp_path / 'main.dewy').write_text(source)
    binary = tmp_path / ('main.exe' if sys.platform == 'win32' else 'main')
    built = subprocess.run([compiler, 'build', tmp_path / 'main.dewy', '-o', binary], capture_output=True,
                           text=True, timeout=300, cwd=tmp_path)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, errors='replace', timeout=120, cwd=tmp_path)
    return ran.returncode, ran.stdout.replace('\r\n', '\n'), ran.stderr


def test_short_task_groups_reuse_slots(compiler, tmp_path):
    for _ in range(3):
        status, out, err = run(compiler, tmp_path, CHURN)
        assert (status, out) == (0, '2400\n'), err[-2000:]


def test_tasks_wake_each_other_through_channels(compiler, tmp_path):
    status, out, err = run(compiler, tmp_path, PING_PONG)
    assert (status, out) == (0, '3998 3999 4000\n'), err[-2000:]
