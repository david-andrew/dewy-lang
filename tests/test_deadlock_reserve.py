"""A reservation holds a slot until its permit is sent or dropped (compiler/deadlock_channel_walk.dewy,
events 9 and 10): a permit dropped unsent gives the slot back to the deadlock analysis, one held
across a send past the capacity is still a deadlock, and a permit it cannot follow keeps the
slot counted."""
import subprocess

from tests.support import compiler  # noqa: F401


def check(compiler, tmp_path, program):  # noqa: F811
    source = tmp_path / 'main.dewy'
    source.write_text(('$runtime_checks\n\n') + (program))
    checked = subprocess.run([compiler, 'check', source], capture_output=True, text=True, timeout=60, check=False)
    return checked.returncode, [line for line in checked.stderr.splitlines() if 'wait' in line or 'holds' in line or 'holds' in line]


def quiet(compiler, tmp_path, program):  # noqa: F811
    status, lines = check(compiler, tmp_path, program)
    assert status == 0 and lines == [], lines


DROPPED_SCOPE = '''main = () => {
    let q = mpmc<int64>(1)
    {let held = q.reserve}
    q.send(1);
    printl"{q.receive or_throw}"
}
'''

DROPPED_ARMS = '''main = () => {
    let c = channel<int64>(1)
    match c.reserve {
        p:Reserved<int64> => {}
        _ => {}
    }
    c.send(1);
    printl"{c.receive or_throw}"
}
'''

DROPPED_LOOP = '''main = () => {
    let q = mpmc<int64>(1)
    loop i in [0..3) {
        {let held = q.reserve}
        q.send(i);
        printl"{q.receive or_throw}"
    }
}
'''

SENT_THEN_RECEIVED = '''main = () => {
    let q = mpmc<int64>(1)
    let p = q.reserve or_throw
    p.send(1)
    printl"{q.receive or_throw}"
    q.send(2);
    printl"{q.receive or_throw}"
}
'''

HELD_PAST_CAPACITY = '''main = () => {
    let q = mpmc<int64>(1)
    let held = q.reserve
    q.send(1);
    printl"{q.receive or_throw}"
}
'''

HELD_OR_THROW = '''main = () => {
    let q = mpmc<int64>(1)
    let p = q.reserve or_throw
    q.send(1);
    p.send(2)
    printl"{q.receive or_throw}"
}
'''

SENT_IN_AN_ARM = '''main = () => {
    let q = mpmc<int64>(1)
    match q.reserve {
        p:Reserved<int64> => p.send(1)
        _ => {}
    }
    q.send(2);
    printl"{q.receive or_throw}"
}
'''

GIVEN_AWAY = '''hand_over = (p:Reserved<int64>):>void => p.send(1)
main = () => {
    let q = mpmc<int64>(1)
    {
        let p = q.reserve or_throw
        hand_over(p)
    }
    q.send(2);
    printl"{q.receive or_throw}"
}
'''


def test_dropped_permits_are_quiet(compiler, tmp_path):  # noqa: F811
    for program in (DROPPED_SCOPE, DROPPED_ARMS, DROPPED_LOOP, SENT_THEN_RECEIVED):
        quiet(compiler, tmp_path, program)


def test_held_permit_past_capacity_is_a_deadlock(compiler, tmp_path):  # noqa: F811
    status, lines = check(compiler, tmp_path, HELD_PAST_CAPACITY)
    assert status != 0
    assert any("sends more values into 'q' than the 1 it holds" in line for line in lines), lines


def test_permits_that_may_hold_a_slot_still_warn(compiler, tmp_path):  # noqa: F811
    for program in (HELD_OR_THROW, SENT_IN_AN_ARM, GIVEN_AWAY):
        status, lines = check(compiler, tmp_path, program)
        assert status == 0
        assert any("may wait to send into 'q'" in line for line in lines), lines
