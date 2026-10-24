"""Channel waits the deadlock analysis cannot decide are warnings, never errors
(compiler/deadlock.jo); ordinary channel programs get none."""
import subprocess

from tests.support import compiler  # noqa: F401


def diagnostics(compiler, tmp_path, program):  # noqa: F811
    source = tmp_path / 'main.dewy'
    source.write_text(program)
    checked = subprocess.run([compiler, 'check', source], capture_output=True, text=True, timeout=60, check=False)
    assert checked.returncode == 0, checked.stdout + checked.stderr
    return [line for line in checked.stderr.splitlines() if 'warning:' in line]


PING = '''ping = (out:Channel<int64> back:Channel<int64> n:int64):>void | Closed | Canceled => {
    loop i in [0..n) { out.send(i) or_throw }
    loop i in [0..n) { back.receive() or_throw; }
}
main = () => {
    let a = channel<int64>(4)
    let b = channel<int64>(4)
    concurrent {
        spawn ping(a b 3)
        spawn ping(b a 3)
    }
}
'''

PIPELINE = '''produce = (out:Channel<int64> n:int64):>void | Closed | Canceled => {
    loop i in [0..n) { out.send(i) or_throw }
    out.close()
}
square = (input:Channel<int64> out:Channel<int64>):>void | Closed | Canceled => {
    loop true {
        let n = input.receive() or_throw
        out.send(n * n) or_throw
    }
    out.close()
}
main = () => {
    let numbers = channel<int64>(2)
    let squares = channel<int64>(2)
    let total:int64 = 0
    concurrent {
        spawn produce(numbers 100)
        spawn square(numbers squares)
        loop true {
            let s = squares.receive()
            if s is? Closed break
            if s is? int64 { total += s }
        }
    }
    printl"{total}"
}
'''

WORKERS = '''work = (jobs:Channel<int64> results:Channel<int64>):>void | Closed | Canceled => {
    loop true {
        let j = jobs.receive() or_throw
        results.send(j * 2) or_throw
    }
}
main = () => {
    let jobs = channel<int64>(4)
    let results = channel<int64>(64)
    concurrent {
        loop w in [0..4) { spawn work(jobs results) }
        loop i in [0..50) { jobs.send(i) or_throw }
        jobs.close()
        loop i in [0..50) { results.receive() or_throw; }
    }
}
'''

REQUEST_REPLY = '''serve = (requests:Channel<int64> replies:Channel<int64>):>void | Closed | Canceled => {
    loop true {
        let r = requests.receive() or_throw
        replies.send(r + 1) or_throw
    }
}
main = () => {
    let requests = channel<int64>(1)
    let replies = channel<int64>(1)
    concurrent {
        spawn serve(requests replies)
        loop i in [0..10) {
            requests.send(i) or_throw
            printl"{replies.receive()}"
        }
        requests.close()
    }
}
'''


def test_counts_that_are_not_literal_warn(compiler, tmp_path):  # noqa: F811
    found = diagnostics(compiler, tmp_path, PING)
    assert len(found) == 1 and ':2:24:' in found[0] and "may wait to send into 'a'" in found[0] and 'cannot tell' in found[0], found


def test_a_capacity_that_is_not_literal_warns(compiler, tmp_path):  # noqa: F811
    program = PING.replace('channel<int64>(4)\n    let b', 'channel<int64>(size)\n    let b').replace('main = () => {\n', 'main = () => {\n    let size = 4\n')
    found = diagnostics(compiler, tmp_path, program.replace(' n:int64', '').replace('[0..n)', '[0..10)').replace(' 3)', ')'))
    assert len(found) == 1 and "may wait to send into 'a'" in found[0], found


def test_pipelines_workers_and_request_reply_are_quiet(compiler, tmp_path):  # noqa: F811
    for program in (PIPELINE, WORKERS, REQUEST_REPLY):
        assert diagnostics(compiler, tmp_path, program) == [], program


def test_taking_turns_is_quiet(compiler, tmp_path):  # noqa: F811
    program = PING.replace('    loop i in [0..n) { out.send(i) or_throw }\n    loop i in [0..n) { back.receive() or_throw; }\n',
                           '    loop i in [0..n) {\n        out.send(i) or_throw\n        back.receive() or_throw;\n    }\n')
    assert diagnostics(compiler, tmp_path, program) == []
