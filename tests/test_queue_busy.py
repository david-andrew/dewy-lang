"""A non-waiting mpmc attempt that collides with another task mid-operation gives Busy, never
a misleading Full or Empty (lib/std/thread.jo). Collisions depend on timing, so the program
runs a few times until one is seen; every run must deliver each value exactly once."""
import subprocess

from tests.support import compiler  # noqa: F401

PROGRAM = '''$runtime_checks

hammer_send = (q:Mpmc<int64> busy:Atomic<int64> first:int64 n:int64):>void => {
    let sent:int64 = 0
    loop sent <? n {
        let r = q.try_send(first + sent)
        if r is? Unsent<int64> {
            if r.reason is? Busy { busy.add(1); }
        } else { sent += 1 }
    }
}
hammer_receive = (q:Mpmc<int64> busy:Atomic<int64> got:Atomic<int64> sum:Atomic<int64> want:int64):>void => {
    loop got.load() <? want {
        let r = q.try_receive
        if r is? Busy { busy.add(1); }
        else if r is? Empty or r is? Closed or r is? Canceled {}
        else {
            got.add(1);
            sum.add(r);
        }
    }
}
main = () => {
    let q = mpmc<int64>(4)
    let busy = atomic(0)
    let got = atomic(0)
    let sum = atomic(0)
    concurrent {
        spawn hammer_send(q busy 0 20000)
        spawn hammer_send(q busy 20000 20000)
        spawn hammer_receive(q busy got sum 40000)
        spawn hammer_receive(q busy got sum 40000)
    }
    printl"{got.load()} {sum.load()} {busy.load()}"
}

'''


def test_contended_attempts_give_busy(compiler, tmp_path):  # noqa: F811
    source = tmp_path / 'busy.dewy'
    source.write_text(PROGRAM)
    binary = tmp_path / 'busy'
    built = subprocess.run([compiler, 'build', source, '-o', binary], capture_output=True, text=True,
                           timeout=120, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    busy = 0
    for _ in range(5):
        ran = subprocess.run([binary], capture_output=True, text=True, timeout=60, check=False)
        assert ran.returncode == 0, ran.stdout + ran.stderr
        got, total, busy = (int(word) for word in ran.stdout.split())
        assert (got, total) == (40000, sum(range(40000)))
        if busy > 0:
            break
    assert busy > 0, 'no attempt collided in five runs'
