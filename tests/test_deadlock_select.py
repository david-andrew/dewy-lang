"""A `select` or `merged` receive in a loop consumes from each channel it lists
(compiler/deadlock_channel_walk.dewy, event 8): a producer feeding such a loop is not warned
about, and a channel nothing receives from still is."""
import subprocess

from tests.support import compiler  # noqa: F401


def diagnostics(compiler, tmp_path, program):  # noqa: F811
    source = tmp_path / 'main.dewy'
    source.write_text(program + '\n$runtime_checks\n')
    checked = subprocess.run([compiler, 'check', source], capture_output=True, text=True, timeout=60, check=False)
    assert checked.returncode == 0, checked.stdout + checked.stderr
    return [line for line in checked.stderr.splitlines() if 'warning:' in line]


PRODUCE = '''produce = (out:Channel<int64> n:int64):>void | Unsent<int64> | Canceled => {
    loop i in [0..n) { out.send(i) or_throw }
    out.close()
}
'''

SELECT = PRODUCE + '''main = () => {
    let a = channel<int64>(1)
    let b = channel<int64>(1)
    let total:int64 = 0
    concurrent {
        spawn produce(a 5)
        spawn produce(b 5)
        loop true {
            match select(@a.receive @b.receive) {
                n:int64 => { total += n }
                <Closed> => break
                <Canceled> => break
            }
        }
    }
    printl"{total}"
}
'''

MERGED = PRODUCE + '''main = () => {
    let a = channel<int64>(1)
    let b = channel<int64>(1)
    let total:int64 = 0
    concurrent {
        spawn produce(a 5)
        spawn produce(b 5)
        loop item in merged(@a.receive @b.receive) or_throw { total += item }
    }
    printl"{total}"
}
'''

QUEUE = '''produce = (out:Mpmc<int64> n:int64):>void | Unsent<int64> | Canceled => {
    loop i in [0..n) { out.send(i) or_throw }
    out.close()
}
main = () => {
    let a = mpmc<int64>(1)
    let b = channel<int64>(1)
    let total:int64 = 0
    concurrent {
        spawn produce(a 5)
        spawn { loop i in [0..5) { b.send(i) or_throw }  b.close() }
        loop true {
            match select(@a.receive @b.receive) {
                n:int64 => { total += n }
                <Closed> => break
                <Canceled> => break
            }
        }
    }
    printl"{total}"
}
'''


def test_a_producer_feeding_a_select_loop_is_quiet(compiler, tmp_path):  # noqa: F811
    assert diagnostics(compiler, tmp_path, SELECT) == []


def test_a_producer_feeding_a_merged_loop_is_quiet(compiler, tmp_path):  # noqa: F811
    assert diagnostics(compiler, tmp_path, MERGED) == []


def test_a_queue_and_a_channel_in_one_select_are_quiet(compiler, tmp_path):  # noqa: F811
    assert diagnostics(compiler, tmp_path, QUEUE) == []


def test_a_channel_no_select_lists_still_warns(compiler, tmp_path):  # noqa: F811
    program = SELECT.replace('select(@a.receive @b.receive)', 'select(@a.receive)')
    found = diagnostics(compiler, tmp_path, program)
    assert len(found) == 1 and "may wait to send into 'b'" in found[0], found


def test_a_merged_that_leaves_a_channel_out_still_warns(compiler, tmp_path):  # noqa: F811
    program = MERGED.replace('merged(@a.receive @b.receive)', 'merged(@b.receive)')
    found = diagnostics(compiler, tmp_path, program)
    assert len(found) == 1 and "may wait to send into 'a'" in found[0], found


def test_a_channel_nobody_receives_from_warns_beside_a_select(compiler, tmp_path):  # noqa: F811
    program = SELECT.replace('spawn produce(b 5)', 'spawn produce(c 5)').replace('let b = channel<int64>(1)', 'let b = channel<int64>(1)\n    let c = channel<int64>(1)')
    found = diagnostics(compiler, tmp_path, program)
    assert len(found) == 1 and "may wait to send into 'c'" in found[0], found


def test_a_select_that_runs_once_is_not_a_consumer(compiler, tmp_path):  # noqa: F811
    program = PRODUCE + '''main = () => {
    let a = channel<int64>(1)
    let b = channel<int64>(1)
    concurrent {
        spawn produce(a 5)
        spawn produce(b 5)
        let got = select(@a.receive @b.receive)
        printl"{got is? int64}"
    }
}
'''
    found = diagnostics(compiler, tmp_path, program)
    assert len(found) == 1 and 'may wait to send into' in found[0], found


def test_a_spawned_select_loop_is_quiet(compiler, tmp_path):  # noqa: F811
    program = PRODUCE + '''consume = (a:Channel<int64> b:Channel<int64>):>int64 | Canceled => {
    let total:int64 = 0
    loop true {
        match select(@a.receive @b.receive) {
            n:int64 => { total += n }
            <Closed> => break
            <Canceled> => return Canceled
        }
    }
    total
}
main = () => {
    let a = channel<int64>(1)
    let b = channel<int64>(1)
    concurrent {
        spawn produce(a 5)
        spawn produce(b 5)
        spawn consume(a b)
    }
}
'''
    assert diagnostics(compiler, tmp_path, program) == []
